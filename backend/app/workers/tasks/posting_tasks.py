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
from app.models.content import Content, ContentStatus, ContentType
from app.models.platform_account import PlatformAccount, Platform
from app.models.settings import get_setting_value, DEFAULT_RATE_LIMIT_SETTINGS
from app.services.platforms.registry import PlatformRegistry

logger = structlog.get_logger()
settings = get_settings()


async def get_rate_limit(db, key: str) -> int:
    """Get a rate limit setting from database."""
    return await get_setting_value(db, key, DEFAULT_RATE_LIMIT_SETTINGS.get(key, {}).get("value", 0))


async def check_content_type_limit(db, persona: Persona, content: Content) -> tuple[bool, str]:
    """Check if content type limit has been reached (persona-level, deprecated).
    
    Returns:
        Tuple of (is_allowed, error_message)
    """
    content_type = content.content_type
    has_video = content.video_urls and len(content.video_urls) > 0
    
    if content_type == ContentType.REEL:
        max_limit = await get_rate_limit(db, "max_reels_per_day")
        current_count = persona.reels_today
        limit_name = "reels"
    elif content_type == ContentType.STORY:
        max_limit = await get_rate_limit(db, "max_stories_per_day")
        current_count = persona.stories_today
        limit_name = "stories"
    elif has_video:
        # Regular post with video
        max_limit = await get_rate_limit(db, "max_video_posts_per_day")
        current_count = persona.video_posts_today
        limit_name = "video posts"
    else:
        # Regular image post
        max_limit = await get_rate_limit(db, "max_posts_per_day")
        current_count = persona.posts_today
        limit_name = "posts"
    
    if current_count >= max_limit:
        return False, f"Daily {limit_name} limit reached ({current_count}/{max_limit})"
    
    return True, ""


async def check_platform_content_limit(db, account: PlatformAccount, content: Content) -> tuple[bool, str]:
    """Check if per-platform content type limit has been reached.
    
    Returns:
        Tuple of (is_allowed, error_message)
    """
    # Reset daily limits if needed (new day)
    account.check_and_reset_daily_limits()
    
    content_type = content.content_type
    has_video = content.video_urls and len(content.video_urls) > 0
    platform_name = account.platform.value.capitalize()
    
    if content_type == ContentType.REEL:
        max_limit = await get_rate_limit(db, "max_reels_per_day")
        current_count = account.reels_today or 0
        limit_name = "reels"
    elif content_type == ContentType.STORY:
        max_limit = await get_rate_limit(db, "max_stories_per_day")
        current_count = account.stories_today or 0
        limit_name = "stories"
    elif has_video:
        # Regular post with video
        max_limit = await get_rate_limit(db, "max_video_posts_per_day")
        current_count = account.video_posts_today or 0
        limit_name = "video posts"
    else:
        # Regular image post
        max_limit = await get_rate_limit(db, "max_posts_per_day")
        current_count = account.posts_today or 0
        limit_name = "posts"
    
    if current_count >= max_limit:
        return False, f"{platform_name} daily {limit_name} limit reached ({current_count}/{max_limit})"
    
    return True, ""


