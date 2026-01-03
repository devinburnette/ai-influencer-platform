"""Content generation and management tasks."""

import asyncio
from typing import Optional
from uuid import UUID

import structlog
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.models.persona import Persona
from app.models.content import Content, ContentStatus, ContentType
from app.models.settings import get_setting_value, DEFAULT_RATE_LIMIT_SETTINGS
from app.services.ai.content_generator import ContentGenerator

logger = structlog.get_logger()


async def get_content_type_limit(db: AsyncSession, key: str) -> int:
    """Get a content type limit setting from database."""
    return await get_setting_value(db, key, DEFAULT_RATE_LIMIT_SETTINGS.get(key, {}).get("value", 0))


def run_async(coro):
    """Run async code in sync context."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


@shared_task(name="app.workers.tasks.content_tasks.generate_content_for_persona")
def generate_content_for_persona(
    persona_id: str,
    topic: Optional[str] = None,
) -> dict:
    """Generate content for a specific persona.
    
    Args:
        persona_id: UUID of the persona
        topic: Optional specific topic to generate about
        
    Returns:
        Dictionary with generation result
    """
    return run_async(_generate_content_for_persona(persona_id, topic))


async def _generate_content_for_persona(
    persona_id: str,
    topic: Optional[str] = None,
    generate_image: bool = True,
) -> dict:
    """Async implementation of content generation."""
    from app.services.image.higgsfield import HiggsfieldImageGenerator
    
    async with async_session_maker() as db:
        # Get persona
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            logger.error("Persona not found", persona_id=persona_id)
            return {"success": False, "error": "Persona not found"}
        
        if not persona.is_active:
            logger.info("Persona is paused, skipping", persona_id=persona_id)
            return {"success": False, "error": "Persona is paused"}
        
        try:
            # Generate content
            generator = ContentGenerator()
            generated = await generator.generate_post(persona, topic=topic)
            
            # Generate image if configured
            media_urls = []
            if generate_image:
                try:
                    character_id = persona.higgsfield_character_id
                    image_generator = HiggsfieldImageGenerator(character_id=character_id)
                    
                    if image_generator.is_configured:
                        logger.info(
                            "Generating image with Higgsfield",
                            persona=persona.name,
                            character_id=character_id,
                        )
                        
                        image_result = await image_generator.generate_for_content(
                            caption=generated["caption"],
                            character_id=character_id,
                            persona_name=persona.name,
                            persona_niche=persona.niche,
                            image_prompt_template=persona.image_prompt_template,
                        )
                        
                        if image_result["success"] and image_result["image_url"]:
                            media_urls.append(image_result["image_url"])
                            logger.info(
                                "Image generated successfully",
                                image_url=image_result["image_url"][:50] + "...",
                            )
                        else:
                            logger.warning(
                                "Image generation failed",
                                error=image_result.get("error"),
                            )
                        
                        await image_generator.close()
                    else:
                        logger.info("Higgsfield not configured, skipping image generation")
                except Exception as e:
                    logger.error("Image generation error", error=str(e))
                    # Continue without image
            
            # Determine initial status
            status = (
                ContentStatus.SCHEDULED
                if persona.auto_approve_content
                else ContentStatus.PENDING_REVIEW
            )
            
            # Create content record
            content = Content(
                persona_id=persona.id,
                caption=generated["caption"],
                hashtags=generated.get("hashtags", []),
                media_urls=media_urls,
                auto_generated=True,
                status=status,
            )
            
            db.add(content)
            await db.commit()
            await db.refresh(content)
            
            logger.info(
                "Content generated",
                persona=persona.name,
                content_id=str(content.id),
                status=status.value,
                has_image=len(media_urls) > 0,
            )
            
            return {
                "success": True,
                "content_id": str(content.id),
                "status": status.value,
                "has_image": len(media_urls) > 0,
            }
            
        except Exception as e:
            logger.error(
                "Content generation failed",
                persona_id=persona_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}


@shared_task(name="app.workers.tasks.content_tasks.generate_content_batch")
def generate_content_batch() -> dict:
    """Generate content for all active personas that need it.
    
    Returns:
        Dictionary with batch results
    """
    return run_async(_generate_content_batch())


async def _generate_content_batch() -> dict:
    """Async implementation of batch content generation."""
    results = {"generated": 0, "skipped": 0, "errors": 0}
    
    async with async_session_maker() as db:
        # Get max posts per day limit
        max_posts = await get_content_type_limit(db, "max_posts_per_day")
        
        # Get active personas
        result = await db.execute(
            select(Persona).where(Persona.is_active == True)
        )
        personas = result.scalars().all()
        
        for persona in personas:
            # Check daily post limit
            if persona.posts_today >= max_posts:
                logger.info(
                    "Daily image post limit reached",
                    persona=persona.name,
                    posts_today=persona.posts_today,
                    limit=max_posts,
                )
                results["skipped"] += 1
                continue
            
            # Check if persona needs POST content (only count POSTs, not reels/stories)
            pending_result = await db.execute(
                select(Content)
                .where(
                    Content.persona_id == persona.id,
                    Content.content_type == ContentType.POST,
                    Content.status.in_([
                        ContentStatus.PENDING_REVIEW,
                        ContentStatus.SCHEDULED,
                    ]),
                )
            )
            pending_count = len(pending_result.scalars().all())
            
            # Skip if enough POST content in queue
            if pending_count >= 5:
                logger.info(
                    "Enough POST content in queue",
                    persona=persona.name,
                    pending=pending_count,
                )
                results["skipped"] += 1
                continue
            
            try:
                # Generate new content
                generator = ContentGenerator()
                generated = await generator.generate_post(persona)
                
                # Generate image with Higgsfield
                media_urls = []
                try:
                    from app.services.image.higgsfield import HiggsfieldImageGenerator
                    
                    character_id = persona.higgsfield_character_id
                    image_generator = HiggsfieldImageGenerator(character_id=character_id)
                    
                    if image_generator.is_configured:
                        logger.info(
                            "Generating image for batch content",
                            persona=persona.name,
                            character_id=character_id,
                        )
                        
                        image_result = await image_generator.generate_for_content(
                            caption=generated["caption"],
                            character_id=character_id,
                            persona_name=persona.name,
                            persona_niche=persona.niche,
                            image_prompt_template=persona.image_prompt_template,
                        )
                        
                        if image_result["success"] and image_result["image_url"]:
                            media_urls.append(image_result["image_url"])
                            logger.info(
                                "Batch image generated",
                                persona=persona.name,
                                image_url=image_result["image_url"][:50] + "...",
                            )
                        else:
                            logger.warning(
                                "Batch image generation failed",
                                persona=persona.name,
                                error=image_result.get("error"),
                            )
                        
                        await image_generator.close()
                    else:
                        logger.info(
                            "Higgsfield not configured, skipping image",
                            persona=persona.name,
                        )
                except Exception as img_err:
                    logger.error(
                        "Batch image generation error",
                        persona=persona.name,
                        error=str(img_err),
                    )
                    # Continue without image
                
                status = (
                    ContentStatus.SCHEDULED
                    if persona.auto_approve_content
                    else ContentStatus.PENDING_REVIEW
                )
                
                content = Content(
                    persona_id=persona.id,
                    caption=generated["caption"],
                    hashtags=generated.get("hashtags", []),
                    media_urls=media_urls,
                    auto_generated=True,
                    status=status,
                )
                
                db.add(content)
                
                # Increment daily posts counter
                persona.posts_today += 1
                
                results["generated"] += 1
                
                logger.info(
                    "Batch content generated",
                    persona=persona.name,
                    has_image=len(media_urls) > 0,
                )
                
            except Exception as e:
                logger.error(
                    "Batch generation failed for persona",
                    persona=persona.name,
                    error=str(e),
                )
                results["errors"] += 1
        
        await db.commit()
    
    logger.info("Batch content generation complete", results=results)
    return results


@shared_task(name="app.workers.tasks.content_tasks.generate_video_content_for_persona")
def generate_video_content_for_persona(
    persona_id: str,
    content_type: str = "reel",
    topic: Optional[str] = None,
) -> dict:
    """Generate video content for a specific persona.
    
    Args:
        persona_id: UUID of the persona
        content_type: Type of video content ("reel", "story", or "video_post")
        topic: Optional specific topic to generate about
        
    Returns:
        Dictionary with generation result
    """
    return run_async(_generate_video_content_for_persona(persona_id, content_type, topic))


async def _generate_video_content_for_persona(
    persona_id: str,
    content_type: str = "reel",
    topic: Optional[str] = None,
) -> dict:
    """Async implementation of video content generation."""
    from app.services.image.higgsfield import HiggsfieldImageGenerator
    
    async with async_session_maker() as db:
        # Get persona
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            logger.error("Persona not found", persona_id=persona_id)
            return {"success": False, "error": "Persona not found"}
        
        if not persona.is_active:
            logger.info("Persona is paused, skipping", persona_id=persona_id)
            return {"success": False, "error": "Persona is paused"}
        
        # Map content_type to ContentType enum
        content_type_map = {
            "reel": ContentType.REEL,
            "story": ContentType.STORY,
            "video_post": ContentType.POST,
        }
        ct = content_type_map.get(content_type, ContentType.REEL)
        
        # Check rate limits based on content type
        if ct == ContentType.REEL:
            max_limit = await get_content_type_limit(db, "max_reels_per_day")
            current_count = persona.reels_today
            limit_name = "reels"
        elif ct == ContentType.STORY:
            max_limit = await get_content_type_limit(db, "max_stories_per_day")
            current_count = persona.stories_today
            limit_name = "stories"
        else:
            max_limit = await get_content_type_limit(db, "max_video_posts_per_day")
            current_count = persona.video_posts_today
            limit_name = "video_posts"
        
        if current_count >= max_limit:
            logger.info(
                f"Daily {limit_name} limit reached",
                persona=persona.name,
                current=current_count,
                limit=max_limit,
            )
            return {"success": False, "error": f"Daily {limit_name} limit reached"}
        
        try:
            # Generate content caption
            generator = ContentGenerator()
            generated = await generator.generate_post(persona, topic=topic)
            
            # Generate video with Higgsfield
            video_urls = []
            image_urls = []
            
            character_id = persona.higgsfield_character_id
            video_generator = HiggsfieldImageGenerator(character_id=character_id)
            
            if video_generator.is_configured:
                logger.info(
                    "Generating video content with Higgsfield",
                    persona=persona.name,
                    content_type=content_type,
                    character_id=character_id,
                )
                
                # Use 9:16 aspect ratio for reels/stories, 1:1 for regular video posts
                aspect_ratio = "9:16" if ct in [ContentType.REEL, ContentType.STORY] else "1:1"
                
                video_result = await video_generator.generate_video_for_content(
                    caption=generated["caption"],
                    character_id=character_id,
                    persona_name=persona.name,
                    persona_niche=persona.niche,
                    aspect_ratio=aspect_ratio,
                    image_prompt_template=persona.image_prompt_template,
                    video_duration=5 if ct == ContentType.STORY else 6,
                )
                
                if video_result["success"] and video_result.get("video_url"):
                    video_urls.append(video_result["video_url"])
                    logger.info(
                        "Video generated successfully",
                        video_url=video_result["video_url"][:50] + "...",
                    )
                else:
                    logger.warning(
                        "Video generation failed",
                        error=video_result.get("error"),
                    )
                    # If video failed but we have an image, still use it
                    if video_result.get("image_url"):
                        image_urls.append(video_result["image_url"])
                        logger.info("Falling back to image content")
                
                await video_generator.close()
            else:
                logger.info("Higgsfield not configured, skipping video generation")
                return {"success": False, "error": "Higgsfield not configured for video generation"}
            
            # Determine initial status
            status = (
                ContentStatus.SCHEDULED
                if persona.auto_approve_content
                else ContentStatus.PENDING_REVIEW
            )
            
            # Create content record
            content = Content(
                persona_id=persona.id,
                content_type=ct,
                caption=generated["caption"],
                hashtags=generated.get("hashtags", []),
                media_urls=image_urls,
                video_urls=video_urls,
                auto_generated=True,
                status=status,
            )
            
            db.add(content)
            
            # Increment the daily counter for this content type
            if ct == ContentType.STORY:
                persona.stories_today += 1
            elif ct == ContentType.REEL:
                persona.reels_today += 1
            elif ct == ContentType.VIDEO_POST:
                persona.video_posts_today += 1
            
            await db.commit()
            await db.refresh(content)
            
            logger.info(
                "Video content generated",
                persona=persona.name,
                content_id=str(content.id),
                content_type=ct.value,
                status=status.value,
                has_video=len(video_urls) > 0,
            )
            
            return {
                "success": True,
                "content_id": str(content.id),
                "content_type": ct.value,
                "status": status.value,
                "has_video": len(video_urls) > 0,
            }
            
        except Exception as e:
            logger.error(
                "Video content generation failed",
                persona_id=persona_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}


@shared_task(name="app.workers.tasks.content_tasks.generate_video_content_batch")
def generate_video_content_batch() -> dict:
    """Generate video content for all active personas based on limits.
    
    Returns:
        Dictionary with batch results
    """
    return run_async(_generate_video_content_batch())


async def _generate_video_content_batch() -> dict:
    """Async implementation of batch video content generation."""
    results = {
        "reels_generated": 0,
        "stories_generated": 0,
        "video_posts_generated": 0,
        "skipped": 0,
        "errors": 0,
    }
    
    async with async_session_maker() as db:
        # Get limits from settings
        max_reels = await get_content_type_limit(db, "max_reels_per_day")
        max_stories = await get_content_type_limit(db, "max_stories_per_day")
        max_video_posts = await get_content_type_limit(db, "max_video_posts_per_day")
        
        # Get active personas
        result = await db.execute(
            select(Persona).where(Persona.is_active == True)
        )
        personas = result.scalars().all()
        
        for persona in personas:
            # Check if Higgsfield is configured for this persona
            if not persona.higgsfield_character_id:
                logger.info(
                    "No Higgsfield character ID, skipping video generation",
                    persona=persona.name,
                )
                results["skipped"] += 1
                continue
            
            # Check pending REEL count and generate if under limits
            pending_reels_result = await db.execute(
                select(Content)
                .where(
                    Content.persona_id == persona.id,
                    Content.content_type == ContentType.REEL,
                    Content.status.in_([ContentStatus.PENDING_REVIEW, ContentStatus.SCHEDULED]),
                )
            )
            pending_reels = len(pending_reels_result.scalars().all())
            
            if persona.reels_today < max_reels and pending_reels < 5:
                try:
                    reel_result = await _generate_video_content_for_persona(
                        str(persona.id),
                        content_type="reel",
                    )
                    if reel_result.get("success"):
                        results["reels_generated"] += 1
                    else:
                        results["errors"] += 1
                except Exception as e:
                    logger.error(
                        "Reel generation failed",
                        persona=persona.name,
                        error=str(e),
                    )
                    results["errors"] += 1
            elif pending_reels >= 5:
                logger.info(
                    "Enough REEL content in queue",
                    persona=persona.name,
                    pending=pending_reels,
                )
            
            # Check pending STORY count and generate if under limits
            pending_stories_result = await db.execute(
                select(Content)
                .where(
                    Content.persona_id == persona.id,
                    Content.content_type == ContentType.STORY,
                    Content.status.in_([ContentStatus.PENDING_REVIEW, ContentStatus.SCHEDULED]),
                )
            )
            pending_stories = len(pending_stories_result.scalars().all())
            
            if persona.stories_today < max_stories and pending_stories < 5:
                try:
                    story_result = await _generate_video_content_for_persona(
                        str(persona.id),
                        content_type="story",
                    )
                    if story_result.get("success"):
                        results["stories_generated"] += 1
                    else:
                        results["errors"] += 1
                except Exception as e:
                    logger.error(
                        "Story generation failed",
                        persona=persona.name,
                        error=str(e),
                    )
                    results["errors"] += 1
            elif pending_stories >= 5:
                logger.info(
                    "Enough STORY content in queue",
                    persona=persona.name,
                    pending=pending_stories,
                )
            
            # Check pending VIDEO_POST count and generate if under limits
            pending_video_posts_result = await db.execute(
                select(Content)
                .where(
                    Content.persona_id == persona.id,
                    Content.content_type == ContentType.POST,
                    Content.video_urls != [],  # Only count POSTs with videos
                    Content.status.in_([ContentStatus.PENDING_REVIEW, ContentStatus.SCHEDULED]),
                )
            )
            pending_video_posts = len(pending_video_posts_result.scalars().all())
            
            if persona.video_posts_today < max_video_posts and pending_video_posts < 5:
                try:
                    video_post_result = await _generate_video_content_for_persona(
                        str(persona.id),
                        content_type="video_post",
                    )
                    if video_post_result.get("success"):
                        results["video_posts_generated"] += 1
                    else:
                        results["errors"] += 1
                except Exception as e:
                    logger.error(
                        "Video post generation failed",
                        persona=persona.name,
                        error=str(e),
                    )
                    results["errors"] += 1
            elif pending_video_posts >= 5:
                logger.info(
                    "Enough VIDEO_POST content in queue",
                    persona=persona.name,
                    pending=pending_video_posts,
                )
    
    logger.info("Batch video content generation complete", results=results)
    return results


@shared_task(name="app.workers.tasks.content_tasks.generate_fanvue_content_for_persona")
def generate_fanvue_content_for_persona(
    persona_id: str,
    is_video: bool = False,
    topic: Optional[str] = None,
) -> dict:
    """Generate content specifically for Fanvue using Seedream 4 and Wan 2.5.
    
    Args:
        persona_id: UUID of the persona
        is_video: Whether to generate video content
        topic: Optional specific topic to generate about
        
    Returns:
        Dictionary with generation result
    """
    return run_async(_generate_fanvue_content_for_persona(persona_id, is_video, topic))


async def _generate_fanvue_content_for_persona(
    persona_id: str,
    is_video: bool = False,
    topic: Optional[str] = None,
) -> dict:
    """Async implementation of Fanvue content generation.
    
    Uses:
    - Seedream 4 Unlimited for image generation
    - Wan 2.5 with handheld style for video generation
    """
    from app.services.image.higgsfield import HiggsfieldImageGenerator
    from app.models.platform_account import PlatformAccount, Platform
    
    async with async_session_maker() as db:
        # Get persona
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            logger.error("Persona not found", persona_id=persona_id)
            return {"success": False, "error": "Persona not found"}
        
        if not persona.is_active:
            logger.info("Persona is paused, skipping", persona_id=persona_id)
            return {"success": False, "error": "Persona is paused"}
        
        # Check if Fanvue is connected
        fanvue_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.platform == Platform.FANVUE,
                PlatformAccount.is_connected == True,
            )
        )
        fanvue_account = fanvue_result.scalar_one_or_none()
        
        if not fanvue_account:
            logger.warning("Fanvue not connected", persona=persona.name)
            return {"success": False, "error": "Fanvue not connected for this persona"}
        
        try:
            # Generate content caption
            generator = ContentGenerator()
            generated = await generator.generate_post(persona, topic=topic)
            
            # Generate media with Higgsfield Seedream 4 / Wan 2.5
            image_generator = HiggsfieldImageGenerator()
            
            if not image_generator.api_key:
                return {"success": False, "error": "Higgsfield API not configured"}
            
            logger.info(
                "Generating Fanvue content with Seedream 4 / Wan 2.5",
                persona=persona.name,
                is_video=is_video,
            )
            
            # Create image prompt from caption
            prompt = f"A beautiful, high-quality photo. {generated['caption'][:100]}"
            
            media_result = await image_generator.generate_for_fanvue(
                prompt=prompt,
                is_video=is_video,
                motion_prompt=generated['caption'][:80] if is_video else None,
                aspect_ratio="9:16",  # Vertical for Fanvue
                video_duration=5,
            )
            
            await image_generator.close()
            
            if not media_result["success"]:
                logger.warning(
                    "Fanvue media generation failed",
                    error=media_result.get("error"),
                )
                return {"success": False, "error": media_result.get("error")}
            
            # Prepare media URLs
            media_urls = []
            video_urls = []
            
            if is_video and media_result.get("video_url"):
                video_urls.append(media_result["video_url"])
                if media_result.get("source_image_url"):
                    media_urls.append(media_result["source_image_url"])
            elif media_result.get("image_url"):
                media_urls.append(media_result["image_url"])
            
            # Determine initial status
            status = (
                ContentStatus.SCHEDULED
                if persona.auto_approve_content
                else ContentStatus.PENDING_REVIEW
            )
            
            # Determine content type
            if is_video:
                content_type = ContentType.REEL
            else:
                content_type = ContentType.POST
            
            # Create content record
            content = Content(
                persona_id=persona.id,
                content_type=content_type,
                caption=generated["caption"],
                hashtags=generated.get("hashtags", []),
                media_urls=media_urls,
                video_urls=video_urls,
                auto_generated=True,
                status=status,
            )
            
            db.add(content)
            await db.commit()
            await db.refresh(content)
            
            logger.info(
                "Fanvue content generated",
                persona=persona.name,
                content_id=str(content.id),
                content_type=content_type.value,
                status=status.value,
                has_video=len(video_urls) > 0,
            )
            
            return {
                "success": True,
                "content_id": str(content.id),
                "content_type": content_type.value,
                "status": status.value,
                "has_image": len(media_urls) > 0,
                "has_video": len(video_urls) > 0,
                "platform": "fanvue",
            }
            
        except Exception as e:
            logger.error(
                "Fanvue content generation failed",
                persona_id=persona_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}


@shared_task(name="app.workers.tasks.content_tasks.generate_story_ideas")
def generate_story_ideas(persona_id: str, count: int = 5) -> dict:
    """Generate story ideas for a persona.
    
    Args:
        persona_id: UUID of the persona
        count: Number of ideas to generate
        
    Returns:
        Dictionary with generated ideas
    """
    return run_async(_generate_story_ideas(persona_id, count))


async def _generate_story_ideas(persona_id: str, count: int = 5) -> dict:
    """Async implementation of story idea generation."""
    async with async_session_maker() as db:
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            return {"success": False, "error": "Persona not found"}
        
        try:
            generator = ContentGenerator()
            ideas = await generator.generate_story_ideas(persona, count)
            
            return {"success": True, "ideas": ideas}
            
        except Exception as e:
            logger.error(
                "Story idea generation failed",
                persona_id=persona_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}


@shared_task(name="app.workers.tasks.content_tasks.improve_content")
def improve_content(content_id: str, feedback: Optional[str] = None) -> dict:
    """Improve existing content based on feedback.
    
    Args:
        content_id: UUID of the content to improve
        feedback: Optional feedback for improvement
        
    Returns:
        Dictionary with improvement result
    """
    return run_async(_improve_content(content_id, feedback))


async def _improve_content(content_id: str, feedback: Optional[str] = None) -> dict:
    """Async implementation of content improvement."""
    async with async_session_maker() as db:
        # Get content
        result = await db.execute(
            select(Content).where(Content.id == UUID(content_id))
        )
        content = result.scalar_one_or_none()
        
        if not content:
            return {"success": False, "error": "Content not found"}
        
        # Get persona
        persona_result = await db.execute(
            select(Persona).where(Persona.id == content.persona_id)
        )
        persona = persona_result.scalar_one_or_none()
        
        if not persona:
            return {"success": False, "error": "Persona not found"}
        
        try:
            generator = ContentGenerator()
            improved = await generator.improve_caption(
                persona,
                content.caption,
                feedback,
            )
            
            # Update content
            content.caption = improved["caption"]
            content.hashtags = improved.get("hashtags", content.hashtags)
            
            await db.commit()
            
            return {
                "success": True,
                "improvements": improved.get("improvements", []),
            }
            
        except Exception as e:
            logger.error(
                "Content improvement failed",
                content_id=content_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}


# ===== NSFW CONTENT GENERATION (for Fanvue) =====

@shared_task(name="app.workers.tasks.content_tasks.generate_nsfw_content_for_persona")
def generate_nsfw_content_for_persona(
    persona_id: str,
    generate_video: bool = False,
) -> dict:
    """Generate NSFW content for a specific persona using Seedream 4 and Wan 2.5.
    
    This task auto-generates prompts for sexy scenes/poses and uses previously
    generated images as reference input to maintain character consistency.
    
    Args:
        persona_id: UUID of the persona
        generate_video: If True, also generate video from the image
        
    Returns:
        Dictionary with generation result
    """
    return run_async(_generate_nsfw_content_for_persona(persona_id, generate_video))


async def _generate_nsfw_content_for_persona(
    persona_id: str,
    generate_video: bool = False,
) -> dict:
    """Async implementation of NSFW content generation."""
    from app.services.image.higgsfield import HiggsfieldImageGenerator
    from app.models.platform_account import PlatformAccount, Platform
    
    async with async_session_maker() as db:
        # Get persona
        result = await db.execute(
            select(Persona).where(Persona.id == UUID(persona_id))
        )
        persona = result.scalar_one_or_none()
        
        if not persona:
            logger.error("Persona not found", persona_id=persona_id)
            return {"success": False, "error": "Persona not found"}
        
        if not persona.is_active:
            logger.info("Persona is paused, skipping", persona_id=persona_id)
            return {"success": False, "error": "Persona is paused"}
        
        # Check if Fanvue is connected
        fanvue_result = await db.execute(
            select(PlatformAccount).where(
                PlatformAccount.persona_id == persona.id,
                PlatformAccount.platform == Platform.FANVUE,
                PlatformAccount.is_connected == True,
            )
        )
        fanvue_account = fanvue_result.scalar_one_or_none()
        
        if not fanvue_account:
            logger.warning("Fanvue not connected", persona=persona.name)
            return {"success": False, "error": "Fanvue not connected for this persona"}
        
        # Check NSFW daily limit (separate limits for images and videos)
        if generate_video:
            max_nsfw = await get_content_type_limit(db, "max_nsfw_videos_per_day")
            current_count = persona.nsfw_videos_today
            content_kind = "video"
        else:
            max_nsfw = await get_content_type_limit(db, "max_nsfw_images_per_day")
            current_count = persona.nsfw_images_today
            content_kind = "image"
        
        if current_count >= max_nsfw:
            logger.info(
                f"Daily NSFW {content_kind} limit reached",
                persona=persona.name,
                current=current_count,
                limit=max_nsfw,
            )
            return {"success": False, "error": f"Daily NSFW {content_kind} limit reached"}
        
        try:
            # Generate NSFW prompt
            generator = ContentGenerator()
            prompt_data = generator.generate_nsfw_prompt(
                persona,
                custom_template=persona.nsfw_prompt_template,
            )
            
            # Generate caption for the content
            caption_data = await generator.generate_nsfw_caption(
                persona,
                setting=prompt_data["setting"],
                pose=prompt_data["pose"],
                mood=prompt_data["mood"],
            )
            
            # Get reference images - first check persona config, then fall back to previous posts
            reference_images = persona.nsfw_reference_images or []
            
            # If no manually configured references, use images from previously posted content
            if not reference_images:
                logger.info("No configured references, fetching from previous posts", persona=persona.name)
                
                # Get media URLs from previously published content for this persona
                from sqlalchemy import func
                previous_content_result = await db.execute(
                    select(Content)
                    .where(
                        Content.persona_id == persona.id,
                        Content.status == ContentStatus.POSTED,
                        func.array_length(Content.media_urls, 1) > 0,  # Has media URLs
                    )
                    .order_by(Content.posted_at.desc())
                    .limit(20)  # Get last 20 posts with images to ensure we have enough
                )
                previous_posts = previous_content_result.scalars().all()
                
                # Collect all image URLs from previous posts
                for post in previous_posts:
                    if post.media_urls:
                        reference_images.extend(post.media_urls)
                        if len(reference_images) >= 14:  # Cap at 14 references
                            break
                
                reference_images = reference_images[:14]  # Limit to 14 max
                
                if reference_images:
                    logger.info(
                        "Using previous post images as references",
                        persona=persona.name,
                        num_references=len(reference_images),
                    )
                else:
                    logger.info(
                        "No previous posts found, will use Soul character model",
                        persona=persona.name,
                    )
            
            # Generate NSFW content with Seedream 4
            # Use persona's character ID for Soul model fallback
            image_generator = HiggsfieldImageGenerator(
                character_id=persona.higgsfield_character_id
            )
            
            if not image_generator.api_key:
                return {"success": False, "error": "Higgsfield API not configured"}
            
            # Log full prompt for debugging NSFW moderation issues
            logger.info(
                "Generating NSFW content with Seedream 4",
                persona=persona.name,
                generate_video=generate_video,
                num_references=len(reference_images),
            )
            logger.warning(
                "FULL NSFW PROMPT FOR DEBUGGING",
                full_prompt=prompt_data["prompt"],
                setting=prompt_data.get("setting"),
                pose=prompt_data.get("pose"),
                mood=prompt_data.get("mood"),
                lighting=prompt_data.get("lighting"),
            )
            
            media_result = await image_generator.generate_nsfw_content(
                prompt=prompt_data["prompt"],
                reference_image_urls=reference_images if reference_images else None,
                generate_video=generate_video,
                aspect_ratio="9:16",  # Vertical for Fanvue
                video_duration=5,
                persona_id=persona_id,  # For browser automation fallback
            )
            
            await image_generator.close()
            
            if not media_result["success"]:
                logger.warning(
                    "NSFW content generation failed",
                    error=media_result.get("error"),
                )
                return {"success": False, "error": media_result.get("error")}
            
            # Prepare media URLs
            media_urls = []
            video_urls = []
            
            if media_result.get("image_url"):
                media_urls.append(media_result["image_url"])
            
            if media_result.get("video_url"):
                video_urls.append(media_result["video_url"])
            
            # Determine initial status
            status = (
                ContentStatus.SCHEDULED
                if persona.auto_approve_content
                else ContentStatus.PENDING_REVIEW
            )
            
            # Create content record with NSFW type
            content = Content(
                persona_id=persona.id,
                content_type=ContentType.NSFW,
                caption=caption_data.get("caption", ""),
                hashtags=caption_data.get("hashtags", []),
                media_urls=media_urls,
                video_urls=video_urls,
                auto_generated=True,
                generation_prompt=prompt_data["prompt"],
                generation_topic=f"{prompt_data['mood']} - {prompt_data['setting']}",
                status=status,
            )
            
            db.add(content)
            
            # Increment daily NSFW counter (separate for images and videos)
            if generate_video:
                persona.nsfw_videos_today += 1
            else:
                persona.nsfw_images_today += 1
            
            await db.commit()
            await db.refresh(content)
            
            logger.info(
                "NSFW content generated",
                persona=persona.name,
                content_id=str(content.id),
                status=status.value,
                has_image=len(media_urls) > 0,
                has_video=len(video_urls) > 0,
            )
            
            return {
                "success": True,
                "content_id": str(content.id),
                "content_type": ContentType.NSFW.value,
                "status": status.value,
                "has_image": len(media_urls) > 0,
                "has_video": len(video_urls) > 0,
                "platform": "fanvue",
                "prompt_used": prompt_data["prompt"][:200],
            }
            
        except Exception as e:
            logger.error(
                "NSFW content generation failed",
                persona_id=persona_id,
                error=str(e),
            )
            return {"success": False, "error": str(e)}


@shared_task(name="app.workers.tasks.content_tasks.generate_nsfw_content_batch")
def generate_nsfw_content_batch() -> dict:
    """Generate NSFW content for all active personas with Fanvue connected.
    
    This batch task generates NSFW content for personas that:
    - Are active
    - Have Fanvue connected
    - Haven't reached their daily NSFW limit
    - Don't have too much pending NSFW content
    
    Returns:
        Dictionary with batch results
    """
    return run_async(_generate_nsfw_content_batch())


async def _generate_nsfw_content_batch() -> dict:
    """Async implementation of batch NSFW content generation."""
    from app.models.platform_account import PlatformAccount, Platform
    
    results = {
        "generated": 0,
        "videos_generated": 0,
        "skipped": 0,
        "errors": 0,
    }
    
    async with async_session_maker() as db:
        # Get separate limits for NSFW images and videos
        max_nsfw_images = await get_content_type_limit(db, "max_nsfw_images_per_day")
        max_nsfw_videos = await get_content_type_limit(db, "max_nsfw_videos_per_day")
        
        # Get active personas with Fanvue connected
        result = await db.execute(
            select(Persona)
            .join(PlatformAccount, Persona.id == PlatformAccount.persona_id)
            .where(
                Persona.is_active == True,
                PlatformAccount.platform == Platform.FANVUE,
                PlatformAccount.is_connected == True,
            )
        )
        personas = result.scalars().all()
        
        for persona in personas:
            # Check if both NSFW limits are reached
            images_at_limit = persona.nsfw_images_today >= max_nsfw_images
            videos_at_limit = persona.nsfw_videos_today >= max_nsfw_videos
            
            if images_at_limit and videos_at_limit:
                logger.info(
                    "Daily NSFW limits reached (both images and videos)",
                    persona=persona.name,
                    images=persona.nsfw_images_today,
                    videos=persona.nsfw_videos_today,
                    max_images=max_nsfw_images,
                    max_videos=max_nsfw_videos,
                )
                results["skipped"] += 1
                continue
            
            # Check pending NSFW content count
            pending_result = await db.execute(
                select(Content)
                .where(
                    Content.persona_id == persona.id,
                    Content.content_type == ContentType.NSFW,
                    Content.status.in_([
                        ContentStatus.PENDING_REVIEW,
                        ContentStatus.SCHEDULED,
                    ]),
                )
            )
            pending_count = len(pending_result.scalars().all())
            
            # Skip if enough NSFW content in queue
            if pending_count >= 10:
                logger.info(
                    "Enough NSFW content in queue",
                    persona=persona.name,
                    pending=pending_count,
                )
                results["skipped"] += 1
                continue
            
            # Check if we have reference images
            has_references = bool(persona.nsfw_reference_images)
            
            try:
                # Generate NSFW content
                # Decide whether to generate video based on available quota
                import random
                
                if videos_at_limit:
                    # Can only generate images
                    generate_video = False
                elif images_at_limit:
                    # Can only generate videos
                    generate_video = True
                else:
                    # Both have room - randomly decide (30% chance for video)
                    generate_video = random.random() < 0.3
                
                nsfw_result = await _generate_nsfw_content_for_persona(
                    str(persona.id),
                    generate_video=generate_video,
                )
                
                if nsfw_result.get("success"):
                    results["generated"] += 1
                    if nsfw_result.get("has_video"):
                        results["videos_generated"] += 1
                else:
                    results["errors"] += 1
                    
            except Exception as e:
                logger.error(
                    "Batch NSFW generation failed for persona",
                    persona=persona.name,
                    error=str(e),
                )
                results["errors"] += 1
    
    logger.info("Batch NSFW content generation complete", results=results)
    return results


