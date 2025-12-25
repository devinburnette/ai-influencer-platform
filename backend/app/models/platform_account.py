"""Platform account database model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Platform(str, Enum):
    """Supported social media platforms."""
    INSTAGRAM = "instagram"
    TWITTER = "twitter"
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"


class PlatformAccount(Base):
    """Platform account linking a persona to a social media account."""
    
    __tablename__ = "platform_accounts"
    
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
    
    # Platform identification
    platform: Mapped[Platform] = mapped_column(
        SQLEnum(Platform),
        nullable=False,
    )
    
    # Account details
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    platform_user_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    profile_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Authentication (encrypted in production)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Browser automation session
    session_cookies: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_browser_session: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Status
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    connection_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Per-platform engagement control
    engagement_paused: Mapped[bool] = mapped_column(Boolean, default=False)  # True = skip this platform for engagements
    posting_paused: Mapped[bool] = mapped_column(Boolean, default=False)  # True = skip this platform for posting
    
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
    persona = relationship("Persona", back_populates="platform_accounts")
    
    def is_token_valid(self) -> bool:
        """Check if the access token is still valid."""
        if not self.access_token or not self.token_expires_at:
            return False
        return datetime.utcnow() < self.token_expires_at
    
    def __repr__(self) -> str:
        return f"<PlatformAccount(id={self.id}, platform={self.platform.value}, username={self.username})>"


