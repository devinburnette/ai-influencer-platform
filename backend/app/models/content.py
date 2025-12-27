"""Content database model."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ContentType(str, Enum):
    """Type of content."""
    POST = "post"
    STORY = "story"
    REEL = "reel"
    CAROUSEL = "carousel"


class ContentStatus(str, Enum):
    """Content status in the pipeline."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    SCHEDULED = "scheduled"
    POSTING = "posting"
    POSTED = "posted"
    FAILED = "failed"
    REJECTED = "rejected"


class Content(Base):
    """Content model for posts, stories, etc."""
    
    __tablename__ = "content"
    
    # Primary key
    id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Foreign key to persona
    persona_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Content type
    content_type: Mapped[ContentType] = mapped_column(
        SQLEnum(ContentType),
        default=ContentType.POST,
    )
    
    # Content data
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    hashtags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    media_urls: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)  # Image URLs
    video_urls: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)  # Video URLs
    
    # Status
    status: Mapped[ContentStatus] = mapped_column(
        SQLEnum(ContentStatus),
        default=ContentStatus.DRAFT,
    )
    
    # Scheduling
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Platform data (legacy single platform)
    platform_post_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    platform_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Multi-platform tracking - stores platforms that have received this content
    # Format: ["twitter", "instagram"]
    posted_platforms: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    
    # Generation metadata
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    generation_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generation_topic: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    
    # Engagement metrics (updated periodically)
    engagement_count: Mapped[int] = mapped_column(Integer, default=0)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    # Relationship
    persona = relationship("Persona", back_populates="content")
    
    def get_full_caption(self) -> str:
        """Get caption with hashtags appended."""
        if self.hashtags:
            hashtag_string = " ".join(f"#{tag}" for tag in self.hashtags)
            return f"{self.caption}\n\n{hashtag_string}"
        return self.caption
    
    def __repr__(self) -> str:
        return f"<Content(id={self.id}, type={self.content_type.value}, status={self.status.value})>"


