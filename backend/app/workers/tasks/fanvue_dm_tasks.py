"""Fanvue Direct Message handling tasks using browser automation."""

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
from app.services.platforms.fanvue.adapter import FanvueAdapter

logger = structlog.get_logger()
settings = get_settings()


def run_async(coro):
    """Run async code in sync context."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@shared_task(name="app.workers.tasks.fanvue_dm_tasks.check_and_respond_fanvue_dms")
def check_and_respond_fanvue_dms() -> dict:
    """Check for new Fanvue DMs and respond automatically.
    
    This is the main scheduled task that runs periodically.
    Uses browser automation to access Fanvue.
    """
    return run_async(_check_and_respond_fanvue_dms())


async def _check_and_respond_fanvue_dms() -> dict:
    """Async implementation of Fanvue DM checking and responding."""
    results = {
        "personas_checked": 0,
        "new_messages": 0,
        "responses_sent": 0,
        "errors": 0,
    }
    
    async with async_session_maker() as db:
        # Get personas with DM auto-respond enabled and Fanvue connected
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
                        "DM response limit reached for Fanvue",
                        persona=persona.name,
                        responses_today=persona.dm_responses_today,
                    )
                    continue
                
                # Check if persona has Fanvue account
                account_result = await db.execute(
                    select(PlatformAccount).where(
                        PlatformAccount.persona_id == persona.id,
                        PlatformAccount.platform == Platform.FANVUE,
                        PlatformAccount.is_connected == True,
                    )
                )
                account = account_result.scalar_one_or_none()
                
                if not account:
                    continue
                
                persona_results = await _check_persona_fanvue_dms(db, persona, account)
                results["personas_checked"] += 1
                results["new_messages"] += persona_results.get("new_messages", 0)
                results["responses_sent"] += persona_results.get("responses_sent", 0)
                
            except Exception as e:
                logger.error("Fanvue DM check failed for persona", persona=persona.name, error=str(e))
                results["errors"] += 1
    
    logger.info("Fanvue DM check cycle complete", results=results)
    return results


async def _check_persona_fanvue_dms(
    db: AsyncSession,
    persona: Persona,
    account: PlatformAccount,
) -> dict:
    """Check Fanvue DMs for a single persona using browser automation."""
    results = {"new_messages": 0, "responses_sent": 0}
    
    # Initialize Fanvue adapter with browser automation
    # Use persona ID as session identifier
    adapter = FanvueAdapter(
        session_id=str(persona.id),
        headless=True,
    )
    
    try:
        # Load cookies from database and authenticate before verifying connection
        if account.session_cookies:
            cookie_count = len(account.session_cookies) if isinstance(account.session_cookies, (list, dict)) else 0
            cookie_type = "list" if isinstance(account.session_cookies, list) else "dict" if isinstance(account.session_cookies, dict) else "unknown"
            logger.info(
                "Loading Fanvue session from database cookies",
                persona=persona.name,
                cookie_count=cookie_count,
                cookie_format=cookie_type,
            )
            auth_success = await adapter.authenticate({"session_cookies": account.session_cookies})
            if auth_success:
                logger.info("Fanvue session authenticated from database", persona=persona.name)
                # Clear any previous connection error since we're now connected
                if account.connection_error:
                    account.connection_error = None
                    account.is_connected = True
                    await db.commit()
            else:
                logger.warning(
                    "Fanvue authentication with stored cookies failed - session may be expired",
                    persona=persona.name,
                    cookie_count=cookie_count,
                )
                # Don't immediately disconnect - the cookies might be refreshable
                # Only set connection error, not is_connected = False
                account.connection_error = "Session needs refresh - try reconnecting if issues persist"
                await db.commit()
                return results
        else:
            logger.warning("No Fanvue cookies stored for persona", persona=persona.name)
            return results
        
        # Skip verify_connection since authenticate already checks is_logged_in
        # verify_connection would just call is_logged_in again which is redundant
        
        # Get unanswered chats via browser
        chats = await adapter.get_dm_inbox(limit=10, filter_unanswered=True)
        
        logger.info(
            "Fetched Fanvue chats via browser",
            persona=persona.name,
            chat_count=len(chats),
        )
        
        for chat_data in chats:
            if persona.dm_responses_today >= persona.dm_max_responses_per_day:
                break
            
            # Extract user info from browser-scraped data
            username = chat_data.get("username", "")
            user_id = chat_data.get("user_id") or username
            
            if not user_id:
                continue
            
            # Get or create conversation record
            conversation = await _get_or_create_fanvue_conversation(
                db, persona, user_id, username
            )
            
            if conversation.status != ConversationStatus.ACTIVE:
                continue
            
            # Get messages for this chat via browser
            messages = await adapter.get_conversation_messages(user_id, limit=20)
            
            if not messages:
                continue
            
            # Process messages and find new ones needing response
            new_inbound = await _process_fanvue_messages(
                db, conversation, messages, results
            )
            
            if not new_inbound:
                continue
            
            # Generate and send response
            response_sent = await _respond_to_fanvue_message(
                db, adapter, persona, conversation, new_inbound[-1], messages
            )
            
            if response_sent:
                results["responses_sent"] += 1
                persona.dm_responses_today += 1
                await db.commit()
            
            # Delay between conversations (human-like behavior)
            delay = random.randint(
                persona.dm_response_delay_min,
                persona.dm_response_delay_max,
            )
            await asyncio.sleep(delay)
        
    finally:
        await adapter.close()
    
    return results


async def _get_or_create_fanvue_conversation(
    db: AsyncSession,
    persona: Persona,
    user_id: str,
    username: str,
) -> Conversation:
    """Get or create a Fanvue conversation record."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.persona_id == persona.id,
            Conversation.platform == "fanvue",
            Conversation.participant_id == user_id,
        )
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        conversation = Conversation(
            persona_id=persona.id,
            platform="fanvue",
            platform_conversation_id=user_id,
            participant_id=user_id,
            participant_username=username,
            participant_name=username,
            participant_profile_url=f"https://www.fanvue.com/{username}" if username else None,
            status=ConversationStatus.ACTIVE,
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        
        logger.info(
            "New Fanvue conversation created",
            persona=persona.name,
            participant=username,
        )
    
    return conversation


async def _process_fanvue_messages(
    db: AsyncSession,
    conversation: Conversation,
    messages: list,
    results: dict,
) -> list:
    """Process Fanvue messages from browser scraping and save new ones.
    
    Returns list of new inbound messages that need responses.
    """
    new_inbound = []
    
    # Get last known message timestamp for this conversation
    last_msg_result = await db.execute(
        select(DirectMessage.sent_at)
        .where(DirectMessage.conversation_id == conversation.id)
        .order_by(DirectMessage.sent_at.desc())
        .limit(1)
    )
    last_msg_row = last_msg_result.fetchone()
    last_msg_time = last_msg_row[0] if last_msg_row else None
    
    for msg_data in messages:
        # Browser-scraped message format
        content = msg_data.get("text", "").strip()
        is_from_me = msg_data.get("is_from_me", False)
        timestamp_str = msg_data.get("timestamp", "")
        
        if not content:
            continue
        
        # Skip outgoing messages
        if is_from_me:
            continue
        
        # For browser automation, we can't easily get unique message IDs
        # Use content hash as a simple deduplication mechanism
        content_hash = f"{conversation.participant_id}_{hash(content) % 10000000}"
        
        # Check if we've already processed this message
        existing_result = await db.execute(
            select(DirectMessage).where(
                DirectMessage.conversation_id == conversation.id,
                DirectMessage.content == content,
                DirectMessage.direction == MessageDirection.INBOUND,
            ).limit(1)
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            continue
        
        # This is a new inbound message
        dm = DirectMessage(
            conversation_id=conversation.id,
            platform_message_id=content_hash,
            direction=MessageDirection.INBOUND,
            content=content,
            status=MessageStatus.PENDING_RESPONSE,
            sent_at=datetime.utcnow(),  # We don't have exact timestamp from scraping
        )
        db.add(dm)
        new_inbound.append(dm)
        results["new_messages"] += 1
    
    if new_inbound:
        await db.commit()
    
    return new_inbound


async def _respond_to_fanvue_message(
    db: AsyncSession,
    adapter: FanvueAdapter,
    persona: Persona,
    conversation: Conversation,
    incoming_msg: DirectMessage,
    message_history: list,
) -> bool:
    """Generate and send a response to a Fanvue message via browser."""
    
    # Build message history for AI context
    history_result = await db.execute(
        select(DirectMessage)
        .where(DirectMessage.conversation_id == conversation.id)
        .order_by(DirectMessage.sent_at.asc())
        .limit(20)
    )
    db_history = list(history_result.scalars().all())
    
    # Generate response using DMResponder
    responder = DMResponder()
    
    should_respond = await responder.should_respond(incoming_msg.content, conversation)
    
    if not should_respond["should_respond"]:
        incoming_msg.status = MessageStatus.IGNORED
        await db.commit()
        logger.info(
            "Skipping Fanvue message",
            reason=should_respond["reason"],
            conversation_id=str(conversation.id),
        )
        return False
    
    response_result = await responder.generate_response(
        persona=persona,
        conversation=conversation,
        incoming_message=incoming_msg.content,
        message_history=db_history,
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
            "Fanvue message flagged for human review",
            conversation_id=str(conversation.id),
        )
        return False
    
    # Send the response via browser
    response_text = response_result["response"]
    
    sent = await adapter.send_dm(
        user_identifier=conversation.participant_id,
        text=response_text,
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
        conversation.message_count += 2
        conversation.last_message_at = datetime.utcnow()
        conversation.last_response_at = datetime.utcnow()
        
        await db.commit()
        
        logger.info(
            "Fanvue DM response sent via browser",
            persona=persona.name,
            participant=conversation.participant_username,
            response_preview=response_text[:50],
        )
        return True
    else:
        incoming_msg.status = MessageStatus.FAILED
        await db.commit()
        return False


@shared_task(name="app.workers.tasks.fanvue_dm_tasks.respond_to_single_fanvue_dm")
def respond_to_single_fanvue_dm(conversation_id: str, message_id: str) -> dict:
    """Manually trigger a response to a specific Fanvue message."""
    return run_async(_respond_to_single_fanvue_dm(conversation_id, message_id))


async def _respond_to_single_fanvue_dm(conversation_id: str, message_id: str) -> dict:
    """Async implementation of single Fanvue DM response via browser."""
    async with async_session_maker() as db:
        # Get conversation and message
        conv_result = await db.execute(
            select(Conversation).where(Conversation.id == UUID(conversation_id))
        )
        conversation = conv_result.scalar_one_or_none()
        
        if not conversation:
            return {"success": False, "error": "Conversation not found"}
        
        if conversation.platform != "fanvue":
            return {"success": False, "error": "Not a Fanvue conversation"}
        
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
                PlatformAccount.platform == Platform.FANVUE,
            )
        )
        account = account_result.scalar_one_or_none()
        
        if not account or not account.is_connected:
            return {"success": False, "error": "No Fanvue account connected"}
        
        # Initialize adapter with browser automation
        adapter = FanvueAdapter(
            session_id=str(persona.id),
            headless=True,
        )
        
        try:
            # Load cookies from database and authenticate
            if not account.session_cookies:
                return {"success": False, "error": "No Fanvue cookies stored"}
            
            auth_success = await adapter.authenticate({"session_cookies": account.session_cookies})
            if not auth_success:
                return {"success": False, "error": "Fanvue session expired - please reconnect"}
            
            sent = await _respond_to_fanvue_message(
                db, adapter, persona, conversation, message, []
            )
            return {"success": sent}
            
        finally:
            await adapter.close()
