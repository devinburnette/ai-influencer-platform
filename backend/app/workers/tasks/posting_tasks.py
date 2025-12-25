"""Content posting tasks."""

import asyncio
import random
from datetime import datetime, timedelta
from uuid import UUID

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import TYPE_CHECKING

from app.config import get_settings
from app.database import async_session_maker
from app.models.persona import Persona
from app.models.content import Content, ContentStatus
from app.models.platform_account import PlatformAccount, Platform
from app.services.platforms.registry import PlatformRegistry

logger = structlog.get_logger()
settings = get_settings()


def run_async(coro):
    """Run async code in sync context."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@shared_task(name="app.workers.tasks.posting_tasks.post_content")
def post_content(content_id: str) -> dict:
    """Post a specific content item to the first available platform.
    
    Args:
        content_id: UUID of the content to post
        
    Returns:
        Dictionary with posting result
    """
    return run_async(_post_content(content_id))


@shared_task(name="app.workers.tasks.posting_tasks.post_content_to_platform")
def post_content_to_platform(content_id: str, platform: str) -> dict:
    """Post a specific content item to a specific platform.
    
    Args:
        content_id: UUID of the content to post
        platform: Platform name (e.g., "twitter", "instagram")
        
    Returns:
        Dictionary with posting result
    """
    return run_async(_post_content_to_platform(content_id, platform))


async def _post_content(content_id: str) -> dict:
    """Async implementation of content posting to first available platform."""
    async with async_session_maker() as db:
        # Get content
        result = await db.execute(
            select(Content).where(Content.id == UUID(content_id))
        )
        content = result.scalar_one_or_none()
        
        if not content:
            logger.error("Content not found", content_id=content_id)
            return {"success": False, "error": "Content not found"}
        
        if content.status == ContentStatus.POSTED:
            logger.info("Content already posted", content_id=content_id)
            return {"success": True, "already_posted": True}
        
        if content.status not in [ContentStatus.SCHEDULED, ContentStatus.POSTING]:
            logger.warning(
                "Content not ready for posting",
                content_id=content_id,
                status=content.status.value,
            )
            return {"success": False, "error": f"Invalid status: {content.status.value}"}
        
        # Get persona
        persona_result = await db.execute(
            select(Persona).where(Persona.id == content.persona_id)
        )
        persona = persona_result.scalar_one_or_none()
        
        if not persona or not persona.is_active:
            logger.warning("Persona not available", persona_id=str(content.persona_id))
            return {"success": False, "error": "Persona not available"}
        
        # Check rate limits
        if persona.posts_today >= settings.max_posts_per_day:
            logger.warning(
                "Post rate limit reached",
                persona=persona.name,
                posts_today=persona.posts_today,
            )
            return {"success": False, "error": "Rate limit reached"}
        
        # Get platform account - try Twitter first, then Instagram, or any connected
        account = None
        for platform in [Platform.TWITTER, Platform.INSTAGRAM]:
            account_result = await db.execute(
                select(PlatformAccount).where(
                    PlatformAccount.persona_id == persona.id,
                    PlatformAccount.platform == platform,
                    PlatformAccount.is_connected == True,
                )
            )
            account = account_result.scalar_one_or_none()
            if account:
                break
        
        if not account:
            logger.error("No connected platform account", persona=persona.name)
            return {"success": False, "error": "No connected platform account"}
        
        # Delegate to platform-specific posting
        return await _post_to_platform(db, content, persona, account)


async def _post_content_to_platform(content_id: str, platform: str) -> dict:
    """Async implementation of content posting to a specific platform."""
    async with async_session_maker() as db:
        # Get content
        result = await db.execute(
            select(Content).where(Content.id == UUID(content_id))
        )
        content = result.scalar_one_or_none()
        
        if not content:
            logger.error("Content not found", content_id=content_id)
            return {"success": False, "error": "Content not found"}
        
        # For multi-platform posting, we allow re-posting to different platforms
        # Only skip if already posted to THIS platform (we'd need to track per-platform status)
        # For now, allow posting unless it's completely posted
        if content.status == ContentStatus.POSTED:
            logger.info("Content already posted", content_id=content_id)
            return {"success": True, "already_posted": True}
        
        # Allow posting from more states since we're specifically targeting a platform
        if content.status not in [ContentStatus.SCHEDULED, ContentStatus.POSTING, ContentStatus.PENDING_REVIEW]:
            logger.warning(
                "Content not ready for posting",
                content_id=content_id,
                status=content.status.value,
            )
            return {"success": False, "error": f"Invalid status: {content.status.value}"}
        
        # Get persona
        persona_result = await db.execute(
            select(Persona).where(Persona.id == content.persona_id)
        )
        persona = persona_result.scalar_one_or_none()
        
        if not persona or not persona.is_active:
            logger.warning("Persona not available", persona_id=str(content.persona_id))
            return {"success": False, "error": "Persona not available"}
        
        # Check rate limits
        if persona.posts_today >= settings.max_posts_per_day:
            logger.warning(
                "Post rate limit reached",
                persona=persona.name,
                posts_today=persona.posts_today,
            )
            return {"success": False, "error": "Rate limit reached"}
        
        # Get the specific platform account
        platform_enum = Platform(platform.lower())
        account_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.platform == platform_enum,
                PlatformAccount.is_connected == True,
            )
        )
        account = account_result.scalar_one_or_none()
        
        if not account:
            logger.error("No connected account for platform", persona=persona.name, platform=platform)
            return {"success": False, "error": f"No connected {platform} account"}
        
        # Delegate to platform-specific posting
        return await _post_to_platform(db, content, persona, account)


async def _post_to_platform(db: AsyncSession, content: Content, persona: Persona, account: PlatformAccount) -> dict:
    """Common implementation for posting content to a platform."""
    adapter = None
    content_id = str(content.id)
    
    # Mark as posting
    content.status = ContentStatus.POSTING
    await db.commit()
    
    try:
        # Create platform adapter based on account platform
        platform_name = account.platform.value
        
        if platform_name == "twitter":
            # Twitter uses app-level credentials from settings + user tokens from account
            adapter = PlatformRegistry.create_adapter(
                "twitter",
                api_key=settings.twitter_api_key,
                api_secret=settings.twitter_api_secret,
                access_token=account.access_token,
                access_token_secret=account.refresh_token,  # OAuth stores secret in refresh_token field
                bearer_token=settings.twitter_bearer_token,
            )
        elif platform_name == "instagram":
            adapter = PlatformRegistry.create_adapter(
                "instagram",
                access_token=account.access_token,
                instagram_account_id=account.platform_user_id,
                session_cookies=account.session_cookies,
            )
        else:
            raise Exception(f"Unsupported platform: {platform_name}")
        
        if not adapter:
            raise Exception("Failed to create platform adapter")
        
        # Authenticate based on platform
        if platform_name == "twitter":
            credentials = {
                "api_key": settings.twitter_api_key,
                "api_secret": settings.twitter_api_secret,
                "access_token": account.access_token,
                "access_token_secret": account.refresh_token,  # OAuth stores secret in refresh_token field
                "bearer_token": settings.twitter_bearer_token,
            }
        else:
            credentials = {}
            if account.access_token:
                credentials["access_token"] = account.access_token
                credentials["instagram_account_id"] = account.platform_user_id
            if account.session_cookies:
                credentials["session_cookies"] = account.session_cookies
        
        if not await adapter.authenticate(credentials):
            raise Exception("Authentication failed")
        
        # Post content
        result = await adapter.post_content(
            caption=content.caption,
            media_paths=content.media_urls if content.media_urls else None,
            hashtags=content.hashtags,
        )
        
        if result.success:
            content.status = ContentStatus.POSTED
            content.posted_at = datetime.utcnow()
            content.platform_post_id = result.post_id
            content.platform_url = result.url
            
            persona.posts_today += 1
            persona.post_count += 1
            
            logger.info(
                "Content posted successfully",
                persona=persona.name,
                platform=platform_name,
                content_id=content_id,
                post_id=result.post_id,
            )
            
            await db.commit()
            return {
                "success": True,
                "platform": platform_name,
                "post_id": result.post_id,
                "url": result.url,
            }
        else:
            raise Exception(result.error_message or "Posting failed")
        
    except Exception as e:
        logger.error(
            "Posting failed",
            content_id=content_id,
            platform=account.platform.value,
            error=str(e),
        )
        
        content.status = ContentStatus.FAILED
        content.error_message = f"[{account.platform.value}] {str(e)}"
        content.retry_count += 1
        
        await db.commit()
        
        return {"success": False, "platform": account.platform.value, "error": str(e)}
    
    finally:
        if adapter:
            await adapter.close()


@shared_task(name="app.workers.tasks.posting_tasks.process_posting_queue")
def process_posting_queue() -> dict:
    """Process the content posting queue.
    
    Finds scheduled content that's due and posts it.
    
    Returns:
        Dictionary with processing results
    """
    return run_async(_process_posting_queue())


async def _process_posting_queue() -> dict:
    """Async implementation of posting queue processing."""
    results = {"posted": 0, "skipped": 0, "errors": 0}
    
    async with async_session_maker() as db:
        now = datetime.utcnow()
        
        # Get content due for posting
        # Include content where scheduled_for is NULL (meaning "post ASAP")
        # or where scheduled_for is in the past
        from sqlalchemy import or_
        
        result = await db.execute(
            select(Content)
            .where(
                Content.status == ContentStatus.SCHEDULED,
                or_(
                    Content.scheduled_for.is_(None),  # No specific time = post ASAP
                    Content.scheduled_for <= now,     # Scheduled time has passed
                ),
            )
            .order_by(Content.scheduled_for.asc().nullsfirst())
            .limit(10)  # Process up to 10 at a time
        )
        content_items = result.scalars().all()
        
        logger.info("Found content for posting", count=len(content_items))
        
        for content in content_items:
            # Add random delay between posts (skip delay for first post)
            if content != content_items[0]:
                delay = random.randint(
                    settings.min_action_delay,
                    settings.max_action_delay,
                )
                logger.info("Waiting before next post", delay_seconds=delay)
                await asyncio.sleep(delay)
            
            logger.info("Processing content for posting", content_id=str(content.id))
            
            try:
                post_result = await _post_content(str(content.id))
                
                if post_result.get("success"):
                    results["posted"] += 1
                else:
                    results["errors"] += 1
                    
            except Exception as e:
                logger.error(
                    "Queue processing error",
                    content_id=str(content.id),
                    error=str(e),
                )
                results["errors"] += 1
    
    logger.info("Posting queue processed", results=results)
    return results


@shared_task(name="app.workers.tasks.posting_tasks.schedule_content")
def schedule_content(content_id: str, scheduled_for: str) -> dict:
    """Schedule content for posting.
    
    Args:
        content_id: UUID of the content
        scheduled_for: ISO format datetime string
        
    Returns:
        Dictionary with scheduling result
    """
    return run_async(_schedule_content(content_id, scheduled_for))


async def _schedule_content(content_id: str, scheduled_for: str) -> dict:
    """Async implementation of content scheduling."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(Content).where(Content.id == UUID(content_id))
        )
        content = result.scalar_one_or_none()
        
        if not content:
            return {"success": False, "error": "Content not found"}
        
        try:
            scheduled_datetime = datetime.fromisoformat(scheduled_for)
            
            content.scheduled_for = scheduled_datetime
            content.status = ContentStatus.SCHEDULED
            
            await db.commit()
            
            logger.info(
                "Content scheduled",
                content_id=content_id,
                scheduled_for=scheduled_for,
            )
            
            return {
                "success": True,
                "scheduled_for": scheduled_for,
            }
            
        except Exception as e:
            logger.error(
                "Scheduling failed",
                content_id=content_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}


