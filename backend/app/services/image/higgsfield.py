"""Higgsfield image generation service using the Soul model.

API Reference: https://cloud.higgsfield.ai/models/higgsfield-ai/soul/character/api-reference
"""

import asyncio
import random
from typing import Optional, Dict, Any, List
import structlog
import httpx

from app.config import get_settings
from app.services.ai.base import Message

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
                    
                    if status in ["failed", "error", "cancelled", "nsfw"]:
                        error = result.get("error") or result.get("message") or "Generation failed"
                        if status == "nsfw":
                            logger.warning("Image generation blocked due to NSFW content detection", status=status)
                        else:
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
                # Extract theme from caption to avoid full text rendering
                caption_words = caption.split()[:12]
                caption_theme = " ".join(caption_words) if caption_words else caption
                
                base_prompt = image_prompt_template.format(
                    caption=caption_theme,  # Use theme, not full caption
                    name=persona_name or "the person",
                    niche=", ".join(persona_niche) if persona_niche else "lifestyle",
                    style_hints="high quality, natural lighting, candid",
                )
                # ALWAYS prepend NO TEXT instruction, even for custom templates
                prompt = f"CRITICAL: NO TEXT in this image. NO words. NO letters. NO captions. NO watermarks. Completely text-free. {base_prompt} NO TEXT anywhere."
                logger.info("Using custom image prompt template with no-text prefix")
            except KeyError as e:
                logger.warning(f"Invalid placeholder in image template: {e}, using default")
                image_prompt_template = None
        
        if not image_prompt_template:
            # Default prompt - create an image-generation-friendly prompt from the caption
            # The Soul model works best with descriptive visual prompts
            # CRITICAL: Put NO TEXT instruction FIRST - models weight beginning of prompts more heavily
            
            # Extract just a theme from caption, not the full text (to avoid text rendering)
            caption_words = caption.split()[:12]  # Take first 12 words max for theme
            theme_hint = " ".join(caption_words) if caption_words else "lifestyle moment"
            
            prompt_parts = [
                # NO TEXT instruction first and prominently
                "CRITICAL: NO TEXT in this image. NO words. NO letters. NO captions. NO watermarks. NO overlays. Completely text-free image.",
                # Character description
                "A candid, spontaneous photo of a young, mixed race, slim female with naturally styled hair and focused, relaxed expression.",
                # Theme from caption (not raw caption)
                f"Scene theme: {theme_hint}.",
                # Additional constraints
                "Absolutely no hands in the image!",
                "High quality, natural lighting, professional photography.",
                "NO TEXT anywhere in the image. Text-free."
            ]
            
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
        "veo3.1/fast/image-to-video",
        "wan-26/image-to-video",   # Backup model
    ]
    
    # Base URL for video generation (different from Soul character model)
    VIDEO_BASE_URL = "https://platform.higgsfield.ai"
    
    async def generate_video(
        self,
        image_url: str,
        motion_prompt: str,
        duration: int = 5,
        model: Optional[str] = None,
        aspect_ratio: str = "9:16",  # Default vertical for social media
    ) -> Dict[str, Any]:
        """Generate a video from an image using Higgsfield's image-to-video API.
        
        Args:
            image_url: URL of the source image
            motion_prompt: Description of desired motion/animation
            duration: Video duration in seconds (default 5)
            model: Specific model to use (defaults to trying models in order)
            aspect_ratio: Video aspect ratio (default 9:16 for vertical social media)
            
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
                aspect_ratio=aspect_ratio,
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
        aspect_ratio: str = "9:16",  # Default vertical for social media
    ) -> Dict[str, Any]:
        """Generate video using a specific model.
        
        Args:
            image_url: Source image URL
            motion_prompt: Motion description
            duration: Video duration in seconds
            model: The model identifier
            aspect_ratio: Video aspect ratio (default 9:16 for vertical social media)
            
        Returns:
            Dictionary with success, video_url, generation_id, and error fields
        """
        try:
            endpoint = f"{self.VIDEO_BASE_URL}/{model}"
            
            # Build request data based on model
            if "veo3.1" in model:
                # Veo 3.1 uses different parameter format
                # Veo only accepts duration of 4, 6, or 8 seconds
                veo_duration = "6"  # Default to 6 seconds
                if duration <= 4:
                    veo_duration = "4"
                elif duration >= 8:
                    veo_duration = "8"
                else:
                    veo_duration = "6"
                
                request_data = {
                    "image_url": image_url,
                    "prompt": motion_prompt,
                    "duration": veo_duration,
                    "resolution": "720",
                    "aspect_ratio": aspect_ratio,
                    "generate_audio": True,
                }
            else:
                # Wan and other models use original format
                request_data = {
                    "image_url": image_url,
                    "prompt": motion_prompt,
                    "duration": duration,
                    "prompt_extend": False,
                    "seed": 776620,
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
                    
                    # Check for failure (including NSFW content detection)
                    if status in ("failed", "error", "cancelled", "nsfw"):
                        error = result.get("error") or result.get("message") or "Unknown error"
                        if status == "nsfw":
                            logger.warning("Video generation blocked due to NSFW content detection", status=status)
                            error = "NSFW content detected - will try backup model"
                        else:
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
        
        # Step 1: Generate the base image with a video-optimized prompt
        # Create a cleaner prompt that won't result in text being rendered
        video_image_prompt = self._create_video_image_prompt(
            caption=caption,
            persona_name=persona_name,
            persona_niche=persona_niche,
        )
        
        image_result = await self.generate_image(
            prompt=video_image_prompt,
            character_id=character_id,
            aspect_ratio=aspect_ratio,
            enhance_prompt=False,
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
        
        # Step 2: Summarize the caption into a short phrase (3-5 words) using AI
        short_phrase = await self._summarize_caption_for_speech(caption)
        logger.info("Caption summarized for video speech", short_phrase=short_phrase)
        
        # Step 3: Create a motion prompt with the short phrase
        video_prompt = self._create_short_video_prompt(short_phrase)
        
        # Step 4: Generate the video
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
    
    def _create_video_image_prompt(
        self,
        caption: str,
        persona_name: Optional[str] = None,
        persona_niche: Optional[List[str]] = None,
    ) -> str:
        """Create an image prompt optimized for video generation.
        
        This creates a clean image without text that will be used as the
        base frame for video generation.
        
        Args:
            caption: The original caption (used for theme extraction only)
            persona_name: Name of the persona
            persona_niche: List of niche topics
            
        Returns:
            Image prompt string that explicitly avoids text
        """
        niche_str = ", ".join(persona_niche) if persona_niche else "lifestyle"
        
        # Extract theme from caption without including text-heavy content
        # Take just a few words for context
        theme_words = caption.split()[:8]
        theme = " ".join(theme_words) if theme_words else "lifestyle moment"
        
        prompt = (
            f"CRITICAL: NO TEXT in this image. NO words. NO letters. NO captions. NO watermarks. NO overlays. Completely text-free. "
            f"A candid, spontaneous photo of a young, mixed race, slim female with naturally styled hair. "
            f"Relaxed, natural expression. Looking at camera with confidence. "
            f"Scene context: {theme}. "
            f"Niche: {niche_str}. "
            f"High quality, natural lighting, professional photography. "
            f"Absolutely no hands visible. No text anywhere in the image."
        )
        
        return prompt
    
    async def _summarize_caption_for_speech(self, caption: str) -> str:
        """Use AI to summarize a caption into a short spoken phrase (3-5 words).
        
        Args:
            caption: The full post caption
            
        Returns:
            A short 3-5 word phrase suitable for speaking in 5-6 seconds
        """
        logger.info("Starting caption summarization for video speech", caption_preview=caption[:80])
        
        try:
            # Import here to avoid circular imports
            from app.services.ai.anthropic_provider import AnthropicProvider
            
            ai = AnthropicProvider()
            logger.info("Anthropic provider initialized for summarization")
            
            messages = [
                Message(
                    role="system",
                    content=(
                        "You are a video script writer. Your job is to take a social media caption "
                        "and create a VERY SHORT spoken phrase (3-5 words maximum) that captures "
                        "the essence or vibe of the caption. This phrase will be spoken by an influencer "
                        "in a 5-6 second video clip.\n\n"
                        "Rules:\n"
                        "- Output ONLY the short phrase, nothing else\n"
                        "- Maximum 5 words\n"
                        "- Should sound natural when spoken casually\n"
                        "- Capture the mood/vibe, not every detail\n"
                        "- Can be a greeting, exclamation, or short thought\n\n"
                        "Examples:\n"
                        "Caption: 'Starting my morning with gratitude and positive energy for the week ahead'\n"
                        "Output: Good morning, feeling grateful!\n\n"
                        "Caption: 'New fitness journey starts today! Ready to transform and become my best self'\n"
                        "Output: Let's do this!\n\n"
                        "Caption: 'Sunday self-care vibes. Taking time to relax and recharge'\n"
                        "Output: Self-care Sunday!"
                    )
                ),
                Message(
                    role="user",
                    content=f"Create a 3-5 word spoken phrase for this caption:\n\n{caption}"
                )
            ]
            
            logger.info("Calling Anthropic for caption summarization")
            result = await ai.generate_text(messages, max_tokens=30, temperature=0.7)
            logger.info("Anthropic call completed", has_text=bool(result.text), model=result.model)
            
            if result.text:
                # Clean up the response - remove quotes if present
                phrase = result.text.strip().strip('"\'')
                # Ensure it's not too long (fallback if AI gives too many words)
                words = phrase.split()
                if len(words) > 6:
                    phrase = " ".join(words[:5])
                logger.info("Successfully summarized caption for video speech", original=caption[:50], phrase=phrase)
                return phrase
            else:
                logger.warning("AI summarization returned no text, using fallback")
                
        except Exception as e:
            logger.error("Caption summarization exception, using fallback", error=str(e), error_type=type(e).__name__)
            import traceback
            logger.error("Traceback", tb=traceback.format_exc())
        
        # Fallback: extract key words
        fallback_words = caption.split()[:4]
        fallback_phrase = " ".join(fallback_words) if fallback_words else "Hey, what's up"
        logger.warning("Using fallback phrase for video speech", fallback_phrase=fallback_phrase)
        return fallback_phrase
    
    def _create_short_video_prompt(self, short_phrase: str) -> str:
        """Create a video prompt suitable for 5-6 second clips.
        
        The subject speaks the provided short phrase (already summarized to 3-5 words).
        
        Args:
            short_phrase: A pre-summarized short phrase (3-5 words) for her to say
            
        Returns:
            Video prompt with speech instructions
        """
        motion_prompt = (
            f"CRITICAL: NO TEXT on screen. NO text overlays. NO captions. NO titles. NO watermarks. NO written words. "
            f"The subject says ONLY this exact phrase: '{short_phrase}' "
            f"IMPORTANT: After saying '{short_phrase}', she STOPS talking completely. She does NOT continue speaking. "
            f"She remains SILENT after the phrase - just smiles and looks at camera. No more words. No gibberish. No mumbling. "
            f"Total speech: Just '{short_phrase}' then silence. "
            f"Natural casual delivery, then quiet smile. "
            f"Subtle natural movement: gentle breathing, slight head movements. "
            f"Smooth cinematic camera, natural lighting. "
            f"Duration: 5-6 seconds."
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
