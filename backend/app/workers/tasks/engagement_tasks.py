"""Engagement automation tasks."""

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
from app.models.engagement import Engagement, EngagementType
from app.models.platform_account import PlatformAccount, Platform
from app.services.ai.content_generator import ContentGenerator
from app.services.platforms.registry import PlatformRegistry

logger = structlog.get_logger()
settings = get_settings()


def run_async(coro):
    """Run async code in sync context."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@shared_task(name="app.workers.tasks.engagement_tasks.run_engagement_cycle")
def run_engagement_cycle() -> dict:
    """Run engagement cycle for all active personas.
    
    Returns:
        Dictionary with engagement results
    """
    return run_async(_run_engagement_cycle())


async def _run_engagement_cycle() -> dict:
    """Async implementation of engagement cycle."""
    results = {"personas_processed": 0, "likes": 0, "comments": 0, "follows": 0, "errors": 0}
    
    async with async_session_maker() as db:
        # Get active personas
        result = await db.execute(
            select(Persona).where(Persona.is_active == True)
        )
        personas = result.scalars().all()
        
        for persona in personas:
            # Check if within engagement hours
            current_hour = datetime.utcnow().hour
            if not (persona.engagement_hours_start <= current_hour < persona.engagement_hours_end):
                logger.info(
                    "Outside engagement hours",
                    persona=persona.name,
                    current_hour=current_hour,
                )
                continue
            
            try:
                persona_results = await _engage_for_persona(db, persona)
                results["personas_processed"] += 1
                results["likes"] += persona_results.get("likes", 0)
                results["comments"] += persona_results.get("comments", 0)
                results["follows"] += persona_results.get("follows", 0)
                
            except Exception as e:
                logger.error(
                    "Engagement cycle error",
                    persona=persona.name,
                    error=str(e),
                )
                results["errors"] += 1
    
    logger.info("Engagement cycle complete", results=results)
    return results


async def _engage_for_persona(db: AsyncSession, persona: Persona) -> dict:
    """Run engagement for a single persona."""
    results = {"likes": 0, "comments": 0, "follows": 0}
    
    # Get platform account
    account_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona.id,
            PlatformAccount.platform == Platform.INSTAGRAM,
            PlatformAccount.is_connected == True,
        )
    )
    account = account_result.scalar_one_or_none()
    
    if not account:
        logger.warning("No connected account", persona=persona.name)
        return results
    
    # Create adapter
    adapter = PlatformRegistry.create_adapter(
        "instagram",
        access_token=account.access_token,
        instagram_account_id=account.platform_user_id,
        session_cookies=account.session_cookies,
    )
    
    if not adapter:
        logger.error("Failed to create adapter", persona=persona.name)
        return results
    
    try:
        # Authenticate
        credentials = {}
        if account.session_cookies:
            credentials["session_cookies"] = account.session_cookies
        if account.access_token:
            credentials["access_token"] = account.access_token
            credentials["instagram_account_id"] = account.platform_user_id
        
        if not await adapter.authenticate(credentials):
            logger.warning("Authentication failed", persona=persona.name)
            return results
        
        # Get content generator for AI analysis
        content_generator = ContentGenerator()
        ai_provider = content_generator._get_provider(persona)
        
        # Search posts by persona's niche hashtags
        for hashtag in persona.niche[:3]:  # Limit to 3 hashtags per cycle
            if persona.likes_today >= settings.max_likes_per_day:
                break
            
            posts = await adapter.search_hashtag(hashtag, limit=10)
            
            for post in posts:
                # Add human-like delay
                delay = random.randint(
                    settings.min_action_delay,
                    settings.max_action_delay,
                )
                await asyncio.sleep(delay)
                
                # Check rate limits
                if persona.likes_today >= settings.max_likes_per_day:
                    break
                
                # Score post relevance
                relevance_score = await ai_provider.score_relevance(
                    post.content or "",
                    persona.niche,
                )
                
                # Like if relevant enough
                if relevance_score >= 0.6:
                    if await adapter.like_post(post.id):
                        persona.likes_today += 1
                        results["likes"] += 1
                        
                        # Log engagement
                        engagement = Engagement(
                            persona_id=persona.id,
                            platform="instagram",
                            engagement_type=EngagementType.LIKE,
                            target_post_id=post.id,
                            target_username=post.author_username,
                            target_url=post.url,
                            relevance_score=relevance_score,
                            trigger_hashtag=hashtag,
                        )
                        db.add(engagement)
                        
                        logger.info(
                            "Liked post",
                            persona=persona.name,
                            post_id=post.id,
                            relevance=relevance_score,
                        )
                
                # Comment on highly relevant posts
                if (
                    relevance_score >= 0.8
                    and persona.comments_today < settings.max_comments_per_day
                    and random.random() < 0.3  # 30% chance to comment
                ):
                    # Generate contextual comment
                    comment_text = await content_generator.generate_comment(
                        persona,
                        post.content or "",
                        post.author_username,
                    )
                    
                    comment_id = await adapter.comment(post.id, comment_text)
                    
                    if comment_id:
                        persona.comments_today += 1
                        results["comments"] += 1
                        
                        engagement = Engagement(
                            persona_id=persona.id,
                            platform="instagram",
                            engagement_type=EngagementType.COMMENT,
                            target_post_id=post.id,
                            target_username=post.author_username,
                            target_url=post.url,
                            comment_text=comment_text,
                            relevance_score=relevance_score,
                            trigger_hashtag=hashtag,
                        )
                        db.add(engagement)
                        
                        logger.info(
                            "Commented on post",
                            persona=persona.name,
                            post_id=post.id,
                        )
                
                # Follow highly relevant users occasionally
                if (
                    relevance_score >= 0.75
                    and persona.follows_today < settings.max_follows_per_day
                    and post.author_username
                    and random.random() < 0.15  # 15% chance to follow
                ):
                    # Check if we've already followed this user recently
                    existing_follow = await db.execute(
                        select(Engagement).where(
                            Engagement.persona_id == persona.id,
                            Engagement.target_username == post.author_username,
                            Engagement.engagement_type == EngagementType.FOLLOW,
                        )
                    )
                    already_followed = existing_follow.scalar_one_or_none()
                    
                    if not already_followed:
                        # Add delay before follow
                        await asyncio.sleep(random.randint(10, 30))
                        
                        if await adapter.follow_user(post.author_username):
                            persona.follows_today += 1
                            results["follows"] += 1
                            
                            engagement = Engagement(
                                persona_id=persona.id,
                                platform="instagram",
                                engagement_type=EngagementType.FOLLOW,
                                target_user_id=post.author_id,
                                target_username=post.author_username,
                                target_url=f"https://instagram.com/{post.author_username}",
                                relevance_score=relevance_score,
                                trigger_hashtag=hashtag,
                            )
                            db.add(engagement)
                            
                            logger.info(
                                "Followed user",
                                persona=persona.name,
                                username=post.author_username,
                                relevance=relevance_score,
                            )
        
        await db.commit()
        
    finally:
        await adapter.close()
    
    return results


@shared_task(name="app.workers.tasks.engagement_tasks.like_posts")
def like_posts(persona_id: str, hashtags: list, limit: int = 10) -> dict:
    """Like posts for a specific persona.
    
    Args:
        persona_id: UUID of the persona
        hashtags: Hashtags to search for
        limit: Maximum posts to like
        
    Returns:
        Dictionary with results
    """
    return run_async(_like_posts(persona_id, hashtags, limit))


async def _like_posts(persona_id: str, hashtags: list, limit: int = 10) -> dict:
    """Async implementation of like posts."""
    results = {"liked": 0, "errors": 0}
    
    async with async_session_maker() as db:
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona or not persona.is_active:
            return {"success": False, "error": "Persona not available"}
        
        if persona.likes_today >= settings.max_likes_per_day:
            return {"success": False, "error": "Rate limit reached"}
        
        # Get account
        account_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.is_connected == True,
            )
        )
        account = account_result.scalar_one_or_none()
        
        if not account:
            return {"success": False, "error": "No connected account"}
        
        adapter = PlatformRegistry.create_adapter(
            "instagram",
            session_cookies=account.session_cookies,
        )
        
        if not adapter:
            return {"success": False, "error": "Adapter creation failed"}
        
        try:
            await adapter.authenticate({"session_cookies": account.session_cookies})
            
            liked = 0
            for hashtag in hashtags:
                posts = await adapter.search_hashtag(hashtag, limit=limit)
                
                for post in posts:
                    if liked >= limit or persona.likes_today >= settings.max_likes_per_day:
                        break
                    
                    # Random delay
                    await asyncio.sleep(random.randint(30, 120))
                    
                    if await adapter.like_post(post.id):
                        liked += 1
                        persona.likes_today += 1
                        
                        engagement = Engagement(
                            persona_id=persona.id,
                            platform="instagram",
                            engagement_type=EngagementType.LIKE,
                            target_post_id=post.id,
                            target_url=post.url,
                            trigger_hashtag=hashtag,
                        )
                        db.add(engagement)
            
            results["liked"] = liked
            await db.commit()
            
        except Exception as e:
            logger.error("Like posts failed", error=str(e))
            results["errors"] += 1
            
        finally:
            await adapter.close()
    
    return results


@shared_task(name="app.workers.tasks.engagement_tasks.follow_users")
def follow_users(persona_id: str, usernames: list = None, hashtags: list = None, limit: int = 5) -> dict:
    """Follow users for a specific persona.
    
    Args:
        persona_id: UUID of the persona
        usernames: Optional list of specific usernames to follow
        hashtags: Optional hashtags to find users from
        limit: Maximum users to follow
        
    Returns:
        Dictionary with results
    """
    return run_async(_follow_users(persona_id, usernames, hashtags, limit))


async def _follow_users(
    persona_id: str,
    usernames: list = None,
    hashtags: list = None,
    limit: int = 5,
) -> dict:
    """Async implementation of follow users."""
    results = {"followed": 0, "skipped": 0, "errors": 0}
    
    async with async_session_maker() as db:
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona or not persona.is_active:
            return {"success": False, "error": "Persona not available"}
        
        if persona.follows_today >= settings.max_follows_per_day:
            return {"success": False, "error": "Follow rate limit reached"}
        
        # Get account
        account_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.is_connected == True,
            )
        )
        account = account_result.scalar_one_or_none()
        
        if not account:
            return {"success": False, "error": "No connected account"}
        
        adapter = PlatformRegistry.create_adapter(
            "instagram",
            session_cookies=account.session_cookies,
        )
        
        if not adapter:
            return {"success": False, "error": "Adapter creation failed"}
        
        try:
            await adapter.authenticate({"session_cookies": account.session_cookies})
            
            users_to_follow = []
            
            # If specific usernames provided, use those
            if usernames:
                users_to_follow = usernames[:limit]
            # Otherwise find users from hashtags
            elif hashtags:
                for hashtag in hashtags:
                    posts = await adapter.search_hashtag(hashtag, limit=20)
                    for post in posts:
                        if post.author_username and post.author_username not in users_to_follow:
                            users_to_follow.append(post.author_username)
                            if len(users_to_follow) >= limit * 2:  # Get extra in case some fail
                                break
                    if len(users_to_follow) >= limit * 2:
                        break
            
            followed = 0
            for username in users_to_follow:
                if followed >= limit or persona.follows_today >= settings.max_follows_per_day:
                    break
                
                # Check if already followed
                existing = await db.execute(
                    select(Engagement).where(
                        Engagement.persona_id == persona.id,
                        Engagement.target_username == username,
                        Engagement.engagement_type == EngagementType.FOLLOW,
                    )
                )
                if existing.scalar_one_or_none():
                    results["skipped"] += 1
                    continue
                
                # Random delay
                await asyncio.sleep(random.randint(30, 90))
                
                if await adapter.follow_user(username):
                    followed += 1
                    persona.follows_today += 1
                    
                    engagement = Engagement(
                        persona_id=persona.id,
                        platform="instagram",
                        engagement_type=EngagementType.FOLLOW,
                        target_username=username,
                        target_url=f"https://instagram.com/{username}",
                    )
                    db.add(engagement)
                    
                    logger.info(
                        "Followed user",
                        persona=persona.name,
                        username=username,
                    )
                else:
                    results["errors"] += 1
            
            results["followed"] = followed
            await db.commit()
            
        except Exception as e:
            logger.error("Follow users failed", error=str(e))
            results["errors"] += 1
            
        finally:
            await adapter.close()
    
    return results


@shared_task(name="app.workers.tasks.engagement_tasks.unfollow_non_followers")
def unfollow_non_followers(persona_id: str, limit: int = 10) -> dict:
    """Unfollow users who don't follow back (housekeeping).
    
    This helps maintain a healthy follower/following ratio.
    
    Args:
        persona_id: UUID of the persona
        limit: Maximum users to unfollow
        
    Returns:
        Dictionary with results
    """
    return run_async(_unfollow_non_followers(persona_id, limit))


async def _unfollow_non_followers(persona_id: str, limit: int = 10) -> dict:
    """Async implementation of unfollow non-followers."""
    results = {"unfollowed": 0, "errors": 0}
    
    async with async_session_maker() as db:
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona or not persona.is_active:
            return {"success": False, "error": "Persona not available"}
        
        # Get old follows (followed more than 3 days ago)
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=3)
        
        old_follows_result = await db.execute(
            select(Engagement).where(
                Engagement.persona_id == persona.id,
                Engagement.engagement_type == EngagementType.FOLLOW,
                Engagement.created_at < cutoff_date,
            ).order_by(Engagement.created_at.asc()).limit(limit * 2)
        )
        old_follows = old_follows_result.scalars().all()
        
        if not old_follows:
            return {"success": True, "unfollowed": 0, "message": "No old follows to clean up"}
        
        # Get account
        account_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.is_connected == True,
            )
        )
        account = account_result.scalar_one_or_none()
        
        if not account:
            return {"success": False, "error": "No connected account"}
        
        adapter = PlatformRegistry.create_adapter(
            "instagram",
            session_cookies=account.session_cookies,
        )
        
        if not adapter:
            return {"success": False, "error": "Adapter creation failed"}
        
        try:
            await adapter.authenticate({"session_cookies": account.session_cookies})
            
            unfollowed = 0
            for follow_record in old_follows:
                if unfollowed >= limit:
                    break
                
                username = follow_record.target_username
                if not username:
                    continue
                
                # Random delay
                await asyncio.sleep(random.randint(30, 60))
                
                # Try to unfollow
                if await adapter.unfollow_user(username):
                    unfollowed += 1
                    
                    # Log the unfollow
                    unfollow_engagement = Engagement(
                        persona_id=persona.id,
                        platform="instagram",
                        engagement_type=EngagementType.UNFOLLOW,
                        target_username=username,
                        target_url=f"https://instagram.com/{username}",
                    )
                    db.add(unfollow_engagement)
                    
                    logger.info(
                        "Unfollowed user",
                        persona=persona.name,
                        username=username,
                    )
                else:
                    results["errors"] += 1
            
            results["unfollowed"] = unfollowed
            await db.commit()
            
        except Exception as e:
            logger.error("Unfollow failed", error=str(e))
            results["errors"] += 1
            
        finally:
            await adapter.close()
    
    return results


@shared_task(name="app.workers.tasks.engagement_tasks.reset_daily_limits")
def reset_daily_limits() -> dict:
    """Reset daily rate limits for all personas.
    
    Returns:
        Dictionary with reset count
    """
    return run_async(_reset_daily_limits())


async def _reset_daily_limits() -> dict:
    """Async implementation of daily limit reset."""
    async with async_session_maker() as db:
        result = await db.execute(select(Persona))
        personas = result.scalars().all()
        
        for persona in personas:
            persona.reset_daily_limits()
        
        await db.commit()
        
        logger.info("Daily limits reset", count=len(personas))
        return {"reset_count": len(personas)}


@shared_task(name="app.workers.tasks.engagement_tasks.sync_analytics")
def sync_analytics() -> dict:
    """Sync analytics from platforms for all personas.
    
    Returns:
        Dictionary with sync results
    """
    return run_async(_sync_analytics())


async def _sync_analytics() -> dict:
    """Async implementation of analytics sync."""
    results = {"synced": 0, "errors": 0}
    
    async with async_session_maker() as db:
        result = await db.execute(
            select(Persona).where(Persona.is_active == True)
        )
        personas = result.scalars().all()
        
        for persona in personas:
            try:
                # Get platform account
                account_result = await db.execute(
                    select(PlatformAccount).where(
                        PlatformAccount.persona_id == persona.id,
                        PlatformAccount.is_connected == True,
                    )
                )
                account = account_result.scalar_one_or_none()
                
                if not account:
                    continue
                
                adapter = PlatformRegistry.create_adapter(
                    "instagram",
                    access_token=account.access_token,
                    instagram_account_id=account.platform_user_id,
                    session_cookies=account.session_cookies,
                )
                
                if adapter:
                    await adapter.authenticate({
                        "access_token": account.access_token,
                        "instagram_account_id": account.platform_user_id,
                        "session_cookies": account.session_cookies,
                    })
                    
                    analytics = await adapter.get_analytics()
                    
                    persona.follower_count = analytics.follower_count
                    persona.following_count = analytics.following_count
                    
                    account.last_sync_at = datetime.utcnow()
                    
                    results["synced"] += 1
                    
                    await adapter.close()
                    
            except Exception as e:
                logger.error(
                    "Analytics sync failed",
                    persona=persona.name,
                    error=str(e),
                )
                results["errors"] += 1
        
        await db.commit()
    
    logger.info("Analytics sync complete", results=results)
    return results

