"""Conversation and Direct Message database models."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Text, Boolean, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ConversationStatus(str, Enum):
    """Status of a conversation."""
    ACTIVE = "active"
    PAUSED = "paused"  # Human takeover requested
    CLOSED = "closed"
    BLOCKED = "blocked"


class MessageDirection(str, Enum):
    """Direction of a message."""
    INBOUND = "inbound"  # Received from user
    OUTBOUND = "outbound"  # Sent by persona


class MessageStatus(str, Enum):
    """Status of a message."""
    RECEIVED = "received"
    PENDING_RESPONSE = "pending_response"
    RESPONDED = "responded"
    FAILED = "failed"
    IGNORED = "ignored"  # Spam or irrelevant


class Conversation(Base):
    """Represents a DM conversation with a user."""
    
    __tablename__ = "conversations"
    
    id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Link to persona
    persona_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("personas.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Platform info
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # twitter, instagram
    platform_conversation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Other participant info
    participant_id: Mapped[str] = mapped_column(String(100), nullable=False)  # Platform user ID
    participant_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    participant_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    participant_profile_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Conversation state
    status: Mapped[ConversationStatus] = mapped_column(
        SQLEnum(ConversationStatus, values_callable=lambda x: [e.value for e in x]),
        default=ConversationStatus.ACTIVE,
    )
    
    # Tracking
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_response_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # AI context - stores conversation summary for context
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Flags
    is_follower: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    persona = relationship("Persona", back_populates="conversations")
    messages = relationship("DirectMessage", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, platform={self.platform}, participant={self.participant_username})>"


class DirectMessage(Base):
    """Represents a single DM in a conversation."""
    
    __tablename__ = "direct_messages"
    
    id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Link to conversation
    conversation_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Message info
    platform_message_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    direction: Mapped[MessageDirection] = mapped_column(
        SQLEnum(MessageDirection, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    
    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    
    # Status
    status: Mapped[MessageStatus] = mapped_column(
        SQLEnum(MessageStatus, values_callable=lambda x: [e.value for e in x]),
        default=MessageStatus.RECEIVED,
    )
    
    # AI generation metadata (for outbound messages)
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    generation_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationship
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self) -> str:
        return f"<DirectMessage(id={self.id}, direction={self.direction.value}, content={self.content[:50]}...)>"

