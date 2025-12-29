"""Persona database model."""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import String, Text, Boolean, Integer, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PersonaVoice:
    """Voice configuration for a persona (stored as JSON)."""
    
    def __init__(
        self,
        tone: str = "friendly",
        vocabulary_level: str = "casual",
        emoji_usage: str = "moderate",
        hashtag_style: str = "relevant",
        signature_phrases: Optional[List[str]] = None,
    ):
        self.tone = tone
        self.vocabulary_level = vocabulary_level
        self.emoji_usage = emoji_usage
        self.hashtag_style = hashtag_style
        self.signature_phrases = signature_phrases or []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON storage."""
        return {
            "tone": self.tone,
            "vocabulary_level": self.vocabulary_level,
            "emoji_usage": self.emoji_usage,
            "hashtag_style": self.hashtag_style,
            "signature_phrases": self.signature_phrases,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "PersonaVoice":
        """Create from dictionary."""
        return cls(
            tone=data.get("tone", "friendly"),
            vocabulary_level=data.get("vocabulary_level", "casual"),
            emoji_usage=data.get("emoji_usage", "moderate"),
            hashtag_style=data.get("hashtag_style", "relevant"),
            signature_phrases=data.get("signature_phrases", []),
        )


class Persona(Base):
    """AI Persona model representing an AI influencer."""
    
    __tablename__ = "personas"
    
    # Primary key
    id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Identity
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    profile_picture_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Niche and interests
    niche: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    
    # Voice configuration (stored as JSON)
    _voice: Mapped[dict] = mapped_column("voice", JSON, nullable=False, default=dict)
    
    @property
    def voice(self) -> PersonaVoice:
        """Get voice configuration."""
        return PersonaVoice.from_dict(self._voice)
    
    @voice.setter
    def voice(self, value: PersonaVoice):
        """Set voice configuration."""
        self._voice = value.to_dict()
    
    # AI configuration
    ai_provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="openai",
    )
    
    # Higgsfield image generation character ID (for Soul model)
    higgsfield_character_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    
    # Custom prompt templates (optional - uses default if not set)
    # Supports placeholders: {name}, {bio}, {niche}, {tone}, {vocabulary_level}, {emoji_usage}, {hashtag_style}
    content_prompt_template: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    comment_prompt_template: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    # Image generation prompt template
    # Supports placeholders: {caption}, {niche}, {name}, {style_hints}
    image_prompt_template: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # DM response prompt template
    # Supports placeholders: {name}, {bio}, {niche}, {message}, {sender_name}, {conversation_history}
    dm_prompt_template: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Per-persona engagement limits (overrides global settings if set)
    max_likes_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_comments_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_follows_per_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # DM settings
    dm_auto_respond: Mapped[bool] = mapped_column(Boolean, default=False)
    dm_response_delay_min: Mapped[int] = mapped_column(Integer, default=30)  # Minimum seconds before responding
    dm_response_delay_max: Mapped[int] = mapped_column(Integer, default=300)  # Maximum seconds before responding
    dm_max_responses_per_day: Mapped[int] = mapped_column(Integer, default=50)
    dm_responses_today: Mapped[int] = mapped_column(Integer, default=0)
    
    # Scheduling
    posting_schedule: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="0 9,13,18 * * *",  # 9am, 1pm, 6pm daily
    )
    engagement_hours_start: Mapped[int] = mapped_column(Integer, default=8)
    engagement_hours_end: Mapped[int] = mapped_column(Integer, default=22)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    
    # Behavior settings
    auto_approve_content: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Stats (updated periodically)
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    following_count: Mapped[int] = mapped_column(Integer, default=0)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Rate limit tracking (daily counts, reset at midnight)
    posts_today: Mapped[int] = mapped_column(Integer, default=0)
    likes_today: Mapped[int] = mapped_column(Integer, default=0)
    comments_today: Mapped[int] = mapped_column(Integer, default=0)
    follows_today: Mapped[int] = mapped_column(Integer, default=0)
    last_rate_limit_reset: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )
    
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
    
    # Relationships
    platform_accounts = relationship(
        "PlatformAccount",
        back_populates="persona",
        cascade="all, delete-orphan",
    )
    content = relationship(
        "Content",
        back_populates="persona",
        cascade="all, delete-orphan",
    )
    engagements = relationship(
        "Engagement",
        back_populates="persona",
        cascade="all, delete-orphan",
    )
    conversations = relationship(
        "Conversation",
        back_populates="persona",
        cascade="all, delete-orphan",
    )
    
    def reset_daily_limits(self):
        """Reset daily rate limit counters."""
        self.posts_today = 0
        self.likes_today = 0
        self.comments_today = 0
        self.follows_today = 0
        self.dm_responses_today = 0
        self.last_rate_limit_reset = datetime.utcnow()
    
    def __repr__(self) -> str:
        return f"<Persona(id={self.id}, name='{self.name}', active={self.is_active})>"


