"""Direct Message handling tasks."""

import asyncio
import random
import re
import unicodedata
from datetime import datetime
from uuid import UUID

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_maker
from app.models.persona import Persona
from app.models.platform_account import PlatformAccount, Platform
from app.models.conversation import (
    Conversation, DirectMessage, ConversationStatus, 
    MessageDirection, MessageStatus
)
from app.services.ai.dm_responder import DMResponder
from app.services.platforms.instagram.browser import InstagramBrowser

logger = structlog.get_logger()
settings = get_settings()


def normalize_message_content(content: str) -> str:
    """Normalize message content for duplicate detection.
    
    Removes emojis, extra whitespace, and normalizes unicode to handle
    slight variations in how Instagram displays messages.
    """
    if not content:
        return ""
    
    # Remove emojis (unicode emoji ranges)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols extended
        "\U00002600-\U000026FF"  # misc symbols
        "]+",
        flags=re.UNICODE
    )
    content = emoji_pattern.sub('', content)
    
    # Normalize unicode
    content = unicodedata.normalize('NFKC', content)
    
    # Remove extra whitespace
    content = ' '.join(content.split())
    
    # Strip leading/trailing whitespace
    content = content.strip()
    
    return content


def run_async(coro):
    """Run async code in sync context."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@shared_task(name="app.workers.tasks.dm_tasks.check_and_respond_dms")
def check_and_respond_dms() -> dict:
    """Check for new DMs and respond automatically.
    
    This is the main scheduled task that runs periodically.
    """
    return run_async(_check_and_respond_dms())


async def _check_and_respond_dms() -> dict:
    """Async implementation of DM checking and responding."""
    results = {
        "personas_checked": 0,
        "new_messages": 0,
        "responses_sent": 0,
        "errors": 0,
    }
    
    async with async_session_maker() as db:
        # Get personas with DM auto-respond enabled
        result = await db.execute(
            select(Persona).where(
                Persona.is_active == True,
                Persona.dm_auto_respond == True,
            )
        )
        personas = result.scalars().all()
        
        for persona in personas:
            try:
                # Check if within daily limit
                if persona.dm_responses_today >= persona.dm_max_responses_per_day:
                    logger.info(
                        "DM response limit reached",
                        persona=persona.name,
                        responses_today=persona.dm_responses_today,
                    )
                    continue
                
                persona_results = await _check_persona_dms(db, persona)
                results["personas_checked"] += 1
                results["new_messages"] += persona_results.get("new_messages", 0)
                results["responses_sent"] += persona_results.get("responses_sent", 0)
                
            except Exception as e:
                logger.error("DM check failed for persona", persona=persona.name, error=str(e))
                results["errors"] += 1
    
    logger.info("DM check cycle complete", results=results)
    return results


async def _check_persona_dms(db: AsyncSession, persona: Persona) -> dict:
    """Check DMs for a single persona."""
    results = {"new_messages": 0, "responses_sent": 0}
    
    # Get connected Instagram account
    account_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona.id,
            PlatformAccount.platform == Platform.INSTAGRAM,
            PlatformAccount.is_connected == True,
        )
    )
    account = account_result.scalar_one_or_none()
    
    if not account or not account.session_cookies:
        logger.info("No Instagram account or session for DMs", persona=persona.name)
        return results
    
    # Initialize browser
    browser = InstagramBrowser()
    
    try:
        # Load session cookies
        await browser.load_cookies(account.session_cookies)
        
        # Verify session is valid
        if not await browser.verify_session():
            logger.warning("Instagram session invalid for DMs", persona=persona.name)
            return results
        
        # First, check message requests (DMs from people we don't follow)
        # These need to be processed first while still on the requests page
        request_conversations = await browser._get_message_requests(limit=5)
        await _process_conversations(
            db, browser, persona, request_conversations, results
        )
        
        # Then check main inbox - check more conversations to catch missed messages
        conversations = await browser.get_dm_inbox(limit=15, include_requests=False)
        await _process_conversations(
            db, browser, persona, conversations[:10], results
        )
        
    finally:
        await browser.close()
    
    return results


async def _process_conversations(
    db: AsyncSession,
    browser,
    persona: Persona,
    conversations: list,
    results: dict,
):
    """Process a list of conversations, responding to messages."""
    # Skip certain entries that are UI elements, not real conversations
    skip_usernames = [
        "Your note", "Back", "Hidden Requests", 
        "Delete all 1", "Delete all 0", "Delete all", "Notes",
        "Primary", "General", "Requests", "Message", "Add a note",
        "Reply to note", "Leave a note", "Their note"
    ]
    
    # Pattern for time indicators (e.g., "5h", "7m", "1d", "2w", "Active now")
    time_indicator_pattern = re.compile(r'^(\d+[smhdwMy]|Active\s*(now)?|Just\s*now|Now|Yesterday)$', re.IGNORECASE)
    
    # Patterns that indicate a Note rather than a real message
    note_patterns = [
        'replied to your note',
        'replied to their note',
        'reply to note',
        'leave a note',
        'add a note',
    ]
    
    for conv_data in conversations:
        # Skip the persona's own note or non-person entries (UI elements)
        username = conv_data.get("participant_username", "")
        if not username:
            continue
            
        # Skip known UI elements
        if username in skip_usernames or username.startswith("Delete all"):
            continue
        
        # Skip time indicators (5h, 7m, etc.) which are incorrectly parsed as usernames
        if time_indicator_pattern.match(username):
            logger.debug("Skipping time indicator parsed as username", username=username)
            continue
        
        # NOTE: We now accept display names with spaces/emojis as valid conversation identifiers
        # Instagram shows display names in the conversation list, and we use them as identifiers
        # The important thing is we can click into the conversation and respond
        
        # Check if this is a message request (always process) or unread
        is_request = conv_data.get("is_request", False)
        is_unread = conv_data.get("unread", False)
        
        # Track position in the conversation list
        conv_position = conversations.index(conv_data) if conv_data in conversations else 999
        
        # Look up this conversation in our database using username (stable key)
        existing_conv = await db.execute(
            select(Conversation).where(
                Conversation.persona_id == persona.id,
                Conversation.platform == "instagram",
                Conversation.participant_username == username,
            )
        )
        existing_conv = existing_conv.scalar_one_or_none()
        
        # For conversations we have in the database, check if we need to respond
        # Note: Instagram's unread detection is unreliable, so we use multiple signals
        should_skip = False
        skip_reason = ""
        should_force_check = False
        
        if existing_conv:
            # Check if we responded recently (within last 10 minutes) - prevents duplicate responses
            if existing_conv.last_response_at:
                time_since_response = datetime.utcnow() - existing_conv.last_response_at
                if time_since_response.total_seconds() < 600:  # 10 minutes
                    should_skip = True
                    skip_reason = f"responded {int(time_since_response.total_seconds())}s ago"
                    logger.info("Skipping - %s", skip_reason, username=username)
                    continue
                # If it's been a while since we responded, force a check to see if there are new messages
                elif time_since_response.total_seconds() > 1800:  # 30 minutes
                    should_force_check = True
                    logger.info("Force checking - been %d minutes since last response", int(time_since_response.total_seconds() / 60), username=username)
            
            # Check if the last message in DB is outbound (we already responded)
            # or if it's inbound and already marked as RESPONDED
            last_db_msg = await db.execute(
                select(DirectMessage)
                .where(DirectMessage.conversation_id == existing_conv.id)
                .order_by(DirectMessage.sent_at.desc())
                .limit(1)
            )
            last_db_msg = last_db_msg.scalar_one_or_none()
            
            if last_db_msg:
                if last_db_msg.direction == MessageDirection.OUTBOUND:
                    # Last message was ours - but check if it's been a while (new messages may have arrived)
                    msg_age = (datetime.utcnow() - last_db_msg.sent_at).total_seconds() if last_db_msg.sent_at else 0
                    if msg_age > 1800:  # 30 minutes since our last message
                        should_force_check = True
                        logger.info("Force checking - our last message was %d min ago", int(msg_age / 60), username=username)
                    else:
                        should_skip = True
                        skip_reason = "last message was our response"
                elif last_db_msg.status == MessageStatus.RESPONDED:
                    should_skip = True
                    skip_reason = "already responded to last message"
        
        # Override skip decision carefully:
        # 1. Always process message requests (they're new)
        # 2. Process unread conversations
        # 3. Force check conversations we haven't checked in a while
        # 4. For top 3 conversations (most recent), always check them
        if is_request:
            should_skip = False
            logger.info("Processing message request", username=username)
        elif is_unread:
            should_skip = False
            logger.info("Processing unread conversation", username=username)
        elif should_force_check:
            should_skip = False
            logger.info("Force checking conversation", username=username)
        elif conv_position < 3:
            # Always check the top 3 conversations (most likely to have new messages)
            should_skip = False
            logger.info("Checking top conversation", username=username, position=conv_position)
        elif should_skip:
            # If we already determined we should skip (last msg was outbound or responded),
            # respect that decision for lower conversations
            logger.info("Skipping - %s", skip_reason, username=username)
            continue
        else:
            # New conversation we haven't seen before - always process
            logger.info("New conversation detected, will process", username=username)
        
        logger.info("Processing conversation", username=username, unread=is_unread, is_request=is_request, position=conv_position)
        
        # Get or create conversation record
        conversation = await _get_or_create_conversation(
            db, persona, conv_data, "instagram"
        )
        
        if conversation.status != ConversationStatus.ACTIVE:
            logger.info("Conversation not active", status=conversation.status)
            continue  # Skip paused/closed conversations
        
        # Click into the conversation to get messages
        # The _element is the clickable conversation button
        element = conv_data.get("_element")
        if element:
            try:
                await element.click()
                await asyncio.sleep(2)  # Wait for messages to load
                
                # If this is a message request, we need to accept it first
                if conv_data.get("is_request"):
                    logger.info("This is a message request, attempting to accept", username=username)
                    accepted = await browser.accept_message_request()
                    if not accepted:
                        logger.warning("Could not accept message request", username=username)
                        continue
                    await asyncio.sleep(1)
                
                # Now get messages from the open conversation
                messages = await browser.get_messages_from_current_thread()
            except Exception as e:
                logger.warning("Failed to open conversation", error=str(e), username=username)
                continue
        else:
            logger.warning("No element to click for conversation", username=username)
            continue
        
        # Save all messages to database and identify if there are new inbound messages
        # that haven't been responded to yet
        logger.info("Processing messages", count=len(messages))
        
        new_inbound_messages = []
        last_outgoing_idx = -1
        
        # Find the last outgoing message index to determine which inbound messages are new
        for idx, msg_data in enumerate(messages):
            if msg_data.get("is_outgoing"):
                last_outgoing_idx = idx
        
        # Fetch all existing messages for this conversation to check for duplicates
        # We need to normalize content for comparison since Instagram may modify text
        existing_msgs_result = await db.execute(
            select(DirectMessage).where(
                DirectMessage.conversation_id == conversation.id
            )
        )
        existing_msgs = existing_msgs_result.scalars().all()
        
        # Build a set of normalized existing message signatures (direction + normalized content)
        existing_signatures = set()
        for msg in existing_msgs:
            normalized = normalize_message_content(msg.content)
            sig = f"{msg.direction.value}:{normalized}"
            existing_signatures.add(sig)
        
        # Process each message
        for idx, msg_data in enumerate(messages):
            content = msg_data.get("content", "").strip()
            if not content:
                continue
            
            content_lower = content.lower()
            
            is_outgoing = msg_data.get("is_outgoing", False)
            
            # Skip Note-related content (Instagram status notes shouldn't be treated as messages)
            is_note_content = False
            for note_pattern in note_patterns:
                if note_pattern in content_lower:
                    is_note_content = True
                    logger.debug("Skipping note content", content_preview=content[:50])
                    break
            if is_note_content:
                continue
            
            # Also skip if the message looks like a note (very short, appears early, etc.)
            # Notes are typically short status updates at the top of the thread
            if idx == 0 and len(content) < 50 and not any(c in content for c in '.?!') and not is_outgoing:
                # First message, short, no punctuation, inbound - likely a note
                logger.debug("Skipping potential note (short first message)", content_preview=content[:50])
                continue
            direction = MessageDirection.OUTBOUND if is_outgoing else MessageDirection.INBOUND
            
            # Check if this message already exists using normalized comparison
            normalized_content = normalize_message_content(content)
            message_sig = f"{direction.value}:{normalized_content}"
            
            if message_sig in existing_signatures:
                # Already exists, skip
                continue
            
            # Add to signatures to prevent duplicates within this batch
            existing_signatures.add(message_sig)
            
            # Extract image URL if present
            image_url = msg_data.get("image_url")
            media_urls_json = None
            if image_url:
                import json
                media_urls_json = json.dumps([image_url])
            
            # Save new message to database
            # Outgoing = already responded, Inbound = pending response
            new_msg = DirectMessage(
                conversation_id=conversation.id,
                direction=direction,
                content=content,
                media_urls=media_urls_json,
                status=MessageStatus.RESPONDED if is_outgoing else MessageStatus.PENDING_RESPONSE,
            )
            db.add(new_msg)
            
            # Track new inbound messages that came AFTER our last response
            if not is_outgoing and idx > last_outgoing_idx:
                new_inbound_messages.append(content)
                results["new_messages"] += 1
        
        await db.commit()
        
        # Get full conversation history from database for context
        history_result = await db.execute(
            select(DirectMessage)
            .where(DirectMessage.conversation_id == conversation.id)
            .order_by(DirectMessage.sent_at.asc())
            .limit(20)  # Last 20 messages for context
        )
        full_history = list(history_result.scalars().all())
        
        # Check if we need to respond:
        # 1. There are new inbound messages detected this cycle, OR
        # 2. There are pending messages in the database that need response
        pending_result = await db.execute(
            select(DirectMessage)
            .where(
                DirectMessage.conversation_id == conversation.id,
                DirectMessage.direction == MessageDirection.INBOUND,
                DirectMessage.status == MessageStatus.PENDING_RESPONSE,
            )
            .order_by(DirectMessage.sent_at.desc())
        )
        pending_messages = list(pending_result.scalars().all())
        
        # Also check: is the last message in the conversation inbound AND not yet responded?
        # If so, we should respond even if messages aren't marked as pending
        last_message = full_history[-1] if full_history else None
        last_msg_needs_response = (
            last_message and 
            last_message.direction == MessageDirection.INBOUND and
            last_message.status != MessageStatus.RESPONDED  # Must not already be responded to!
        )
        needs_response = (
            len(new_inbound_messages) > 0 or  # New messages detected
            len(pending_messages) > 0 or  # Pending messages in DB
            last_msg_needs_response  # Last msg is inbound and not yet responded
        )
        
        if not needs_response:
            logger.info("No new messages to respond to", username=username)
            continue
        
        # Get the latest inbound message to respond to
        latest_msg = pending_messages[0] if pending_messages else (
            last_message if last_message and last_message.direction == MessageDirection.INBOUND else None
        )
        
        if not latest_msg:
            logger.info("No pending messages to respond to", username=username)
            continue
        
        # Extract image URLs from recent inbound messages for vision analysis
        import json
        image_urls = []
        for msg in pending_messages[:3]:  # Check last 3 pending messages for images
            if msg.media_urls:
                try:
                    urls = json.loads(msg.media_urls)
                    image_urls.extend(urls)
                except (json.JSONDecodeError, TypeError):
                    pass
        
        # Generate and send ONE response for the conversation
        logger.info(
            "Generating response to conversation",
            username=username,
            new_messages=len(new_inbound_messages),
            history_length=len(full_history),
            has_images=bool(image_urls),
        )
        
        response_sent = await _respond_to_message(
            db, browser, persona, conversation, latest_msg, full_history, image_urls
        )
        
        if response_sent:
            results["responses_sent"] += 1
            
            # Mark all pending inbound messages as responded
            pending_to_update = (await db.execute(
                select(DirectMessage).where(
                    DirectMessage.conversation_id == conversation.id,
                    DirectMessage.direction == MessageDirection.INBOUND,
                    DirectMessage.status == MessageStatus.PENDING_RESPONSE,
                )
            )).scalars().all()
            
            for msg in pending_to_update:
                msg.status = MessageStatus.RESPONDED
                logger.debug("Marked message as responded", message_id=str(msg.id))
            
            # Update context_summary periodically when conversation gets long
            # This helps the AI remember important details from earlier
            if len(full_history) >= 10 and len(full_history) % 5 == 0:
                # Generate a proper summary every 5 messages after 10
                try:
                    responder = DMResponder()
                    summary = await responder.generate_conversation_summary(
                        persona, full_history
                    )
                    if summary:
                        conversation.context_summary = summary
                        logger.info("Updated conversation summary", 
                                    username=username, summary_preview=summary[:50])
                except Exception as e:
                    logger.warning("Failed to generate conversation summary", error=str(e))
            
            await db.commit()
            
            logger.info(
                "Response cycle complete", 
                username=username, 
                marked_responded=len(pending_to_update)
            )
        
        # Delay before processing next conversation
        delay = random.randint(
            persona.dm_response_delay_min,
            persona.dm_response_delay_max,
        )
        await asyncio.sleep(delay)


async def _get_or_create_conversation(
    db: AsyncSession,
    persona: Persona,
    conv_data: dict,
    platform: str,
) -> Conversation:
    """Get or create a conversation record."""
    # Use participant_username as the primary key - it's stable unlike position-based IDs
    participant_username = conv_data.get("participant_username")
    
    result = await db.execute(
        select(Conversation).where(
            Conversation.persona_id == persona.id,
            Conversation.platform == platform,
            Conversation.participant_username == participant_username,
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        conversation = Conversation(
            persona_id=persona.id,
            platform=platform,
            platform_conversation_id=conv_data.get("conversation_id"),
            participant_id=participant_username,  # Use username as ID for stability
            participant_username=participant_username,
            participant_name=conv_data.get("participant_name"),
            status=ConversationStatus.ACTIVE,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        
        logger.info(
            "New conversation created",
            persona=persona.name,
            participant=conv_data.get("participant_username"),
        )
    
    return conversation


async def _respond_to_message(
    db: AsyncSession,
    browser: InstagramBrowser,
    persona: Persona,
    conversation: Conversation,
    incoming_msg: DirectMessage,
    message_history: list = None,
    image_urls: list = None,
) -> bool:
    """Generate and send a response to a message.
    
    Args:
        message_history: Optional list of DirectMessage objects for context.
                        If not provided, will be fetched from database.
        image_urls: Optional list of image URLs to analyze for context.
    """
    
    # Check daily limit again
    if persona.dm_responses_today >= persona.dm_max_responses_per_day:
        logger.info("Daily DM response limit reached", persona=persona.name)
        return False
    
    # Get message history for context if not provided
    if message_history is None:
        result = await db.execute(
            select(DirectMessage)
            .where(DirectMessage.conversation_id == conversation.id)
            .order_by(DirectMessage.created_at.asc())
            .limit(20)
        )
        message_history = result.scalars().all()
    
    # Generate response
    responder = DMResponder()
    should_respond = await responder.should_respond(incoming_msg.content, conversation)
    
    if not should_respond["should_respond"]:
        incoming_msg.status = MessageStatus.IGNORED
        await db.commit()
        logger.info(
            "Skipping message",
            reason=should_respond["reason"],
            conversation_id=str(conversation.id),
        )
        return False
    
    response_result = await responder.generate_response(
        persona=persona,
        conversation=conversation,
        incoming_message=incoming_msg.content,
        message_history=message_history,
        image_urls=image_urls,
    )
    
    if not response_result["success"]:
        incoming_msg.status = MessageStatus.FAILED
        await db.commit()
        return False
    
    # Check if requires human review
    if response_result.get("requires_review"):
        conversation.requires_human_review = True
        incoming_msg.status = MessageStatus.PENDING_RESPONSE
        await db.commit()
        logger.info(
            "Message flagged for human review",
            conversation_id=str(conversation.id),
        )
        return False
    
    # Send the response
    response_text = response_result["response"]
    
    # Check for duplicate response - don't send if we recently sent something very similar
    # This prevents the bot from responding twice with the same/similar message
    recent_outbound = await db.execute(
        select(DirectMessage)
        .where(
            DirectMessage.conversation_id == conversation.id,
            DirectMessage.direction == MessageDirection.OUTBOUND,
        )
        .order_by(DirectMessage.sent_at.desc())
        .limit(3)
    )
    recent_outbound_msgs = recent_outbound.scalars().all()
    
    normalized_response = normalize_message_content(response_text)
    for recent_msg in recent_outbound_msgs:
        normalized_recent = normalize_message_content(recent_msg.content)
        # If the responses are very similar (80%+ overlap), skip sending
        if normalized_response and normalized_recent:
            # Simple similarity check - if one contains most of the other
            shorter = min(normalized_response, normalized_recent, key=len)
            longer = max(normalized_response, normalized_recent, key=len)
            if len(shorter) > 10 and shorter in longer:
                logger.warning(
                    "Skipping duplicate response",
                    conversation_id=str(conversation.id),
                    response_preview=response_text[:50],
                )
                incoming_msg.status = MessageStatus.RESPONDED  # Mark as handled
                await db.commit()
                return False
    
    # First try sending in the current thread (if we clicked into it)
    sent = await browser.send_dm_in_current_thread(response_text)
    
    # If that fails, try navigating to the thread
    if not sent and conversation.platform_conversation_id:
        sent = await browser.send_dm(
            conversation.platform_conversation_id,
            response_text,
        )
    elif not sent:
        sent = await browser.send_dm_to_user(
            conversation.participant_username,
            response_text,
        )
    
    if sent:
        # Save outgoing message
        outgoing_msg = DirectMessage(
            conversation_id=conversation.id,
            direction=MessageDirection.OUTBOUND,
            content=response_text,
            status=MessageStatus.RESPONDED,
            ai_generated=True,
            response_time_ms=response_result.get("response_time_ms"),
        )
        db.add(outgoing_msg)
        
        # Update tracking
        incoming_msg.status = MessageStatus.RESPONDED
        conversation.message_count += 2  # Incoming + outgoing
        conversation.last_message_at = datetime.utcnow()
        conversation.last_response_at = datetime.utcnow()
        persona.dm_responses_today += 1
        
        await db.commit()
        
        logger.info(
            "DM response sent",
            persona=persona.name,
            participant=conversation.participant_username,
            response_preview=response_text[:50],
        )
        return True
    else:
        incoming_msg.status = MessageStatus.FAILED
        await db.commit()
        return False


@shared_task(name="app.workers.tasks.dm_tasks.respond_to_single_dm")
def respond_to_single_dm(conversation_id: str, message_id: str) -> dict:
    """Manually trigger a response to a specific message."""
    return run_async(_respond_to_single_dm(conversation_id, message_id))


async def _respond_to_single_dm(conversation_id: str, message_id: str) -> dict:
    """Async implementation of single DM response."""
    async with async_session_maker() as db:
        # Get conversation and message
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == UUID(conversation_id))
        )
        conversation = conv_result.scalar_one_or_none()
        
        if not conversation:
            return {"success": False, "error": "Conversation not found"}
        
        msg_result = await db.execute(
            select(DirectMessage).where(DirectMessage.id == UUID(message_id))
        )
        message = msg_result.scalar_one_or_none()
        
        if not message:
            return {"success": False, "error": "Message not found"}
        
        # Get persona
        persona_result = await db.execute(
            select(Persona).where(Persona.id == conversation.persona_id)
        )
        persona = persona_result.scalar_one_or_none()
        
        if not persona:
            return {"success": False, "error": "Persona not found"}
        
        # Get account
        account_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.platform == Platform.INSTAGRAM,
            )
        )
        account = account_result.scalar_one_or_none()
        
        if not account or not account.session_cookies:
            return {"success": False, "error": "No Instagram session"}
        
        # Initialize browser
        browser = InstagramBrowser()
        
        try:
            await browser.load_cookies(account.session_cookies)
            if not await browser.verify_session():
                return {"success": False, "error": "Session invalid"}
            
            sent = await _respond_to_message(db, browser, persona, conversation, message)
            return {"success": sent}
            
        finally:
            await browser.close()

