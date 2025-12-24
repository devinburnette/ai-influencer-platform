"""Engagement database model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EngagementType(str, Enum):
    """Type of engagement action."""
    LIKE = "like"
    COMMENT = "comment"
    FOLLOW = "follow"
    UNFOLLOW = "unfollow"
    STORY_VIEW = "story_view"
    STORY_REACTION = "story_reaction"


class Engagement(Base):
    """Engagement model tracking all actions performed by personas."""
    
    __tablename__ = "engagements"
    
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
    
    # Platform reference
    platform: Mapped[str] = mapped_column(String(50), nullable=False, default="instagram")
    
    # Engagement type
    engagement_type: Mapped[EngagementType] = mapped_column(
        SQLEnum(EngagementType),
        nullable=False,
    )
    
    # Target information
    target_post_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # For comments
    comment_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Scoring/context
    relevance_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    trigger_hashtag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Success tracking
    success: Mapped[bool] = mapped_column(default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    
    # Relationship
    persona = relationship("Persona", back_populates="engagements")
    
    def __repr__(self) -> str:
        return f"<Engagement(id={self.id}, type={self.engagement_type.value}, target={self.target_username})>"

