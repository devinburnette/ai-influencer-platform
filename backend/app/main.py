"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import get_settings
from app.database import init_db
from app.api import personas, content, analytics, settings as settings_api, auth

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    logger.info("Starting AI Influencer Platform", app_name=settings.app_name)
    await init_db()
    yield
    logger.info("Shutting down AI Influencer Platform")


app = FastAPI(
    title=settings.app_name,
    description="Platform for building and maintaining autonomous AI social media influencers",
    version="0.1.0",
    lifespan=lifespan,
    redoc_url=None,  # Using Swagger UI only
)

# CORS middleware for dashboard
# Origins can be configured via CORS_ORIGINS env var (comma-separated)
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(personas.router, prefix="/api/personas", tags=["Personas"])
app.include_router(content.router, prefix="/api/content", tags=["Content"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["Settings"])
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "app": settings.app_name}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }



