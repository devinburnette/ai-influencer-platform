"""Content management API endpoints."""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.content import Content, ContentStatus, ContentType

router = APIRouter()


class ContentCreate(BaseModel):
    """Schema for creating content."""
    persona_id: UUID
    content_type: ContentType = ContentType.POST
    caption: str = Field(..., max_length=2200)
    hashtags: List[str] = Field(default_factory=list)
    scheduled_for: Optional[datetime] = None
    auto_generated: bool = False


class ContentUpdate(BaseModel):
    """Schema for updating content."""
    caption: Optional[str] = Field(None, max_length=2200)
    hashtags: Optional[List[str]] = None
    media_urls: Optional[List[str]] = None  # Image URLs to attach
    scheduled_for: Optional[datetime] = None
    status: Optional[ContentStatus] = None


class ContentResponse(BaseModel):
    """Schema for content response."""
    id: UUID
    persona_id: UUID
    content_type: ContentType
    caption: str
    hashtags: List[str]
    media_urls: List[str]  # Image URLs
    video_urls: List[str] = []  # Video URLs
    status: ContentStatus
    scheduled_for: Optional[datetime]
    posted_at: Optional[datetime]
    auto_generated: bool
    engagement_count: int
    error_message: Optional[str] = None
    posted_platforms: List[str] = []  # Which platforms have received this content
    platform_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContentQueueResponse(BaseModel):
    """Response for content queue."""
    pending_review: List[ContentResponse]
    scheduled: List[ContentResponse]
    posted: List[ContentResponse]


