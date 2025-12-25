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
from app.models.settings import get_setting_value, DEFAULT_RATE_LIMIT_SETTINGS
from app.services.ai.content_generator import ContentGenerator
from app.services.platforms.registry import PlatformRegistry

logger = structlog.get_logger()
settings = get_settings()


async def get_rate_limit(db, key: str) -> int:
    """Get a rate limit setting from database."""
    return await get_setting_value(db, key, DEFAULT_RATE_LIMIT_SETTINGS.get(key, {}).get("value", 0))


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
            # Check if within engagement hours (in persona's timezone)
            try:
                import pytz
                persona_tz = pytz.timezone(persona.timezone or "UTC")
                current_time_in_tz = datetime.now(pytz.UTC).astimezone(persona_tz)
                current_hour = current_time_in_tz.hour
            except Exception:
                # Fallback to UTC if timezone parsing fails
                current_hour = datetime.utcnow().hour
            
            if not (persona.engagement_hours_start <= current_hour < persona.engagement_hours_end):
                logger.info(
                    "Outside engagement hours",
                    persona=persona.name,
                    current_hour=current_hour,
                    persona_timezone=persona.timezone,
                    hours_range=f"{persona.engagement_hours_start}-{persona.engagement_hours_end}",
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
    """Run engagement for a single persona across all enabled platforms."""
    from app.config import get_settings
    settings = get_settings()
    
    results = {"likes": 0, "comments": 0, "follows": 0, "platforms_engaged": []}
    
    # Get all connected platform accounts for this persona
    accounts_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == persona.id,
            PlatformAccount.is_connected == True,
        )
    )
    accounts = accounts_result.scalars().all()
    
    if not accounts:
        logger.warning("No connected accounts for engagement", persona=persona.name)
        return results
    
    # Process each platform independently
    for account in accounts:
        # Skip if engagement is paused for this platform
        if getattr(account, 'engagement_paused', False):
            logger.info(
                "Engagement paused for platform",
                persona=persona.name,
                platform=account.platform.value,
            )
            continue
        
        platform_name = account.platform.value
        adapter = None
        
        try:
            if account.platform == Platform.TWITTER:
                adapter = PlatformRegistry.create_adapter(
                    "twitter",
                    api_key=settings.twitter_api_key,
                    api_secret=settings.twitter_api_secret,
                    access_token=account.access_token,
                    access_token_secret=account.refresh_token,
                    bearer_token=settings.twitter_bearer_token,
                    session_cookies=account.session_cookies,
                )
                logger.info(
                    "Running Twitter engagement",
                    persona=persona.name,
                    has_cookies=account.session_cookies is not None,
                )
            elif account.platform == Platform.INSTAGRAM:
                adapter = PlatformRegistry.create_adapter(
                    "instagram",
                    access_token=account.access_token,
                    instagram_account_id=account.platform_user_id,
                    session_cookies=account.session_cookies,
                )
                logger.info("Running Instagram engagement", persona=persona.name)
            else:
                logger.info(
                    "Skipping unsupported platform for engagement",
                    platform=platform_name,
                )
                continue
            
            if not adapter:
                continue
            
            # Run engagement for this platform
            platform_results = await _engage_on_platform(
                db, persona, account, adapter, platform_name, settings
            )
            
            # Aggregate results
            results["likes"] += platform_results.get("likes", 0)
            results["comments"] += platform_results.get("comments", 0)
            results["follows"] += platform_results.get("follows", 0)
            results["platforms_engaged"].append(platform_name)
            
        except Exception as e:
            logger.error(
                "Error during platform engagement",
                persona=persona.name,
                platform=platform_name,
                error=str(e),
            )
            continue
    
    return results


