"""Platform adapter registry for managing multiple platforms."""

from typing import Dict, Type, Optional
import structlog

from app.services.platforms.base import PlatformAdapter

logger = structlog.get_logger()


class PlatformRegistry:
    """Registry for platform adapters."""

    _adapters: Dict[str, Type[PlatformAdapter]] = {}
    _instances: Dict[str, PlatformAdapter] = {}

    @classmethod
    def register(cls, name: str, adapter_class: Type[PlatformAdapter]):
        """Register a platform adapter.
        
        Args:
            name: Platform name (e.g., "instagram")
            adapter_class: Adapter class to register
        """
        cls._adapters[name.lower()] = adapter_class
        logger.info("Registered platform adapter", platform=name)

    @classmethod
    def get_adapter_class(cls, name: str) -> Optional[Type[PlatformAdapter]]:
        """Get an adapter class by name.
        
        Args:
            name: Platform name
            
        Returns:
            Adapter class if registered
        """
        return cls._adapters.get(name.lower())

    @classmethod
    def create_adapter(cls, name: str, **kwargs) -> Optional[PlatformAdapter]:
        """Create a new adapter instance.
        
        Args:
            name: Platform name
            **kwargs: Arguments to pass to adapter constructor
            
        Returns:
            Adapter instance if platform is registered
        """
        adapter_class = cls.get_adapter_class(name)
        if adapter_class:
            return adapter_class(**kwargs)
        return None

    @classmethod
    def get_or_create_instance(
        cls,
        name: str,
        instance_key: str,
        **kwargs,
    ) -> Optional[PlatformAdapter]:
        """Get or create a cached adapter instance.
        
        Args:
            name: Platform name
            instance_key: Unique key for this instance (e.g., account ID)
            **kwargs: Arguments for creating new instance
            
        Returns:
            Cached or new adapter instance
        """
        cache_key = f"{name}:{instance_key}"
        
        if cache_key not in cls._instances:
            adapter = cls.create_adapter(name, **kwargs)
            if adapter:
                cls._instances[cache_key] = adapter
        
        return cls._instances.get(cache_key)

    @classmethod
    def list_platforms(cls) -> list:
        """List all registered platform names."""
        return list(cls._adapters.keys())

    @classmethod
    async def close_all(cls):
        """Close all cached adapter instances."""
        for instance in cls._instances.values():
            try:
                await instance.close()
            except Exception as e:
                logger.error("Error closing adapter", error=str(e))
        cls._instances.clear()


# Auto-register adapters when module is imported
def _register_builtin_adapters():
    """Register built-in platform adapters."""
    # Register Instagram adapter
    try:
        from app.services.platforms.instagram.adapter import InstagramAdapter
        PlatformRegistry.register("instagram", InstagramAdapter)
    except ImportError:
        logger.warning("Instagram adapter not available")
    
    # Register Twitter/X adapter
    try:
        from app.services.platforms.twitter.adapter import TwitterAdapter
        PlatformRegistry.register("twitter", TwitterAdapter)
    except ImportError:
        logger.warning("Twitter adapter not available")
    
    # Register Fanvue adapter
    try:
        from app.services.platforms.fanvue.adapter import FanvueAdapter
        PlatformRegistry.register("fanvue", FanvueAdapter)
    except ImportError:
        logger.warning("Fanvue adapter not available")


# Register on import
_register_builtin_adapters()


