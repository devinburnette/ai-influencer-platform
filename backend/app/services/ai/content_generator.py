"""Content generation service using AI providers."""

from typing import Optional, List, Dict, Any
import structlog
import random

from app.config import get_settings
from app.models.persona import Persona
from app.services.ai.base import AIProvider, Message
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.anthropic_provider import AnthropicProvider

logger = structlog.get_logger()
settings = get_settings()


class ContentGenerator:
    """Generate content for AI personas using configured AI provider."""
    
    # Content format types for variety
    CONTENT_FORMATS = [
        {"type": "hot_take", "instruction": "Share a bold, slightly controversial opinion that sparks discussion"},
        {"type": "personal_story", "instruction": "Share a brief personal anecdote or experience that's relatable"},
        {"type": "tip", "instruction": "Share a practical tip or piece of advice your audience can use today"},
        {"type": "question", "instruction": "Ask an engaging question to spark conversation with your audience"},
        {"type": "observation", "instruction": "Share an interesting observation or insight you've noticed lately"},
        {"type": "motivation", "instruction": "Share something motivational or encouraging"},
        {"type": "behind_scenes", "instruction": "Share a behind-the-scenes moment or honest reality of your day"},
        {"type": "myth_bust", "instruction": "Bust a common myth or misconception in your field"},
        {"type": "quick_win", "instruction": "Share a quick win or small success your audience can celebrate"},
        {"type": "unpopular_opinion", "instruction": "Share an unpopular opinion you genuinely hold"},
        {"type": "lesson_learned", "instruction": "Share a lesson you learned (possibly the hard way)"},
        {"type": "recommendation", "instruction": "Recommend something you genuinely love (tool, habit, practice)"},
        {"type": "challenge", "instruction": "Challenge your audience to try something new"},
        {"type": "celebration", "instruction": "Celebrate a small win or milestone"},
        {"type": "vulnerability", "instruction": "Share something real and vulnerable that humanizes you"},
    ]
    
    # Opening hooks for variety
    OPENING_HOOKS = [
        "Start with a surprising statistic or fact",
        "Start with a relatable frustration",
        "Start with 'Nobody talks about...'",
        "Start with a bold statement",
        "Start with a question",
        "Start mid-story to create intrigue",
        "Start with 'Unpopular opinion:'",
        "Start with 'Hot take:'",
        "Start with 'The truth is...'",
        "Start with 'Stop doing this...'",
        "Start with 'Here's what I've learned...'",
        "Start conversationally like you're talking to a friend",
        "Start with 'Real talk:'",
        "Start with a confession",
        "Start with 'I used to think... but now...'",
    ]
    
    # Tone variations
    TONE_VARIATIONS = [
        "Be playfully sarcastic",
        "Be warm and encouraging",
        "Be direct and no-nonsense",
        "Be thoughtful and reflective",
        "Be energetic and enthusiastic",
        "Be casual and conversational",
        "Be witty and clever",
        "Be vulnerable and authentic",
    ]

    def __init__(self, provider: Optional[AIProvider] = None):
        """Initialize content generator.
        
        Args:
            provider: AI provider to use (auto-detected from settings if None)
        """
        self.provider = provider

    def _get_provider(self, persona: Optional[Persona] = None) -> AIProvider:
        """Get the AI provider for a persona or use default."""
        if self.provider:
            return self.provider
        
        # Determine provider from persona or settings
        provider_name = (
            persona.ai_provider if persona else settings.default_ai_provider
        )
        
        if provider_name == "anthropic":
            return AnthropicProvider()
        return OpenAIProvider()

    def _get_template_vars(self, persona: Persona) -> dict:
        """Get template variables for prompt substitution."""
        voice = persona.voice
        
        emoji_guidance = {
            "none": "Do not use any emojis.",
            "minimal": "Use emojis sparingly, only 1-2 per post if appropriate.",
            "moderate": "Use emojis naturally throughout the post, about 3-5 per post.",
            "heavy": "Use emojis frequently to add energy and personality, 6+ per post.",
        }
        
        hashtag_guidance = {
            "minimal": "Use only 1-3 highly relevant hashtags.",
            "relevant": "Use 4-8 relevant hashtags that fit the content.",
            "comprehensive": "Use 8-15 hashtags including niche and popular ones.",
            "viral": "Use 15+ hashtags optimized for maximum reach.",
        }
        
        return {
            "name": persona.name,
            "bio": persona.bio,
            "niche": ", ".join(persona.niche),
            "tone": voice.tone,
            "vocabulary_level": voice.vocabulary_level,
            "emoji_usage": voice.emoji_usage,
            "emoji_guidance": emoji_guidance.get(voice.emoji_usage, emoji_guidance['moderate']),
            "hashtag_style": voice.hashtag_style,
            "hashtag_guidance": hashtag_guidance.get(voice.hashtag_style, hashtag_guidance['relevant']),
            "signature_phrases": ", ".join(voice.signature_phrases) if voice.signature_phrases else "",
        }
    
    def _build_default_prompt(self, persona: Persona) -> str:
        """Build the default system prompt for a persona."""
        vars = self._get_template_vars(persona)
        
        return f"""You are {vars['name']}, an AI social media influencer.

Bio: {vars['bio']}

Your content focuses on: {vars['niche']}

Voice and Personality:
- Tone: {vars['tone']}
- Vocabulary: {vars['vocabulary_level']}
- {vars['emoji_guidance']}
- {vars['hashtag_guidance']}

{"Signature phrases you sometimes use: " + vars['signature_phrases'] if vars['signature_phrases'] else ""}

Write content that feels authentic to this persona. Stay in character and maintain a consistent voice."""

    def _build_persona_prompt(self, persona: Persona, prompt_type: str = "content") -> str:
        """Build system prompt for persona voice.
        
        Args:
            persona: The persona to build the prompt for
            prompt_type: Either "content" or "comment" to select the template
        
        Returns:
            The system prompt string
        """
        # Check for custom template
        custom_template = None
        if prompt_type == "content" and hasattr(persona, 'content_prompt_template'):
            custom_template = persona.content_prompt_template
        elif prompt_type == "comment" and hasattr(persona, 'comment_prompt_template'):
            custom_template = persona.comment_prompt_template
        
        # Use custom template if provided
        if custom_template:
            try:
                vars = self._get_template_vars(persona)
                return custom_template.format(**vars)
            except KeyError as e:
                logger.warning(f"Invalid placeholder in custom template: {e}, falling back to default")
            except Exception as e:
                logger.warning(f"Error applying custom template: {e}, falling back to default")
        
        # Fall back to default
        return self._build_default_prompt(persona)

    def _calculate_total_length(self, caption: str, hashtags: List[str]) -> int:
        """Calculate total character count including caption and hashtags.
        
        Args:
            caption: The post caption
            hashtags: List of hashtags (without # symbol)
            
        Returns:
            Total character count
        """
        hashtag_text = " ".join(f"#{tag}" for tag in hashtags)
        separator = "\n\n" if hashtags else ""
        total = len(caption) + len(separator) + len(hashtag_text)
        return total

    async def generate_post(
        self,
        persona: Persona,
        topic: Optional[str] = None,
        content_type: str = "post",
        context: Optional[str] = None,
        platform: str = "twitter",
    ) -> Dict[str, Any]:
        """Generate a social media post for the persona.
        
        Args:
            persona: The persona to generate content for
            topic: Optional specific topic to write about
            content_type: Type of content (post, story, reel)
            context: Optional additional context
            platform: Target platform (twitter, instagram)
            
        Returns:
            Dictionary with caption and hashtags
        """
        provider = self._get_provider(persona)
        
        # Select random variations for this generation
        content_format = random.choice(self.CONTENT_FORMATS)
        opening_hook = random.choice(self.OPENING_HOOKS)
        tone_variation = random.choice(self.TONE_VARIATIONS)
        selected_niche = random.choice(persona.niche)
        
        logger.info(
            "Generating post",
            persona=persona.name,
            topic=topic,
            platform=platform,
            provider=provider.name,
            content_format=content_format["type"],
            opening_hook=opening_hook[:30],
        )

        # Build topic instruction with more variety
        if topic:
            topic_instruction = f"Write about: {topic}"
        else:
            topic_instruction = f"Write about something related to: {selected_niche}"
        
        context_note = f"\nContext: {context}" if context else ""
        
        # Platform-specific character limits and guidance
        platform_limits = {
            "twitter": {
                "max_chars": 280,
                "caption_guidance": "Keep the caption SHORT - maximum 200 characters to leave room for hashtags",
                "hashtag_guidance": "Use only 2-4 hashtags (each hashtag adds to character count)",
                "total_guidance": "CRITICAL: Caption + hashtags + spaces must total UNDER 280 characters",
            },
            "instagram": {
                "max_chars": 500,
                "caption_guidance": "Keep the caption SHORT and punchy - maximum 2-3 sentences (under 300 characters)",
                "hashtag_guidance": "Use only 3-5 relevant hashtags",
                "total_guidance": "Keep it concise! Caption + hashtags should be under 500 characters total",
            },
        }
        
        limits = platform_limits.get(platform, platform_limits["twitter"])

        messages = [
            Message(role="system", content=self._build_persona_prompt(persona)),
            Message(
                role="user",
                content=f"""{topic_instruction}{context_note}

CONTENT FORMAT: {content_format['type'].upper().replace('_', ' ')}
{content_format['instruction']}

STYLE DIRECTION:
- {opening_hook}
- {tone_variation}
- Make it feel like something you'd actually say, not a corporate post
- Don't be generic - be specific and add personality
- Avoid clichés like "game-changer", "unlock your potential", "level up"

Create an engaging {content_type} for {platform.upper()} that will resonate with your audience.
Be ORIGINAL - don't repeat common phrases or structures.

Respond in JSON format:
{{
    "caption": "your caption here (without hashtags)",
    "hashtags": ["hashtag1", "hashtag2", ...]
}}

PLATFORM REQUIREMENTS ({platform.upper()} - {limits['max_chars']} character limit):
- {limits['caption_guidance']}
- {limits['hashtag_guidance']}
- {limits['total_guidance']}
- Hashtags should NOT include the # symbol in your response
- The TOTAL of: caption + space + hashtags (with # and spaces) must be under {limits['max_chars']} characters

Example for Twitter: If caption is 180 chars and you have 3 hashtags averaging 10 chars each, that's 180 + 2 (newlines) + 33 (3 hashtags with # and spaces) = 215 chars ✓"""
            ),
        ]

        # Increase temperature for more variety
        result = await provider.generate_json(messages, max_tokens=500, temperature=0.95)
        
        # Validate and enforce character limits
        caption = result.get("caption", "")
        hashtags = result.get("hashtags", [])
        
        total_length = self._calculate_total_length(caption, hashtags)
        max_chars = limits["max_chars"]
        
        # If over limit, try to trim hashtags first, then caption
        if total_length > max_chars:
            logger.warning(
                "Generated content exceeds limit, trimming",
                total_length=total_length,
                max_chars=max_chars,
            )
            
            # Remove hashtags one by one until under limit
            while hashtags and self._calculate_total_length(caption, hashtags) > max_chars:
                hashtags.pop()
            
            # If still over, truncate caption
            if self._calculate_total_length(caption, hashtags) > max_chars:
                # Calculate how much space we have for caption
                hashtag_text = " ".join(f"#{tag}" for tag in hashtags)
                separator_len = 2 if hashtags else 0
                available_for_caption = max_chars - len(hashtag_text) - separator_len - 3  # -3 for "..."
                
                if available_for_caption > 20:
                    caption = caption[:available_for_caption] + "..."
                else:
                    # Last resort: no hashtags, truncate caption
                    hashtags = []
                    caption = caption[:max_chars - 3] + "..."
            
            result["caption"] = caption
            result["hashtags"] = hashtags
        
        final_length = self._calculate_total_length(caption, hashtags)
        
        logger.info(
            "Generated post content",
            persona=persona.name,
            platform=platform,
            caption_length=len(caption),
            hashtag_count=len(hashtags),
            total_length=final_length,
            max_chars=max_chars,
        )

        return result

    async def generate_comment(
        self,
        persona: Persona,
        post_content: str,
        post_author: str,
        context: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> str:
        """Generate a contextual comment for a post.
        
        Args:
            persona: The persona making the comment
            post_content: Content of the post to comment on
            post_author: Username of the post author
            context: Optional additional context
            image_url: Optional URL of the post's image for vision analysis
            
        Returns:
            Comment text
        """
        provider = self._get_provider(persona)
        
        logger.info(
            "Generating comment",
            persona=persona.name,
            post_author=post_author,
            provider=provider.name,
            has_image=bool(image_url),
        )

        # If an image URL is provided, analyze it first to add context
        image_context = ""
        if image_url:
            try:
                image_description = await provider.analyze_image(
                    image_url,
                    "Briefly describe this social media post image in 1-2 sentences. Focus on the main subject, setting, and mood."
                )
                if image_description:
                    image_context = f"\nImage shows: {image_description}"
                    logger.info("Image analyzed for comment", description=image_description[:100])
            except Exception as e:
                logger.warning("Image analysis failed, proceeding without image context", error=str(e))

        context_note = f"\nContext: {context}" if context else ""

        messages = [
            Message(role="system", content=self._build_persona_prompt(persona, prompt_type="comment")),
            Message(
                role="user",
                content=f"""You're commenting on a post by @{post_author}.

Post content: "{post_content}"{image_context}{context_note}

Write a genuine, engaging comment that:
- Feels authentic and not generic
- Adds value to the conversation
- Matches your personality and voice
- Is concise (1-3 sentences max)
- Might naturally lead to engagement
- References specific details from the image if relevant

Return only the comment text, nothing else."""
            ),
        ]

        result = await provider.generate_text(messages, max_tokens=100, temperature=0.8)
        
        return result.text.strip().strip('"')

    async def generate_story_ideas(
        self,
        persona: Persona,
        count: int = 5,
    ) -> List[Dict[str, str]]:
        """Generate story content ideas for the persona.
        
        Args:
            persona: The persona to generate ideas for
            count: Number of ideas to generate
            
        Returns:
            List of story ideas with type and description
        """
        provider = self._get_provider(persona)

        messages = [
            Message(role="system", content=self._build_persona_prompt(persona)),
            Message(
                role="user",
                content=f"""Generate {count} engaging story ideas that would resonate with your audience.

Mix different types:
- Behind-the-scenes moments
- Quick tips or advice
- Polls or questions
- Day-in-the-life snippets
- Promotional but natural content

Respond in JSON format:
{{
    "ideas": [
        {{"type": "type_of_story", "description": "brief description", "hook": "opening text"}}
    ]
}}"""
            ),
        ]

        result = await provider.generate_json(messages, max_tokens=800, temperature=0.9)
        
        return result.get("ideas", [])

    async def generate_content_calendar(
        self,
        persona: Persona,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Generate a content calendar for the persona.
        
        Args:
            persona: The persona to plan for
            days: Number of days to plan
            
        Returns:
            List of content plan items
        """
        provider = self._get_provider(persona)

        messages = [
            Message(role="system", content=self._build_persona_prompt(persona)),
            Message(
                role="user",
                content=f"""Plan a {days}-day content calendar for your social media.

Consider:
- Variety in content types and topics
- Optimal posting times for engagement
- Trending topics in your niche
- A good mix of value, entertainment, and personal content

Respond in JSON format:
{{
    "calendar": [
        {{
            "day": 1,
            "posts": [
                {{
                    "time": "9:00 AM",
                    "type": "post",
                    "topic": "topic summary",
                    "caption_hook": "opening line of the caption"
                }}
            ]
        }}
    ]
}}"""
            ),
        ]

        result = await provider.generate_json(messages, max_tokens=1500, temperature=0.7)
        
        return result.get("calendar", [])

    async def improve_caption(
        self,
        persona: Persona,
        original_caption: str,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Improve an existing caption.
        
        Args:
            persona: The persona whose voice to use
            original_caption: The original caption text
            feedback: Optional feedback for improvement
            
        Returns:
            Dictionary with improved caption and hashtags
        """
        provider = self._get_provider(persona)

        feedback_note = f"\nFeedback to address: {feedback}" if feedback else ""

        messages = [
            Message(role="system", content=self._build_persona_prompt(persona)),
            Message(
                role="user",
                content=f"""Improve this caption while maintaining my voice:

Original: "{original_caption}"{feedback_note}

Make it more engaging, authentic, and optimized for social media.

Respond in JSON format:
{{
    "caption": "improved caption here",
    "hashtags": ["hashtag1", "hashtag2", ...],
    "improvements": ["what you changed and why"]
}}"""
            ),
        ]

        return await provider.generate_json(messages, max_tokens=600, temperature=0.7)


