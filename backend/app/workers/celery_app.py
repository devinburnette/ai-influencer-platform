"""Celery application configuration."""

import os
from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_influencer",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks.content_tasks",
        "app.workers.tasks.posting_tasks",
        "app.workers.tasks.engagement_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/New_York",  # Use Eastern Time for all schedules
    enable_utc=False,  # Display times in local timezone
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3000,  # 50 minutes soft limit
    worker_prefetch_multiplier=1,  # One task at a time for browser automation
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


def get_schedule_from_db():
    """Load schedule settings from database.
    
    Falls back to defaults if database is not available.
    """
    # Default values
    content_gen_hours = 6
    posting_queue_mins = 15
    engagement_mins = 30
    analytics_hour = 2
    daily_reset_hour = 0
    
    try:
        # Use synchronous database access for Celery beat
        import psycopg2
        from urllib.parse import urlparse
        
        db_url = os.environ.get("DATABASE_URL", settings.database_url)
        # Convert async URL to sync if needed
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        
        parsed = urlparse(db_url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            dbname=parsed.path.lstrip("/"),
        )
        
        cursor = conn.cursor()
        
        # Try to fetch settings
        settings_map = {
            "content_generation_hours": "content_gen_hours",
            "posting_queue_minutes": "posting_queue_mins",
            "engagement_cycle_minutes": "engagement_mins",
            "analytics_sync_hour": "analytics_hour",
            "daily_reset_hour": "daily_reset_hour",
        }
        
        for key, var_name in settings_map.items():
            try:
                cursor.execute(
                    "SELECT value FROM app_settings WHERE key = %s",
                    (key,)
                )
                result = cursor.fetchone()
                if result:
                    locals()[var_name] = int(result[0])
            except Exception:
                pass
        
        # Re-read the values since locals() assignment doesn't work as expected
        cursor.execute("SELECT key, value FROM app_settings WHERE key IN %s", 
                       (tuple(settings_map.keys()),))
        for row in cursor.fetchall():
            key, value = row
            if key == "content_generation_hours":
                content_gen_hours = int(value)
            elif key == "posting_queue_minutes":
                posting_queue_mins = int(value)
            elif key == "engagement_cycle_minutes":
                engagement_mins = int(value)
            elif key == "analytics_sync_hour":
                analytics_hour = int(value)
            elif key == "daily_reset_hour":
                daily_reset_hour = int(value)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        # Log but don't fail - use defaults
        import structlog
        logger = structlog.get_logger()
        logger.warning("Could not load schedule from database, using defaults", error=str(e))
    
    return {
        "content_generation_hours": content_gen_hours,
        "posting_queue_minutes": posting_queue_mins,
        "engagement_cycle_minutes": engagement_mins,
        "analytics_sync_hour": analytics_hour,
        "daily_reset_hour": daily_reset_hour,
    }


def build_beat_schedule():
    """Build the Celery beat schedule from database settings."""
    sched = get_schedule_from_db()
    
    return {
        # Generate content for active personas
        "generate-content-periodically": {
            "task": "app.workers.tasks.content_tasks.generate_content_batch",
            "schedule": crontab(hour=f"*/{sched['content_generation_hours']}"),
        },
        # Process posting queue
        "process-posting-queue": {
            "task": "app.workers.tasks.posting_tasks.process_posting_queue",
            "schedule": crontab(minute=f"*/{sched['posting_queue_minutes']}"),
        },
        # Run engagement for active personas
        "run-engagement-cycle": {
            "task": "app.workers.tasks.engagement_tasks.run_engagement_cycle",
            "schedule": crontab(minute=f"*/{sched['engagement_cycle_minutes']}"),
        },
        # Reset daily rate limits
        "reset-daily-limits": {
            "task": "app.workers.tasks.engagement_tasks.reset_daily_limits",
            "schedule": crontab(hour=sched['daily_reset_hour'], minute=0),
        },
        # Sync analytics daily
        "sync-analytics": {
            "task": "app.workers.tasks.engagement_tasks.sync_analytics",
            "schedule": crontab(hour=sched['analytics_sync_hour'], minute=0),
        },
        # Unfollow housekeeping - clean up old follows weekly
        "unfollow-housekeeping": {
            "task": "app.workers.tasks.engagement_tasks.unfollow_non_followers",
            "schedule": crontab(day_of_week=0, hour=3, minute=0),  # Sundays at 3 AM
        },
    }


# Beat schedule for periodic tasks - loaded from database
celery_app.conf.beat_schedule = build_beat_schedule()

