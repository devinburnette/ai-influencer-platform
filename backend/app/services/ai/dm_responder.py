"""DM Response Generator - AI-powered direct message responses."""

import random
from typing import Optional, List, Dict, Any
from datetime import datetime
import structlog

from app.config import get_settings
from app.models.persona import Persona
from app.models.conversation import Conversation, DirectMessage, MessageDirection
from app.services.ai.base import AIProvider, Message
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.anthropic_provider import AnthropicProvider

logger = structlog.get_logger()
settings = get_settings()


class DMResponder:
    """Generate AI-powered responses to direct messages."""
    
    DEFAULT_DM_PROMPT = """You are {name}, an influencer with the following profile:

Bio: {bio}

Niche/Expertise: {niche}

Voice & Personality:
- Tone: {tone}
- Vocabulary: {vocabulary_level}
- Emoji usage: {emoji_usage}

You're responding to a direct message from {sender_name}. Be authentic, friendly, and engaging.

IMPORTANT GUIDELINES:
1. Keep responses SHORT and natural (1-3 sentences typically)
2. Match the energy of the incoming message
3. Be helpful but don't over-promise
4. If asked for personal details (address, phone, etc.), politely decline
5. If the conversation seems spammy or inappropriate, respond briefly and don't encourage more
6. Reference previous context naturally when relevant
7. RARELY use emojis - most messages should have NO emojis. Only use one occasionally (maybe 1 in 5 messages)
8. Don't be overly formal or robotic
9. If unsure about something, it's okay to say so
10. For business inquiries, express interest but suggest they follow for updates

CONVERSATION STYLE - CRITICAL:
- DO NOT always ask a follow-up question. Most of the time (70%+), just answer or respond without asking anything back
- Only ask a question when it genuinely makes sense and moves the conversation forward
- If they asked you something, just answer it - you don't need to ask something back every time
- NEVER ask the same question twice. Check the conversation history carefully
- Don't repeat topics or questions that were already discussed
- Sometimes a simple "haha nice" or "thats awesome" or "for sure" is the right response
- Vary your response style - not every message needs to be a complete thought

SAFETY:
- Never share personal information
- Don't make commitments you can't keep
- Don't engage with harassment or inappropriate content
- If something feels off, keep the response brief and neutral"""

    def __init__(self):
        """Initialize the DM responder."""
        pass
    
    def _get_provider(self, persona: Persona) -> AIProvider:
        """Get the appropriate AI provider for a persona."""
        if persona.ai_provider == "anthropic":
            return AnthropicProvider()
        return OpenAIProvider()
    
    def _build_system_prompt(self, persona: Persona, sender_name: str) -> str:
        """Build the system prompt for DM response generation."""
        # Use custom template if available
        if persona.dm_prompt_template:
            template = persona.dm_prompt_template
        else:
            template = self.DEFAULT_DM_PROMPT
        
        # Get voice settings
        voice = persona.voice
        niche_str = ", ".join(persona.niche) if persona.niche else "lifestyle"
        
        return template.format(
            name=persona.name,
            bio=persona.bio,
            niche=niche_str,
            tone=voice.tone,
            vocabulary_level=voice.vocabulary_level,
            emoji_usage=voice.emoji_usage,
            sender_name=sender_name or "someone",
        )
    
    def _build_conversation_context(
        self,
        messages: List[DirectMessage],
        max_messages: int = 10,
    ) -> str:
        """Build conversation history context."""
        if not messages:
            return ""
        
        # Take the last N messages
        recent_messages = messages[-max_messages:]
        
        context_parts = ["CONVERSATION HISTORY:"]
        for msg in recent_messages:
            speaker = "Them" if msg.direction == MessageDirection.INBOUND else "You"
            timestamp = msg.sent_at.strftime("%I:%M %p") if msg.sent_at else ""
            context_parts.append(f"[{timestamp}] {speaker}: {msg.content}")
        
        return "\n".join(context_parts)
    
    async def generate_response(
        self,
        persona: Persona,
        conversation: Conversation,
        incoming_message: str,
        message_history: Optional[List[DirectMessage]] = None,
    ) -> Dict[str, Any]:
        """Generate a response to a direct message.
        
        Args:
            persona: The persona responding
            conversation: The conversation context
            incoming_message: The message to respond to
            message_history: Optional list of previous messages for context
            
        Returns:
            Dictionary with response, tokens_used, and any flags
        """
        logger.info(
            "Generating DM response",
            persona=persona.name,
            participant=conversation.participant_username,
            message_preview=incoming_message[:50],
        )
        
        provider = self._get_provider(persona)
        
        # Build the system prompt
        system_prompt = self._build_system_prompt(
            persona,
            conversation.participant_name or conversation.participant_username,
        )
        
        # Build conversation context
        history_context = ""
        if message_history:
            history_context = self._build_conversation_context(message_history)
        
        # Add conversation summary if available
        if conversation.context_summary:
            history_context = f"SUMMARY OF EARLIER CONVERSATION:\n{conversation.context_summary}\n\n{history_context}"
        
        # Determine conversation depth for flirtiness
        message_count = len(message_history) if message_history else 0
        flirty_guidance = ""
        if message_count >= 6:
            flirty_guidance = """
- This conversation has been going well! Feel free to be a little flirty and playful
- Use some teasing, compliments, or playful banter when it fits naturally
- Keep it tasteful and fun - nothing too forward or inappropriate
- Match their energy - if they're flirting back, lean into it a bit more"""
        elif message_count >= 4:
            flirty_guidance = """
- The conversation is warming up - you can start being a bit more playful and charming
- A little light teasing or friendly compliment is fine if it feels natural"""
        
        # Build the user message
        user_content = f"""{history_context}

LATEST MESSAGE FROM {conversation.participant_name or conversation.participant_username}:
"{incoming_message}"

Write ONE natural response as {persona.name}. 
- If they asked something, just answer it - DON'T ask a follow-up question back
- Only ask a question if it's truly necessary and you haven't asked it before
- Check the history - don't repeat any questions you've already asked
- Keep it short (1-3 sentences), friendly, and authentic
- Sometimes a brief "haha" or "nice!" or "totally" is enough
- Don't repeat what you've already said in previous messages
- NO EMOJI in this response (save emojis for rare special moments){flirty_guidance}"""

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content),
        ]
        
        try:
            start_time = datetime.utcnow()
            result = await provider.generate_text(
                messages=messages,
                max_tokens=300,  # Keep responses short
                temperature=0.8,  # Some creativity but not too random
            )
            end_time = datetime.utcnow()
            response_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            response_text = result.text.strip()
            
            # Clean up response (remove quotes if AI wrapped it)
            if response_text.startswith('"') and response_text.endswith('"'):
                response_text = response_text[1:-1]
            
            # Add human-like imperfections to make typing more natural
            response_text = self._humanize_text(response_text)
            
            # Check for potentially problematic content
            requires_review = self._check_requires_review(response_text, incoming_message)
            
            logger.info(
                "DM response generated",
                persona=persona.name,
                response_preview=response_text[:50],
                response_time_ms=response_time_ms,
                requires_review=requires_review,
            )
            
            return {
                "success": True,
                "response": response_text,
                "tokens_used": result.tokens_used,
                "response_time_ms": response_time_ms,
                "requires_review": requires_review,
            }
            
        except Exception as e:
            logger.error("DM response generation failed", error=str(e))
            return {
                "success": False,
                "response": None,
                "error": str(e),
                "requires_review": True,
            }
    
    def _check_requires_review(self, response: str, incoming: str) -> bool:
        """Check if a response requires human review.
        
        Returns True if the conversation should be flagged for review.
        """
        # Keywords that might indicate sensitive topics
        sensitive_keywords = [
            "meet up", "meeting", "address", "phone number", "call me",
            "payment", "money", "bank", "wire", "venmo", "paypal",
            "investment", "crypto", "nft",
            "send me", "share your",
            "hate", "kill", "hurt", "suicide", "self-harm",
        ]
        
        combined = (response + " " + incoming).lower()
        
        for keyword in sensitive_keywords:
            if keyword in combined:
                return True
        
        return False
    
    def _humanize_text(self, text: str) -> str:
        """Add human-like imperfections to text to make it feel more natural.
        
        Randomly applies various transformations to make the response
        feel less robotic and more like casual texting.
        """
        if not text:
            return text
        
        # 40% chance to apply any humanization
        if random.random() > 0.4:
            return text
        
        # Pick one or two random transformations
        transformations = []
        
        # Lowercase the first letter sometimes (30% chance)
        if random.random() < 0.3 and text[0].isupper():
            text = text[0].lower() + text[1:]
            transformations.append("lowercase_start")
        
        # Remove trailing punctuation sometimes (25% chance)
        if random.random() < 0.25 and text and text[-1] in ".!":
            text = text[:-1]
            transformations.append("no_end_punct")
        
        # Replace some words with casual versions (20% chance)
        if random.random() < 0.2:
            casual_replacements = {
                "I am": random.choice(["im", "I'm"]),
                "I'm": random.choice(["im", "I'm"]),
                "you are": random.choice(["youre", "you're", "ur"]),
                "you're": random.choice(["youre", "you're", "ur"]),
                "going to": random.choice(["gonna", "going to"]),
                "want to": random.choice(["wanna", "want to"]),
                "have to": random.choice(["gotta", "have to"]),
                "kind of": random.choice(["kinda", "kind of"]),
                "sort of": random.choice(["sorta", "sort of"]),
                "because": random.choice(["bc", "cuz", "because"]),
                "probably": random.choice(["prob", "prolly", "probably"]),
                "definitely": random.choice(["def", "definitely"]),
                "really": random.choice(["rly", "rlly", "really"]),
                "about": random.choice(["abt", "about"]),
                "though": random.choice(["tho", "though"]),
                "right now": random.choice(["rn", "right now"]),
                "to be honest": random.choice(["tbh", "to be honest"]),
                "in my opinion": random.choice(["imo", "in my opinion"]),
                "laughing": random.choice(["lol", "haha", "laughing"]),
            }
            for formal, casual in casual_replacements.items():
                if formal.lower() in text.lower():
                    # Case-insensitive replacement
                    import re
                    text = re.sub(re.escape(formal), casual, text, flags=re.IGNORECASE, count=1)
                    transformations.append(f"casual_{formal}")
                    break
        
        # Sometimes add a casual filler at the start (15% chance)
        if random.random() < 0.15:
            fillers = ["oh", "haha", "lol", "omg", "aw", "ahh", "ooh", "hmm"]
            filler = random.choice(fillers)
            text = filler + " " + text
            transformations.append("add_filler")
        
        # Double a letter in an expressive word (10% chance)
        if random.random() < 0.1:
            expressive_patterns = [
                ("so ", "soo "),
                ("no ", "noo "),
                ("yes", "yess"),
                ("nice", "nicee"),
                ("cool", "coool"),
                ("same", "samee"),
                ("love", "lovee"),
                ("wow", "woww"),
            ]
            for pattern, replacement in expressive_patterns:
                if pattern in text.lower():
                    text = text.replace(pattern, replacement, 1)
                    transformations.append("double_letter")
                    break
        
        # Sometimes split into fragments with ellipsis or line break (10% chance)
        if random.random() < 0.1 and len(text) > 30 and ". " in text:
            # Replace first period-space with something more casual
            replacements = [".. ", "... ", " - "]
            text = text.replace(". ", random.choice(replacements), 1)
            transformations.append("fragment")
        
        if transformations:
            logger.debug("Humanized DM response", transformations=transformations)
        
        return text
    
    async def generate_conversation_summary(
        self,
        persona: Persona,
        messages: List[DirectMessage],
    ) -> str:
        """Generate a summary of a conversation for context.
        
        This is useful for long conversations to maintain context
        without sending the entire history.
        """
        if len(messages) < 5:
            return ""
        
        provider = self._get_provider(persona)
        
        # Build message history text
        history_parts = []
        for msg in messages:
            speaker = "User" if msg.direction == MessageDirection.INBOUND else persona.name
            history_parts.append(f"{speaker}: {msg.content}")
        
        history_text = "\n".join(history_parts)
        
        messages_for_summary = [
            Message(
                role="system",
                content="You are a helpful assistant that summarizes conversations concisely."
            ),
            Message(
                role="user",
                content=f"""Summarize this conversation in 2-3 sentences, capturing:
1. What the user wanted/asked about
2. Key information exchanged
3. The overall tone of the conversation

CONVERSATION:
{history_text}

SUMMARY:"""
            ),
        ]
        
        try:
            result = await provider.generate_text(
                messages=messages_for_summary,
                max_tokens=150,
                temperature=0.3,
            )
            return result.text.strip()
        except Exception as e:
            logger.error("Failed to generate conversation summary", error=str(e))
            return ""
    
    async def should_respond(
        self,
        incoming_message: str,
        conversation: Conversation,
    ) -> Dict[str, Any]:
        """Determine if the persona should respond to a message.
        
        Returns a dict with:
        - should_respond: bool
        - reason: str (why or why not)
        - urgency: str (low, medium, high)
        """
        message_lower = incoming_message.lower()
        
        # Always ignore obvious spam patterns
        spam_patterns = [
            "click here", "free money", "limited time offer",
            "act now", "congratulations you won", "verify your account",
            "send me crypto", "investment opportunity",
        ]
        
        for pattern in spam_patterns:
            if pattern in message_lower:
                return {
                    "should_respond": False,
                    "reason": "Appears to be spam",
                    "urgency": "low",
                }
        
        # Check for empty or very short messages
        if len(incoming_message.strip()) < 2:
            return {
                "should_respond": False,
                "reason": "Message too short",
                "urgency": "low",
            }
        
        # Check for simple greetings (respond but low urgency)
        greetings = ["hi", "hey", "hello", "sup", "yo", "hii", "heyy"]
        if incoming_message.strip().lower() in greetings:
            return {
                "should_respond": True,
                "reason": "Greeting",
                "urgency": "low",
            }
        
        # Questions get higher urgency
        if "?" in incoming_message:
            return {
                "should_respond": True,
                "reason": "Question asked",
                "urgency": "high",
            }
        
        # Business/collaboration mentions get higher urgency
        business_keywords = ["collab", "partnership", "sponsor", "brand", "business", "work together"]
        for keyword in business_keywords:
            if keyword in message_lower:
                return {
                    "should_respond": True,
                    "reason": "Potential business inquiry",
                    "urgency": "high",
                }
        
        # Default: respond with medium urgency
        return {
            "should_respond": True,
            "reason": "Normal message",
            "urgency": "medium",
        }

