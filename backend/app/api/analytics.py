"""Analytics API endpoints."""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.persona import Persona
from app.models.content import Content, ContentStatus
from app.models.engagement import Engagement, EngagementType

router = APIRouter()


class PersonaStats(BaseModel):
    """Statistics for a persona."""
    persona_id: UUID
    persona_name: str
    follower_count: int
    following_count: int
    post_count: int
    total_likes_given: int
    total_comments_given: int
    total_follows_given: int
    content_pending_review: int
    content_scheduled: int
    is_active: bool


class EngagementStats(BaseModel):
    """Engagement statistics."""
    date: str
    likes: int
    comments: int
    follows: int


class ContentPerformance(BaseModel):
    """Content performance metrics."""
    content_id: UUID
    caption_preview: str
    posted_at: Optional[datetime]
    engagement_count: int
    content_type: str


class DashboardOverview(BaseModel):
    """Dashboard overview data."""
    total_personas: int
    active_personas: int
    total_posts: int
    posts_today: int
    engagements_today: int
    pending_content: int


class ActivityLogEntry(BaseModel):
    """Activity log entry."""
    id: UUID
    persona_id: UUID
    persona_name: str
    action_type: str
    target_url: Optional[str]
    details: Optional[str]
    created_at: datetime


@router.get("/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard overview statistics."""
    # Total and active personas
    personas_result = await db.execute(select(Persona))
    personas = personas_result.scalars().all()
    total_personas = len(personas)
    active_personas = sum(1 for p in personas if p.is_active)
    
    # Total posts
    posts_result = await db.execute(
        select(func.count(Content.id)).where(Content.status == ContentStatus.POSTED)
    )
    total_posts = posts_result.scalar() or 0
    
    # Posts today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    posts_today_result = await db.execute(
        select(func.count(Content.id)).where(
            Content.status == ContentStatus.POSTED,
            Content.posted_at >= today_start,
        )
    )
    posts_today = posts_today_result.scalar() or 0
    
    # Engagements today
    engagements_today_result = await db.execute(
        select(func.count(Engagement.id)).where(
            Engagement.created_at >= today_start,
        )
    )
    engagements_today = engagements_today_result.scalar() or 0
    
    # Pending content
    pending_result = await db.execute(
        select(func.count(Content.id)).where(
            Content.status == ContentStatus.PENDING_REVIEW,
        )
    )
    pending_content = pending_result.scalar() or 0
    
    return DashboardOverview(
        total_personas=total_personas,
        active_personas=active_personas,
        total_posts=total_posts,
        posts_today=posts_today,
        engagements_today=engagements_today,
        pending_content=pending_content,
    )


