"""Direct Message handling tasks."""

import asyncio
import random
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
        
        # Then check main inbox
        conversations = await browser.get_dm_inbox(limit=10, include_requests=False)
        await _process_conversations(
            db, browser, persona, conversations[:5], results
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
    # Skip certain entries
    skip_usernames = ["Your note", "alaina.tomlinson", "Back", "Hidden Requests", "Delete all 1", "Delete all 0"]
    
    for conv_data in conversations:
        # Skip the persona's own note or non-person entries
        username = conv_data.get("participant_username", "")
        if not username or username in skip_usernames:
            continue
        
        # Check if this is a message request (always process) or unread
        is_request = conv_data.get("is_request", False)
        is_unread = conv_data.get("unread", False)
        
        # For regular inbox conversations, also check if we've already responded recently
        # This handles cases where Instagram's unread detection doesn't work
        if not is_request and not is_unread:
            # Check if the last message preview is different from what we've seen
            last_preview = conv_data.get("last_message_preview", "")
            
            # Look up this conversation in our database using username (stable key)
            existing_conv = await db.execute(
                select(Conversation).where(
                    Conversation.persona_id == persona.id,
                    Conversation.platform == "instagram",
                    Conversation.participant_username == username,
                )
            )
            existing_conv = existing_conv.scalar_one_or_none()
            
            # If we have a record and the last message matches our last seen, skip
            if existing_conv and existing_conv.context_summary == last_preview:
                logger.info("Skipping - already processed this message", username=username)
                continue
            
            # Otherwise, it might be a new message even if not marked unread
            if last_preview:
                logger.info("Processing conversation with new message preview", username=username, preview=last_preview[:30])
            else:
                logger.info("Skipping read conversation with no preview", username=username)
                continue
        else:
            logger.info("Processing conversation", username=username, unread=is_unread, is_request=is_request)
        
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
        
        # Process each message
        for idx, msg_data in enumerate(messages):
            content = msg_data.get("content", "").strip()
            if not content:
                continue
                
            is_outgoing = msg_data.get("is_outgoing", False)
            direction = MessageDirection.OUTBOUND if is_outgoing else MessageDirection.INBOUND
            
            # Check if this message already exists in our database
            existing = await db.execute(
                select(DirectMessage).where(
                    DirectMessage.conversation_id == conversation.id,
                    DirectMessage.content == content,
                    DirectMessage.direction == direction,
                )
            )
            
            if not existing.scalar_one_or_none():
                # Save new message to database
                # Outgoing = already responded, Inbound = pending response
                new_msg = DirectMessage(
                    conversation_id=conversation.id,
                    direction=direction,
                    content=content,
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
        
        # Also check: is the last message in the conversation inbound?
        # If so, we should respond even if messages aren't marked as pending
        last_message = full_history[-1] if full_history else None
        needs_response = (
            len(new_inbound_messages) > 0 or  # New messages detected
            len(pending_messages) > 0 or  # Pending messages in DB
            (last_message and last_message.direction == MessageDirection.INBOUND)  # Last msg is inbound
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
        
        # Generate and send ONE response for the conversation
        logger.info(
            "Generating response to conversation",
            username=username,
            new_messages=len(new_inbound_messages),
            history_length=len(full_history),
        )
        
        response_sent = await _respond_to_message(
            db, browser, persona, conversation, latest_msg, full_history
        )
        
        if response_sent:
            results["responses_sent"] += 1
            
            # Mark all pending inbound messages as responded
            await db.execute(
                select(DirectMessage)
                .where(
                    DirectMessage.conversation_id == conversation.id,
                    DirectMessage.direction == MessageDirection.INBOUND,
                    DirectMessage.status == MessageStatus.PENDING_RESPONSE,
                )
            )
            for msg in (await db.execute(
                select(DirectMessage).where(
                    DirectMessage.conversation_id == conversation.id,
                    DirectMessage.direction == MessageDirection.INBOUND,
                    DirectMessage.status == MessageStatus.PENDING_RESPONSE,
                )
            )).scalars().all():
                msg.status = MessageStatus.RESPONDED
            
            # Update context_summary with the last message
            conversation.context_summary = latest_msg.content[:200] if latest_msg.content else None
            await db.commit()
        
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
) -> bool:
    """Generate and send a response to a message.
    
    Args:
        message_history: Optional list of DirectMessage objects for context.
                        If not provided, will be fetched from database.
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

