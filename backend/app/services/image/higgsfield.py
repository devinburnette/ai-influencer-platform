"""Higgsfield image generation service using the Soul model.

API Reference: https://cloud.higgsfield.ai/models/higgsfield-ai/soul/character/api-reference
"""

import asyncio
import random
from typing import Optional, Dict, Any, List
import structlog
import httpx

from app.config import get_settings

logger = structlog.get_logger()

# Higgsfield API base URL for Soul character model
BASE_URL = "https://platform.higgsfield.ai/higgsfield-ai/soul/character"


class HiggsfieldImageGenerator:
    """Generate images using Higgsfield's Soul character model."""
    
    # Available style IDs for realistic social media photos
    STYLE_IDS = [
        "1cb4b936-77bf-4f9a-9039-f3d349a4cdbe",
        "1b798b54-03da-446a-93bf-12fcba1050d7",
        "464ea177-8d40-4940-8d9d-b438bab269c7",
    ]
    
    @classmethod
    def get_random_style_id(cls) -> str:
        """Get a randomly selected style ID."""
        return random.choice(cls.STYLE_IDS)
    
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
        aspect_ratio: str = "1:1",
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
            aspect_ratio: Image aspect ratio (1:1 default for Instagram, 4:3, 16:9, etc.)
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
            
            # Randomly select style ID if not provided
            effective_style_id = style_id or self.get_random_style_id()
            
            logger.info(
                "Using style ID",
                style_id=effective_style_id,
            )
            
            # Build request payload matching Higgsfield's expected format
            request_data = {
                "seed": effective_seed,
                "prompt": prompt,
                "style_id": effective_style_id,
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
        aspect_ratio: str = "1:1",
        image_prompt_template: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate an image appropriate for a social media post.
        
        This method creates an optimized prompt for social media content
        based on the post caption.
        
        Args:
            caption: The post caption to generate an image for
            character_id: Custom reference ID (overrides default)
            persona_name: Name of the persona (for context)
            persona_niche: List of niche topics
            aspect_ratio: Image aspect ratio (default "1:1")
            image_prompt_template: Optional custom prompt template with placeholders
            
        Returns:
            Dictionary with success, image_url, and error fields
        """
        # Use custom template if provided
        if image_prompt_template:
            try:
                prompt = image_prompt_template.format(
                    caption=caption,
                    name=persona_name or "the person",
                    niche=", ".join(persona_niche) if persona_niche else "lifestyle",
                    style_hints="high quality, natural lighting, candid",
                )
                logger.info("Using custom image prompt template")
            except KeyError as e:
                logger.warning(f"Invalid placeholder in image template: {e}, using default")
                image_prompt_template = None
        
        if not image_prompt_template:
            # Default prompt - create an image-generation-friendly prompt from the caption
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
    
    # ===== VIDEO GENERATION =====
    
    # Video generation models (in order of preference)
    VIDEO_MODELS = [
        "wan-26/image-to-video",
    ]
    
    # Base URL for video generation (different from Soul character model)
    VIDEO_BASE_URL = "https://platform.higgsfield.ai"
    
    async def generate_video(
        self,
        image_url: str,
        motion_prompt: str,
        duration: int = 5,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a video from an image using Higgsfield's image-to-video API.
        
        Args:
            image_url: URL of the source image
            motion_prompt: Description of desired motion/animation
            duration: Video duration in seconds (default 5)
            model: Specific model to use (defaults to trying models in order)
            
        Returns:
            Dictionary with success, video_url, and error fields
        """
        if not self.api_key or not self.api_secret:
            return {
                "success": False,
                "video_url": None,
                "error": "Higgsfield API credentials not configured",
            }
        
        models_to_try = [model] if model else self.VIDEO_MODELS
        
        for video_model in models_to_try:
            logger.info(
                "Attempting video generation",
                model=video_model,
                image_url=image_url[:100],
                motion_prompt=motion_prompt[:100],
            )
            
            result = await self._generate_video_with_model(
                image_url=image_url,
                motion_prompt=motion_prompt,
                duration=duration,
                model=video_model,
            )
            
            if result["success"]:
                return result
            
            logger.warning(
                "Video model failed, trying next",
                model=video_model,
                error=result.get("error"),
            )
        
        return {
            "success": False,
            "video_url": None,
            "error": f"All video models failed. Last error: {result.get('error')}",
        }
    
    async def _generate_video_with_model(
        self,
        image_url: str,
        motion_prompt: str,
        duration: int,
        model: str,
    ) -> Dict[str, Any]:
        """Generate video using a specific model.
        
        Args:
            image_url: Source image URL
            motion_prompt: Motion description
            duration: Video duration in seconds
            model: The model identifier
            
        Returns:
            Dictionary with success, video_url, generation_id, and error fields
        """
        try:
            endpoint = f"{self.VIDEO_BASE_URL}/{model}"
            
            request_data = {
                "image_url": image_url,
                "prompt": motion_prompt,
                "duration": duration,
                "prompt_extend": False,  # Enable prompt enhancement
                "seed": 776620,  # Consistent seed for reproducibility
            }
            
            logger.info("Sending video generation request", endpoint=endpoint, data=request_data)
            
            response = await self.client.post(endpoint, json=request_data)
            response.raise_for_status()
            result = response.json()
            
            logger.info("Video generation response", response=result)
            
            # Extract generation ID and check for immediate result
            generation_id = result.get("generation_id") or result.get("request_id") or result.get("id")
            video_url = (
                result.get("video_url") or
                result.get("video", {}).get("url") or  # Higgsfield returns video.url
                result.get("output", {}).get("video_url")
            )
            status_url = result.get("status_url")
            
            # If video is ready immediately
            if video_url:
                return {
                    "success": True,
                    "video_url": video_url,
                    "generation_id": generation_id,
                }
            
            # Poll for completion
            if generation_id or status_url:
                logger.info("Video generation started, polling for result", generation_id=generation_id)
                video_url = await self._poll_for_video_completion(
                    generation_id=generation_id,
                    status_url=status_url,
                    model=model,
                )
                
                if video_url:
                    return {
                        "success": True,
                        "video_url": video_url,
                        "generation_id": generation_id,
                    }
                else:
                    return {
                        "success": False,
                        "video_url": None,
                        "error": "Video generation timed out or failed",
                        "generation_id": generation_id,
                    }
            
            return {
                "success": False,
                "video_url": None,
                "error": f"Unexpected API response: {result}",
            }
            
        except httpx.HTTPStatusError as e:
            error_msg = f"Higgsfield video API error: {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_msg = error_data.get("error", {}).get("message", str(error_data))
            except Exception:
                error_msg = e.response.text[:200] if e.response.text else error_msg
            logger.error("Video API error", error=error_msg, status_code=e.response.status_code)
            return {
                "success": False,
                "video_url": None,
                "error": error_msg,
            }
        except Exception as e:
            logger.error("Video generation failed", error=str(e))
            return {
                "success": False,
                "video_url": None,
                "error": str(e),
            }
    
    async def _poll_for_video_completion(
        self,
        generation_id: str,
        status_url: Optional[str] = None,
        model: Optional[str] = None,
        max_attempts: int = 180,  # 9 minutes max for video generation
        poll_interval: float = 3.0,
    ) -> Optional[str]:
        """Poll for video generation completion.
        
        Args:
            generation_id: The generation task ID
            status_url: Direct status URL from API response
            model: The model used (for constructing status URL)
            max_attempts: Maximum polling attempts
            poll_interval: Seconds between polls
            
        Returns:
            Video URL if successful, None if timeout/failed
        """
        # Build possible status URLs
        if status_url:
            status_urls = [status_url]
        elif model:
            status_urls = [
                f"{self.VIDEO_BASE_URL}/{model}/status/{generation_id}",
                f"{self.VIDEO_BASE_URL}/{model}/{generation_id}",
                f"{self.VIDEO_BASE_URL}/generations/{generation_id}",
            ]
        else:
            status_urls = [f"{self.VIDEO_BASE_URL}/generations/{generation_id}"]
        
        for attempt in range(max_attempts):
            for poll_url in status_urls:
                try:
                    response = await self.client.get(poll_url)
                    
                    if response.status_code == 404:
                        continue
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    logger.debug("Video poll response", attempt=attempt, response=result)
                    
                    status = (result.get("status") or "").lower()
                    
                    # Check for completion
                    if status in ("completed", "succeeded", "success", "done"):
                        video_url = (
                            result.get("video_url") or
                            result.get("video", {}).get("url") or  # Higgsfield returns video.url
                            result.get("output", {}).get("video_url") or
                            result.get("result", {}).get("video_url")
                        )
                        if video_url:
                            logger.info("Video generation completed", video_url=video_url[:100])
                            return video_url
                    
                    # Check for failure
                    if status in ("failed", "error", "cancelled"):
                        error = result.get("error") or result.get("message") or "Unknown error"
                        logger.error("Video generation failed", status=status, error=error)
                        return None
                    
                    # Still processing
                    if status in ("processing", "pending", "running", "in_progress", "queued"):
                        break  # Continue polling
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code != 404:
                        logger.warning("Video poll error", status_code=e.response.status_code)
                except Exception as e:
                    logger.warning("Video poll exception", error=str(e))
            
            await asyncio.sleep(poll_interval)
        
        logger.error("Video generation timed out", generation_id=generation_id)
        return None
    
    async def generate_video_for_content(
        self,
        caption: str,
        character_id: Optional[str] = None,
        persona_name: Optional[str] = None,
        persona_niche: Optional[List[str]] = None,
        aspect_ratio: str = "9:16",  # Vertical for Reels/Stories
        image_prompt_template: Optional[str] = None,
        video_duration: int = 5,
    ) -> Dict[str, Any]:
        """Generate a video for social media content (full pipeline).
        
        This method:
        1. Generates an image using the Soul character model
        2. Uses that image to generate a video with motion
        
        Args:
            caption: The post caption to base content on
            character_id: Custom character ID for image generation
            persona_name: Name of the persona
            persona_niche: List of niche topics
            aspect_ratio: Video aspect ratio (default 9:16 for vertical)
            image_prompt_template: Optional custom image prompt template
            video_duration: Video duration in seconds (default 5)
            
        Returns:
            Dictionary with success, video_url, image_url, and error fields
        """
        logger.info(
            "Starting video generation pipeline",
            caption=caption[:50],
            persona=persona_name,
        )
        
        # Step 1: Generate the base image
        image_result = await self.generate_for_content(
            caption=caption,
            character_id=character_id,
            persona_name=persona_name,
            persona_niche=persona_niche,
            aspect_ratio=aspect_ratio,
            image_prompt_template=image_prompt_template,
        )
        
        if not image_result["success"] or not image_result.get("image_url"):
            return {
                "success": False,
                "video_url": None,
                "image_url": None,
                "error": f"Image generation failed: {image_result.get('error')}",
            }
        
        image_url = image_result["image_url"]
        logger.info("Image generated for video", image_url=image_url[:100])
        
        # Step 2: Use the same caption as the video prompt
        # This ensures consistency between the image and video content
        video_prompt = caption
        
        # Step 3: Generate the video
        video_result = await self.generate_video(
            image_url=image_url,
            motion_prompt=video_prompt,
            duration=video_duration,
        )
        
        if video_result["success"]:
            return {
                "success": True,
                "video_url": video_result["video_url"],
                "image_url": image_url,
                "generation_id": video_result.get("generation_id"),
            }
        else:
            # Return the image even if video fails - can still use it
            return {
                "success": False,
                "video_url": None,
                "image_url": image_url,
                "error": f"Video generation failed: {video_result.get('error')}",
            }
    
    def _create_motion_prompt(
        self,
        caption: str,
        niche: Optional[List[str]] = None,
    ) -> str:
        """Create a motion prompt for video generation based on caption.
        
        Args:
            caption: The original post caption
            niche: List of niche topics for context
            
        Returns:
            Motion prompt string
        """
        # Extract key themes for motion
        niche_str = ", ".join(niche) if niche else "lifestyle"
        
        # Create a subtle, natural motion prompt
        motion_prompt = (
            f"Subtle natural movement, gentle motion. "
            f"The subject breathes naturally and has slight movements. "
            f"Smooth cinematic camera with very slow push in. "
            f"Natural lighting shifts subtly. "
            f"Professional video quality, 4K, shallow depth of field. "
            f"Context: {niche_str}. "
            f"Scene: {caption[:150]}"
        )
        
        return motion_prompt
    
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