async def _engage_on_platform(
    db: AsyncSession,
    persona: Persona,
    account: PlatformAccount,
    adapter,
    platform_name: str,
    settings,
) -> dict:
    """Run engagement on a specific platform."""
    results = {"likes": 0, "comments": 0, "follows": 0}
    
    try:
        # Authenticate based on platform
        credentials = {}
        if platform_name == "twitter":
            credentials = {
                "api_key": settings.twitter_api_key,
                "api_secret": settings.twitter_api_secret,
                "access_token": account.access_token,
                "access_token_secret": account.refresh_token,
            }
        elif platform_name == "instagram":
            if account.session_cookies:
                credentials["session_cookies"] = account.session_cookies
            if account.access_token:
                credentials["access_token"] = account.access_token
                credentials["instagram_account_id"] = account.platform_user_id
        
        if not await adapter.authenticate(credentials):
            logger.warning("Authentication failed", persona=persona.name, platform=platform_name)
            return results
        
        # Get content generator for AI analysis (optional - can skip for efficiency)
        content_generator = ContentGenerator()
        ai_provider = content_generator._get_provider(persona)
        
        # Pick ONE random hashtag from persona's niche to minimize API calls
        if not persona.niche:
            logger.warning("No niche hashtags configured", persona=persona.name)
            return results
        
        hashtag = random.choice(persona.niche)
        logger.info("Searching hashtag for engagement", persona=persona.name, hashtag=hashtag)
        
        # Limit to 5 posts to stay well under rate limits
        posts = await adapter.search_hashtag(hashtag, limit=5)
        
        if not posts:
            logger.info("No posts found for hashtag", hashtag=hashtag)
            return results
        
        # Get rate limits from database
        min_delay = await get_rate_limit(db, "min_action_delay")
        max_delay = await get_rate_limit(db, "max_action_delay")
        max_likes = await get_rate_limit(db, "max_likes_per_day")
        max_comments = await get_rate_limit(db, "max_comments_per_day")
        max_follows = await get_rate_limit(db, "max_follows_per_day")
        
        for post in posts:
            # Add human-like delay
            delay = random.randint(min_delay, max_delay)
            await asyncio.sleep(delay)
            
            # Check rate limits
            if persona.likes_today >= max_likes:
                break
            
            # Score post relevance - use keyword matching with stricter thresholds
            # The post was found via hashtag search, but we need to verify it's actually relevant
            post_text = (post.content or "").lower()
            niche_keywords = [n.lower() for n in persona.niche]
            
            # Count keyword matches in the caption text
            matches = sum(1 for keyword in niche_keywords if keyword in post_text)
            
            # Calculate relevance score more strictly:
            # - Base score from keyword matches (0.2 per keyword match, max 0.6)
            # - Bonus for multiple matches
            # - Posts with no caption text get a lower score
            if not post_text.strip():
                # Empty captions are less likely to be quality content
                relevance_score = 0.4
            elif matches == 0:
                # Post found via hashtag but no keywords in caption
                # This is common for reels where hashtags are in a separate field
                # Give it a baseline score since it matched the hashtag search
                relevance_score = 0.5
            elif matches == 1:
                # Single keyword match - moderate relevance
                relevance_score = 0.65
            elif matches == 2:
                # Two keyword matches - good relevance
                relevance_score = 0.8
            else:
                # Multiple matches - high relevance
                relevance_score = 0.95
            
            # Log with more detail to help debug relevance
            logger.debug(
                "Post relevance scored",
                post_id=post.id,
                matches=matches,
                relevance=relevance_score,
                caption_length=len(post_text),
                caption_preview=post_text[:100] if post_text else "(empty)",
            )
            
            # Like if relevant enough
            if relevance_score >= 0.6:
                try:
                    # Use post.url if available (contains proper permalink with shortcode)
                    # Fall back to post.id only for platforms where ID works directly
                    post_identifier = post.url if post.url else post.id
                    if await adapter.like_post(post_identifier):
                        persona.likes_today += 1
                        results["likes"] += 1
                        
                        # Try to get the author username if not already available
                        target_username = post.author_username
                        if not target_username and hasattr(adapter, 'get_post_author'):
                            try:
                                target_username = await adapter.get_post_author()
                                if target_username:
                                    # Update the post object so comments/follows can use it too
                                    post.author_username = target_username
                            except Exception:
                                pass
                        
                        # Log engagement
                        engagement = Engagement(
                            persona_id=persona.id,
                            platform=platform_name,
                            engagement_type=EngagementType.LIKE,
                            target_post_id=post.id,
                            target_username=target_username,
                            target_url=post.url,
                            relevance_score=relevance_score,
                            trigger_hashtag=hashtag,
                        )
                        db.add(engagement)
                        
                        # Commit immediately after each successful like to prevent rollback
                        await db.commit()
                        
                        logger.info(
                            "Liked post",
                            persona=persona.name,
                            post_id=post.id,
                            target_username=target_username,
                            relevance=relevance_score,
                        )
                except Exception as like_error:
                    logger.error("Like action failed", post_id=post.id, error=str(like_error))
            
            # Comment on relevant posts
            if (
                relevance_score >= 0.6
                and persona.comments_today < max_comments
                and random.random() < 0.5  # 50% chance to comment on relevant posts
            ):
                try:
                    # Generate contextual comment
                    comment_text = await content_generator.generate_comment(
                        persona,
                        post.content or "",
                        post.author_username,
                    )
                    
                    # Use post.url if available (contains proper permalink)
                    post_identifier = post.url if post.url else post.id
                    comment_id = await adapter.comment(post_identifier, comment_text, author_username=post.author_username)
                    
                    if comment_id:
                        persona.comments_today += 1
                        results["comments"] += 1
                        
                        engagement = Engagement(
                            persona_id=persona.id,
                            platform=platform_name,
                            engagement_type=EngagementType.COMMENT,
                            target_post_id=post.id,
                            target_username=post.author_username,
                            target_url=post.url,
                            comment_text=comment_text,
                            relevance_score=relevance_score,
                            trigger_hashtag=hashtag,
                        )
                        db.add(engagement)
                        
                        # Commit immediately after each successful comment
                        await db.commit()
                        
                        logger.info(
                            "Commented on post",
                            persona=persona.name,
                            post_id=post.id,
                        )
                except Exception as comment_error:
                    logger.error("Comment action failed", post_id=post.id, error=str(comment_error))
            
            # Follow relevant users
            if (
                relevance_score >= 0.6
                and persona.follows_today < max_follows
                and post.author_username
                and random.random() < 0.4  # 40% chance to follow relevant users
            ):
                try:
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
                            
                            # Determine profile URL based on platform
                            if platform_name == "twitter":
                                profile_url = f"https://twitter.com/{post.author_username}"
                            else:
                                profile_url = f"https://instagram.com/{post.author_username}"
                            
                            engagement = Engagement(
                                persona_id=persona.id,
                                platform=platform_name,
                                engagement_type=EngagementType.FOLLOW,
                                target_user_id=post.author_id,
                                target_username=post.author_username,
                                target_url=profile_url,
                                relevance_score=relevance_score,
                                trigger_hashtag=hashtag,
                            )
                            db.add(engagement)
                            
                            # Commit immediately after each successful follow
                            await db.commit()
                            
                            logger.info(
                                "Followed user",
                                persona=persona.name,
                                username=post.author_username,
                                relevance=relevance_score,
                            )
                except Exception as follow_error:
                    logger.error("Follow action failed", username=post.author_username, error=str(follow_error))
        
        # Final commit for any persona updates (daily counters)
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
    from app.config import get_settings
    app_settings = get_settings()
    
    results = {"liked": 0, "errors": 0}
    
    async with async_session_maker() as db:
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona or not persona.is_active:
            return {"success": False, "error": "Persona not available"}
        
        max_likes = await get_rate_limit(db, "max_likes_per_day")
        if persona.likes_today >= max_likes:
            return {"success": False, "error": "Rate limit reached"}
        
        # Try Twitter first, then Instagram
        adapter = None
        platform_name = None
        
        # Try Twitter
        twitter_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.platform == Platform.TWITTER,
                PlatformAccount.is_connected == True,
            )
        )
        twitter_account = twitter_result.scalar_one_or_none()
        
        if twitter_account:
            platform_name = "twitter"
            adapter = PlatformRegistry.create_adapter(
                "twitter",
                api_key=app_settings.twitter_api_key,
                api_secret=app_settings.twitter_api_secret,
                access_token=twitter_account.access_token,
                access_token_secret=twitter_account.refresh_token,
                bearer_token=app_settings.twitter_bearer_token,
                session_cookies=twitter_account.session_cookies,  # For browser fallback
            )
        else:
            # Fall back to Instagram
            ig_result = await db.execute(
                select(PlatformAccount).where(
                    PlatformAccount.persona_id == persona.id,
                    PlatformAccount.platform == Platform.INSTAGRAM,
                    PlatformAccount.is_connected == True,
                )
            )
            ig_account = ig_result.scalar_one_or_none()
            
            if ig_account:
                platform_name = "instagram"
                adapter = PlatformRegistry.create_adapter(
                    "instagram",
                    session_cookies=ig_account.session_cookies,
                )
        
        if not adapter:
            return {"success": False, "error": "No connected account or adapter creation failed"}
        
        account = twitter_account or ig_account
        
        try:
            # Authenticate based on platform
            if platform_name == "twitter":
                await adapter.authenticate({
                    "api_key": app_settings.twitter_api_key,
                    "api_secret": app_settings.twitter_api_secret,
                    "access_token": account.access_token,
                    "access_token_secret": account.refresh_token,
                })
            else:
                await adapter.authenticate({"session_cookies": account.session_cookies})
            
            liked = 0
            # Only use ONE hashtag to avoid rate limits (pick first one)
            hashtag = hashtags[0] if hashtags else None
            
            if not hashtag:
                return {"success": False, "error": "No hashtags provided"}
            
            logger.info("Searching for posts", hashtag=hashtag, limit=limit)
            posts = await adapter.search_hashtag(hashtag, limit=limit)
            
            logger.info("Found posts to like", count=len(posts), hashtag=hashtag)
            
            # Filter posts to ensure they're actually relevant to the hashtag
            hashtag_lower = hashtag.lower().replace("#", "")
            relevant_posts = []
            for post in posts:
                content = (post.content or "").lower()
                # Check if the hashtag or related keyword is in the tweet
                if hashtag_lower in content or f"#{hashtag_lower}" in content:
                    relevant_posts.append(post)
                    logger.info("Post is relevant", post_id=post.id, preview=content[:100])
                else:
                    logger.info("Skipping irrelevant post", post_id=post.id, hashtag=hashtag, preview=content[:100])
            
            logger.info("Relevant posts after filtering", count=len(relevant_posts), total=len(posts))
            
            for post in relevant_posts:
                if liked >= limit or persona.likes_today >= max_likes:
                    logger.info("Stopping - limit reached", liked=liked, daily_limit=persona.likes_today, max_likes=max_likes)
                    break
                
                # Random delay between likes (shorter for manual trigger)
                delay = random.randint(5, 15)
                logger.info("Waiting before like", delay=delay)
                await asyncio.sleep(delay)
                
                # Try to get author username for browser fallback
                author_username = getattr(post, 'author_username', None)
                
                # Use post.url if available (contains proper permalink)
                post_identifier = post.url if post.url else post.id
                if await adapter.like_post(post_identifier, author_username):
                    liked += 1
                    persona.likes_today += 1
                    
                    engagement = Engagement(
                        persona_id=persona.id,
                        platform=platform_name,
                        engagement_type=EngagementType.LIKE,
                        target_post_id=post.id,
                        target_url=post.url,
                        trigger_hashtag=hashtag,
                    )
                    db.add(engagement)
                    logger.info("Liked post", persona=persona.name, platform=platform_name, post_id=post.id, content_preview=(post.content or "")[:80])
                else:
                    logger.warning("Failed to like post", post_id=post.id)
            
            results["liked"] = liked
            
            # Check if session was found to be invalid and clear cookies
            if hasattr(adapter, 'session_needs_refresh') and adapter.session_needs_refresh:
                logger.warning("Clearing invalid session cookies for account", account_id=str(account.id))
                account.session_cookies = None
            
            await db.commit()
            
        except Exception as e:
            logger.error("Like posts failed", platform=platform_name, error=str(e))
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
    from app.config import get_settings
    app_settings = get_settings()
    
    results = {"followed": 0, "skipped": 0, "errors": 0}
    
    async with async_session_maker() as db:
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona or not persona.is_active:
            return {"success": False, "error": "Persona not available"}
        
        max_follows = await get_rate_limit(db, "max_follows_per_day")
        if persona.follows_today >= max_follows:
            return {"success": False, "error": "Follow rate limit reached"}
        
        # Try Twitter first, then Instagram
        adapter = None
        platform_name = None
        account = None
        
        # Try Twitter
        twitter_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.platform == Platform.TWITTER,
                PlatformAccount.is_connected == True,
            )
        )
        twitter_account = twitter_result.scalar_one_or_none()
        
        if twitter_account:
            account = twitter_account
            platform_name = "twitter"
            adapter = PlatformRegistry.create_adapter(
                "twitter",
                api_key=app_settings.twitter_api_key,
                api_secret=app_settings.twitter_api_secret,
                access_token=account.access_token,
                access_token_secret=account.refresh_token,
                bearer_token=app_settings.twitter_bearer_token,
                session_cookies=account.session_cookies,  # For browser fallback
            )
        else:
            # Fall back to Instagram
            ig_result = await db.execute(
                select(PlatformAccount).where(
                    PlatformAccount.persona_id == persona.id,
                    PlatformAccount.platform == Platform.INSTAGRAM,
                    PlatformAccount.is_connected == True,
                )
            )
            ig_account = ig_result.scalar_one_or_none()
            
            if ig_account:
                account = ig_account
                platform_name = "instagram"
                adapter = PlatformRegistry.create_adapter(
                    "instagram",
                    session_cookies=account.session_cookies,
                )
        
        if not adapter:
            return {"success": False, "error": "No connected account or adapter creation failed"}
        
        try:
            # Authenticate based on platform
            if platform_name == "twitter":
                await adapter.authenticate({
                    "api_key": app_settings.twitter_api_key,
                    "api_secret": app_settings.twitter_api_secret,
                    "access_token": account.access_token,
                    "access_token_secret": account.refresh_token,
                })
            else:
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
                if followed >= limit or persona.follows_today >= max_follows:
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
                    
                    # Determine profile URL based on platform
                    if platform_name == "twitter":
                        profile_url = f"https://twitter.com/{username}"
                    else:
                        profile_url = f"https://instagram.com/{username}"
                    
                    engagement = Engagement(
                        persona_id=persona.id,
                        platform=platform_name,
                        engagement_type=EngagementType.FOLLOW,
                        target_username=username,
                        target_url=profile_url,
                    )
                    db.add(engagement)
                    
                    logger.info(
                        "Followed user",
                        persona=persona.name,
                        platform=platform_name,
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
    from app.config import get_settings
    app_settings = get_settings()
    
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
        
        # Try Twitter first, then Instagram
        adapter = None
        platform_name = None
        account = None
        
        # Try Twitter
        twitter_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.platform == Platform.TWITTER,
                PlatformAccount.is_connected == True,
            )
        )
        twitter_account = twitter_result.scalar_one_or_none()
        
        if twitter_account:
            account = twitter_account
            platform_name = "twitter"
            adapter = PlatformRegistry.create_adapter(
                "twitter",
                api_key=app_settings.twitter_api_key,
                api_secret=app_settings.twitter_api_secret,
                access_token=account.access_token,
                access_token_secret=account.refresh_token,
                bearer_token=app_settings.twitter_bearer_token,
                session_cookies=account.session_cookies,  # For browser fallback
            )
        else:
            # Fall back to Instagram
            ig_result = await db.execute(
                select(PlatformAccount).where(
                    PlatformAccount.persona_id == persona.id,
                    PlatformAccount.platform == Platform.INSTAGRAM,
                    PlatformAccount.is_connected == True,
                )
            )
            ig_account = ig_result.scalar_one_or_none()
            
            if ig_account:
                account = ig_account
                platform_name = "instagram"
                adapter = PlatformRegistry.create_adapter(
                    "instagram",
                    session_cookies=account.session_cookies,
                )
        
        if not adapter:
            return {"success": False, "error": "No connected account or adapter creation failed"}
        
        try:
            # Authenticate based on platform
            if platform_name == "twitter":
                await adapter.authenticate({
                    "api_key": app_settings.twitter_api_key,
                    "api_secret": app_settings.twitter_api_secret,
                    "access_token": account.access_token,
                    "access_token_secret": account.refresh_token,
                })
            else:
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
                    
                    # Determine profile URL based on platform
                    if platform_name == "twitter":
                        profile_url = f"https://twitter.com/{username}"
                    else:
                        profile_url = f"https://instagram.com/{username}"
                    
                    # Log the unfollow
                    unfollow_engagement = Engagement(
                        persona_id=persona.id,
                        platform=platform_name,
                        engagement_type=EngagementType.UNFOLLOW,
                        target_username=username,
                        target_url=profile_url,
                    )
                    db.add(unfollow_engagement)
                    
                    logger.info(
                        "Unfollowed user",
                        persona=persona.name,
                        platform=platform_name,
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

