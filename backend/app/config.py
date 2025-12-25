"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "AI Influencer Platform"
    debug: bool = False
    secret_key: str = "dev-secret-key-change-in-production"

    # Database
    database_url: str = "postgresql://aip_user:aip_password@localhost:5432/ai_influencer"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # AI Providers
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    default_ai_provider: str = "openai"  # or "anthropic"

    # Instagram (Meta)
    meta_app_id: Optional[str] = None
    meta_app_secret: Optional[str] = None
    
    # Twitter/X
    twitter_api_key: Optional[str] = None
    twitter_api_secret: Optional[str] = None
    twitter_access_token: Optional[str] = None
    twitter_access_token_secret: Optional[str] = None
    twitter_bearer_token: Optional[str] = None
    
    # Higgsfield (Image Generation)
    higgsfield_api_key: Optional[str] = None
    higgsfield_api_secret: Optional[str] = None
    higgsfield_character_id: Optional[str] = None  # Default character ID (can be overridden per persona)

    # Rate Limiting (daily limits per persona)
    max_posts_per_day: int = 3
    max_likes_per_day: int = 100
    max_comments_per_day: int = 30
    max_follows_per_day: int = 20

    # Timing (seconds)
    min_action_delay: int = 30
    max_action_delay: int = 300

    # Media Storage
    media_storage_path: str = "/app/media"

    @property
    def async_database_url(self) -> str:
        """Get async database URL for SQLAlchemy async engine."""
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


