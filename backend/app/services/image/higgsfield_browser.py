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
                'button:has-text("X")',
                'button:has-text("Close")',
                'button:has-text("No thanks")',
                'button:has-text("Maybe later")',
                'button:has-text("Not now")',
                'button:has-text("Skip")',
                'button:has-text("Got it")',
                'button:has-text("Dismiss")',
                '.modal button.close',
                '.popup button.close',
                '[data-testid="modal-close"]',
                'div[role="dialog"] button:has-text("×")',
                'div[role="dialog"] button[aria-label*="close" i]',
                'div[role="dialog"] button:first-child',  # Often the X is the first button
                # The X button in the top right of the modal
                'button:has([class*="close"])',
                'svg[class*="close"]',
                # Overlay/backdrop click to close
                '.modal-backdrop',
                '.overlay',
                # Promo/marketing modals
                '[class*="promo"] button',
                '[class*="popup"] button',
                '[class*="banner"] button[aria-label*="close" i]',
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
                if await locator.count() > 0:
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
                if await locator.count() > 0:
                    generate_button = locator.first
                    break
            
            if generate_button:
                # Wait for page to stabilize
                await asyncio.sleep(2)
                
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
            # First download the image
            temp_path = self._download_dir / f"ref_{random.randint(1000, 9999)}.jpg"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url, follow_redirects=True)
                if response.status_code != 200:
                    logger.warning("Failed to download reference image", status=response.status_code)
                    return False
                with open(temp_path, "wb") as f:
                    f.write(response.content)
                logger.info("Downloaded reference image", path=str(temp_path))
            
            # Look for file input (most common way)
            file_input = page.locator('input[type="file"]')
            file_count = await file_input.count()
            logger.info(f"Found {file_count} file input(s)")
            
            if file_count > 0:
                await file_input.first.set_input_files(str(temp_path))
                await asyncio.sleep(2)  # Wait for upload to process
                logger.info("Uploaded reference image via file input")
                return True
            
            # Try clicking upload button/area first to reveal file input
            upload_trigger_selectors = [
                'button:has-text("Upload")',
                'button:has-text("Add Image")',
                'button:has-text("Reference")',
                'div:has-text("Drop image")',
                'div:has-text("Upload")',
                '[data-testid="upload-button"]',
                '.upload-area',
                '.upload-zone',
                'label[for*="file"]',
            ]
            
            for selector in upload_trigger_selectors:
                try:
                    trigger = page.locator(selector)
                    if await trigger.count() > 0:
                        logger.info(f"Found upload trigger: {selector}")
                        await trigger.first.click(timeout=5000)
                        await asyncio.sleep(1)
                        
                        # Check if file input appeared
                        file_input = page.locator('input[type="file"]')
                        if await file_input.count() > 0:
                            await file_input.first.set_input_files(str(temp_path))
                            await asyncio.sleep(2)
                            logger.info("Uploaded reference image after clicking trigger")
                            return True
                except Exception as e:
                    logger.debug(f"Upload trigger {selector} failed: {e}")
                    continue
            
            # Try URL input as fallback
            url_input_selectors = [
                'input[placeholder*="image" i]',
                'input[placeholder*="url" i]',
                'input[placeholder*="reference" i]',
                'input[type="url"]',
            ]
            
            for selector in url_input_selectors:
                url_input = page.locator(selector)
                if await url_input.count() > 0:
                    await url_input.first.fill(image_url)
                    logger.info("Added reference via URL input")
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
            # Track ALL video src values and video element count
            existing_videos = set()
            all_videos = await page.locator('video').all()
            initial_video_count = len(all_videos)
            
            for vid in all_videos:
                try:
                    src = await vid.get_attribute("src")
                    if src:
                        existing_videos.add(src)
                except:
                    pass
            logger.info(f"Found {len(existing_videos)} existing video sources")
            
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
            
            # Click the generate button
            try:
                await generate_button.click(force=True, timeout=10000)
                logger.info("Clicked video generate button")
            except Exception as click_error:
                logger.warning(f"Force click failed: {click_error}, trying JavaScript click")
                await generate_button.evaluate("button => button.click()")
                logger.info("Clicked video generate button (JavaScript)")
            
            # Wait a moment for generation to start
            await asyncio.sleep(3)
            
            # Scroll to top of page to see new generation
            await page.evaluate("window.scrollTo(0, 0)")
            
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

    def _is_valid_video_url(self, url: str, existing_videos: set) -> bool:
        """Check if a URL is a valid video content URL (not a page URL or invalid format).
        
        STRICT validation - only accept URLs that are clearly video files.
        """
        if not url:
            return False
        
        # Skip URLs already seen
        if url in existing_videos:
            return False
        
        # Skip data URLs
        if url.startswith("data:"):
            return False
        
        # Skip blob URLs (can't be saved/shared)
        if url.startswith("blob:"):
            return False
        
        # Skip relative page paths (these are navigation links, not video files)
        if url.startswith("/"):
            return False
        
        # Skip anchor links
        if url.startswith("#"):
            return False
        
        # Skip javascript links
        if url.startswith("javascript:"):
            return False
        
        # Must be a proper HTTP(S) URL
        if not url.startswith("http://") and not url.startswith("https://"):
            return False
        
        url_lower = url.lower()
        
        # REJECT known non-video domains
        non_video_domains = [
            "discord.gg", "discord.com",
            "twitter.com", "x.com",
            "facebook.com", "instagram.com",
            "youtube.com",  # YouTube URLs need special handling
            "tiktok.com",
            "linkedin.com",
            "github.com",
            "google.com",
            "higgsfield.ai/create",  # Page URLs
            "higgsfield.ai/edit",
            "higgsfield.ai/signin",
            "higgsfield.ai/login",
            "higgsfield.ai/home",
            "higgsfield.ai/profile",
        ]
        for domain in non_video_domains:
            if domain in url_lower:
                return False
        
        # MUST have a video file indicator - be very strict
        # Real video URLs typically have .mp4, .webm, .mov or come from CDN with video path
        video_file_extensions = [".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v"]
        has_video_extension = any(ext in url_lower for ext in video_file_extensions)
        
        # CloudFront URLs for video content (Higgsfield uses CloudFront)
        is_cloudfront_video = "cloudfront.net" in url_lower and (
            has_video_extension or 
            "/video" in url_lower or
            # CloudFront video URLs often have UUIDs followed by extension
            any(f"/{c}" in url_lower for c in "0123456789abcdef")
        )
        
        # Higgsfield's own CDN for video content
        is_higgsfield_cdn = "cdn.higgsfield.ai" in url_lower and (
            "wan2" in url_lower or  # Wan 2.5 videos
            "motion" in url_lower or
            "video" in url_lower or
            has_video_extension
        )
        
        # Other known video CDNs
        is_known_video_cdn = any(cdn in url_lower for cdn in [
            "mux.com",
            "vimeocdn.com",
            "akamaized.net",
            "fastly.net",
            "bunnycdn.com",
        ]) and (has_video_extension or "/video" in url_lower)
        
        # Accept if it has a clear video file extension
        if has_video_extension:
            return True
        
        # Accept if it's from CloudFront with video indicators
        if is_cloudfront_video:
            return True
        
        # Accept if it's from Higgsfield's own CDN
        if is_higgsfield_cdn:
            return True
        
        # Accept if it's from a known video CDN
        if is_known_video_cdn:
            return True
        
        # Reject everything else - better to miss a video than accept garbage
        return False

    async def _wait_for_video_generation(
        self,
        timeout: int = 420,  # 7 minutes for video generation
        existing_videos: Optional[set] = None,
    ) -> Optional[str]:
        """Wait for video generation to complete and return the video URL.
        
        Args:
            timeout: Maximum seconds to wait for generation
            existing_videos: Set of video URLs that existed before generation started
        """
        page = await self.page
        existing_videos = existing_videos or set()
        
        # Also add the current page URL to existing to avoid returning it
        current_page_url = page.url
        existing_videos.add(current_page_url)
        
        # Track video URLs found via network requests
        found_video_urls = []
        
        async def handle_response(response):
            url = response.url
            # Look for CloudFront .mp4 downloads OR cdn.higgsfield.ai videos
            if (".mp4" in url or "wan2_5" in url) and url not in existing_videos:
                if "cloudfront.net" in url or "cdn.higgsfield" in url:
                    logger.info(f"Intercepted video URL: {url[:150]}")
                    if url not in found_video_urls:
                        found_video_urls.append(url)
        
        # Set up response interceptor
        page.on("response", handle_response)
        
        try:
            # Wait for generation to start
            await asyncio.sleep(5)
            
            # Poll for completion
            poll_count = 0
            for _ in range(timeout // 10):  # Poll every 10 seconds
                poll_count += 1
                elapsed = poll_count * 10
                
                # Dismiss any modals that might be blocking (every 30 seconds)
                if poll_count % 3 == 1:
                    await self._dismiss_modals()
                
                # Scroll to top periodically to ensure we see new content
                if poll_count % 5 == 0:
                    await page.evaluate("window.scrollTo(0, 0)")
                    await asyncio.sleep(1)
                
                # Check if we found a video URL via network interception
                if found_video_urls:
                    # Return the most recent one (last in list)
                    video_url = found_video_urls[-1]
                    logger.info(f"Returning intercepted video URL: {video_url[:150]}")
                    return video_url
                
                # Strategy 0: Click the FIRST ITEM in the grid (the newest generation)
                # The new video appears as a thumbnail at the top - clicking it loads the video player
                # The video player then has the CloudFront src URL
                if poll_count >= 6 and poll_count % 2 == 0:  # Try every 20 seconds starting at 60s
                    try:
                        # Find the first item in the grid - this should be the NEW video thumbnail
                        # We want to click the CONTAINER, not an existing video element
                        first_item_selectors = [
                            'div[class*="grid"] > div:first-child',  # First item in grid
                            'main section > div > div:first-child',
                            'div[class*="list"] > div:first-child',
                            '[class*="result"]:first-child',
                            '[class*="item"]:first-child',
                        ]
                        
                        for sel in first_item_selectors:
                            element = page.locator(sel)
                            if await element.count() > 0:
                                await element.first.click(timeout=5000, force=True)
                                await asyncio.sleep(5)
                                
                                # Check for CloudFront video after click
                                for attempt in range(5):
                                    cf_video = page.locator('video[src*="cloudfront.net"][src*=".mp4"]')
                                    if await cf_video.count() > 0:
                                        for i in range(await cf_video.count()):
                                            src = await cf_video.nth(i).get_attribute("src")
                                            if src and src not in existing_videos:
                                                logger.info(f"Found CloudFront video: {src[:100]}")
                                                return src
                                    await asyncio.sleep(2)
                                break
                    except Exception as e:
                        logger.debug(f"Could not click grid item: {e}")
                
                # Strategy 1: Look for the first video in history/list view (Higgsfield specific)
                # The completed video appears as the first item in the history list
                history_video_selectors = [
                    'main video:first-of-type',  # First video in main content
                    '[class*="history"] video:first-of-type',
                    '[class*="list"] video:first-of-type',
                    'div[role="list"] video:first-of-type',
                    '.grid video:first-of-type',
                    'ul video:first-of-type',
                    'article video:first-of-type',
                ]
                
                for selector in history_video_selectors:
                    try:
                        first_video = page.locator(selector)
                        if await first_video.count() > 0:
                            src = await first_video.first.get_attribute("src")
                            # For blob URLs, try to find download link instead
                            if src and src.startswith("blob:"):
                                # Look for nearby download link
                                parent = first_video.first.locator("xpath=ancestor::*[position()<=3]")
                                download = parent.locator('a[download], a[href*=".mp4"], button:has-text("Download")')
                                if await download.count() > 0:
                                    href = await download.first.get_attribute("href")
                                    if self._is_valid_video_url(href, existing_videos):
                                        logger.info(f"Found download link near blob video: {href[:150]}")
                                        return href
                            elif self._is_valid_video_url(src, existing_videos):
                                logger.info(f"Found first video in history/list: {src[:150]}")
                                return src
                    except Exception as e:
                        logger.debug(f"History video selector failed: {selector}, error: {e}")
                        continue
                
                # Strategy 2: Look for result/output container with video
                result_containers = [
                    '.result video',
                    '.output video',
                    '.generation-result video',
                    '[data-result] video',
                    '.preview-container video',
                    '.video-result video',
                ]
                
                for container_selector in result_containers:
                    result_video = page.locator(container_selector)
                    if await result_video.count() > 0:
                        try:
                            src = await result_video.first.get_attribute("src")
                            if self._is_valid_video_url(src, existing_videos):
                                logger.info(f"Found video in result container: {src[:150]}")
                                return src
                        except:
                            pass
                
                # Strategy 2: Look for video elements with CloudFront src
                # CloudFront URLs are the actual video files: d8j0ntlcm91z4.cloudfront.net/user_{ID}/{UUID}.mp4
                
                # Check ALL video elements for CloudFront URLs
                all_videos = await page.locator('video').all()
                all_video_srcs = set()
                
                for vid in all_videos:
                    try:
                        src = await vid.get_attribute("src")
                        if not src:
                            continue
                        all_video_srcs.add(src)
                        
                        # Check for NEW CloudFront video (this is what we want!)
                        if "cloudfront.net" in src and ".mp4" in src:
                            if src not in existing_videos:
                                logger.info(f"Found NEW CloudFront video: {src}")
                                return src
                    except:
                        continue
                
                # Find which ones are NEW
                new_video_srcs = all_video_srcs - existing_videos
                
                # Check if any new video appeared (even non-CloudFront)
                for src in new_video_srcs:
                    if ".mp4" in src:
                        logger.info(f"Found NEW video (non-CloudFront): {src[:150]}")
                        # If it's cdn.higgsfield, we can still use it
                        if "cdn.higgsfield.ai" in src:
                            return src
                
                # Log progress every 40 seconds
                if poll_count % 4 == 0:
                    logger.info(f"Waiting for video... ({elapsed}s elapsed, {len(new_video_srcs)} new sources found)")
                
                for src in new_video_srcs:
                    if self._is_valid_video_url(src, set()):  # Don't pass existing_videos since we already filtered
                        logger.info(f"Found valid new CDN video: {src[:150]}")
                        return src
                    else:
                        logger.debug(f"Video src rejected by validation: {src[:100]}")
                
                # Strategy 3: Check for download button and get its URL
                download_selectors = [
                    'a[download][href*=".mp4"]',
                    'a[download][href*="video"]',
                    'a[href*="cloudfront"][href*=".mp4"]',
                    'a[href*="cloudfront"][href*="video"]',
                    'a[href*="cdn.higgsfield.ai"]',  # Higgsfield CDN
                    'button[data-url*=".mp4"]',
                    'a[href*=".mp4"]:not([href^="blob:"])',
                    'a[href*=".webm"]:not([href^="blob:"])',
                    # Higgsfield specific - look for download buttons
                    'button:has-text("Download") + a',
                    'a[aria-label*="download" i]',
                    '[class*="download"] a[href]',
                ]
                
                for sel in download_selectors:
                    try:
                        download_link = page.locator(sel)
                        if await download_link.count() > 0:
                            href = await download_link.first.get_attribute("href") or await download_link.first.get_attribute("data-url")
                            if self._is_valid_video_url(href, existing_videos):
                                logger.info(f"Found video download link: {href[:100]}")
                                return href
                    except:
                        continue
                
                # Strategy 3b: Find download button - it's an icon button with download arrow
                # Look for buttons with download icon/tooltip in the video result toolbar
                download_button_selectors = [
                    'button:has-text("Download")',
                    'a:has-text("Download")',
                    '[aria-label*="download" i]',
                    '[title*="download" i]',
                    'button:has(svg[class*="download"])',
                    'button:has([class*="download"])',
                    # Icon button with download arrow - look for common icon patterns
                    'button svg path[d*="M19"]',  # Common download icon paths
                    '[data-testid*="download"]',
                    '.download-button',
                    # Look for toolbar buttons near video results
                    'button[class*="icon"]',
                ]
                
                download_buttons = page.locator(', '.join(download_button_selectors[:6]))
                download_count = await download_buttons.count()
                
                if download_count > 0:
                    # Try to get URL from download buttons
                    for i in range(min(download_count, 5)):
                        try:
                            btn = download_buttons.nth(i)
                            for attr in ["href", "data-url", "data-href"]:
                                url = await btn.get_attribute(attr)
                                if self._is_valid_video_url(url, existing_videos):
                                    logger.info(f"Found video from download button: {url[:100]}")
                                    return url
                        except:
                            continue
                
                # Strategy 4: Look for generation status indicators ("In Queue" / "In progress")
                # When these disappear, the video is complete and the URL should be in that container
                queue_indicator = page.locator(':has-text("In Queue"), :has-text("In queue")')
                progress_indicator = page.locator(':has-text("In Progress"), :has-text("In progress"), :has-text("Generating")')
                
                queue_count = await queue_indicator.count()
                progress_count = await progress_indicator.count()
                
                if poll_count % 2 == 0:
                    logger.info(f"Status check: queue_indicators={queue_count}, progress_indicators={progress_count}")
                
                # If we previously saw queue/progress but now it's gone, generation is complete
                if poll_count > 3 and queue_count == 0 and progress_count == 0:
                    logger.info("No queue/progress indicators found - checking if generation completed")
                    
                    # Try to find video elements that appeared after generation
                    all_vids = await page.locator('video').all()
                    for vid in all_vids:
                        try:
                            src = await vid.get_attribute("src")
                            if self._is_valid_video_url(src, existing_videos):
                                logger.info(f"Found new video after generation: {src[:150]}")
                                return src
                            # For blob URLs, try to find the actual download link nearby
                            elif src and src.startswith("blob:"):
                                parent = vid.locator("xpath=ancestor::div[position()<=5]")
                                download = parent.locator('a[href*=".mp4"], a[href*="cloudfront"], a[download]')
                                if await download.count() > 0:
                                    href = await download.first.get_attribute("href")
                                    if self._is_valid_video_url(href, existing_videos):
                                        logger.info(f"Found download near blob video: {href[:150]}")
                                        return href
                        except:
                            continue
                    
                    # Also scan all links for video URLs
                    try:
                        all_links = await page.locator('a[href]').all()
                        for link in all_links:
                            href = await link.get_attribute("href")
                            if self._is_valid_video_url(href, existing_videos):
                                logger.info(f"Found video URL in page links: {href[:150]}")
                                return href
                    except:
                        pass
                
                # Strategy 5: Check for percentage-based progress bars
                progress_value = None
                try:
                    progress_bar = page.locator('.progress-bar, [role="progressbar"], progress')
                    if await progress_bar.count() > 0:
                        text = await progress_bar.first.text_content()
                        if text and "%" in text:
                            progress_value = text
                except:
                    pass
                
                # Count blob videos (may indicate loading)
                blob_count = 0
                for vid in all_videos:
                    try:
                        src = await vid.get_attribute("src")
                        if src and src.startswith("blob:"):
                            blob_count += 1
                    except:
                        pass
                
                # Strategy 6: Search for CDN video URLs in links/elements
                if poll_count > 3:
                    try:
                        all_links = await page.locator('a[href]').all()
                        for link in all_links:
                            href = await link.get_attribute("href")
                            if self._is_valid_video_url(href, existing_videos):
                                logger.info(f"Found video link: {href[:100]}")
                                return href
                        
                        # Check data attributes
                        video_data_elements = await page.locator('[data-video-url], [data-src*="video"], [data-url*="video"]').all()
                        for elem in video_data_elements:
                            for attr in ["data-video-url", "data-src", "data-url"]:
                                try:
                                    val = await elem.get_attribute(attr)
                                    if self._is_valid_video_url(val, existing_videos):
                                        logger.info(f"Found video in data attr: {val[:100]}")
                                        return val
                                except:
                                    continue
                    except:
                        pass
                
                # Log progress every 60 seconds
                if poll_count % 6 == 0:
                    logger.info(f"Waiting for video... ({elapsed}s elapsed)")
                
                # If progress completed (100%), look harder for video
                if progress_value and "100" in progress_value:
                    await asyncio.sleep(3)
                    for vid in await page.locator('video').all():
                        try:
                            src = await vid.get_attribute("src")
                            if src and src not in existing_videos and not src.startswith(("data:", "blob:")):
                                logger.info(f"Found completed video: {src[:100]}")
                                return src
                        except:
                            continue
                
                # Check for error messages
                error_indicators = ['error', 'failed', 'unable', 'rejected']
                error_msg = page.locator('.error, [data-error], .error-message')
                if await error_msg.count() > 0:
                    try:
                        error_text = await error_msg.first.text_content()
                        if error_text and any(x in error_text.lower() for x in error_indicators):
                            logger.warning("Video generation error detected", error=error_text[:100])
                            return None
                    except:
                        pass
                
                await asyncio.sleep(10)
            
            logger.warning("Video generation timed out after polling")
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

