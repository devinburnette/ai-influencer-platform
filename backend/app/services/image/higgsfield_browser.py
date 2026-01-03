"""Higgsfield browser automation module using Playwright.

Uses browser automation to bypass API content moderation for NSFW content generation.
The web interface at higgsfield.ai does not have the same moderation restrictions as the API.
"""

import asyncio
import os
import json
import random
import tempfile
import httpx
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from app.config import get_settings

logger = structlog.get_logger()

# Directory to store browser session data
BROWSER_DATA_DIR = Path("/tmp/higgsfield_sessions")


class HiggsfieldBrowser:
    """Higgsfield browser automation client using Playwright.
    
    This class uses browser automation to interact with the Higgsfield web interface
    at higgsfield.ai for image generation, bypassing API-level content moderation.
    Uses session cookies stored from guided login for authentication.
    """
    
    BASE_URL = "https://higgsfield.ai"
    GENERATE_URL = "https://higgsfield.ai/image/seedream_v4_5"  # Seedream 4.5 for NSFW
    
    def __init__(
        self,
        session_id: str = "default",
        headless: bool = True,
        cookies: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize Higgsfield browser automation.
        
        Args:
            session_id: Unique identifier for browser session (typically persona_id)
            headless: Whether to run browser in headless mode
            cookies: Pre-loaded cookies from database (from guided login)
        """
        self.session_id = session_id
        self.headless = headless
        self.settings = get_settings()
        self._preloaded_cookies = cookies
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        # Session data directory for this session
        self._session_dir = BROWSER_DATA_DIR / session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)
        
        # Cookie file path (backup, prefer database cookies)
        self._cookies_path = self._session_dir / "cookies.json"
        
        # Download directory
        self._download_dir = self._session_dir / "downloads"
        self._download_dir.mkdir(parents=True, exist_ok=True)
    
    async def _init_browser(self) -> None:
        """Initialize the browser and context."""
        if self._browser is not None:
            return
        
        self._playwright = await async_playwright().start()
        
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        
        # Create context with stored cookies if available
        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "accept_downloads": True,
        }
        
        self._context = await self._browser.new_context(**context_options)
        
        # Load saved cookies if they exist
        await self._load_session()
        
        self._page = await self._context.new_page()
        
        # Set default timeout (longer for image generation)
        self._page.set_default_timeout(120000)
    
    @property
    async def page(self) -> Page:
        """Get the browser page, initializing if needed."""
        if self._page is None:
            await self._init_browser()
        return self._page
    
    async def _load_session(self) -> bool:
        """Load saved session cookies.
        
        Prioritizes preloaded cookies from database (from guided login),
        falls back to file-based cookies.
        """
        # First try preloaded cookies from database
        if self._preloaded_cookies and self._context:
            try:
                await self._context.add_cookies(self._preloaded_cookies)
                logger.info("Loaded Higgsfield session from database cookies", count=len(self._preloaded_cookies))
                return True
            except Exception as e:
                logger.warning("Failed to load database cookies", error=str(e))
        
        # Fall back to file-based cookies
        if not self._cookies_path.exists():
            return False
        
        try:
            with open(self._cookies_path, "r") as f:
                cookies = json.load(f)
            
            if cookies and self._context:
                await self._context.add_cookies(cookies)
                logger.info("Loaded Higgsfield session from file", count=len(cookies))
                return True
        except Exception as e:
            logger.warning("Failed to load Higgsfield session from file", error=str(e))
        
        return False
    
    async def _save_session(self) -> None:
        """Save current session cookies."""
        if self._context is None:
            return
        
        try:
            cookies = await self._context.cookies()
            with open(self._cookies_path, "w") as f:
                json.dump(cookies, f, indent=2)
            logger.info("Saved Higgsfield session cookies", count=len(cookies))
        except Exception as e:
            logger.warning("Failed to save Higgsfield session", error=str(e))
    
    async def close(self) -> None:
        """Close the browser and save session."""
        await self._save_session()
        
        if self._page:
            await self._page.close()
            self._page = None
        
        if self._context:
            await self._context.close()
            self._context = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def check_session_valid(self) -> bool:
        """Check if the current session is valid (user is logged in).
        
        This is used to verify cookies from guided login are still valid.
        """
        page = await self.page
        
        try:
            # Navigate to the main page or a protected page
            await page.goto(self.BASE_URL)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            return await self._is_logged_in()
            
        except Exception as e:
            logger.warning("Session check failed", error=str(e))
            return False
    
    async def get_current_cookies(self) -> List[Dict[str, Any]]:
        """Get current browser cookies for saving to database."""
        if self._context is None:
            return []
        
        try:
            cookies = await self._context.cookies()
            return cookies
        except Exception as e:
            logger.warning("Failed to get cookies", error=str(e))
            return []
    
    async def _is_logged_in(self) -> bool:
        """Check if currently logged in."""
        page = await self.page
        
        try:
            # Look for indicators of being logged in
            # This may need adjustment based on the actual Higgsfield UI
            logged_in_indicators = [
                'button:has-text("Logout")',
                'a:has-text("Logout")',
                'button:has-text("Account")',
                '[data-testid="user-menu"]',
                '.user-avatar',
                'button:has-text("Generate")',
            ]
            
            for selector in logged_in_indicators:
                if await page.locator(selector).count() > 0:
                    return True
            
            # Check if we can access the generation page
            current_url = page.url
            if "seedream" in current_url or "generate" in current_url:
                return True
            
            return False
        except:
            return False
    
    async def _dismiss_modals(self) -> None:
        """Dismiss any promotional modals or popups that might be blocking the page."""
        page = await self.page
        
        try:
            # Common modal close button selectors
            close_selectors = [
                'button[aria-label*="close" i]',
                'button[aria-label*="dismiss" i]',
                'button:has-text("×")',
                'button:has-text("✕")',
                '.modal button.close',
                '.popup button.close',
                '[data-testid="modal-close"]',
                'div[role="dialog"] button:has-text("×")',
                'div[role="dialog"] button[aria-label*="close" i]',
                # The X button in the top right of the modal we saw in screenshots
                'button:has([class*="close"])',
                'svg[class*="close"]',
            ]
            
            for selector in close_selectors:
                try:
                    close_btn = page.locator(selector)
                    count = await close_btn.count()
                    if count > 0:
                        logger.info(f"Found modal close button: {selector}")
                        await close_btn.first.click(timeout=3000)
                        await asyncio.sleep(0.5)
                        logger.info("Dismissed modal")
                except:
                    continue
            
            # Also try pressing Escape key to close any modal
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                logger.info("Pressed Escape to dismiss any modal")
            except:
                pass
            
            # Click outside any modal to dismiss it (click on page edges)
            try:
                await page.mouse.click(10, 10)
                await asyncio.sleep(0.3)
            except:
                pass
                
        except Exception as e:
            logger.warning("Error dismissing modals", error=str(e))
    
    async def generate_image(
        self,
        prompt: str,
        reference_image_url: Optional[str] = None,
        aspect_ratio: str = "9:16",
        negative_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate an image using the Higgsfield web interface.
        
        Args:
            prompt: The image generation prompt
            reference_image_url: Optional URL of reference image for style transfer
            aspect_ratio: Aspect ratio for the generated image
            negative_prompt: Optional negative prompt
            
        Returns:
            Dictionary with:
                - success: Whether generation succeeded
                - image_url: URL of the generated image (if successful)
                - local_path: Local path where image was saved
                - error: Error message (if failed)
        """
        page = await self.page
        
        try:
            logger.info(
                "Generating image via Higgsfield browser",
                prompt=prompt[:100],
                has_reference=bool(reference_image_url),
            )
            
            # Set a longer default timeout for operations
            page.set_default_timeout(120000)  # 120 seconds
            
            # Navigate to the generation page
            logger.info("Navigating to Higgsfield generation page", url=self.GENERATE_URL)
            try:
                await page.goto(self.GENERATE_URL, timeout=60000, wait_until="domcontentloaded")
                logger.info("Page DOM loaded, waiting for stability...")
                await asyncio.sleep(5)
            except Exception as nav_error:
                logger.warning("Navigation issue, continuing anyway", error=str(nav_error))
            
            # Log current URL and page title
            try:
                current_url = page.url
                title = await page.title()
                logger.info("Page loaded", url=current_url, title=title)
            except Exception as e:
                logger.warning("Could not get page info", error=str(e))
            
            # Skip strict login check - proceed if we have cookies
            # The page should be accessible with valid session cookies
            logger.info("Proceeding with generation (cookies loaded)")
            
            # Dismiss any promotional modals/popups before proceeding
            await self._dismiss_modals()
            
            # Find and fill the prompt input - try multiple selectors
            prompt_selectors = [
                'textarea[placeholder*="prompt" i]',
                'textarea[name="prompt"]',
                'textarea[id*="prompt" i]',
                'input[placeholder*="prompt" i]',
                '[data-testid="prompt-input"]',
                'textarea',  # Fallback to any textarea
            ]
            
            prompt_input = None
            for selector in prompt_selectors:
                locator = page.locator(selector)
                count = await locator.count()
                logger.info(f"Selector '{selector}' found {count} elements")
                if count > 0:
                    prompt_input = locator.first
                    break
            
            if not prompt_input:
                return {
                    "success": False,
                    "image_url": None,
                    "error": "Could not find prompt input field on Higgsfield page",
                }
            
            await prompt_input.fill(prompt, timeout=10000)
            logger.info("Filled prompt input")
            
            # Fill negative prompt if available
            if negative_prompt:
                neg_prompt_input = page.locator(
                    'textarea[placeholder*="negative" i], '
                    'textarea[name*="negative" i], '
                    'input[placeholder*="negative" i]'
                )
                if await neg_prompt_input.count() > 0:
                    await neg_prompt_input.first.fill(negative_prompt)
                    logger.info("Filled negative prompt input")
            
            # Handle reference image if provided
            if reference_image_url:
                await self._add_reference_image(reference_image_url)
            
            # Set aspect ratio if there's a selector
            await self._set_aspect_ratio(aspect_ratio)
            
            # Click generate button - try multiple selectors
            generate_selectors = [
                'button:has-text("Generate")',
                'button:has-text("Create")',
                'button:has-text("Run")',
                'button[type="submit"]',
                'button.generate-button',
                '[data-testid="generate-button"]',
            ]
            
            generate_button = None
            for selector in generate_selectors:
                locator = page.locator(selector)
                count = await locator.count()
                logger.info(f"Generate button selector '{selector}' found {count} elements")
                if count > 0:
                    generate_button = locator.first
                    break
            
            if generate_button:
                # Wait a moment for page to stabilize after filling prompt
                await asyncio.sleep(2)
                
                # Check if button is disabled
                is_disabled = await generate_button.is_disabled()
                logger.info(f"Generate button is_disabled: {is_disabled}")
                
                # Record existing images BEFORE clicking generate
                existing_images = set()
                all_imgs = await page.locator('img').all()
                for img in all_imgs:
                    try:
                        src = await img.get_attribute("src")
                        if src:
                            existing_images.add(src)
                    except:
                        pass
                logger.info(f"Found {len(existing_images)} existing images before generation")
                
                # Try force click to bypass any overlay or disabled state
                try:
                    await generate_button.click(force=True, timeout=10000)
                    logger.info("Clicked generate button (force)")
                except Exception as click_error:
                    logger.warning(f"Force click failed: {click_error}, trying JavaScript click")
                    # Try JavaScript click as fallback
                    await generate_button.evaluate("button => button.click()")
                    logger.info("Clicked generate button (JavaScript)")
            else:
                return {
                    "success": False,
                    "image_url": None,
                    "error": "Could not find generate button on Higgsfield page",
                }
            
            # Wait for generation to complete - pass existing images to exclude
            image_url = await self._wait_for_generation(existing_images=existing_images)
            
            if image_url:
                # Download the image
                local_path = await self._download_image(image_url)
                
                return {
                    "success": True,
                    "image_url": image_url,
                    "local_path": str(local_path) if local_path else None,
                }
            else:
                return {
                    "success": False,
                    "image_url": None,
                    "error": "Generation timed out or failed",
                }
                
        except Exception as e:
            logger.error("Higgsfield browser generation failed", error=str(e))
            return {
                "success": False,
                "image_url": None,
                "error": str(e),
            }
    
    async def _add_reference_image(self, image_url: str) -> bool:
        """Add a reference image for style transfer."""
        page = await self.page
        
        try:
            # Look for image upload or URL input
            image_url_input = page.locator(
                'input[placeholder*="image" i], '
                'input[placeholder*="url" i], '
                'input[type="url"]'
            )
            
            if await image_url_input.count() > 0:
                await image_url_input.first.fill(image_url)
                return True
            
            # Try file upload - would need to download image first
            file_input = page.locator('input[type="file"]')
            if await file_input.count() > 0:
                # Download image to temp file
                async with httpx.AsyncClient() as client:
                    response = await client.get(image_url)
                    if response.status_code == 200:
                        temp_path = self._download_dir / f"ref_{random.randint(1000, 9999)}.jpg"
                        with open(temp_path, "wb") as f:
                            f.write(response.content)
                        
                        await file_input.first.set_input_files(str(temp_path))
                        return True
            
            logger.warning("Could not add reference image - no input found")
            return False
            
        except Exception as e:
            logger.warning("Failed to add reference image", error=str(e))
            return False
    
    async def _set_aspect_ratio(self, aspect_ratio: str) -> bool:
        """Set the aspect ratio for generation."""
        page = await self.page
        
        try:
            # Quick timeout for aspect ratio - don't block if not found
            # Look for aspect ratio selector
            aspect_selector = page.locator(
                f'button:has-text("{aspect_ratio}"), '
                f'[data-value="{aspect_ratio}"], '
                f'option:has-text("{aspect_ratio}")'
            )
            
            count = await aspect_selector.count()
            if count > 0:
                await aspect_selector.first.click(timeout=5000)
                logger.info(f"Set aspect ratio to {aspect_ratio}")
                return True
            
            logger.info(f"Aspect ratio selector not found for {aspect_ratio}, using default")
            return False
            
        except Exception as e:
            logger.warning("Failed to set aspect ratio, using default", error=str(e))
            return False
    
    async def _wait_for_generation(self, timeout: int = 180, existing_images: Optional[set] = None) -> Optional[str]:
        """Wait for image generation to complete and return the image URL.
        
        Args:
            timeout: Maximum seconds to wait for generation
            existing_images: Set of image URLs that existed before generation started
        """
        page = await self.page
        existing_images = existing_images or set()
        
        try:
            # Wait for generation to start
            await asyncio.sleep(3)
            
            # Poll for completion
            poll_count = 0
            for _ in range(timeout // 5):  # Poll every 5 seconds
                poll_count += 1
                
                # Count current images on page
                all_images = await page.locator('img').all()
                current_count = len(all_images)
                new_count = 0
                for img in all_images:
                    try:
                        src = await img.get_attribute("src")
                        if src and src not in existing_images:
                            new_count += 1
                    except:
                        pass
                
                # Log progress periodically
                if poll_count % 6 == 0:  # Every 30 seconds
                    logger.info(f"Waiting for generation... ({poll_count * 5}s elapsed, {new_count} new images)")
                
                # Check for NEW images on the page (not in existing_images set)
                for img in all_images:
                    try:
                        src = await img.get_attribute("src")
                        if not src or src.startswith("data:"):
                            continue
                        
                        # Skip images that existed before we clicked generate
                        if src in existing_images:
                            continue
                        
                        # Check if it's a generated image (usually from CDN)
                        if any(x in src for x in ["cloudfront", "storage", "cdn", "blob", "generated", "output", "result"]):
                            # Check dimensions - generated images are usually larger
                            box = await img.bounding_box()
                            if box and box.get("width", 0) > 200 and box.get("height", 0) > 200:
                                logger.info(f"Found NEW result image: {src[:100]}, size: {box}")
                                return src
                    except:
                        continue
                
                # Check for download button (indicates generation complete)
                download_button = page.locator(
                    'button:has-text("Download"), '
                    'a:has-text("Download"), '
                    'button[aria-label*="download" i], '
                    'a[download]'
                )
                
                download_count = await download_button.count()
                if download_count > 0:
                    logger.info(f"Found {download_count} download button(s), checking for new images")
                    
                    # Look for new images
                    for img in all_images:
                        try:
                            src = await img.get_attribute("src")
                            if src and not src.startswith("data:") and src not in existing_images:
                                box = await img.bounding_box()
                                if box and box.get("width", 0) > 150:
                                    logger.info(f"Found new image after download button: {src[:100]}")
                                    return src
                        except:
                            continue
                
                # Check for progress/loading indicators
                loading = page.locator('.loading, .spinner, [data-loading="true"], div:has-text("Generating"), div:has-text("Processing")')
                loading_count = await loading.count()
                if loading_count > 0 and poll_count <= 3:
                    logger.info(f"Generation in progress (found {loading_count} loading indicators)")
                
                # Check for error messages
                error_msg = page.locator('.error-message, [data-error], div.error')
                if await error_msg.count() > 0:
                    try:
                        error_text = await error_msg.first.text_content()
                        if error_text and len(error_text) < 200:
                            logger.warning("Generation error detected", error=error_text[:100])
                            return None
                    except:
                        pass
                
                await asyncio.sleep(5)
                
                await asyncio.sleep(3)
            
            logger.warning("Generation timed out")
            return None
            
        except Exception as e:
            logger.error("Error waiting for generation", error=str(e))
            return None
    
    async def _download_image(self, image_url: str) -> Optional[Path]:
        """Download the generated image to local storage."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, follow_redirects=True)
                
                if response.status_code == 200:
                    # Generate unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"generated_{timestamp}_{random.randint(1000, 9999)}.jpg"
                    local_path = self._download_dir / filename
                    
                    with open(local_path, "wb") as f:
                        f.write(response.content)
                    
                    logger.info("Downloaded generated image", path=str(local_path))
                    return local_path
                else:
                    logger.warning("Failed to download image", status=response.status_code)
                    return None
                    
        except Exception as e:
            logger.error("Error downloading image", error=str(e))
            return None

    async def generate_video(
        self,
        source_image_url: str,
        motion_prompt: str,
        duration: int = 5,
    ) -> Dict[str, Any]:
        """Generate a video from an image using the Higgsfield web interface (Wan 2.5).
        
        This bypasses API content moderation by using the web interface at
        https://higgsfield.ai/create/video
        
        Args:
            source_image_url: URL of the source image to animate
            motion_prompt: Description of the desired motion/animation
            duration: Video duration in seconds (default 5)
            
        Returns:
            Dictionary with success, video_url, local_path, and error fields
        """
        page = await self.page
        VIDEO_URL = "https://higgsfield.ai/create/video"
        
        try:
            logger.info(
                "Generating video via Higgsfield browser",
                source_image=source_image_url[:80] if source_image_url else None,
                prompt=motion_prompt[:100],
                duration=duration,
            )
            
            # Set a longer default timeout for video operations
            page.set_default_timeout(180000)  # 3 minutes
            
            # Navigate to the video generation page
            logger.info("Navigating to Higgsfield video page", url=VIDEO_URL)
            try:
                await page.goto(VIDEO_URL, timeout=60000, wait_until="domcontentloaded")
                logger.info("Video page DOM loaded, waiting for stability...")
                await asyncio.sleep(5)
            except Exception as nav_error:
                logger.warning("Navigation issue, continuing anyway", error=str(nav_error))
            
            # Log current URL
            try:
                current_url = page.url
                title = await page.title()
                logger.info("Video page loaded", url=current_url, title=title)
            except Exception as e:
                logger.warning("Could not get page info", error=str(e))
            
            # Dismiss any promotional modals/popups
            await self._dismiss_modals()
            
            # Upload the source image - look for file input or upload area
            image_uploaded = await self._upload_source_image_for_video(source_image_url)
            if not image_uploaded:
                logger.warning("Could not upload source image, trying to proceed anyway")
            
            # Find and fill the prompt input for video
            prompt_selectors = [
                'textarea[placeholder*="prompt" i]',
                'textarea[name="prompt"]',
                'textarea[id*="prompt" i]',
                'textarea[placeholder*="describe" i]',
                'textarea',  # Fallback to any textarea
            ]
            
            prompt_input = None
            for selector in prompt_selectors:
                locator = page.locator(selector)
                count = await locator.count()
                if count > 0:
                    prompt_input = locator.first
                    logger.info(f"Found video prompt input with selector '{selector}'")
                    break
            
            if not prompt_input:
                return {
                    "success": False,
                    "video_url": None,
                    "error": "Could not find prompt input field on video page",
                }
            
            await prompt_input.fill(motion_prompt, timeout=10000)
            logger.info("Filled video motion prompt")
            
            # Try to select Wan 2.5 model if there's a model selector
            await self._select_video_model("Wan 2.5")
            
            # Try to set duration
            await self._set_video_duration(duration)
            
            # Wait a moment for page to stabilize
            await asyncio.sleep(2)
            
            # Record existing videos BEFORE clicking generate
            existing_videos = set()
            all_videos = await page.locator('video').all()
            for vid in all_videos:
                try:
                    src = await vid.get_attribute("src")
                    if src:
                        existing_videos.add(src)
                except:
                    pass
            logger.info(f"Found {len(existing_videos)} existing videos before generation")
            
            # Click generate button
            generate_selectors = [
                'button:has-text("Generate")',
                'button:has-text("Create")',
                'button:has-text("Run")',
                'button[type="submit"]',
            ]
            
            generate_button = None
            for selector in generate_selectors:
                locator = page.locator(selector)
                count = await locator.count()
                if count > 0:
                    generate_button = locator.first
                    logger.info(f"Found video generate button with selector '{selector}'")
                    break
            
            if not generate_button:
                return {
                    "success": False,
                    "video_url": None,
                    "error": "Could not find generate button on video page",
                }
            
            # Check if button is disabled
            is_disabled = await generate_button.is_disabled()
            logger.info(f"Video generate button is_disabled: {is_disabled}")
            
            # Click the generate button
            try:
                await generate_button.click(force=True, timeout=10000)
                logger.info("Clicked video generate button")
            except Exception as click_error:
                logger.warning(f"Force click failed: {click_error}, trying JavaScript click")
                await generate_button.evaluate("button => button.click()")
                logger.info("Clicked video generate button (JavaScript)")
            
            # Wait for video generation to complete
            video_url = await self._wait_for_video_generation(existing_videos=existing_videos)
            
            if video_url:
                # Download the video
                local_path = await self._download_video(video_url)
                
                return {
                    "success": True,
                    "video_url": video_url,
                    "local_path": str(local_path) if local_path else None,
                }
            else:
                return {
                    "success": False,
                    "video_url": None,
                    "error": "Video generation timed out or failed",
                }
                
        except Exception as e:
            logger.error("Higgsfield browser video generation failed", error=str(e))
            return {
                "success": False,
                "video_url": None,
                "error": str(e),
            }

    async def _upload_source_image_for_video(self, image_url: str) -> bool:
        """Upload a source image for video generation."""
        page = await self.page
        
        try:
            # First, download the image to a temp file
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, follow_redirects=True)
                if response.status_code != 200:
                    logger.warning("Failed to download source image", status=response.status_code)
                    return False
                
                # Save to temp file
                temp_path = self._download_dir / f"source_{random.randint(1000, 9999)}.jpg"
                with open(temp_path, "wb") as f:
                    f.write(response.content)
                
                logger.info("Downloaded source image for video", path=str(temp_path))
            
            # Look for file input for image upload
            file_input = page.locator('input[type="file"]')
            if await file_input.count() > 0:
                await file_input.first.set_input_files(str(temp_path))
                logger.info("Uploaded source image via file input")
                await asyncio.sleep(3)  # Wait for upload to process
                return True
            
            # Try clicking an upload button/area first
            upload_button_selectors = [
                'button:has-text("Upload")',
                'button:has-text("Add Image")',
                'div:has-text("Drop")',
                '[data-testid="upload-button"]',
                '.upload-area',
            ]
            
            for selector in upload_button_selectors:
                try:
                    locator = page.locator(selector)
                    if await locator.count() > 0:
                        await locator.first.click(timeout=5000)
                        await asyncio.sleep(1)
                        
                        # Now look for file input again
                        file_input = page.locator('input[type="file"]')
                        if await file_input.count() > 0:
                            await file_input.first.set_input_files(str(temp_path))
                            logger.info("Uploaded source image after clicking upload button")
                            await asyncio.sleep(3)
                            return True
                except:
                    continue
            
            logger.warning("Could not find image upload input")
            return False
            
        except Exception as e:
            logger.error("Error uploading source image for video", error=str(e))
            return False

    async def _select_video_model(self, model_name: str) -> bool:
        """Select the video generation model."""
        page = await self.page
        
        try:
            # Look for model selector dropdown
            model_selectors = [
                f'button:has-text("{model_name}")',
                f'div:has-text("{model_name}")',
                'button:has-text("Model")',
                '[data-testid="model-selector"]',
            ]
            
            for selector in model_selectors:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    await locator.first.click(timeout=5000)
                    await asyncio.sleep(1)
                    
                    # Try to click the specific model option
                    model_option = page.locator(f'*:has-text("{model_name}")')
                    if await model_option.count() > 0:
                        await model_option.first.click(timeout=5000)
                        logger.info(f"Selected model: {model_name}")
                        return True
            
            logger.info("Model selector not found, using default")
            return False
            
        except Exception as e:
            logger.warning("Failed to select video model", error=str(e))
            return False

    async def _set_video_duration(self, duration: int) -> bool:
        """Set the video duration."""
        page = await self.page
        
        try:
            # Look for duration selector
            duration_selectors = [
                f'button:has-text("{duration}s")',
                f'button:has-text("{duration}")',
                'button:has-text("Duration")',
                '[data-testid="duration-selector"]',
            ]
            
            for selector in duration_selectors:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    await locator.first.click(timeout=5000)
                    await asyncio.sleep(1)
                    
                    # Try to click the specific duration option
                    duration_option = page.locator(f'*:has-text("{duration}s")')
                    if await duration_option.count() > 0:
                        await duration_option.first.click(timeout=5000)
                        logger.info(f"Set video duration: {duration}s")
                        return True
            
            logger.info("Duration selector not found, using default")
            return False
            
        except Exception as e:
            logger.warning("Failed to set video duration", error=str(e))
            return False

    async def _wait_for_video_generation(
        self,
        timeout: int = 300,
        existing_videos: Optional[set] = None,
    ) -> Optional[str]:
        """Wait for video generation to complete and return the video URL.
        
        Args:
            timeout: Maximum seconds to wait for generation
            existing_videos: Set of video URLs that existed before generation started
        """
        page = await self.page
        existing_videos = existing_videos or set()
        
        try:
            # Wait for generation to start
            await asyncio.sleep(5)
            
            # Poll for completion - video generation takes longer than images
            poll_count = 0
            for _ in range(timeout // 10):  # Poll every 10 seconds
                poll_count += 1
                elapsed = poll_count * 10
                
                # Check for new video elements
                all_videos = await page.locator('video').all()
                new_count = 0
                for vid in all_videos:
                    try:
                        src = await vid.get_attribute("src")
                        if src and src not in existing_videos:
                            new_count += 1
                            # Check if it's a completed video (from CDN)
                            if any(x in src for x in ["cloudfront", "storage", "cdn", "blob", "generated", "output", "result"]):
                                logger.info(f"Found NEW result video: {src[:100]}")
                                return src
                    except:
                        continue
                
                # Also check for download button (indicates generation complete)
                download_button = page.locator(
                    'button:has-text("Download"), '
                    'a:has-text("Download"), '
                    'button[aria-label*="download" i], '
                    'a[download]'
                )
                
                download_count = await download_button.count()
                if download_count > 0:
                    logger.info(f"Found {download_count} download button(s), checking for new videos")
                    
                    # Look for new video sources
                    for vid in all_videos:
                        try:
                            src = await vid.get_attribute("src")
                            if src and src not in existing_videos:
                                logger.info(f"Found new video after download button: {src[:100]}")
                                return src
                        except:
                            continue
                
                # Check for progress/loading indicators
                loading = page.locator('.loading, .spinner, [data-loading="true"], div:has-text("Generating"), div:has-text("Processing")')
                loading_count = await loading.count()
                
                if poll_count % 3 == 0:  # Log every 30 seconds
                    logger.info(f"Waiting for video generation... ({elapsed}s elapsed, {new_count} new videos, {loading_count} loading indicators)")
                
                # Check for error messages
                error_msg = page.locator('.error-message, [data-error], div.error')
                if await error_msg.count() > 0:
                    try:
                        error_text = await error_msg.first.text_content()
                        if error_text and len(error_text) < 200:
                            logger.warning("Video generation error detected", error=error_text[:100])
                            return None
                    except:
                        pass
                
                await asyncio.sleep(10)  # Wait 10 seconds before next poll
            
            logger.warning("Video generation timed out")
            return None
            
        except Exception as e:
            logger.error("Error waiting for video generation", error=str(e))
            return None

    async def _download_video(self, video_url: str) -> Optional[Path]:
        """Download the generated video to local storage."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(video_url, follow_redirects=True)
                
                if response.status_code == 200:
                    # Generate unique filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"generated_video_{timestamp}_{random.randint(1000, 9999)}.mp4"
                    local_path = self._download_dir / filename
                    
                    with open(local_path, "wb") as f:
                        f.write(response.content)
                    
                    logger.info("Downloaded generated video", path=str(local_path))
                    return local_path
                else:
                    logger.warning("Failed to download video", status=response.status_code)
                    return None
                    
        except Exception as e:
            logger.error("Error downloading video", error=str(e))
            return None


async def generate_nsfw_image_via_browser(
    prompt: str,
    reference_image_url: Optional[str] = None,
    aspect_ratio: str = "9:16",
    negative_prompt: Optional[str] = None,
    session_id: str = "default",
    cookies: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Convenience function to generate NSFW image via browser automation.
    
    This is a standalone function that handles browser lifecycle.
    
    Args:
        prompt: The image generation prompt
        reference_image_url: Optional reference image URL
        aspect_ratio: Aspect ratio for the generated image
        negative_prompt: Optional negative prompt
        session_id: Session ID for browser persistence
        cookies: Session cookies from database (from guided login)
        
    Returns:
        Dictionary with generation result
    """
    async with HiggsfieldBrowser(
        session_id=session_id,
        headless=True,
        cookies=cookies,
    ) as browser:
        return await browser.generate_image(
            prompt=prompt,
            reference_image_url=reference_image_url,
            aspect_ratio=aspect_ratio,
            negative_prompt=negative_prompt,
        )


async def generate_nsfw_video_via_browser(
    source_image_url: str,
    motion_prompt: str,
    duration: int = 5,
    session_id: str = "default",
    cookies: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Convenience function to generate NSFW video via browser automation.
    
    This is a standalone function that handles browser lifecycle.
    Uses Wan 2.5 via the web interface at higgsfield.ai/create/video
    
    Args:
        source_image_url: URL of the source image to animate
        motion_prompt: Description of the desired motion/animation
        duration: Video duration in seconds (default 5)
        session_id: Session ID for browser persistence
        cookies: Session cookies from database (from guided login)
        
    Returns:
        Dictionary with generation result (success, video_url, local_path, error)
    """
    async with HiggsfieldBrowser(
        session_id=session_id,
        headless=True,
        cookies=cookies,
    ) as browser:
        return await browser.generate_video(
            source_image_url=source_image_url,
            motion_prompt=motion_prompt,
            duration=duration,
        )


async def launch_guided_login(headless: bool = False) -> Dict[str, Any]:
    """Launch a visible browser for user to login to Higgsfield.
    
    Opens higgsfield.ai login page and waits for user to complete login.
    Returns captured cookies on success.
    
    Args:
        headless: Should be False for guided login (user needs to see browser)
        
    Returns:
        Dictionary with:
            - success: Whether login was successful
            - cookies: List of captured cookies
            - error: Error message if failed
    """
    browser = HiggsfieldBrowser(session_id="guided_login", headless=headless)
    
    try:
        await browser._init_browser()
        page = await browser.page
        
        # Navigate to login page
        await page.goto("https://higgsfield.ai/login")
        await page.wait_for_load_state("networkidle")
        
        logger.info("Waiting for user to login to Higgsfield...")
        
        # Wait for successful login (up to 5 minutes)
        max_wait = 300  # 5 minutes
        for i in range(max_wait // 3):
            if await browser._is_logged_in():
                logger.info("Higgsfield login detected!")
                cookies = await browser.get_current_cookies()
                await browser._save_session()
                return {
                    "success": True,
                    "cookies": cookies,
                }
            await asyncio.sleep(3)
        
        return {
            "success": False,
            "cookies": [],
            "error": "Login timed out - user did not complete login within 5 minutes",
        }
        
    except Exception as e:
        logger.error("Guided login failed", error=str(e))
        return {
            "success": False,
            "cookies": [],
            "error": str(e),
        }
    finally:
        await browser.close()