@router.get("/", response_model=List[ContentResponse])
async def list_content(
    persona_id: Optional[UUID] = None,
    status: Optional[ContentStatus] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List content with optional filters."""
    query = select(Content)
    
    if persona_id:
        query = query.where(Content.persona_id == persona_id)
    if status:
        query = query.where(Content.status == status)
    
    query = query.order_by(Content.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    content_list = result.scalars().all()
    
    return content_list


@router.get("/queue/{persona_id}", response_model=ContentQueueResponse)
async def get_content_queue(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get content queue for a persona organized by status."""
    # Pending review
    pending_query = select(Content).where(
        Content.persona_id == persona_id,
        Content.status == ContentStatus.PENDING_REVIEW,
    ).order_by(Content.created_at.desc())
    pending_result = await db.execute(pending_query)
    pending = pending_result.scalars().all()
    
    # Scheduled
    scheduled_query = select(Content).where(
        Content.persona_id == persona_id,
        Content.status == ContentStatus.SCHEDULED,
    ).order_by(Content.scheduled_for.asc())
    scheduled_result = await db.execute(scheduled_query)
    scheduled = scheduled_result.scalars().all()
    
    # Posted (recent)
    posted_query = select(Content).where(
        Content.persona_id == persona_id,
        Content.status == ContentStatus.POSTED,
    ).order_by(Content.posted_at.desc()).limit(20)
    posted_result = await db.execute(posted_query)
    posted = posted_result.scalars().all()
    
    return ContentQueueResponse(
        pending_review=pending,
        scheduled=scheduled,
        posted=posted,
    )


@router.post("/", response_model=ContentResponse, status_code=status.HTTP_201_CREATED)
async def create_content(
    content_data: ContentCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create new content."""
    content = Content(
        persona_id=content_data.persona_id,
        content_type=content_data.content_type,
        caption=content_data.caption,
        hashtags=content_data.hashtags,
        scheduled_for=content_data.scheduled_for,
        auto_generated=content_data.auto_generated,
        status=ContentStatus.PENDING_REVIEW if not content_data.scheduled_for else ContentStatus.SCHEDULED,
    )
    
    db.add(content)
    await db.flush()
    await db.refresh(content)
    
    return content


@router.get("/{content_id}", response_model=ContentResponse)
async def get_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get specific content by ID."""
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found",
        )
    
    return content


@router.patch("/{content_id}", response_model=ContentResponse)
async def update_content(
    content_id: UUID,
    content_data: ContentUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update content."""
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found",
        )
    
    update_data = content_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(content, field, value)
    
    await db.flush()
    await db.refresh(content)
    
    return content


@router.post("/{content_id}/approve", response_model=ContentResponse)
async def approve_content(
    content_id: UUID,
    scheduled_for: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    """Approve content for posting."""
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found",
        )
    
    content.status = ContentStatus.SCHEDULED
    if scheduled_for:
        content.scheduled_for = scheduled_for
    
    await db.flush()
    await db.refresh(content)
    
    return content


@router.post("/{content_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Reject and delete content."""
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found",
        )
    
    await db.delete(content)


@router.delete("/{content_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete content."""
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found",
        )
    
    await db.delete(content)


class PostNowRequest(BaseModel):
    """Request body for post-now endpoint."""
    platforms: Optional[List[str]] = None  # List of platform names, e.g., ["twitter", "instagram"]


@router.post("/{content_id}/post-now", response_model=ContentResponse)
async def post_content_now(
    content_id: UUID,
    request: Optional[PostNowRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Post content immediately to selected platforms.
    
    Supports reposting to platforms that haven't received the content yet.
    
    Args:
        content_id: UUID of the content to post
        request: Optional request body with platforms list. If not provided or empty,
                 posts to all connected platforms that haven't received this content.
    """
    from app.models.persona import Persona
    from app.models.platform_account import PlatformAccount, Platform
    
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found",
        )
    
    # Check if content is in a postable state OR already posted (for reposting to other platforms)
    # Include FAILED and POSTING for retry scenarios
    postable_statuses = [ContentStatus.SCHEDULED, ContentStatus.PENDING_REVIEW, ContentStatus.DRAFT, ContentStatus.POSTED, ContentStatus.FAILED, ContentStatus.POSTING]
    if content.status not in postable_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content cannot be posted (current status: {content.status})",
        )
    
    # Get platforms this content has already been posted to
    already_posted_to = set(content.posted_platforms or [])
    
    # Get persona's connected platform accounts
    pa_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == content.persona_id,
            PlatformAccount.is_connected == True,
        )
    )
    all_accounts = pa_result.scalars().all()
    
    if not all_accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No platform accounts connected. Please connect a social media account first.",
        )
    
    # Filter accounts by requested platforms (if specified)
    requested_platforms = request.platforms if request and request.platforms else None
    
    if requested_platforms:
        # Normalize platform names and filter
        valid_platforms = {p.lower() for p in requested_platforms}
        accounts_to_post = [a for a in all_accounts if a.platform.value.lower() in valid_platforms]
        
        if not accounts_to_post:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No connected accounts for platforms: {', '.join(requested_platforms)}",
            )
    else:
        # Post to all connected platforms (excluding already posted)
        accounts_to_post = all_accounts
    
    # Filter out platforms that have already received this content
    accounts_to_post = [a for a in accounts_to_post if a.platform.value.lower() not in already_posted_to]
    
    if not accounts_to_post:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content has already been posted to all selected platforms: {', '.join(already_posted_to)}",
        )
    
    # Update status (only if not already posted - preserve POSTED status for reposting)
    if content.status != ContentStatus.POSTED:
        content.status = ContentStatus.SCHEDULED
    await db.commit()
    await db.refresh(content)
    
    # Trigger posting task for each platform
    from app.workers.tasks.posting_tasks import post_content_to_platform
    for account in accounts_to_post:
        post_content_to_platform.delay(str(content.id), account.platform.value)
    
    return content


@router.post("/{content_id}/retry", response_model=ContentResponse)
async def retry_failed_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retry posting failed content."""
    from app.models.persona import Persona
    from app.models.platform_account import PlatformAccount
    
    result = await db.execute(select(Content).where(Content.id == content_id))
    content = result.scalar_one_or_none()
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Content {content_id} not found",
        )
    
    # Check if content is in a retriable state (FAILED or POSTED with remaining platforms)
    already_posted = set(content.posted_platforms or [])
    
    if content.status == ContentStatus.POSTED:
        # Content was posted to at least one platform - check if there are remaining platforms
        # This handles the case where one platform succeeded and another failed
        pass  # Will check for remaining platforms below
    elif content.status != ContentStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content cannot be retried (current status: {content.status})",
        )
    
    # Get persona's connected platform accounts
    pa_result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.persona_id == content.persona_id,
            PlatformAccount.is_connected == True,
        )
    )
    platform_accounts = pa_result.scalars().all()
    
    if not platform_accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No platform accounts connected. Please connect a social media account first.",
        )
    
    # Filter out platforms already posted to (already_posted defined above)
    accounts_to_post = [a for a in platform_accounts if a.platform.value.lower() not in already_posted]
    
    if not accounts_to_post:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content has already been posted to all connected platforms.",
        )
    
    # Reset error message (keep POSTED status if already posted to some platforms)
    if content.status != ContentStatus.POSTED:
        content.status = ContentStatus.SCHEDULED
    content.error_message = None
    await db.commit()
    await db.refresh(content)
    
    # Trigger posting task for each platform that hasn't received this content
    from app.workers.tasks.posting_tasks import post_content_to_platform
    for account in accounts_to_post:
        post_content_to_platform.delay(str(content.id), account.platform.value)
    
    return content