@shared_task(name="app.workers.tasks.posting_tasks.retry_failed_posts")
def retry_failed_posts() -> dict:
    """Retry posting failed content.
    
    Returns:
        Dictionary with retry results
    """
    return run_async(_retry_failed_posts())


async def _retry_failed_posts() -> dict:
    """Async implementation of retry logic."""
    results = {"retried": 0, "max_retries": 0}
    max_retries = 3
    
    async with async_session_maker() as db:
        # Get failed content that hasn't exceeded retry limit
        result = await db.execute(
            select(Content)
            .where(
                Content.status == ContentStatus.FAILED,
                Content.retry_count < max_retries,
            )
        )
        failed_content = result.scalars().all()
        
        for content in failed_content:
            # Reset to scheduled for retry
            content.status = ContentStatus.SCHEDULED
            content.scheduled_for = datetime.utcnow() + timedelta(minutes=30)
            results["retried"] += 1
        
        # Mark content that exceeded retries
        exceeded_result = await db.execute(
            select(Content)
            .where(
                Content.status == ContentStatus.FAILED,
                Content.retry_count >= max_retries,
            )
        )
        exceeded_content = exceeded_result.scalars().all()
        
        for content in exceeded_content:
            content.error_message = f"Max retries ({max_retries}) exceeded. " + (content.error_message or "")
            results["max_retries"] += 1
        
        await db.commit()
    
    logger.info("Retry processing complete", results=results)
    return results