def increment_content_type_counter(persona: Persona, content: Content, account: PlatformAccount = None):
    """Increment the appropriate daily counter based on content type.
    
    Args:
        persona: The persona to increment counters for (legacy, still updated for backwards compat)
        content: The content being posted
        account: The platform account to increment per-platform counters for
    """
    content_type = content.content_type
    has_video = content.video_urls and len(content.video_urls) > 0
    
    # Increment persona-level counter (legacy)
    if content_type == ContentType.REEL:
        persona.reels_today += 1
    elif content_type == ContentType.STORY:
        persona.stories_today += 1
    elif has_video:
        persona.video_posts_today += 1
    else:
        persona.posts_today += 1
    
    # Always increment total post count
    persona.post_count += 1
    
    # Increment per-platform counter
    if account:
        if content_type == ContentType.REEL:
            account.reels_today = (account.reels_today or 0) + 1
        elif content_type == ContentType.STORY:
            account.stories_today = (account.stories_today or 0) + 1
        elif has_video:
            account.video_posts_today = (account.video_posts_today or 0) + 1
        else:
            account.posts_today = (account.posts_today or 0) + 1
        account.post_count += 1


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
    """Async implementation of content posting to ALL connected platforms."""
    async with async_session_maker() as db:
        # Get content WITH ROW LOCK to prevent duplicate posts from concurrent tasks
        result = await db.execute(
            select(Content)
            .where(Content.id == UUID(content_id))
            .with_for_update(nowait=False)  # Wait for lock if another task has it
        )
        content = result.scalar_one_or_none()
        
        if not content:
            logger.error("Content not found", content_id=content_id)
            return {"success": False, "error": "Content not found"}
        
        if content.status == ContentStatus.POSTED:
            logger.info("Content already posted (duplicate task)", content_id=content_id)
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
        
        # Check rate limits based on content type
        is_allowed, limit_error = await check_content_type_limit(db, persona, content)
        if not is_allowed:
            logger.warning(
                "Content type rate limit reached",
                persona=persona.name,
                content_type=content.content_type.value,
                error=limit_error,
            )
            return {"success": False, "error": limit_error}
        
        # Get ALL connected platform accounts
        accounts_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.is_connected == True,
            )
        )
        accounts = accounts_result.scalars().all()
        
        if not accounts:
            logger.error("No connected platform accounts", persona=persona.name)
            return {"success": False, "error": "No connected platform account"}
        
        # NSFW content should ONLY be posted to Fanvue
        if content.content_type == ContentType.NSFW:
            accounts = [a for a in accounts if a.platform == Platform.FANVUE]
            if not accounts:
                logger.error("NSFW content requires Fanvue connection", persona=persona.name)
                return {"success": False, "error": "NSFW content can only be posted to Fanvue"}
            logger.info(
                "NSFW content - restricting to Fanvue only",
                persona=persona.name,
                content_id=content_id,
            )
        
        logger.info(
            "Posting to all connected platforms",
            persona=persona.name,
            platforms=[a.platform.value for a in accounts],
            content_id=content_id,
        )
        
        # Mark as posting
        content.status = ContentStatus.POSTING
        await db.commit()
        
        # Post to each platform
        results = {"success": False, "platforms": {}}
        any_success = False
        errors = []
        first_success_url = None
        first_success_post_id = None
        
        # Track which platforms we successfully posted to
        newly_posted_platforms = []
        
        for account in accounts:
            platform_name = account.platform.value
            
            # Skip platforms this content was already posted to
            if content.posted_platforms and platform_name in content.posted_platforms:
                logger.info("Content already posted to platform, skipping", platform=platform_name)
                results["platforms"][platform_name] = {"success": True, "already_posted": True}
                continue
            
            try:
                platform_result = await _post_to_platform(db, content, persona, account, update_status=False)
                results["platforms"][platform_name] = platform_result
                
                if platform_result.get("success"):
                    any_success = True
                    newly_posted_platforms.append(platform_name)
                    if first_success_url is None:
                        first_success_url = platform_result.get("url")
                        first_success_post_id = platform_result.get("post_id")
                    logger.info(
                        "Posted to platform",
                        platform=platform_name,
                        post_id=platform_result.get("post_id"),
                    )
                else:
                    errors.append(f"[{platform_name}] {platform_result.get('error')}")
                    logger.warning(
                        "Failed to post to platform",
                        platform=platform_name,
                        error=platform_result.get("error"),
                    )
            except Exception as e:
                logger.error(
                    "Platform posting error",
                    platform=platform_name,
                    error=str(e),
                )
                errors.append(f"[{platform_name}] {str(e)}")
                results["platforms"][platform_name] = {"success": False, "error": str(e)}
        
        # Update content status based on results
        if any_success or (content.posted_platforms and len(content.posted_platforms) > 0):
            content.status = ContentStatus.POSTED
            if content.posted_at is None:
                content.posted_at = datetime.utcnow()
            if first_success_url and not content.platform_url:
                content.platform_url = first_success_url
                content.platform_post_id = first_success_post_id
            
            # Track which platforms have this content
            existing_platforms = content.posted_platforms or []
            content.posted_platforms = list(set(existing_platforms + newly_posted_platforms))
            
            # Only increment content type counter if this is the first time posting this content
            if not existing_platforms and newly_posted_platforms:
                increment_content_type_counter(persona, content)
        else:
            content.status = ContentStatus.FAILED
            content.error_message = "; ".join(errors)
            content.retry_count += 1
        
        await db.commit()
        
        results["success"] = any_success
        return results