class GenerateContentRequest(BaseModel):
    """Request body for content generation."""
    content_type: ContentType = ContentType.POST
    topic: Optional[str] = None
    platform: str = "twitter"
    generate_image: bool = True  # Whether to generate an image with Higgsfield
    generate_video: bool = False  # Whether to generate a video (for reels/stories)


@router.post("/{persona_id}/generate", response_model=ContentResponse)
async def generate_content_for_persona(
    persona_id: UUID,
    request: Optional[GenerateContentRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """Generate new AI content for a persona.
    
    Args:
        persona_id: UUID of the persona
        request: Optional request body with generation options
    """
    from app.services.ai.content_generator import ContentGenerator
    from app.services.image.higgsfield import HiggsfieldImageGenerator
    from app.models.persona import Persona
    import structlog
    
    logger = structlog.get_logger()
    
    # Parse request parameters
    content_type = request.content_type if request else ContentType.POST
    topic = request.topic if request else None
    platform = request.platform if request else "twitter"
    generate_image = request.generate_image if request else True
    generate_video = request.generate_video if request else False
    
    # Auto-enable video for reels and stories
    if content_type in [ContentType.REEL, ContentType.STORY]:
        generate_video = True
        platform = "instagram"  # Reels/Stories are Instagram-specific
    
    # Validate platform
    valid_platforms = ["twitter", "instagram"]
    if platform.lower() not in valid_platforms:
        platform = "twitter"
    
    # Get persona
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    # Generate text content with platform-aware character limits
    generator = ContentGenerator()
    generated = await generator.generate_post(
        persona, 
        topic=topic, 
        platform=platform.lower(),
    )
    
    # Generate media (image and/or video) if requested and Higgsfield is configured
    media_urls = []
    video_urls = []
    
    if generate_image or generate_video:
        try:
            # Use persona-specific character ID if available
            character_id = persona.higgsfield_character_id
            media_generator = HiggsfieldImageGenerator(character_id=character_id)
            
            if media_generator.is_configured:
                if generate_video:
                    # Generate video (which also generates the base image)
                    logger.info(
                        "Generating video with Higgsfield",
                        persona=persona.name,
                        content_type=content_type.value,
                        caption_preview=generated["caption"][:50],
                    )
                    
                    # Use 9:16 aspect ratio for reels/stories, 1:1 for posts
                    aspect_ratio = "9:16" if content_type in [ContentType.REEL, ContentType.STORY] else "1:1"
                    
                    video_result = await media_generator.generate_video_for_content(
                        caption=generated["caption"],
                        character_id=character_id,
                        persona_name=persona.name,
                        persona_niche=persona.niche,
                        aspect_ratio=aspect_ratio,
                        image_prompt_template=persona.image_prompt_template,
                        video_duration=5,  # 5 second videos
                    )
                    
                    if video_result.get("video_url"):
                        video_urls.append(video_result["video_url"])
                        logger.info(
                            "Video generated successfully",
                            video_url=video_result["video_url"][:50] + "...",
                        )
                    
                    # Also keep the source image
                    if video_result.get("image_url"):
                        media_urls.append(video_result["image_url"])
                    
                    if not video_result["success"]:
                        logger.warning(
                            "Video generation failed, but image may be available",
                            error=video_result.get("error"),
                        )
                
                elif generate_image:
                    # Generate image only
                    logger.info(
                        "Generating image with Higgsfield",
                        persona=persona.name,
                        character_id=character_id,
                        caption_preview=generated["caption"][:50],
                    )
                    
                    image_result = await media_generator.generate_for_content(
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
                
                await media_generator.close()
            else:
                logger.info(
                    "Higgsfield not configured, skipping media generation",
                    has_character_id=bool(character_id),
                )
        except Exception as e:
            logger.error("Media generation error", error=str(e))
            # Continue without media - don't fail content generation
    
    content = Content(
        persona_id=persona_id,
        content_type=content_type,
        caption=generated["caption"],
        hashtags=generated["hashtags"],
        media_urls=media_urls,  # Image URLs
        video_urls=video_urls,  # Video URLs
        auto_generated=True,
        status=ContentStatus.PENDING_REVIEW,
    )
    
    db.add(content)
    await db.flush()
    await db.refresh(content)
    
    return content