@router.get("/personas/{persona_id}/stats", response_model=PersonaStats)
async def get_persona_stats(
    persona_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a specific persona."""
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    # Count engagements
    likes_result = await db.execute(
        select(func.count(Engagement.id)).where(
            Engagement.persona_id == persona_id,
            Engagement.engagement_type == EngagementType.LIKE,
        )
    )
    total_likes = likes_result.scalar() or 0
    
    comments_result = await db.execute(
        select(func.count(Engagement.id)).where(
            Engagement.persona_id == persona_id,
            Engagement.engagement_type == EngagementType.COMMENT,
        )
    )
    total_comments = comments_result.scalar() or 0
    
    follows_result = await db.execute(
        select(func.count(Engagement.id)).where(
            Engagement.persona_id == persona_id,
            Engagement.engagement_type == EngagementType.FOLLOW,
        )
    )
    total_follows = follows_result.scalar() or 0
    
    # Content counts
    pending_result = await db.execute(
        select(func.count(Content.id)).where(
            Content.persona_id == persona_id,
            Content.status == ContentStatus.PENDING_REVIEW,
        )
    )
    pending_count = pending_result.scalar() or 0
    
    scheduled_result = await db.execute(
        select(func.count(Content.id)).where(
            Content.persona_id == persona_id,
            Content.status == ContentStatus.SCHEDULED,
        )
    )
    scheduled_count = scheduled_result.scalar() or 0
    
    return PersonaStats(
        persona_id=persona.id,
        persona_name=persona.name,
        follower_count=persona.follower_count,
        following_count=persona.following_count,
        post_count=persona.post_count,
        total_likes_given=total_likes,
        total_comments_given=total_comments,
        total_follows_given=total_follows,
        content_pending_review=pending_count,
        content_scheduled=scheduled_count,
        is_active=persona.is_active,
    )


@router.get("/personas/{persona_id}/engagement", response_model=List[EngagementStats])
async def get_persona_engagement_history(
    persona_id: UUID,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    """Get engagement history for a persona over the last N days."""
    result = await db.execute(select(Persona).where(Persona.id == persona_id))
    persona = result.scalar_one_or_none()
    
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Persona {persona_id} not found",
        )
    
    stats = []
    for i in range(days):
        date = datetime.utcnow().date() - timedelta(days=i)
        day_start = datetime.combine(date, datetime.min.time())
        day_end = datetime.combine(date, datetime.max.time())
        
        # Count each type
        likes_result = await db.execute(
            select(func.count(Engagement.id)).where(
                Engagement.persona_id == persona_id,
                Engagement.engagement_type == EngagementType.LIKE,
                Engagement.created_at >= day_start,
                Engagement.created_at <= day_end,
            )
        )
        likes = likes_result.scalar() or 0
        
        comments_result = await db.execute(
            select(func.count(Engagement.id)).where(
                Engagement.persona_id == persona_id,
                Engagement.engagement_type == EngagementType.COMMENT,
                Engagement.created_at >= day_start,
                Engagement.created_at <= day_end,
            )
        )
        comments = comments_result.scalar() or 0
        
        follows_result = await db.execute(
            select(func.count(Engagement.id)).where(
                Engagement.persona_id == persona_id,
                Engagement.engagement_type == EngagementType.FOLLOW,
                Engagement.created_at >= day_start,
                Engagement.created_at <= day_end,
            )
        )
        follows = follows_result.scalar() or 0
        
        stats.append(EngagementStats(
            date=date.isoformat(),
            likes=likes,
            comments=comments,
            follows=follows,
        ))
    
    return stats


@router.get("/personas/{persona_id}/top-content", response_model=List[ContentPerformance])
async def get_top_performing_content(
    persona_id: UUID,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Get top performing content for a persona."""
    result = await db.execute(
        select(Content)
        .where(
            Content.persona_id == persona_id,
            Content.status == ContentStatus.POSTED,
        )
        .order_by(Content.engagement_count.desc())
        .limit(limit)
    )
    content_list = result.scalars().all()
    
    return [
        ContentPerformance(
            content_id=c.id,
            caption_preview=c.caption[:100] + "..." if len(c.caption) > 100 else c.caption,
            posted_at=c.posted_at,
            engagement_count=c.engagement_count,
            content_type=c.content_type.value,
        )
        for c in content_list
    ]


@router.get("/activity-log", response_model=List[ActivityLogEntry])
async def get_activity_log(
    persona_id: Optional[UUID] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Get activity log with optional persona filter."""
    query = select(Engagement)
    
    if persona_id:
        query = query.where(Engagement.persona_id == persona_id)
    
    query = query.order_by(Engagement.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    engagements = result.scalars().all()
    
    # Get persona names
    persona_ids = {e.persona_id for e in engagements}
    personas_result = await db.execute(
        select(Persona).where(Persona.id.in_(persona_ids))
    )
    personas = {p.id: p.name for p in personas_result.scalars().all()}
    
    return [
        ActivityLogEntry(
            id=e.id,
            persona_id=e.persona_id,
            persona_name=personas.get(e.persona_id, "Unknown"),
            action_type=e.engagement_type.value,
            target_url=e.target_url,
            details=e.comment_text if e.engagement_type == EngagementType.COMMENT else None,
            created_at=e.created_at,
        )
        for e in engagements
    ]

