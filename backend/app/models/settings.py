"""App settings database model."""

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import String, Integer, Boolean, DateTime, Text, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Base


class AppSettings(Base):
    """Application-wide settings stored in the database."""
    
    __tablename__ = "app_settings"
    
    # Primary key
    id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Setting key (unique identifier)
    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    
    # Setting value (stored as string, parsed based on type)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Value type for parsing
    value_type: Mapped[str] = mapped_column(
        String(20),
        default="string",
    )  # string, integer, boolean, json
    
    # Description for documentation
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
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
    
    def get_value(self):
        """Get the typed value."""
        if self.value_type == "integer":
            return int(self.value)
        elif self.value_type == "boolean":
            return self.value.lower() in ("true", "1", "yes")
        elif self.value_type == "json":
            import json
            return json.loads(self.value)
        return self.value
    
    def set_value(self, val):
        """Set value with proper type conversion."""
        if isinstance(val, bool):
            self.value = str(val).lower()
            self.value_type = "boolean"
        elif isinstance(val, int):
            self.value = str(val)
            self.value_type = "integer"
        elif isinstance(val, (dict, list)):
            import json
            self.value = json.dumps(val)
            self.value_type = "json"
        else:
            self.value = str(val)
            self.value_type = "string"
    
    def __repr__(self) -> str:
        return f"<AppSettings(key={self.key}, value={self.value})>"


# Default automation settings
DEFAULT_AUTOMATION_SETTINGS = {
    "content_generation_hours": {
        "value": 6,
        "type": "integer",
        "description": "Hours between content generation runs",
    },
    "posting_queue_minutes": {
        "value": 15,
        "type": "integer",
        "description": "Minutes between posting queue checks",
    },
    "engagement_cycle_minutes": {
        "value": 30,
        "type": "integer",
        "description": "Minutes between engagement cycles",
    },
    "analytics_sync_hour": {
        "value": 2,
        "type": "integer",
        "description": "Hour (UTC) to run daily analytics sync",
    },
    "daily_reset_hour": {
        "value": 0,
        "type": "integer",
        "description": "Hour (UTC) to reset daily limits",
    },
}

# Default rate limit settings (conservative to avoid detection)
# Note: Engagement limits (likes, comments, follows) are now per-persona only
DEFAULT_RATE_LIMIT_SETTINGS = {
    "max_posts_per_day": {
        "value": 3,
        "type": "integer",
        "description": "Maximum image posts per persona per day",
    },
    "max_video_posts_per_day": {
        "value": 2,
        "type": "integer",
        "description": "Maximum video posts per persona per day",
    },
    "max_stories_per_day": {
        "value": 5,
        "type": "integer",
        "description": "Maximum stories per persona per day",
    },
    "max_reels_per_day": {
        "value": 2,
        "type": "integer",
        "description": "Maximum reels per persona per day",
    },
    "min_action_delay": {
        "value": 30,
        "type": "integer",
        "description": "Minimum seconds between actions",
    },
    "max_action_delay": {
        "value": 120,
        "type": "integer",
        "description": "Maximum seconds between actions",
    },
}

# Default per-persona engagement limits (used when persona doesn't have custom limits set)
DEFAULT_PERSONA_ENGAGEMENT_LIMITS = {
    "max_likes_per_day": 25,
    "max_comments_per_day": 10,
    "max_follows_per_day": 10,
}


async def get_setting_value(db: AsyncSession, key: str, default: Any = None) -> Any:
    """Get a setting value from the database.
    
    Args:
        db: Database session
        key: Setting key
        default: Default value if not found
        
    Returns:
        The setting value, or default if not found
    """
    result = await db.execute(select(AppSettings).where(AppSettings.key == key))
    setting = result.scalar_one_or_none()
    
    if setting:
        return setting.get_value()
    
    # Try to get from defaults
    if key in DEFAULT_RATE_LIMIT_SETTINGS:
        return DEFAULT_RATE_LIMIT_SETTINGS[key]["value"]
    if key in DEFAULT_AUTOMATION_SETTINGS:
        return DEFAULT_AUTOMATION_SETTINGS[key]["value"]
    
    return default


async def get_all_rate_limits(db: AsyncSession) -> Dict[str, int]:
    """Get all rate limit settings from the database.
    
    Args:
        db: Database session
        
    Returns:
        Dictionary with all rate limit settings
    """
    limits = {}
    for key, config in DEFAULT_RATE_LIMIT_SETTINGS.items():
        limits[key] = await get_setting_value(db, key, config["value"])
    return limits

