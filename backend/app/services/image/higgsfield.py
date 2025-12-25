"""Higgsfield image generation service using the Soul model.

API Reference: https://cloud.higgsfield.ai/models/higgsfield-ai/soul/character/api-reference
"""

import asyncio
from typing import Optional, Dict, Any, List
import structlog
import httpx

from app.config import get_settings

logger = structlog.get_logger()

# Higgsfield API base URL for Soul character model
BASE_URL = "https://platform.higgsfield.ai/higgsfield-ai/soul/character"


class HiggsfieldImageGenerator:
    """Generate images using Higgsfield's Soul character model."""
    
    # Default style ID for realistic social media photos
    DEFAULT_STYLE_ID = "1cb4b936-77bf-4f9a-9039-f3d349a4cdbe"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        character_id: Optional[str] = None,
    ):
        """Initialize Higgsfield client.
        
        Args:
            api_key: Higgsfield API key (defaults to settings)
            api_secret: Higgsfield API secret (defaults to settings)
            character_id: Soul model character/custom reference ID (defaults to settings)
        """
        settings = get_settings()
        self.api_key = api_key or settings.higgsfield_api_key
        self.api_secret = api_secret or settings.higgsfield_api_secret
        self.character_id = character_id or settings.higgsfield_character_id
        self._client: Optional[httpx.AsyncClient] = None
        
        if not self.api_key or not self.api_secret:
            logger.warning("Higgsfield API credentials not fully configured")
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "Content-Type": "application/json",
                    "hf-api-key": self.api_key or "",
                    "hf-secret": self.api_secret or "",
                },
                timeout=120.0,  # Image generation can take a while
            )
        return self._client
    
    @property
    def is_configured(self) -> bool:
        """Check if the service is properly configured."""
        return bool(self.api_key and self.api_secret and self.character_id)
    
    async def generate_image(
        self,
        prompt: str,
        character_id: Optional[str] = None,
        style_id: Optional[str] = None,
        seed: Optional[int] = None,
        batch_size: int = 1,
        resolution: str = "720p",
        aspect_ratio: str = "4:3",
        enhance_prompt: bool = False,
        style_strength: float = 1.0,
        custom_reference_strength: float = 1.0,
        **kwargs,
    ) -> Dict[str, Any]:
        """Generate an image using the Soul character model.
        
        Args:
            prompt: Text description for image generation
            character_id: Custom reference ID for the character (overrides default)
            style_id: Style preset ID (defaults to realistic style)
            seed: Random seed for reproducibility (optional)
            batch_size: Number of images to generate (default 1)
            resolution: Image resolution (720p, 1080p, etc.)
            aspect_ratio: Image aspect ratio (4:3 default, 1:1 for Instagram, 16:9, etc.)
            enhance_prompt: Whether to enhance the prompt with AI (default False)
            style_strength: Strength of style application (0-1)
            custom_reference_strength: Strength of character reference (0-1)
            **kwargs: Additional parameters for the API
            
        Returns:
            Dictionary with:
                - success: bool
                - image_url: str (publicly accessible URL) or image_urls for batch
                - error: str (if failed)
                - generation_id: str (task ID)
        """
        effective_character_id = character_id or self.character_id
        
        if not self.api_key or not self.api_secret:
            return {
                "success": False,
                "image_url": None,
                "error": "Higgsfield API not configured. Set HIGGSFIELD_API_KEY and HIGGSFIELD_API_SECRET.",
            }
        
        if not effective_character_id:
            return {
                "success": False,
                "image_url": None,
                "error": "No character ID configured. Set HIGGSFIELD_CHARACTER_ID or configure per persona.",
            }
        
        try:
            # Use provided seed or default to hardcoded value for consistency
            effective_seed = seed if seed is not None else 776620
            
            logger.info(
                "Generating image with Higgsfield Soul model",
                prompt=prompt[:100],
                character_id=effective_character_id,
                aspect_ratio=aspect_ratio,
                seed=effective_seed,
            )
            
            # Build request payload matching Higgsfield's expected format
            request_data = {
                "seed": effective_seed,
                "prompt": prompt,
                "style_id": style_id or self.DEFAULT_STYLE_ID,
                "batch_size": batch_size,
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
                "enhance_prompt": enhance_prompt,
                "style_strength": style_strength,
                "custom_reference_id": effective_character_id,
                "custom_reference_strength": custom_reference_strength,
            }
            
            # Add any additional parameters
            request_data.update(kwargs)
            
            # Submit generation request
            response = await self.client.post(
                BASE_URL,
                json=request_data,
            )
            response.raise_for_status()
            result = response.json()
            
            logger.info("Higgsfield API response", response=result)
            
            # Handle different response formats
            # The API may return immediately with a task ID or with the result
            
            # Check for task/generation ID (async generation)
            generation_id = (
                result.get("id") or 
                result.get("task_id") or 
                result.get("generation_id") or
                result.get("request_id")
            )
            
            # Check for immediate image URLs
            if result.get("images") or result.get("image_urls"):
                image_urls = result.get("images") or result.get("image_urls", [])
                return {
                    "success": True,
                    "image_url": image_urls[0] if image_urls else None,
                    "image_urls": image_urls,
                    "generation_id": generation_id,
                }
            
            if result.get("image_url") or result.get("url"):
                image_url = result.get("image_url") or result.get("url")
                return {
                    "success": True,
                    "image_url": image_url,
                    "generation_id": generation_id,
                }
            
            # If we have a generation ID but no immediate result, poll for completion
            # Use the status_url if provided by the API
            status_url = result.get("status_url")
            if generation_id or status_url:
                logger.info("Generation started, polling for result", generation_id=generation_id, status_url=status_url)
                image_url = await self._poll_for_completion(generation_id, status_url=status_url)
                
                if image_url:
                    return {
                        "success": True,
                        "image_url": image_url,
                        "generation_id": generation_id,
                    }
                else:
                    return {
                        "success": False,
                        "image_url": None,
                        "error": "Image generation timed out or failed",
                        "generation_id": generation_id,
                    }
            
            # Unknown response format
            logger.warning("Unexpected API response format", response=result)
            return {
                "success": False,
                "image_url": None,
                "error": f"Unexpected API response: {result}",
            }
                
        except httpx.HTTPStatusError as e:
            error_msg = f"Higgsfield API error: {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(error_data))
            except Exception:
                error_msg = e.response.text[:200] if e.response.text else error_msg
            logger.error("Higgsfield API error", error=error_msg, status_code=e.response.status_code)
            return {
                "success": False,
                "image_url": None,
                "error": error_msg,
            }
        except Exception as e:
            logger.error("Image generation failed", error=str(e))
            return {
                "success": False,
                "image_url": None,
                "error": str(e),
            }
    
    async def _poll_for_completion(
        self,
        generation_id: str,
        max_attempts: int = 120,  # 6 minutes max for image generation
        poll_interval: float = 3.0,
        status_url: Optional[str] = None,
    ) -> Optional[str]:
        """Poll for generation completion.
        
        Args:
            generation_id: The generation task ID
            max_attempts: Maximum polling attempts (default 120 = 6 minutes)
            poll_interval: Seconds between polls
            status_url: Direct status URL from API response (preferred)
            
        Returns:
            Image URL if successful, None if timeout/failed
        """
        # Use provided status_url or fall back to common patterns
        if status_url:
            status_urls = [status_url]
        else:
            status_urls = [
                f"{BASE_URL}/status/{generation_id}",
                f"{BASE_URL}/{generation_id}",
                f"{BASE_URL}/generations/{generation_id}",
            ]
        
        for attempt in range(max_attempts):
            for poll_url in status_urls:
                try:
                    # Use full URL if provided, otherwise use client base
                    if poll_url.startswith("http"):
                        response = await self.client.get(poll_url)
                    else:
                        response = await self.client.get(poll_url)
                    
                    if response.status_code == 404:
                        continue  # Try next URL pattern
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    logger.info("Poll response", attempt=attempt, response=result)
                    
                    status = (result.get("status") or "").lower()
                    
                    if status in ["completed", "succeeded", "success", "done", "finished"]:
                        # Try different possible field names for the image URL
                        # Higgsfield returns images as [{'url': '...'}]
                        output = result.get("output") or result.get("result") or {}
                        images = (
                            result.get("images") or 
                            result.get("image_urls") or 
                            output.get("images") or
                            output.get("image_urls") or
                            []
                        )
                        
                        # Extract URL from images array - may be string or dict
                        first_image = images[0] if images else None
                        if isinstance(first_image, dict):
                            first_image_url = first_image.get("url") or first_image.get("image_url")
                        else:
                            first_image_url = first_image
                        
                        image_url = (
                            result.get("image_url") or
                            result.get("url") or
                            output.get("image_url") or
                            output.get("url") or
                            first_image_url
                        )
                        
                        if image_url:
                            logger.info("Image generation completed", image_url=image_url[:50] if image_url else None)
                            return image_url
                        else:
                            logger.warning("Completed but no image URL found", result=result)
                            return None
                    
                    if status in ["failed", "error", "cancelled"]:
                        error = result.get("error") or result.get("message") or "Generation failed"
                        logger.error("Generation failed", error=error)
                        return None
                    
                    # Still processing (queued, processing, running), break inner loop and wait
                    if attempt % 10 == 0:
                        logger.info("Still waiting for image", status=status, attempt=attempt)
                    break
                    
                except httpx.HTTPStatusError:
                    continue
                except Exception as e:
                    logger.warning(
                        "Polling error",
                        generation_id=generation_id,
                        attempt=attempt,
                        error=str(e),
                    )
            
            await asyncio.sleep(poll_interval)
        
        logger.error("Generation timed out", generation_id=generation_id)
        return None
    
    async def generate_for_content(
        self,
        caption: str,
        character_id: Optional[str] = None,
        persona_name: Optional[str] = None,
        persona_niche: Optional[List[str]] = None,
        aspect_ratio: str = "4:3",
    ) -> Dict[str, Any]:
        """Generate an image appropriate for a social media post.
        
        This method creates an optimized prompt for social media content
        based on the post caption.
        
        Args:
            caption: The post caption to generate an image for
            character_id: Custom reference ID (overrides default)
            persona_name: Name of the persona (for context)
            persona_niche: List of niche topics
            aspect_ratio: Image aspect ratio (default "4:3")
            
        Returns:
            Dictionary with success, image_url, and error fields
        """
        # Create an image-generation-friendly prompt from the caption
        # The Soul model works best with descriptive visual prompts
        prompt_parts = [
            "A candid, spontaneous photo of a young, mixed race, slim female with naturally styled hair and focused, relaxed expression.",
        ]
        
        # Add the caption as the scene description
        prompt_parts.append(caption)
        
        # Add constraint to avoid hands
        prompt_parts.append("Absolutely no hands in the image!")
        
        prompt = " ".join(prompt_parts)
        
        return await self.generate_image(
            prompt=prompt,
            character_id=character_id,
            aspect_ratio=aspect_ratio,
            enhance_prompt=False,
        )
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance for convenience
_generator: Optional[HiggsfieldImageGenerator] = None


def get_image_generator(character_id: Optional[str] = None) -> HiggsfieldImageGenerator:
    """Get or create the image generator instance.
    
    Args:
        character_id: Optional character ID to use (for persona-specific generation)
    """
    global _generator
    if _generator is None or character_id:
        # Create new instance if we need a specific character ID
        return HiggsfieldImageGenerator(character_id=character_id)
    return _generator
