"""Platform adapters package."""

from app.services.platforms.base import PlatformAdapter, Post, PostResult, Analytics
from app.services.platforms.registry import PlatformRegistry

__all__ = [
    "PlatformAdapter",
    "Post",
    "PostResult",
    "Analytics",
    "PlatformRegistry",
]



