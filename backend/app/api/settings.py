"""Settings API endpoints."""

from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings, Settings
from app.database import get_db
from app.models.settings import AppSettings, DEFAULT_AUTOMATION_SETTINGS, DEFAULT_RATE_LIMIT_SETTINGS

router = APIRouter()


class RateLimitsResponse(BaseModel):
    """Rate limits configuration."""
    max_posts_per_day: int
    max_likes_per_day: int
    max_comments_per_day: int
    max_follows_per_day: int
    min_action_delay: int
    max_action_delay: int


class RateLimitsUpdate(BaseModel):
    """Update rate limits."""
    max_posts_per_day: Optional[int] = Field(None, ge=1, le=100)
    max_likes_per_day: Optional[int] = Field(None, ge=1, le=1000)
    max_comments_per_day: Optional[int] = Field(None, ge=1, le=500)
    max_follows_per_day: Optional[int] = Field(None, ge=1, le=200)
    min_action_delay: Optional[int] = Field(None, ge=1, le=300)
    max_action_delay: Optional[int] = Field(None, ge=5, le=600)


class ApiKeysStatus(BaseModel):
    """API keys configuration status."""
    openai_configured: bool
    anthropic_configured: bool
    twitter_configured: bool
    meta_configured: bool


class SystemStatus(BaseModel):
    """System status information."""
    database_connected: bool
    redis_connected: bool
    celery_workers_active: int
    api_keys: ApiKeysStatus
    rate_limits: RateLimitsResponse


async def get_rate_limit_setting(db: AsyncSession, key: str) -> int:
    """Get a rate limit setting from DB, falling back to defaults."""
    result = await db.execute(select(AppSettings).where(AppSettings.key == key))
    setting = result.scalar_one_or_none()
    
    if setting:
        return setting.get_value()
    
    # Fall back to default if not in DB
    if key in DEFAULT_RATE_LIMIT_SETTINGS:
        return DEFAULT_RATE_LIMIT_SETTINGS[key]["value"]
    
    # Final fallback to config
    config = get_settings()
    return getattr(config, key, 0)


@router.get("/rate-limits", response_model=RateLimitsResponse)
async def get_rate_limits(db: AsyncSession = Depends(get_db)):
    """Get current rate limit configuration from database."""
    # Ensure all rate limit settings exist in DB
    for key, config in DEFAULT_RATE_LIMIT_SETTINGS.items():
        await get_or_create_setting(
            db, key, config["value"], config.get("description", "")
        )
    await db.commit()
    
    return RateLimitsResponse(
        max_posts_per_day=await get_rate_limit_setting(db, "max_posts_per_day"),
        max_likes_per_day=await get_rate_limit_setting(db, "max_likes_per_day"),
        max_comments_per_day=await get_rate_limit_setting(db, "max_comments_per_day"),
        max_follows_per_day=await get_rate_limit_setting(db, "max_follows_per_day"),
        min_action_delay=await get_rate_limit_setting(db, "min_action_delay"),
        max_action_delay=await get_rate_limit_setting(db, "max_action_delay"),
    )