async def _post_content_to_platform(content_id: str, platform: str) -> dict:
    """Async implementation of content posting to a specific platform."""
    async with async_session_maker() as db:
        # Get content WITH ROW LOCK to prevent duplicate posts from concurrent tasks
        # This ensures only one task can post to a platform at a time
        result = await db.execute(
            select(Content)
            .where(Content.id == UUID(content_id))
            .with_for_update(nowait=False)  # Wait for lock if another task has it
        )
        content = result.scalar_one_or_none()
        
        if not content:
            logger.error("Content not found", content_id=content_id)
            return {"success": False, "error": "Content not found"}
        
        # Check if already posted to this specific platform (now with row lock, this check is safe)
        if content.posted_platforms and platform.lower() in content.posted_platforms:
            logger.info("Content already posted to this platform (duplicate task)", content_id=content_id, platform=platform)
            return {"success": True, "already_posted": True, "platform": platform}
        
        # Allow posting from more states - including POSTED for reposting to other platforms
        allowed_statuses = [ContentStatus.SCHEDULED, ContentStatus.POSTING, ContentStatus.PENDING_REVIEW, ContentStatus.POSTED]
        if content.status not in allowed_statuses:
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
        
        # Get the specific platform account FIRST so we can check per-platform limits
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
        
        # Check per-platform rate limits based on content type
        is_allowed, limit_error = await check_platform_content_limit(db, account, content)
        if not is_allowed:
            logger.warning(
                "Platform content type rate limit reached",
                persona=persona.name,
                platform=platform,
                content_type=content.content_type.value,
                error=limit_error,
            )
            return {"success": False, "error": limit_error}
        
        # Mark as posting
        content.status = ContentStatus.POSTING
        await db.commit()
        
        # Post to platform
        result = await _post_to_platform(db, content, persona, account, update_status=False)
        
        # Update status based on result
        if result.get("success"):
            # Track which platforms have this content
            existing_platforms = content.posted_platforms or []
            was_first_post = len(existing_platforms) == 0
            
            content.status = ContentStatus.POSTED
            if content.posted_at is None:
                content.posted_at = datetime.utcnow()
            if not content.platform_url:
                content.platform_url = result.get("url")
                content.platform_post_id = result.get("post_id")
            
            # Add this platform to the list
            if platform.lower() not in existing_platforms:
                content.posted_platforms = existing_platforms + [platform.lower()]
            
            # Always increment per-platform counter
            increment_content_type_counter(persona, content, account)
        else:
            # Only mark as failed if it hasn't been posted to any platform
            if not content.posted_platforms:
                content.status = ContentStatus.FAILED
            content.error_message = f"[{platform}] {result.get('error')}"
            content.retry_count += 1
        
        await db.commit()
        return result


async def _post_to_platform(
    db: AsyncSession, 
    content: Content, 
    persona: Persona, 
    account: PlatformAccount,
    update_status: bool = True,
) -> dict:
    """Common implementation for posting content to a platform.
    
    Args:
        db: Database session
        content: Content to post
        persona: Persona posting the content
        account: Platform account to post to
        update_status: Whether to update content status (False when posting to multiple platforms)
    """
    adapter = None
    content_id = str(content.id)
    platform_name = account.platform.value
    
    # Check if posting is paused for this platform
    if getattr(account, 'posting_paused', False):
        logger.info(
            "Posting paused for platform",
            persona=persona.name,
            platform=platform_name,
            content_id=content_id,
        )
        return {
            "success": False,
            "platform": platform_name,
            "skipped": True,
            "message": f"Posting is paused for {platform_name}",
        }
    
    try:
        # Create platform adapter based on account platform
        if platform_name == "twitter":
            # Twitter uses app-level credentials from settings + user tokens from account
            # Also include session_cookies for browser fallback when API is rate limited
            adapter = PlatformRegistry.create_adapter(
                "twitter",
                api_key=settings.twitter_api_key,
                api_secret=settings.twitter_api_secret,
                access_token=account.access_token,
                access_token_secret=account.refresh_token,  # OAuth stores secret in refresh_token field
                bearer_token=settings.twitter_bearer_token,
                session_cookies=account.session_cookies,  # Enable browser fallback for posting
            )
        elif platform_name == "instagram":
            adapter = PlatformRegistry.create_adapter(
                "instagram",
                access_token=account.access_token,
                instagram_account_id=account.platform_user_id,
                session_cookies=account.session_cookies,
            )
        elif platform_name == "fanvue":
            # Fanvue uses browser automation - session stored by persona ID
            adapter = PlatformRegistry.create_adapter(
                "fanvue",
                session_id=str(content.persona_id),
                headless=True,
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
        elif platform_name == "fanvue":
            # Fanvue uses browser automation with session cookies from database
            credentials = {
                "session_id": str(content.persona_id),
                "session_cookies": account.session_cookies,
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
        
        # Determine which media to use (video takes priority if available)
        has_video = content.video_urls and len(content.video_urls) > 0
        if has_video:
            media_paths = content.video_urls
            is_video = True
            logger.info("Posting video content", content_type=content.content_type.value if content.content_type else None, video_url=content.video_urls[0][:80] if content.video_urls else None)
        else:
            media_paths = content.media_urls if content.media_urls else None
            is_video = False
        
        # Post content
        result = await adapter.post_content(
            caption=content.caption,
            media_paths=media_paths,
            hashtags=content.hashtags,
            is_video=is_video,
            content_type=content.content_type,
        )
        
        if result.success:
            logger.info(
                "Content posted successfully",
                persona=persona.name,
                platform=platform_name,
                content_id=content_id,
                post_id=result.post_id,
            )
            
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
            platform=platform_name,
            error=str(e),
        )
        
        return {"success": False, "platform": platform_name, "error": str(e)}
    
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
        
        # Get delay settings from database
        min_delay = await get_rate_limit(db, "min_action_delay")
        max_delay = await get_rate_limit(db, "max_action_delay")
        
        for content in content_items:
            # Add random delay between posts (skip delay for first post)
            if content != content_items[0]:
                delay = random.randint(min_delay, max_delay)
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



