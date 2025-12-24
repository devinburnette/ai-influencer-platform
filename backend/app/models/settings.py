"""App settings database model."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

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