@router.patch("/rate-limits", response_model=RateLimitsResponse)
async def update_rate_limits(
    updates: RateLimitsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update rate limit configuration."""
    update_data = updates.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        if value is not None:
            result = await db.execute(select(AppSettings).where(AppSettings.key == key))
            setting = result.scalar_one_or_none()
            
            if setting:
                setting.value = str(value)
            else:
                setting = AppSettings(
                    key=key,
                    value=str(value),
                    value_type="integer",
                    description=DEFAULT_RATE_LIMIT_SETTINGS.get(key, {}).get("description", ""),
                )
                db.add(setting)
    
    await db.commit()
    
    # Return updated settings
    return await get_rate_limits(db)


@router.get("/api-keys/status", response_model=ApiKeysStatus)
async def get_api_keys_status():
    """Get API keys configuration status (not the keys themselves)."""
    settings = get_settings()
    return ApiKeysStatus(
        openai_configured=bool(settings.openai_api_key),
        anthropic_configured=bool(settings.anthropic_api_key),
        # Only check app-level credentials, not user-level (those are per-persona)
        twitter_configured=bool(
            settings.twitter_api_key and 
            settings.twitter_api_secret
        ),
        meta_configured=bool(settings.meta_app_id and settings.meta_app_secret),
    )


@router.get("/status", response_model=SystemStatus)
async def get_system_status():
    """Get overall system status."""
    settings = get_settings()
    
    # Check database connection
    database_connected = True
    try:
        from app.database import engine
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
    except Exception:
        database_connected = False
    
    # Check Redis connection
    redis_connected = True
    try:
        import redis
        r = redis.from_url(settings.redis_url)
        r.ping()
    except Exception:
        redis_connected = False
    
    # Check Celery workers
    celery_workers_active = 0
    try:
        from app.workers.celery_app import celery_app
        inspect = celery_app.control.inspect()
        active = inspect.active()
        if active:
            celery_workers_active = len(active)
    except Exception:
        pass
    
    return SystemStatus(
        database_connected=database_connected,
        redis_connected=redis_connected,
        celery_workers_active=celery_workers_active,
        api_keys=ApiKeysStatus(
            openai_configured=bool(settings.openai_api_key),
            anthropic_configured=bool(settings.anthropic_api_key),
            twitter_configured=bool(
                settings.twitter_api_key and 
                settings.twitter_api_secret and 
                settings.twitter_access_token and 
                settings.twitter_access_token_secret
            ),
            meta_configured=bool(settings.meta_app_id and settings.meta_app_secret),
        ),
        rate_limits=RateLimitsResponse(
            max_posts_per_day=settings.max_posts_per_day,
            max_likes_per_day=settings.max_likes_per_day,
            max_comments_per_day=settings.max_comments_per_day,
            max_follows_per_day=settings.max_follows_per_day,
            min_action_delay=settings.min_action_delay,
            max_action_delay=settings.max_action_delay,
        ),
    )


# Automation Settings Models
class AutomationSettingsResponse(BaseModel):
    """Automation schedule settings."""
    content_generation_hours: int = Field(default=6, description="Hours between content generation")
    posting_queue_minutes: int = Field(default=15, description="Minutes between posting queue checks")
    engagement_cycle_minutes: int = Field(default=30, description="Minutes between engagement cycles")
    analytics_sync_hour: int = Field(default=2, description="Hour (UTC) for daily analytics sync")
    daily_reset_hour: int = Field(default=0, description="Hour (UTC) to reset daily limits")


class AutomationSettingsUpdate(BaseModel):
    """Update automation settings."""
    content_generation_hours: Optional[int] = Field(None, ge=1, le=24)
    posting_queue_minutes: Optional[int] = Field(None, ge=5, le=60)
    engagement_cycle_minutes: Optional[int] = Field(None, ge=15, le=120)
    analytics_sync_hour: Optional[int] = Field(None, ge=0, le=23)
    daily_reset_hour: Optional[int] = Field(None, ge=0, le=23)


async def get_or_create_setting(db: AsyncSession, key: str, default_value: int, description: str = "") -> AppSettings:
    """Get a setting from DB or create with default value."""
    result = await db.execute(select(AppSettings).where(AppSettings.key == key))
    setting = result.scalar_one_or_none()
    
    if not setting:
        setting = AppSettings(
            key=key,
            value=str(default_value),
            value_type="integer",
            description=description,
        )
        db.add(setting)
        await db.flush()
    
    return setting


@router.get("/automation", response_model=AutomationSettingsResponse)
async def get_automation_settings(db: AsyncSession = Depends(get_db)):
    """Get automation schedule settings."""
    settings = {}
    
    for key, config in DEFAULT_AUTOMATION_SETTINGS.items():
        setting = await get_or_create_setting(
            db, key, config["value"], config.get("description", "")
        )
        settings[key] = setting.get_value()
    
    await db.commit()
    
    return AutomationSettingsResponse(**settings)


@router.patch("/automation", response_model=AutomationSettingsResponse)
async def update_automation_settings(
    updates: AutomationSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update automation schedule settings."""
    update_data = updates.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        if value is not None:
            result = await db.execute(select(AppSettings).where(AppSettings.key == key))
            setting = result.scalar_one_or_none()
            
            if setting:
                setting.value = str(value)
            else:
                setting = AppSettings(
                    key=key,
                    value=str(value),
                    value_type="integer",
                )
                db.add(setting)
    
    await db.commit()
    
    # Return updated settings
    return await get_automation_settings(db)


@router.post("/automation/apply")
async def apply_automation_settings(db: AsyncSession = Depends(get_db)):
    """Signal that automation settings should be reloaded.
    
    Note: In production, this would trigger a Celery beat reload.
    For now, it stores a flag that workers can check.
    """
    # Store a flag indicating settings need to be reloaded
    result = await db.execute(
        select(AppSettings).where(AppSettings.key == "schedule_needs_reload")
    )
    setting = result.scalar_one_or_none()
    
    if setting:
        setting.value = "true"
    else:
        setting = AppSettings(
            key="schedule_needs_reload",
            value="true",
            value_type="boolean",
            description="Flag to trigger schedule reload",
        )
        db.add(setting)
    
    await db.commit()
    
    return {"message": "Settings saved. Restart celery-beat to apply changes.", "requires_restart": True}


