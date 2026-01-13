"""Instagram browser automation using Playwright."""

import asyncio
import random
from typing import List, Optional, Dict, Any
import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.config import get_settings
from app.services.platforms.base import Post, PostResult, UserProfile

logger = structlog.get_logger()
settings = get_settings()


class InstagramBrowser:
    """Instagram browser automation for actions not supported by Graph API."""

    def __init__(self):
        """Initialize browser automation."""
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in = False
        self._logged_in_username: Optional[str] = None  # Track logged-in username to filter from author extraction
        self._session_invalid = False

    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            
            # Match production Chrome on macOS (current stable version)
            self._context = await self._browser.new_context(
                viewport={"width": 1512, "height": 982},  # MacBook Pro 14" default
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="America/New_York",
            )
            
            # Anti-detection measures
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Realistic plugins array
                Object.defineProperty(navigator, 'plugins', {
                    get: () => {
                        const plugins = [
                            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                            { name: 'Native Client', filename: 'internal-nacl-plugin' }
                        ];
                        plugins.length = 3;
                        return plugins;
                    }
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Realistic platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'MacIntel'
                });
                
                // Hardware concurrency (typical MacBook)
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 10
                });
                
                // Device memory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
            """)
            
            self._page = await self._context.new_page()
            logger.info("Instagram browser initialized")

    async def _human_delay(self, min_seconds: float = 30.0, max_seconds: float = 120.0):
        """Add human-like delay between major actions (30 seconds to 2 minutes).
        
        Use this between significant actions like liking, commenting, following.
        For UI micro-interactions (clicking, typing), use _quick_delay instead.
        """
        delay = random.uniform(min_seconds, max_seconds)
        logger.info(f"Human delay: {delay:.1f} seconds before next action")
        await asyncio.sleep(delay)
    
    async def _quick_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0):
        """Quick delay for UI micro-interactions (clicking buttons, typing, etc.)."""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def _random_scroll(self):
        """Perform random scrolling to appear more human."""
        if self._page:
            scroll_amount = random.randint(100, 500)
            await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await self._quick_delay(0.3, 0.8)

    async def click_conversation_element(self, element, username: str = None) -> bool:
        """Robustly click on a conversation element with retry logic and fallbacks.
        
        Args:
            element: Playwright element handle for the conversation
            username: Username for logging purposes
            
        Returns:
            True if successfully clicked/navigated, False otherwise
        """
        if not element:
            return False
            
        # Try 1: Scroll into view and click with shorter timeout
        try:
            await element.scroll_into_view_if_needed(timeout=5000)
            await self._quick_delay(0.3, 0.5)
            await element.click(timeout=10000)
            logger.info("Clicked conversation element", username=username)
            return True
        except Exception as e:
            logger.debug("First click attempt failed", error=str(e), username=username)
        
        # Try 2: Force click (bypasses actionability checks)
        try:
            await element.click(force=True, timeout=5000)
            logger.info("Force clicked conversation element", username=username)
            return True
        except Exception as e:
            logger.debug("Force click attempt failed", error=str(e), username=username)
        
        # Try 3: Extract href and navigate directly
        try:
            href = await element.get_attribute("href")
            if href and "/direct/t/" in href:
                # Handle relative URLs
                if href.startswith("/"):
                    href = f"https://www.instagram.com{href}"
                logger.info("Navigating directly to conversation URL", url=href, username=username)
                await self._page.goto(href, wait_until="domcontentloaded", timeout=15000)
                return True
            
            # If element itself doesn't have href, try to find a child link
            child_link = await element.query_selector('a[href*="/direct/t/"]')
            if child_link:
                href = await child_link.get_attribute("href")
                if href:
                    if href.startswith("/"):
                        href = f"https://www.instagram.com{href}"
                    logger.info("Navigating to child link URL", url=href, username=username)
                    await self._page.goto(href, wait_until="domcontentloaded", timeout=15000)
                    return True
        except Exception as e:
            logger.warning("Failed to navigate via href fallback", error=str(e), username=username)
        
        return False

    async def open_conversation_by_username(self, target_username: str) -> bool:
        """Navigate to inbox and open a conversation by username.
        
        This method handles stale element references by navigating to the inbox
        and finding the conversation fresh each time.
        
        Args:
            target_username: The username/display name of the conversation to open
            
        Returns:
            True if successfully opened the conversation, False otherwise
        """
        import re
        
        try:
            await self._ensure_browser()
            if not self._page:
                self._page = await self._context.new_page()
            
            # Always navigate to inbox fresh to ensure clean state
            # (Instagram's split view can leave stale elements from previous conversations)
            logger.info("Navigating to inbox to find conversation", username=target_username)
            await self._page.goto("https://www.instagram.com/direct/inbox/", wait_until="domcontentloaded", timeout=30000)
            await self._quick_delay(1, 2)
            
            # Wait for inbox to load
            await self._page.wait_for_selector('div[role="button"]', timeout=10000)
            await self._quick_delay(0.5, 1)
            
            # Find conversation elements
            conv_elements = await self._page.query_selector_all('div[role="button"]')
            logger.info("Found conversation elements in inbox", count=len(conv_elements))
            
            # Look through each element to find one matching our target username
            for element in conv_elements:
                try:
                    # Try to get username from profile image alt text
                    username_found = None
                    
                    img_elements = await element.query_selector_all('img')
                    for img in img_elements:
                        alt_text = await img.get_attribute('alt')
                        if alt_text:
                            alt_match = re.match(r"^(.+?)(?:'s profile picture|'s photo)$", alt_text, re.IGNORECASE)
                            if alt_match:
                                username_found = alt_match.group(1).strip()
                                break
                    
                    # Fallback: check first span text
                    if not username_found:
                        spans = await element.query_selector_all('span')
                        for span in spans:
                            span_text = await span.text_content()
                            if span_text and len(span_text.strip()) > 0 and len(span_text.strip()) < 100:
                                username_found = span_text.strip()
                                break
                    
                    # Check if this matches our target
                    if username_found and username_found == target_username:
                        logger.info("Found matching conversation, clicking", username=target_username)
                        
                        # Click the element
                        await element.scroll_into_view_if_needed(timeout=5000)
                        await self._quick_delay(0.2, 0.4)
                        await element.click(timeout=10000)
                        
                        logger.info("Clicked conversation", username=target_username)
                        return True
                        
                except Exception as e:
                    logger.debug("Error checking conversation element", error=str(e))
                    continue
            
            logger.warning("Could not find conversation in inbox", username=target_username)
            return False
            
        except Exception as e:
            logger.warning("Failed to open conversation by username", error=str(e), username=target_username)
            return False

    async def load_cookies(self, cookies: Dict[str, str], username: Optional[str] = None):
        """Load cookies to restore session.
        
        Args:
            cookies: Dictionary of cookie name/value pairs
            username: Optional username to track for author filtering
        """
        await self._ensure_browser()
        
        cookie_list = [
            {"name": name, "value": value, "domain": ".instagram.com", "path": "/"}
            for name, value in cookies.items()
        ]
        
        await self._context.add_cookies(cookie_list)
        
        # Track the logged-in username if provided
        if username:
            self._logged_in_username = username
        
        logger.info("Cookies loaded", count=len(cookie_list), username=username)

    async def get_cookies(self) -> Dict[str, str]:
        """Get current session cookies."""
        if not self._context:
            return {}
        
        cookies = await self._context.cookies()
        return {c["name"]: c["value"] for c in cookies if "instagram.com" in c["domain"]}

    async def verify_session(self) -> bool:
        """Verify the current session is valid."""
        await self._ensure_browser()
        
        try:
            await self._page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=15000)
            await self._quick_delay(1, 2)
            
            # Check if we're redirected to login
            current_url = self._page.url
            if "login" in current_url or "accounts/login" in current_url:
                logger.info("Session invalid - redirected to login")
                self._logged_in = False
                self._session_invalid = True
                return False
            
            # Check if we're logged in by looking for the profile icon
            logged_in = await self._page.query_selector('[aria-label="Profile"]') is not None
            
            if not logged_in:
                # Also check for feed content as an indicator
                logged_in = await self._page.query_selector('[role="feed"]') is not None
            
            if not logged_in:
                # Check for navigation bar items (New post, etc.)
                logged_in = await self._page.query_selector('[aria-label="New post"]') is not None
            
            self._logged_in = logged_in
            self._session_invalid = not logged_in
            logger.info("Session verified", logged_in=logged_in)
            return logged_in
            
        except Exception as e:
            logger.error("Session verification failed", error=str(e))
            # If we have cookies, assume session might still be valid
            if self._context:
                cookies = await self._context.cookies()
                if any("instagram.com" in c.get("domain", "") for c in cookies):
                    logger.info("Assuming session valid based on cookies presence")
                    self._logged_in = True
                    return True
            return False
    
    @property
    def session_needs_refresh(self) -> bool:
        """Check if the session needs to be refreshed."""
        return self._session_invalid
    
    async def download_image_for_post(self, image_url: str) -> Optional[str]:
        """Download an image from URL for browser-based posting.
        
        Instagram browser automation requires local files, but the Graph API
        uses URLs. This method downloads the image to a temp file.
        
        Args:
            image_url: URL of the image to download
            
        Returns:
            Path to the downloaded image file, or None if failed
        """
        import tempfile
        import httpx
        import os
        
        try:
            logger.info("Downloading image for browser posting", url=image_url[:100])
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(image_url)
                response.raise_for_status()
                
                # Determine file extension from content type or URL
                content_type = response.headers.get("content-type", "")
                if "jpeg" in content_type or "jpg" in content_type:
                    ext = ".jpg"
                elif "png" in content_type:
                    ext = ".png"
                elif "webp" in content_type:
                    ext = ".webp"
                elif "gif" in content_type:
                    ext = ".gif"
                else:
                    # Try to get from URL
                    url_lower = image_url.lower()
                    if ".png" in url_lower:
                        ext = ".png"
                    elif ".gif" in url_lower:
                        ext = ".gif"
                    elif ".webp" in url_lower:
                        ext = ".webp"
                    else:
                        ext = ".jpg"  # Default to jpg
                
                # Create temp file
                fd, temp_path = tempfile.mkstemp(suffix=ext, prefix="ig_post_")
                os.close(fd)
                
                with open(temp_path, "wb") as f:
                    f.write(response.content)
                
                logger.info("Image downloaded for browser posting", path=temp_path, size=len(response.content))
                return temp_path
                
        except Exception as e:
            logger.error("Failed to download image for browser posting", url=image_url[:100], error=str(e))
            return None

    async def login(self, username: str, password: str) -> bool:
        """Log in to Instagram."""
        await self._ensure_browser()
        
        try:
            await self._page.goto("https://www.instagram.com/accounts/login/")
            await self._quick_delay(2, 3)
            
            # Accept cookies if prompted
            try:
                cookie_button = await self._page.query_selector(
                    'button:has-text("Accept")'
                )
                if cookie_button:
                    await cookie_button.click()
                    await self._human_delay()
            except Exception:
                pass
            
            # Enter username
            username_input = await self._page.wait_for_selector(
                'input[name="username"]',
                timeout=10000,
            )
            await username_input.type(username, delay=random.randint(50, 150))
            await self._human_delay()
            
            # Enter password
            password_input = await self._page.query_selector('input[name="password"]')
            await password_input.type(password, delay=random.randint(50, 150))
            await self._human_delay()
            
            # Click login
            login_button = await self._page.query_selector('button[type="submit"]')
            await login_button.click()
            
            # Wait for navigation
            await self._page.wait_for_load_state("networkidle")
            await self._quick_delay(3, 5)
            
            # Check for successful login
            if await self.verify_session():
                self._logged_in = True
                self._logged_in_username = username
                self._session_invalid = False
                logger.info("Login successful", username=username)
                return True
            
            logger.warning("Login may have failed", username=username)
            self._logged_in = False
            self._logged_in_username = None
            return False
            
        except Exception as e:
            logger.error("Login failed", error=str(e))
            self._logged_in = False
            return False

    async def like_post(self, post_url_or_id: str) -> bool:
        """Like a post."""
        await self._ensure_browser()
        
        try:
            # Navigate to post if needed
            if not post_url_or_id.startswith("http"):
                post_url = f"https://www.instagram.com/p/{post_url_or_id}/"
            else:
                post_url = post_url_or_id
            
            logger.info("Navigating to post", url=post_url)
            await self._page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
            await self._quick_delay(2, 4)  # Wait longer for page to fully load
            
            # Check if we're logged in or redirected to login
            current_url = self._page.url
            if "login" in current_url or "accounts/login" in current_url:
                logger.error("Not logged in - redirected to login page")
                self._session_invalid = True
                return False
            
            # Check for "Page not found" or similar error
            page_content = await self._page.content()
            if "Sorry, this page isn't available" in page_content or "Page Not Found" in page_content:
                logger.warning("Post not found or unavailable", url=post_url)
                return False
            
            # Try multiple selectors for the like button (Instagram changes these frequently)
            like_selectors = [
                # Main like button selectors
                'svg[aria-label="Like"]',
                '[aria-label="Like"]',
                'span[class*="xp7jhwk"] svg[aria-label="Like"]',
                'section svg[aria-label="Like"]',
                'article svg[aria-label="Like"]',
                # Button containers
                'button svg[aria-label="Like"]',
                'div[role="button"] svg[aria-label="Like"]',
                # Try by test ID if available
                '[data-testid="like-button"]',
                # Heart icon alternatives
                'svg[fill="none"][stroke="currentColor"]',
            ]
            
            like_button = None
            for selector in like_selectors:
                like_button = await self._page.query_selector(selector)
                if like_button:
                    logger.debug("Found like button with selector", selector=selector)
                    break
            
            # Check if already liked (unlike button present)
            unlike_selectors = [
                'svg[aria-label="Unlike"]',
                '[aria-label="Unlike"]',
                'button svg[aria-label="Unlike"]',
            ]
            
            for selector in unlike_selectors:
                unlike_button = await self._page.query_selector(selector)
                if unlike_button:
                    logger.info("Post already liked", url=post_url)
                    return True
            
            if like_button:
                # Get the parent button/clickable element for more reliable clicking
                try:
                    # Try to get the actual clickable parent
                    parent = await like_button.evaluate_handle(
                        "el => el.closest('div[role=\"button\"]') || el.closest('button') || el.parentElement"
                    )
                    if parent:
                        # Use JavaScript click for more reliability
                        await parent.evaluate("el => el.click()")
                        logger.debug("Clicked like button via parent element")
                    else:
                        # Direct click on the SVG
                        await like_button.evaluate("el => el.click()")
                        logger.debug("Clicked like button directly")
                except Exception as click_error:
                    logger.warning("Click method 1 failed, trying alternative", error=str(click_error))
                    try:
                        # Alternative: Use page click at element location
                        box = await like_button.bounding_box()
                        if box:
                            await self._page.mouse.click(
                                box["x"] + box["width"] / 2,
                                box["y"] + box["height"] / 2
                            )
                            logger.debug("Clicked like button via mouse coordinates")
                    except Exception as mouse_error:
                        logger.error("All click methods failed", error=str(mouse_error))
                        return False
                
                # Wait for the state to change
                await self._human_delay(1.5, 2.5)
                
                # Verify the like actually registered by checking for Unlike button
                for selector in unlike_selectors:
                    unlike_button = await self._page.query_selector(selector)
                    if unlike_button:
                        logger.info("Post liked successfully - verified Unlike button appeared", url=post_url)
                        return True
                
                # Also check if the Like button is gone (it should be)
                like_still_present = await self._page.query_selector('svg[aria-label="Like"]')
                if like_still_present:
                    logger.warning("Like button still present after click - like may not have registered", url=post_url)
                    return False
                
                # If Like button is gone but Unlike not found, might still be processing
                logger.info("Like button clicked, Like button no longer present", url=post_url)
                return True
            
            # Log page info for debugging
            logger.warning(
                "Like button not found",
                url=post_url,
                current_url=current_url,
            )
            return False
            
        except Exception as e:
            logger.error("Like failed", url=post_url_or_id, error=str(e))
            return False

    async def get_post_author(self) -> Optional[str]:
        """Extract the author username from the current post page.
        
        Call this after navigating to a post (e.g., after like_post).
        """
        if not self._page:
            return None
        
        try:
            import re
            
            # Reserved Instagram paths that are NOT usernames
            reserved_paths = {
                "reels", "reel", "explore", "direct", "accounts", "static", 
                "stories", "tags", "p", "tv", "live", "about", "legal",
                "privacy", "safety", "help", "api", "developer", "blog",
                "press", "jobs", "brand", "directory", "locations", "web",
                "download", "lite", "contact", "nametag", "session", "emails",
                "instagram", "facebook", "meta",
            }
            
            def is_valid_username(username: str) -> bool:
                """Check if username is valid and not a reserved path."""
                if not username:
                    return False
                if username.lower() in reserved_paths:
                    return False
                if not re.match(r'^[a-zA-Z0-9_.]{1,30}$', username):
                    return False
                return True
            
            # Method 1 (PRIORITY): Try meta tags - most reliable for Reels
            # og:description and title often contain @username of the actual author
            try:
                # Try og:description which often contains @username
                og_desc = await self._page.query_selector('meta[property="og:description"]')
                if og_desc:
                    content = await og_desc.get_attribute("content")
                    if content:
                        match = re.search(r'@([a-zA-Z0-9_.]+)', content)
                        if match:
                            username = match.group(1)
                            if is_valid_username(username):
                                logger.info("Extracted post author from og:description", username=username)
                                return username
                
                # Try og:title which may have different format
                og_title = await self._page.query_selector('meta[property="og:title"]')
                if og_title:
                    content = await og_title.get_attribute("content")
                    if content:
                        # Pattern: "Username on Instagram: ..." or "@username ..."
                        match = re.search(r'@([a-zA-Z0-9_.]+)', content)
                        if match:
                            username = match.group(1)
                            if is_valid_username(username):
                                logger.info("Extracted post author from og:title", username=username)
                                return username
                        # Pattern: "Username on Instagram" without @
                        match = re.search(r'^([a-zA-Z0-9_.]+)\s+on\s+Instagram', content, re.IGNORECASE)
                        if match:
                            username = match.group(1)
                            if is_valid_username(username):
                                logger.info("Extracted post author from og:title pattern", username=username)
                                return username
                
                # Try page title
                title = await self._page.title()
                if title:
                    match = re.search(r'@([a-zA-Z0-9_.]+)', title)
                    if match:
                        username = match.group(1)
                        if is_valid_username(username):
                            logger.info("Extracted post author from title", username=username)
                            return username
                    # Pattern: "Username on Instagram" or "Username (@handle)"
                    match = re.search(r'^([a-zA-Z0-9_.]+)\s+on\s+Instagram', title, re.IGNORECASE)
                    if match:
                        username = match.group(1)
                        if is_valid_username(username):
                            logger.info("Extracted post author from title pattern", username=username)
                            return username
            except Exception as e:
                logger.debug("Meta/title extraction failed", error=str(e))
            
            # Method 2: Try to extract from page's embedded JSON data
            try:
                scripts = await self._page.query_selector_all('script[type="application/ld+json"]')
                for script in scripts:
                    content = await script.inner_text()
                    if content:
                        import json
                        try:
                            data = json.loads(content)
                            # Look for author info
                            if isinstance(data, dict):
                                author = data.get("author", {})
                                if isinstance(author, dict):
                                    identifier = author.get("identifier", {})
                                    if isinstance(identifier, dict):
                                        username = identifier.get("value")
                                        if is_valid_username(username):
                                            logger.info("Extracted post author from JSON-LD", username=username)
                                            return username
                                    alt_name = author.get("alternateName")
                                    if alt_name and alt_name.startswith("@"):
                                        username = alt_name[1:]
                                        if is_valid_username(username):
                                            logger.info("Extracted post author from JSON-LD alternateName", username=username)
                                            return username
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                logger.debug("JSON-LD extraction failed", error=str(e))
            
            # Method 3: Look for username in visible text elements (for Reels especially)
            try:
                # Reels often show username near the top of the page
                # Look for elements with username patterns
                username_selectors = [
                    'span[dir="auto"] a[href^="/"]',  # Username link in span
                    'div[role="button"] span a[href^="/"]',  # Username in button/link
                    'a[role="link"][href^="/"]',  # Direct profile link
                ]
                
                for selector in username_selectors:
                    elements = await self._page.query_selector_all(selector)
                    for element in elements:
                        href = await element.get_attribute("href")
                        if not href:
                            continue
                        # Skip non-profile links
                        if any(x in href for x in ["/p/", "/reel/", "/reels/", "/explore/", "/direct/", "/accounts/", "/static/", "/stories/", "/tags/", "/tv/", "/live/", "/hashtag/", "?", "#"]):
                            continue
                        # Check if it's a simple /username/ path
                        parts = [p for p in href.split("/") if p]
                        if len(parts) == 1:
                            username = parts[0]
                            # Skip if it's our own username
                            if self._logged_in_username and username.lower() == self._logged_in_username.lower():
                                continue
                            if is_valid_username(username):
                                logger.info("Extracted post author from visible link", username=username)
                                return username
            except Exception as e:
                logger.debug("Visible link extraction failed", error=str(e))
            
            # Method 4: Look for username link in the post header area
            try:
                # Look for author link near the post content
                author_selectors = [
                    'header a[href^="/"]',  # Author link in header
                    'article a[href^="/"]',  # Author link in article
                    'div[role="dialog"] a[href^="/"]',  # Modal view
                ]
                
                for selector in author_selectors:
                    links = await self._page.query_selector_all(selector)
                    for link in links:
                        href = await link.get_attribute("href")
                        if not href:
                            continue
                        # Skip non-profile links
                        if any(x in href for x in ["/p/", "/reel/", "/reels/", "/explore/", "/direct/", "/accounts/", "/static/", "/stories/", "/tags/", "/tv/", "/live/", "/hashtag/", "?", "#"]):
                            continue
                        # Check if it's a simple /username/ path
                        parts = [p for p in href.split("/") if p]
                        if len(parts) == 1:
                            username = parts[0]
                            # Skip if it's our own username
                            if self._logged_in_username and username.lower() == self._logged_in_username.lower():
                                continue
                            if is_valid_username(username):
                                logger.info("Extracted post author from header link", username=username)
                                return username
            except Exception as e:
                logger.debug("Header link extraction failed", error=str(e))
            
            # Method 5: Try to find username from aria-label attributes
            try:
                # Some profile links have aria-label with the username
                aria_links = await self._page.query_selector_all('a[aria-label]')
                for link in aria_links:
                    aria = await link.get_attribute("aria-label")
                    href = await link.get_attribute("href")
                    if aria and href:
                        # Skip non-profile links
                        if any(x in href for x in ["/p/", "/reel/", "/explore/", "/direct/"]):
                            continue
                        # Extract username from aria-label like "username's profile picture"
                        match = re.search(r"^([a-zA-Z0-9_.]+)'s\s+profile", aria, re.IGNORECASE)
                        if match:
                            username = match.group(1)
                            if self._logged_in_username and username.lower() == self._logged_in_username.lower():
                                continue
                            if is_valid_username(username):
                                logger.info("Extracted post author from aria-label", username=username)
                                return username
            except Exception as e:
                logger.debug("Aria-label extraction failed", error=str(e))
            
            logger.debug("Could not extract post author from page")
            return None
            
        except Exception as e:
            logger.debug("Failed to extract post author", error=str(e))
            return None

    async def get_post_image_url(self) -> Optional[str]:
        """Extract the main image/video thumbnail URL from the current post page.
        
        Call this after navigating to a post (e.g., after like_post).
        """
        if not self._page:
            return None
        
        try:
            # Method 1: Try to get from meta og:image tag (most reliable)
            try:
                meta_image = await self._page.query_selector('meta[property="og:image"]')
                if meta_image:
                    content = await meta_image.get_attribute("content")
                    if content and content.startswith("http"):
                        logger.info("Extracted image URL from og:image", url=content[:80])
                        return content
            except Exception as e:
                logger.debug("og:image extraction failed", error=str(e))
            
            # Method 2: Try to get from the main post image element
            try:
                # Look for the main image in the post
                img_selectors = [
                    'article img[style*="object-fit"]',
                    'article div[role="button"] img',
                    'article img[alt]',
                    'div[role="presentation"] img',
                ]
                
                for selector in img_selectors:
                    img = await self._page.query_selector(selector)
                    if img:
                        src = await img.get_attribute("src")
                        if src and src.startswith("http") and "150x150" not in src and "s64x64" not in src:
                            logger.info("Extracted image URL from img element", url=src[:80])
                            return src
            except Exception as e:
                logger.debug("Img element extraction failed", error=str(e))
            
            # Method 3: Check for video poster
            try:
                video = await self._page.query_selector('article video')
                if video:
                    poster = await video.get_attribute("poster")
                    if poster and poster.startswith("http"):
                        logger.info("Extracted video poster URL", url=poster[:80])
                        return poster
            except Exception as e:
                logger.debug("Video poster extraction failed", error=str(e))
            
            logger.debug("Could not extract image URL from page")
            return None
            
        except Exception as e:
            logger.debug("Failed to extract post image URL", error=str(e))
            return None

    async def unlike_post(self, post_url_or_id: str) -> bool:
        """Unlike a post."""
        await self._ensure_browser()
        
        try:
            if not post_url_or_id.startswith("http"):
                post_url = f"https://www.instagram.com/p/{post_url_or_id}/"
            else:
                post_url = post_url_or_id
            
            await self._page.goto(post_url, wait_until="networkidle")
            await self._human_delay()
            
            unlike_button = await self._page.query_selector(
                '[aria-label="Unlike"][role="button"]'
            )
            
            if unlike_button:
                await unlike_button.click()
                await self._human_delay()
                return True
            
            return False
            
        except Exception as e:
            logger.error("Unlike failed", error=str(e))
            return False

    async def comment_on_post(self, post_url_or_id: str, text: str) -> Optional[str]:
        """Comment on a post."""
        await self._ensure_browser()
        
        try:
            if not post_url_or_id.startswith("http"):
                post_url = f"https://www.instagram.com/p/{post_url_or_id}/"
            else:
                post_url = post_url_or_id
            
            # Check if we're already on this page (from a previous like action)
            current_url = self._page.url
            if post_url not in current_url:
                logger.info("Navigating to post for comment", url=post_url)
                await self._page.goto(post_url, wait_until="domcontentloaded", timeout=30000)
                await self._quick_delay(2, 4)
            else:
                # If we're already on the page, just wait a moment for any dynamic updates
                await self._quick_delay(1, 2)
            
            # Try multiple selectors for the comment input (Instagram changes these)
            comment_selectors = [
                'textarea[aria-label="Add a comment…"]',
                'textarea[placeholder="Add a comment…"]',
                'textarea[aria-label="Add a comment..."]',
                'form textarea',
                '[contenteditable="true"]',
            ]
            
            comment_input = None
            for selector in comment_selectors:
                try:
                    comment_input = await self._page.query_selector(selector)
                    if comment_input:
                        logger.debug("Found comment input with selector", selector=selector)
                        break
                except Exception:
                    continue
            
            if not comment_input:
                logger.warning("Comment input not found", url=post_url)
                return None
            
            # Click to focus - use JavaScript click for reliability
            try:
                await comment_input.evaluate("el => el.click()")
            except Exception:
                await comment_input.click()
            
            await self._quick_delay(0.5, 1)
            
            # Re-query the input after clicking (it might have transformed)
            for selector in comment_selectors:
                try:
                    comment_input = await self._page.query_selector(selector)
                    if comment_input:
                        break
                except Exception:
                    continue
            
            if not comment_input:
                logger.warning("Comment input disappeared after click", url=post_url)
                return None
            
            # Type the comment - use fill for reliability instead of type
            try:
                await comment_input.fill(text)
            except Exception:
                # Fallback to typing character by character
                await comment_input.type(text, delay=random.randint(30, 80))
            
            await self._quick_delay(0.5, 1.5)
            
            # Find and click post button - try multiple selectors
            post_button_selectors = [
                'div[role="button"]:has-text("Post")',
                'button:has-text("Post")',
                '[role="button"]:text("Post")',
                'form button[type="submit"]',
            ]
            
            post_button = None
            for selector in post_button_selectors:
                try:
                    post_button = await self._page.query_selector(selector)
                    if post_button:
                        # Make sure it's enabled/visible
                        is_disabled = await post_button.get_attribute("disabled")
                        if not is_disabled:
                            break
                        post_button = None
                except Exception:
                    continue
            
            if post_button:
                try:
                    await post_button.evaluate("el => el.click()")
                except Exception:
                    await post_button.click()
                    
                await self._human_delay(1.5, 3)
                logger.info("Comment posted", url=post_url, text_preview=text[:50])
                return "comment_posted"
            else:
                logger.warning("Post button not found or disabled", url=post_url)
                return None
            
        except Exception as e:
            logger.error("Comment failed", url=post_url_or_id, error=str(e))
            return None

    async def follow_user(self, username: str) -> bool:
        """Follow a user."""
        await self._ensure_browser()
        
        try:
            logger.info("Navigating to user profile for follow", username=username)
            await self._page.goto(
                f"https://www.instagram.com/{username}/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await self._quick_delay(2, 4)
            
            # Check if we're redirected to login
            current_url = self._page.url
            if "login" in current_url or "accounts/login" in current_url:
                logger.error("Not logged in - redirected to login page")
                self._session_invalid = True
                return False
            
            # Check if page not found
            page_content = await self._page.content()
            if "Sorry, this page isn't available" in page_content:
                logger.warning("User profile not found", username=username)
                return False
            
            # Check if already following first
            already_following_selectors = [
                'button:has-text("Following")',
                'button:has-text("Requested")',
                '[aria-label="Following"]',
            ]
            
            for selector in already_following_selectors:
                try:
                    already_following = await self._page.query_selector(selector)
                    if already_following:
                        logger.info("Already following user", username=username)
                        return True
                except Exception:
                    continue
            
            # Try multiple selectors for the follow button
            follow_selectors = [
                # Direct text match
                'button:has-text("Follow")',
                # Header area follow button (primary button usually)
                'header button:has-text("Follow")',
                'section button:has-text("Follow")',
                # By role
                'button[type="button"]:has-text("Follow")',
            ]
            
            follow_button = None
            for selector in follow_selectors:
                try:
                    buttons = await self._page.query_selector_all(selector)
                    for btn in buttons:
                        # Make sure it's not "Following" or "Follow Back"
                        text = await btn.inner_text()
                        if text.strip() == "Follow":
                            follow_button = btn
                            break
                    if follow_button:
                        break
                except Exception:
                    continue
            
            if follow_button:
                try:
                    await follow_button.evaluate("el => el.click()")
                except Exception:
                    await follow_button.click()
                    
                await self._human_delay(1.5, 3)
                
                # Verify the follow worked by checking for "Following" or "Requested"
                for selector in already_following_selectors:
                    try:
                        now_following = await self._page.query_selector(selector)
                        if now_following:
                            logger.info("Successfully followed user - verified", username=username)
                            return True
                    except Exception:
                        continue
                
                # If we can't verify, assume success if button was clicked
                logger.info("Followed user (unverified)", username=username)
                return True
            
            logger.warning("Follow button not found", username=username)
            return False
            
        except Exception as e:
            logger.error("Follow failed", username=username, error=str(e))
            return False

    async def unfollow_user(self, username: str) -> bool:
        """Unfollow a user."""
        await self._ensure_browser()
        
        try:
            await self._page.goto(
                f"https://www.instagram.com/{username}/",
                wait_until="networkidle",
            )
            await self._human_delay()
            
            following_button = await self._page.query_selector(
                'button:has-text("Following")'
            )
            
            if following_button:
                await following_button.click()
                await self._human_delay()
                
                # Confirm unfollow
                unfollow_confirm = await self._page.query_selector(
                    'button:has-text("Unfollow")'
                )
                if unfollow_confirm:
                    await unfollow_confirm.click()
                    await self._human_delay()
                    logger.info("Unfollowed user", username=username)
                    return True
            
            return False
            
        except Exception as e:
            logger.error("Unfollow failed", username=username, error=str(e))
            return False

    async def get_home_feed(self, limit: int = 20) -> List[Post]:
        """Get posts from home feed."""
        await self._ensure_browser()
        posts = []
        
        try:
            await self._page.goto("https://www.instagram.com/", wait_until="networkidle")
            await self._human_delay()
            
            # Scroll and collect posts
            for _ in range(min(limit // 5, 10)):
                await self._random_scroll()
                await self._human_delay()
            
            # Extract post data (simplified)
            articles = await self._page.query_selector_all('article')
            
            for article in articles[:limit]:
                try:
                    # Get post link
                    link = await article.query_selector('a[href*="/p/"]')
                    if link:
                        href = await link.get_attribute("href")
                        post_id = href.split("/p/")[1].rstrip("/") if "/p/" in href else ""
                        
                        posts.append(Post(
                            id=post_id,
                            author_id="",
                            author_username="",
                            content="",
                            url=f"https://www.instagram.com{href}",
                        ))
                except Exception:
                    continue
            
        except Exception as e:
            logger.error("Get feed failed", error=str(e))
        
        return posts

    async def search_hashtag(self, hashtag: str, limit: int = 20) -> List[Post]:
        """Search for posts by hashtag."""
        await self._ensure_browser()
        posts = []
        
        try:
            logger.info("Searching hashtag", hashtag=hashtag)
            
            await self._page.goto(
                f"https://www.instagram.com/explore/tags/{hashtag}/",
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await self._quick_delay(2, 4)
            
            # Check if redirected to login
            current_url = self._page.url
            if "login" in current_url or "accounts/login" in current_url:
                logger.error("Not logged in - redirected to login during hashtag search")
                self._session_invalid = True
                return []
            
            # Scroll to load more posts
            for _ in range(min(limit // 10, 5)):
                await self._random_scroll()
                await self._human_delay()
            
            # Extract post and reel links - Instagram now mixes both in hashtag pages
            # First get regular posts
            post_links = await self._page.query_selector_all('a[href*="/p/"]')
            # Then get reels
            reel_links = await self._page.query_selector_all('a[href*="/reel/"]')
            
            seen_ids = set()
            
            # Process regular posts
            for link in post_links:
                if len(posts) >= limit:
                    break
                    
                try:
                    href = await link.get_attribute("href")
                    if href and "/p/" in href:
                        post_id = href.split("/p/")[1].rstrip("/")
                        
                        if post_id not in seen_ids:
                            seen_ids.add(post_id)
                            post_url = f"https://www.instagram.com{href}"
                            posts.append(Post(
                                id=post_id,
                                author_id="",
                                author_username="",
                                content="",
                                hashtags=[hashtag],
                                url=post_url,
                            ))
                            logger.debug("Found post", post_id=post_id, url=post_url)
                except Exception:
                    continue
            
            # Process reels
            for link in reel_links:
                if len(posts) >= limit:
                    break
                    
                try:
                    href = await link.get_attribute("href")
                    if href and "/reel/" in href:
                        post_id = href.split("/reel/")[1].rstrip("/")
                        
                        if post_id not in seen_ids:
                            seen_ids.add(post_id)
                            post_url = f"https://www.instagram.com{href}"
                            posts.append(Post(
                                id=post_id,
                                author_id="",
                                author_username="",
                                content="",
                                hashtags=[hashtag],
                                url=post_url,
                            ))
                            logger.debug("Found reel", post_id=post_id, url=post_url)
                except Exception:
                    continue
            
            logger.info("Hashtag search complete", hashtag=hashtag, posts_found=len(posts))
            
        except Exception as e:
            logger.error("Hashtag search failed", hashtag=hashtag, error=str(e))
        
        return posts

    async def get_user_profile(self, username: str) -> Optional[UserProfile]:
        """Get a user's profile information."""
        await self._ensure_browser()
        
        try:
            await self._page.goto(
                f"https://www.instagram.com/{username}/",
                wait_until="networkidle",
            )
            await self._human_delay()
            
            # Extract profile data (simplified)
            return UserProfile(
                id=username,
                username=username,
            )
            
        except Exception as e:
            logger.error("Get profile failed", username=username, error=str(e))
            return None

    async def get_user_posts(self, username: str, limit: int = 20) -> List[Post]:
        """Get posts from a specific user."""
        await self._ensure_browser()
        posts = []
        
        try:
            await self._page.goto(
                f"https://www.instagram.com/{username}/",
                wait_until="networkidle",
            )
            await self._human_delay()
            
            # Extract post links
            links = await self._page.query_selector_all('a[href*="/p/"]')
            
            for link in links[:limit]:
                try:
                    href = await link.get_attribute("href")
                    if href and "/p/" in href:
                        post_id = href.split("/p/")[1].rstrip("/")
                        posts.append(Post(
                            id=post_id,
                            author_id=username,
                            author_username=username,
                            content="",
                            url=f"https://www.instagram.com{href}",
                        ))
                except Exception:
                    continue
            
        except Exception as e:
            logger.error("Get user posts failed", username=username, error=str(e))
        
        return posts

    async def get_own_profile(self) -> Optional[UserProfile]:
        """Get the logged-in user's profile."""
        await self._ensure_browser()
        
        try:
            # Click profile icon
            profile_link = await self._page.query_selector('[aria-label="Profile"]')
            if profile_link:
                await profile_link.click()
                await self._page.wait_for_load_state("networkidle")
                await self._human_delay()
                
                # Get username from URL
                url = self._page.url
                username = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
                
                return UserProfile(id=username, username=username)
            
            return None
            
        except Exception as e:
            logger.error("Get own profile failed", error=str(e))
            return None

    async def create_post(
        self,
        caption: str,
        media_path: Optional[str] = None,
    ) -> PostResult:
        """Create a post using browser automation.
        
        Instagram requires an image for every post. The media_path should be
        a path to a local image file.
        
        Args:
            caption: Post caption
            media_path: Path to local image file (required for Instagram)
            
        Returns:
            PostResult with success status and post ID if available
        """
        await self._ensure_browser()
        
        if not media_path:
            logger.error("Instagram requires an image for every post")
            return PostResult(
                success=False,
                error_message="Instagram requires an image for every post",
            )
        
        try:
            logger.info("Creating Instagram post via browser", caption_length=len(caption), media=media_path)
            
            # Navigate to Instagram home page
            await self._page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
            await self._quick_delay(2, 3)
            
            # Check if we're logged in
            logged_in = await self.verify_session()
            if not logged_in:
                logger.error("Not logged in, cannot create post")
                return PostResult(
                    success=False,
                    error_message="Instagram session invalid - please re-authenticate",
                )
            
            # Find and click the "Create" or "New post" button
            create_button = None
            create_selectors = [
                '[aria-label="New post"]',
                '[aria-label="Create"]',
                'svg[aria-label="New post"]',
                'svg[aria-label="Create"]',
                '[href="/create/style/"]',
                'a[href*="create"]',
            ]
            
            for selector in create_selectors:
                create_button = await self._page.query_selector(selector)
                if create_button:
                    logger.info("Found create button", selector=selector)
                    break
            
            if not create_button:
                # Try clicking the + icon in the navigation
                nav_items = await self._page.query_selector_all('nav a, nav svg')
                for item in nav_items:
                    try:
                        aria_label = await item.get_attribute("aria-label")
                        if aria_label and ("create" in aria_label.lower() or "new" in aria_label.lower()):
                            create_button = item
                            logger.info("Found create button in nav", label=aria_label)
                            break
                    except Exception:
                        continue
            
            if not create_button:
                logger.error("Create button not found on Instagram")
                return PostResult(
                    success=False,
                    error_message="Create button not found - Instagram UI may have changed",
                )
            
            await create_button.click()
            await self._quick_delay(1, 2)
            
            # Wait for the file input dialog or creation modal
            await self._quick_delay(1, 2)
            
            # Find the file input for image upload
            file_input = await self._page.query_selector('input[type="file"][accept*="image"]')
            
            if not file_input:
                # Sometimes the modal needs to load - wait and try again
                await self._quick_delay(2, 3)
                file_input = await self._page.query_selector('input[type="file"][accept*="image"]')
            
            if not file_input:
                # Try clicking "Select from computer" button if present
                select_button = await self._page.query_selector('button:has-text("Select from computer")')
                if select_button:
                    await select_button.click()
                    await self._quick_delay(1, 2)
                    file_input = await self._page.query_selector('input[type="file"][accept*="image"]')
            
            if not file_input:
                logger.error("File input not found for image upload")
                return PostResult(
                    success=False,
                    error_message="Image upload dialog not found",
                )
            
            # Upload the image
            logger.info("Uploading image", path=media_path)
            await file_input.set_input_files(media_path)
            await self._quick_delay(3, 5)
            
            # Wait for image to process
            # Look for "Next" button which appears after image is uploaded
            next_button = None
            for _ in range(10):  # Wait up to 10 iterations
                next_button = await self._page.query_selector('button:has-text("Next"), div[role="button"]:has-text("Next")')
                if next_button:
                    break
                await self._human_delay(1, 1.5)
            
            if not next_button:
                logger.error("Next button not found after image upload")
                return PostResult(
                    success=False,
                    error_message="Image upload may have failed - Next button not found",
                )
            
            # Click Next to go to filters/edit screen
            await next_button.click()
            await self._quick_delay(1, 2)
            
            # Click Next again to skip filters (go to caption screen)
            next_button = await self._page.wait_for_selector(
                'button:has-text("Next"), div[role="button"]:has-text("Next")',
                timeout=10000,
            )
            await next_button.click()
            await self._quick_delay(1, 2)
            
            # Now we should be on the caption screen
            # Find the caption textarea
            caption_input = None
            caption_selectors = [
                'textarea[aria-label*="caption"]',
                'textarea[aria-label*="Caption"]',
                '[contenteditable="true"]',
                'textarea[placeholder*="Write"]',
            ]
            
            for selector in caption_selectors:
                try:
                    caption_input = await self._page.wait_for_selector(selector, timeout=5000)
                    if caption_input:
                        logger.info("Found caption input", selector=selector)
                        break
                except Exception:
                    continue
            
            if not caption_input:
                logger.warning("Caption input not found, trying to post without caption")
            else:
                # Enter the caption
                await caption_input.click()
                await self._human_delay(0.3, 0.6)
                
                # Type caption with human-like delays
                type_delay = max(10, min(50, 2000 // len(caption))) if len(caption) > 0 else 30
                await caption_input.type(caption, delay=type_delay)
                await self._quick_delay(0.5, 1)
            
            # Find and click the Share button
            share_button = None
            share_selectors = [
                'button:has-text("Share")',
                'div[role="button"]:has-text("Share")',
                '[aria-label="Share"]',
            ]
            
            for selector in share_selectors:
                share_button = await self._page.query_selector(selector)
                if share_button:
                    logger.info("Found share button", selector=selector)
                    break
            
            if not share_button:
                logger.error("Share button not found")
                return PostResult(
                    success=False,
                    error_message="Share button not found",
                )
            
            # Click share
            logger.info("Clicking share button")
            await share_button.click()
            await self._quick_delay(3, 5)
            
            # Wait for post to be shared
            # Instagram shows "Post shared" or similar message, or redirects to profile
            success = False
            post_id = None
            post_url = None
            
            # Check for success indicators
            for _ in range(15):  # Wait up to 15 seconds
                # Check for "Post shared" message
                shared_message = await self._page.query_selector(':has-text("Post shared"), :has-text("Your post has been shared")')
                if shared_message:
                    success = True
                    logger.info("Post shared successfully (message confirmation)")
                    break
                
                # Check if modal is closed (returned to feed)
                modal_open = await self._page.query_selector('[role="dialog"]')
                if not modal_open:
                    success = True
                    logger.info("Post shared successfully (modal closed)")
                    break
                
                # Check current URL for post ID
                current_url = self._page.url
                if "/p/" in current_url:
                    post_id = current_url.split("/p/")[1].split("/")[0]
                    post_url = current_url
                    success = True
                    logger.info("Post created", post_id=post_id, url=post_url)
                    break
                
                await self._quick_delay(0.5, 1)
            
            if success:
                return PostResult(
                    success=True,
                    post_id=post_id,
                    url=post_url,
                )
            else:
                logger.warning("Post may have succeeded but could not confirm")
                return PostResult(
                    success=True,  # Assume success if no error
                    post_id=None,
                    url=None,
                )
            
        except Exception as e:
            logger.error("Instagram browser posting failed", error=str(e))
            return PostResult(
                success=False,
                error_message=f"Browser posting failed: {str(e)}",
            )

    # ===== DIRECT MESSAGES =====
    
    async def _get_message_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get message requests (DMs from people you don't follow).
        
        These are stored separately from the main inbox.
        """
        conversations = []
        
        try:
            await self._ensure_browser()
            if not self._page:
                self._page = await self._context.new_page()
            
            # Navigate to message requests
            logger.info("Checking Instagram message requests")
            await self._page.goto("https://www.instagram.com/direct/requests/", wait_until="domcontentloaded", timeout=30000)
            await self._human_delay(2, 3)
            
            # Check if we're on the requests page
            current_url = self._page.url
            if "requests" not in current_url:
                logger.info("Message requests page not available")
                return conversations
            
            # Find request items - they're similar to regular inbox items
            request_selectors = [
                'div[role="button"]',
                'a[href*="/direct/t/"]',
                '[role="listitem"]',
            ]
            
            request_elements = []
            for selector in request_selectors:
                elements = await self._page.query_selector_all(selector)
                if len(elements) > 0:
                    request_elements = elements[:limit]
                    logger.info("Found request elements", selector=selector, count=len(request_elements))
                    break
            
            for idx, element in enumerate(request_elements):
                try:
                    # Get text content
                    text_content = await element.text_content() or ""
                    
                    # Try to get username from spans
                    username = None
                    spans = await element.query_selector_all('span')
                    for span in spans:
                        span_text = await span.text_content()
                        if span_text and len(span_text) > 1 and len(span_text) < 50:
                            if not username:
                                username = span_text.strip()
                                break
                    
                    if username:
                        conversations.append({
                            "conversation_id": f"request_{idx}",
                            "participant_username": username,
                            "participant_name": username,
                            "last_message_preview": None,
                            "unread": True,  # Requests are always "unread" in a sense
                            "is_request": True,
                            "_element": element,
                        })
                        logger.info("Found message request", username=username)
                        
                except Exception as e:
                    logger.warning("Failed to parse request", error=str(e))
                    continue
            
            logger.info("Fetched message requests", count=len(conversations))
            return conversations
            
        except Exception as e:
            logger.error("Failed to get message requests", error=str(e))
            return conversations
    
    async def get_dm_inbox(self, limit: int = 20, include_requests: bool = True) -> List[Dict[str, Any]]:
        """Get list of DM conversations from inbox and optionally requests.
        
        Args:
            limit: Maximum number of conversations to fetch
            include_requests: Whether to also check Message Requests
            
        Returns:
            List of conversation dictionaries with participant info
        """
        try:
            await self._ensure_browser()
            if not self._page:
                self._page = await self._context.new_page()
            
            all_conversations = []
            
            # Note: We DON'T fetch requests here because navigating away detaches elements.
            # Instead, we'll check requests separately and process them inline.
            # The include_requests flag is used to indicate we should also check requests.
            
            # Navigate to main inbox first
            logger.info("Navigating to Instagram DM inbox")
            await self._page.goto("https://www.instagram.com/direct/inbox/", wait_until="domcontentloaded", timeout=30000)
            await self._human_delay(3, 5)
            
            conversations = []
            
            # Wait for page to fully load - look for any inbox-related element
            # Instagram's inbox uses various selectors depending on UI version
            inbox_selectors = [
                '[aria-label*="Chats"]',
                '[aria-label*="Message"]',
                'a[href*="/direct/t/"]',
                'div[class*="x9f619"]',  # Instagram's common container class
                '[role="main"]',
            ]
            
            page_loaded = False
            for selector in inbox_selectors:
                try:
                    await self._page.wait_for_selector(selector, timeout=5000)
                    page_loaded = True
                    logger.info("Inbox page loaded", selector=selector)
                    break
                except Exception:
                    continue
            
            if not page_loaded:
                # Take screenshot for debugging
                logger.warning("Inbox selectors not found, attempting to continue anyway")
                await self._human_delay(2, 3)
            
            # Find conversation items - Instagram uses links to individual threads
            # First, let's log the current URL to confirm we're on the right page
            current_url = self._page.url
            logger.info("On inbox page", url=current_url)
            
            conversation_selectors = [
                'a[href*="/direct/t/"]',
                '[role="listitem"]',
                '[role="row"]',
                'div[role="button"]',
            ]
            
            conv_elements = []
            for selector in conversation_selectors:
                elements = await self._page.query_selector_all(selector)
                logger.info("Selector check", selector=selector, count=len(elements))
                if elements:
                    conv_elements = elements[:limit]
                    logger.info("Found conversation elements", selector=selector, count=len(conv_elements))
                    break
            
            # If still no elements, try to get all links and filter for /direct/
            if not conv_elements:
                all_links = await self._page.query_selector_all('a')
                dm_links = []
                for link in all_links:
                    href = await link.get_attribute("href")
                    if href and "/direct/" in href:
                        dm_links.append(link)
                        logger.info("Found DM link", href=href)
                conv_elements = dm_links[:limit]
            
            for idx, element in enumerate(conv_elements):
                try:
                    # Extract conversation info
                    username = None
                    display_name = None
                    last_message = None
                    unread = False
                    conversation_id = None
                    
                    import re
                    
                    # PRIMARY METHOD: Get username from profile image alt text
                    # Instagram profile pics always have alt like "username's profile picture"
                    # This is the most reliable source - don't try to parse from random text
                    img_elements = await element.query_selector_all('img')
                    for img in img_elements:
                        alt_text = await img.get_attribute('alt')
                        if alt_text:
                            # Match patterns like "username's profile picture" or "Display Name's profile picture"
                            alt_match = re.match(r"^(.+?)(?:'s profile picture|'s photo)$", alt_text, re.IGNORECASE)
                            if alt_match:
                                username = alt_match.group(1).strip()
                                display_name = username
                                logger.info("Found username from profile image", username=username)
                                break
                    
                    # FALLBACK: If no profile image found, try aria-label on the element
                    if not username:
                        aria_label = await element.get_attribute("aria-label")
                        if aria_label:
                            # aria-label often contains "Conversation with username"
                            aria_match = re.match(r"^(?:Conversation with |Chat with )?(.+?)(?:'s conversation)?$", aria_label, re.IGNORECASE)
                            if aria_match:
                                username = aria_match.group(1).strip()
                                display_name = username
                                logger.info("Found username from aria-label", username=username)
                    
                    # LAST RESORT: Get the first distinct text that isn't a timestamp or common UI text
                    if not username:
                        time_pattern = re.compile(r'^(\d+[smhdwMy]|Active\s*(now|today|\d+[smhdw]\s*ago)|Just\s*now|Now|Yesterday)$', re.IGNORECASE)
                        ui_texts = {"Your note", "Seen", "Sent", "Delivered", "Active now", "Typing..."}
                        self_username = (self._logged_in_username or "").lower()
                        
                        spans = await element.query_selector_all('span')
                        for span in spans:
                            span_text = await span.text_content()
                            if not span_text:
                                continue
                            text = span_text.strip()
                            
                            # Skip empty, timestamps, UI text, and self
                            if not text or len(text) > 100:
                                continue
                            if time_pattern.match(text):
                                continue
                            if text in ui_texts:
                                continue
                            if text.lower() == self_username:
                                continue
                            
                            # First valid span is likely the display name/username
                            username = text
                            display_name = text
                            logger.info("Found username from first span (fallback)", username=username)
                            break
                    
                    # Get message preview - look for spans after we've identified the username
                    if username:
                        time_pattern = re.compile(r'^(\d+[smhdwMy]|Active\s*(now|today|\d+[smhdw]\s*ago)|Just\s*now|Now|Yesterday)$', re.IGNORECASE)
                        spans = await element.query_selector_all('span')
                        for span in spans:
                            span_text = await span.text_content()
                            if not span_text:
                                continue
                            text = span_text.strip()
                            
                            # Skip username, empty, timestamps
                            if not text or text == username or text == display_name:
                                continue
                            if time_pattern.match(text):
                                continue
                            if len(text) > 100:  # Skip very long concatenated text
                                continue
                            
                            # This is likely the message preview
                            last_message = text
                            break
                    
                    # Check for unread indicator (blue dot, bold text, etc.)
                    # Instagram uses various indicators for unread messages
                    unread_selectors = [
                        '[class*="unread"]',
                        '[aria-label*="unread"]',
                        'svg circle[fill="#0095F6"]',  # Blue dot SVG
                        'svg circle[fill="rgb(0, 149, 246)"]',
                        'div[style*="background-color: rgb(0, 149, 246)"]',
                        'div[style*="background: rgb(0, 149, 246)"]',
                        # Look for the blue notification dot
                        'div[class*="x1i10hfl"][style*="background"]',
                    ]
                    
                    unread = False
                    for unread_sel in unread_selectors:
                        try:
                            indicators = await element.query_selector_all(unread_sel)
                            if indicators and len(indicators) > 0:
                                unread = True
                                logger.info("Found unread indicator", selector=unread_sel, username=username)
                                break
                        except Exception:
                            continue
                    
                    # Also check if the text appears bold (Instagram bolds unread conversations)
                    if not unread:
                        try:
                            font_weight = await element.evaluate('el => window.getComputedStyle(el).fontWeight')
                            if font_weight and int(font_weight) >= 600:
                                unread = True
                                logger.info("Conversation appears bold (unread)", username=username)
                        except Exception:
                            pass
                    
                    # If no username found from spans, try aria-label
                    if not username:
                        aria_label = await element.get_attribute("aria-label")
                        if aria_label:
                            username = aria_label.split(" ")[0] if aria_label else None
                    
                    # Generate a pseudo conversation_id from index if we can't get the real one
                    # We'll click into the conversation to get the real ID
                    conversation_id = f"inbox_{idx}"
                    
                    if username:
                        conversations.append({
                            "conversation_id": conversation_id,
                            "participant_username": username,
                            "participant_name": display_name or username,
                            "last_message_preview": last_message,
                            "unread": unread,
                            "_element": element,  # Keep reference for clicking
                        })
                        logger.info("Found conversation", username=username, unread=unread, preview=last_message[:30] if last_message else None)
                        
                except Exception as e:
                    logger.warning("Failed to parse conversation", error=str(e))
                    continue
            
            # Combine with request conversations (requests first as they're likely more urgent)
            all_conversations.extend(conversations)
            logger.info("Fetched DM inbox", inbox_count=len(conversations), total_count=len(all_conversations))
            return all_conversations
            
        except Exception as e:
            logger.error("Failed to get DM inbox", error=str(e))
            return all_conversations  # Return any requests we found
    
    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get messages from a specific conversation.
        
        Args:
            conversation_id: The Instagram conversation/thread ID
            limit: Maximum number of messages to fetch
            
        Returns:
            List of message dictionaries
        """
        try:
            await self._ensure_browser()
            if not self._page:
                self._page = await self._context.new_page()
            
            # Navigate to specific conversation
            url = f"https://www.instagram.com/direct/t/{conversation_id}/"
            logger.info("Opening conversation", conversation_id=conversation_id)
            await self._page.goto(url, wait_until="networkidle", timeout=30000)
            await self._human_delay(2, 3)
            
            messages = []
            
            # Wait for messages to load
            await self._page.wait_for_selector('[role="row"], [class*="message"]', timeout=15000)
            
            # Find message elements
            message_selectors = [
                '[role="row"]',
                'div[class*="message-content"]',
                'div[class*="Message"]',
            ]
            
            msg_elements = []
            for selector in message_selectors:
                elements = await self._page.query_selector_all(selector)
                if elements:
                    msg_elements = elements[-limit:]  # Get most recent
                    break
            
            for element in msg_elements:
                try:
                    content = await element.text_content()
                    
                    # Determine if sent by us or received
                    # Usually outgoing messages have different styling
                    is_outgoing = False
                    elem_class = await element.get_attribute("class") or ""
                    if "sent" in elem_class.lower() or "outgoing" in elem_class.lower():
                        is_outgoing = True
                    
                    # Check for right-aligned messages (typically sent)
                    style = await element.evaluate("el => window.getComputedStyle(el).textAlign")
                    if style == "right":
                        is_outgoing = True
                    
                    if content and content.strip():
                        messages.append({
                            "content": content.strip(),
                            "is_outgoing": is_outgoing,
                            "timestamp": None,  # Would need more complex parsing
                        })
                        
                except Exception as e:
                    logger.warning("Failed to parse message", error=str(e))
                    continue
            
            logger.info("Fetched conversation messages", conversation_id=conversation_id, count=len(messages))
            return messages
            
        except Exception as e:
            logger.error("Failed to get conversation messages", error=str(e))
            return []
    
    async def accept_message_request(self) -> bool:
        """Accept a message request in the currently open conversation.
        
        When viewing a message request, there are "Block", "Delete", and "Accept" buttons
        at the bottom of the conversation panel.
        
        Returns:
            True if accepted successfully (or already accepted)
        """
        try:
            if not self._page:
                return False
            
            # Wait for the buttons to appear
            await self._quick_delay(1, 2)
            
            # The Accept button is typically at the bottom right of the conversation panel
            # It's alongside Block and Delete buttons
            accept_button = None
            
            # Try various selectors for the Accept button
            accept_selectors = [
                # Most specific - the actual button in the request footer
                'div[role="button"]:has-text("Accept"):not(:has-text("Block")):not(:has-text("Delete"))',
                'button:has-text("Accept")',
                '[role="button"]:has-text("Accept")',
                # Try by aria-label
                '[aria-label="Accept"]',
                '[aria-label*="Accept"]',
            ]
            
            for selector in accept_selectors:
                try:
                    accept_button = await self._page.query_selector(selector)
                    if accept_button:
                        # Verify it's the right button by checking text
                        text = await accept_button.text_content()
                        if text and 'Accept' in text and 'Block' not in text:
                            logger.info("Found Accept button", selector=selector, text=text)
                            break
                        accept_button = None
                except Exception:
                    continue
            
            # If still not found, try clicking in the bottom right area where Accept is located
            if not accept_button:
                # Find all buttons/clickable elements with "Accept" text
                all_elements = await self._page.query_selector_all('[role="button"], button')
                for element in all_elements:
                    try:
                        text = await element.text_content()
                        if text and text.strip() == 'Accept':
                            accept_button = element
                            logger.info("Found Accept button by iterating elements")
                            break
                    except Exception:
                        continue
            
            if accept_button:
                logger.info("Clicking Accept button")
                await accept_button.click()
                # Wait for the modal to appear
                await self._quick_delay(1, 2)
                
                # Instagram shows a modal: "Move messages from X into: Primary / General / Cancel"
                # We need to click "Primary" to accept into main inbox
                primary_selectors = [
                    'button:has-text("Primary")',
                    'div[role="button"]:has-text("Primary")',
                    '[role="button"]:has-text("Primary")',
                    'div:has-text("Primary"):not(:has-text("General"))',
                ]
                
                for selector in primary_selectors:
                    try:
                        primary_button = await self._page.query_selector(selector)
                        if primary_button:
                            text = await primary_button.text_content()
                            if text and 'Primary' in text:
                                logger.info("Found Primary button in modal, clicking")
                                await primary_button.click()
                                await self._human_delay(3, 5)
                                break
                    except Exception:
                        continue
                else:
                    # If no Primary button found, try clicking any dialog button that's not Cancel
                    all_buttons = await self._page.query_selector_all('[role="button"], button')
                    for btn in all_buttons:
                        text = await btn.text_content()
                        if text and text.strip() == 'Primary':
                            logger.info("Found Primary button by iterating, clicking")
                            await btn.click()
                            await self._human_delay(3, 5)
                            break
                
                # Log current URL after handling modal
                current_url = self._page.url
                logger.info("URL after accepting and choosing Primary", url=current_url)
                
                # Verify the message input now appears
                input_selectors = [
                    'textarea[placeholder*="Message"]',
                    'div[role="textbox"]',
                    '[contenteditable="true"]',
                    'textarea',
                    'input[type="text"]',
                ]
                
                for selector in input_selectors:
                    message_input = await self._page.query_selector(selector)
                    if message_input:
                        logger.info("Accept successful - message input found", selector=selector)
                        return True
                
                logger.warning("Clicked Accept and Primary but message input not found yet")
                # Give it more time
                await self._human_delay(2, 3)
                return True
            
            # If no Accept button found, maybe it's already accepted
            # Check if there's a message input (indicates we can reply)
            message_input = await self._page.query_selector('textarea[placeholder*="Message"], div[role="textbox"]')
            if message_input:
                logger.info("No Accept button but message input found - request may already be accepted")
                return True
            
            logger.warning("Could not find Accept button or message input")
            return False
            
        except Exception as e:
            logger.error("Failed to accept message request", error=str(e))
            return False
    
    async def get_messages_from_current_thread(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get messages from the currently open conversation thread.
        
        This assumes a conversation is already open (after clicking on it from inbox).
        
        Returns:
            List of message dictionaries
        """
        messages = []
        
        try:
            if not self._page:
                return messages
            
            # Wait a moment for messages to render
            await self._quick_delay(1, 2)
            
            # Skip common UI elements that aren't messages
            skip_texts = [
                'seen', 'delivered', 'sent', 'active now', 'active today',
                'message', 'home', 'search', 'explore', 'reels', 'messages',
                'notifications', 'create', 'profile', 'more', 'settings',
                'hidden requests', 'delete all', 'block', 'accept', 'delete',
                'back', 'instagram', 'threads', 'your note', 'add a note',
                'reply to note', 'note', 'notes', 'leave a note', 'their note',
                'replied to your note', 'replied to their note'
            ]
            
            # Patterns that indicate a Note (status) rather than a message
            note_indicators = [
                'replied to your note',
                'replied to their note', 
                'reply to note',
                'leave a note',
                'add a note',
            ]
            
            # Look for the actual message bubbles in the conversation
            # Instagram DM messages are typically in divs with specific structure
            message_container_selectors = [
                # Message bubble containers
                'div[class*="x1n2onr6"] div[dir="auto"]',
                'div[class*="xexx8yu"] span',
                # Fallback to spans with auto direction (actual text content)
                'div[role="row"] span[dir="auto"]',
            ]
            
            msg_elements = []
            for selector in message_container_selectors:
                elements = await self._page.query_selector_all(selector)
                if len(elements) >= 1:
                    msg_elements = elements[-limit:]
                    logger.info("Found potential message elements", selector=selector, count=len(msg_elements))
                    break
            
            # If no specific message elements found, try to find the message text directly
            if not msg_elements:
                # Look for any text that looks like a message (not navigation)
                all_spans = await self._page.query_selector_all('span[dir="auto"], div[dir="auto"]')
                for span in all_spans:
                    text = await span.text_content()
                    if text:
                        text = text.strip()
                        # Skip navigation and UI text
                        if text.lower() not in skip_texts and len(text) > 3 and len(text) < 1000:
                            # Check if it looks like an actual message
                            # Messages usually have punctuation or are proper sentences
                            if any(c in text for c in '.?!,') or text[0].isupper():
                                msg_elements.append(span)
                                if len(msg_elements) >= limit:
                                    break
            
            for element in msg_elements:
                try:
                    content = await element.text_content()
                    if not content or not content.strip():
                        continue
                    
                    content = content.strip()
                    content_lower = content.lower()
                    
                    # Skip UI elements
                    if content_lower in skip_texts:
                        continue
                    
                    # Skip very short content (likely buttons or icons)
                    if len(content) < 3:
                        continue
                    
                    # Skip Note-related content (Instagram status notes)
                    # Notes appear at the top of threads and shouldn't be treated as messages
                    is_note = False
                    for note_indicator in note_indicators:
                        if note_indicator in content_lower:
                            is_note = True
                            logger.debug("Skipping note indicator", content_preview=content[:50])
                            break
                    if is_note:
                        continue
                    
                    # Check if this element is part of a Note bubble (at top of thread)
                    # Notes typically have a specific container structure near the top
                    try:
                        is_note_element = await element.evaluate("""(el) => {
                            // Check if this is inside a Note container
                            let current = el;
                            for (let i = 0; i < 15; i++) {
                                if (!current.parentElement) break;
                                current = current.parentElement;
                                
                                // Notes often have specific aria labels or class patterns
                                const ariaLabel = current.getAttribute('aria-label') || '';
                                if (ariaLabel.toLowerCase().includes('note')) return true;
                                
                                // Check for Note-specific structure (circular bubble at top)
                                const className = current.className || '';
                                if (className.includes('note') || className.includes('Note')) return true;
                                
                                // Notes are usually very close to the top of the conversation
                                const rect = current.getBoundingClientRect();
                                if (rect.top < 150 && rect.height < 100) {
                                    // Small element near top - could be a note
                                    // Check if there's a circular image (avatar) nearby
                                    const imgs = current.querySelectorAll('img');
                                    for (const img of imgs) {
                                        const imgStyle = window.getComputedStyle(img);
                                        if (imgStyle.borderRadius === '50%') {
                                            return true;  // Circular avatar = likely a note
                                        }
                                    }
                                }
                            }
                            return false;
                        }""")
                        if is_note_element:
                            logger.debug("Skipping note element based on structure", content_preview=content[:50])
                            continue
                    except Exception:
                        pass  # If check fails, continue with normal processing
                    
                    # Determine if this is an outgoing message
                    # Instagram uses multiple signals:
                    # 1. Sent messages typically positioned on right side
                    # 2. Sent messages have colored (blue/purple) background
                    # 3. Received messages have gray/white background
                    is_outgoing = False
                    
                    try:
                        # Method 1: Check bounding box position (right side = sent)
                        bounding_box = await element.bounding_box()
                        if bounding_box:
                            viewport = self._page.viewport_size
                            # Use 40% threshold since some sent messages may not be fully right-aligned
                            if viewport and bounding_box['x'] > viewport['width'] * 0.4:
                                is_outgoing = True
                        
                        # Method 2: Check parent element's background color
                        # Sent messages in Instagram typically have a gradient or colored bg
                        if not is_outgoing:
                            bg_info = await element.evaluate("""(el) => {
                                // Traverse up to find the message bubble
                                let current = el;
                                for (let i = 0; i < 10; i++) {
                                    if (!current.parentElement) break;
                                    current = current.parentElement;
                                    const style = window.getComputedStyle(current);
                                    const bg = style.backgroundColor;
                                    // Check for colored backgrounds (not white/gray/transparent)
                                    if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
                                        // Parse RGB values
                                        const match = bg.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                                        if (match) {
                                            const [_, r, g, b] = match.map(Number);
                                            // Instagram sent messages are typically blue/purple (high blue, lower red/green)
                                            // Gray messages have r ≈ g ≈ b (within ~30 of each other)
                                            const isGray = Math.abs(r - g) < 30 && Math.abs(g - b) < 30 && Math.abs(r - b) < 30;
                                            const isWhite = r > 240 && g > 240 && b > 240;
                                            const isColored = !isGray && !isWhite && (b > 100 || r > 100 || g > 100);
                                            if (isColored) {
                                                return { isOutgoing: true, bg: bg };
                                            }
                                        }
                                    }
                                }
                                return { isOutgoing: false, bg: null };
                            }""")
                            if bg_info and bg_info.get('isOutgoing'):
                                is_outgoing = True
                                
                        # Method 3: Check flex-end or right alignment in parent
                        if not is_outgoing:
                            is_right_aligned = await element.evaluate("""(el) => {
                                let current = el;
                                for (let i = 0; i < 10; i++) {
                                    if (!current.parentElement) break;
                                    current = current.parentElement;
                                    const style = window.getComputedStyle(current);
                                    if (style.alignItems === 'flex-end' || 
                                        style.justifyContent === 'flex-end' ||
                                        style.alignSelf === 'flex-end' ||
                                        style.marginLeft === 'auto') {
                                        return true;
                                    }
                                }
                                return false;
                            }""")
                            if is_right_aligned:
                                is_outgoing = True
                                
                    except Exception as e:
                        logger.debug("Error detecting outgoing message", error=str(e))
                    
                    messages.append({
                        "content": content,
                        "is_outgoing": is_outgoing,
                        "timestamp": None,
                        "image_url": None,
                    })
                    logger.info("Extracted message", content_preview=content[:50], is_outgoing=is_outgoing)
                    
                except Exception:
                    continue
            
            # Now look for images in the conversation
            # Instagram DM images are typically in img tags or as background images
            # We want to find images sent IN the conversation, not profile pics or UI elements
            try:
                # Look for images that are likely DM content (larger images, not small avatars)
                image_elements = await self._page.query_selector_all('img[src*="cdninstagram"], img[src*="scontent"]')
                
                for img_elem in image_elements:
                    try:
                        # Get the image src
                        img_src = await img_elem.get_attribute("src")
                        if not img_src:
                            continue
                        
                        # Skip profile pictures and avatars - these URLs typically contain specific patterns
                        # Profile pics: /v/t51.2885-19/ (profile pics format)
                        # Regular DM images: /v/t51.2885-15/ (feed/dm images format)
                        if "/t51.2885-19/" in img_src:
                            continue  # This is a profile picture, skip
                        if "profile" in img_src.lower() or "avatar" in img_src.lower():
                            continue
                        
                        # Check image size - profile pics are usually small (< 100px)
                        bounding_box = await img_elem.bounding_box()
                        if not bounding_box:
                            continue
                            
                        # Skip small images (likely profile pics or icons)
                        if bounding_box['width'] < 100 or bounding_box['height'] < 100:
                            continue
                        
                        # Check if image is circular (avatars are usually round via border-radius)
                        is_circular = await img_elem.evaluate("""(el) => {
                            const style = window.getComputedStyle(el);
                            const borderRadius = style.borderRadius;
                            // If border-radius is 50% or very high, it's circular (likely avatar)
                            if (borderRadius === '50%' || borderRadius === '100%') return true;
                            // Check if it's a large pixel value that makes it circular
                            const match = borderRadius.match(/^(\\d+)px$/);
                            if (match) {
                                const radius = parseInt(match[1]);
                                const rect = el.getBoundingClientRect();
                                // If radius is >= half the width, it's circular
                                if (radius >= rect.width / 2) return true;
                            }
                            return false;
                        }""")
                        if is_circular:
                            logger.debug("Skipping circular image (likely avatar)")
                            continue
                        
                        # Check if there's a name/username near this image (indicates avatar)
                        has_adjacent_name = await img_elem.evaluate("""(el) => {
                            // Look at parent and siblings for text that looks like a username
                            let parent = el.parentElement;
                            for (let i = 0; i < 3 && parent; i++) {
                                // Check siblings
                                const siblings = Array.from(parent.children);
                                for (const sibling of siblings) {
                                    if (sibling === el || sibling.contains(el)) continue;
                                    const text = sibling.textContent?.trim() || '';
                                    // Skip if text is too long (message content) or empty
                                    if (text.length > 0 && text.length < 30) {
                                        // Usernames are short and often have @ or are just names
                                        if (text.match(/^@?[a-zA-Z0-9_.]+$/) || 
                                            text.match(/^[A-Z][a-z]+ [A-Z][a-z]+$/) ||
                                            text.match(/^[A-Z][a-z]+$/)) {
                                            return true;  // Looks like a username next to image
                                        }
                                    }
                                }
                                parent = parent.parentElement;
                            }
                            return false;
                        }""")
                        if has_adjacent_name:
                            logger.debug("Skipping image with adjacent name (likely avatar)")
                            continue
                        
                        # Check if image is at the far left edge (avatars are usually at x < 80px)
                        if bounding_box['x'] < 80:
                            logger.debug("Skipping image at far left edge (likely avatar)")
                            continue
                        
                        # Check position to determine if incoming or outgoing
                        is_outgoing = False
                        viewport = self._page.viewport_size
                        if viewport and bounding_box['x'] > viewport['width'] * 0.4:
                            is_outgoing = True
                        
                        # Add as an image message
                        messages.append({
                            "content": "[Image sent]" if is_outgoing else "[Image received]",
                            "is_outgoing": is_outgoing,
                            "timestamp": None,
                            "image_url": img_src,
                        })
                        logger.info("Found DM image", is_outgoing=is_outgoing, width=bounding_box['width'], x=bounding_box['x'])
                            
                    except Exception as img_e:
                        logger.debug("Error extracting image", error=str(img_e))
                        continue
                        
            except Exception as img_err:
                logger.debug("Error looking for images in conversation", error=str(img_err))
            
            logger.info("Fetched messages from current thread", count=len(messages))
            return messages
            
        except Exception as e:
            logger.error("Failed to get messages from current thread", error=str(e))
            return messages
    
    async def send_dm_in_current_thread(self, message: str) -> bool:
        """Send a direct message in the currently open thread.
        
        Returns:
            True if message was sent successfully
        """
        try:
            if not self._page:
                return False
            
            # Wait for the conversation to fully load
            await self._human_delay(2, 3)
            
            # Log current URL for debugging
            current_url = self._page.url
            logger.info("Attempting to send DM", url=current_url)
            
            # Try using Tab key to navigate to message input
            # In Instagram, pressing Tab usually focuses on the message input
            await self._page.keyboard.press("Tab")
            await self._quick_delay()
            await self._page.keyboard.press("Tab")
            await self._quick_delay()
            
            # Find message input - Instagram uses various elements
            input_selectors = [
                'textarea[placeholder*="Message"]',
                'textarea[aria-label*="Message"]',
                'div[role="textbox"][contenteditable="true"]',
                'div[aria-label*="Message"][contenteditable="true"]',
                'p[data-lexical-text="true"]',  # Instagram's Lexical editor
                '[contenteditable="true"]',
                'div[role="textbox"]',
            ]
            
            message_input = None
            for selector in input_selectors:
                try:
                    # Wait for the element with a short timeout
                    message_input = await self._page.wait_for_selector(selector, timeout=3000)
                    if message_input:
                        logger.info("Found message input", selector=selector)
                        break
                except Exception:
                    continue
            
            if not message_input:
                # Click on the right side of the screen (message area) 
                # Instagram DMs have the input at the bottom right
                viewport = self._page.viewport_size
                if viewport:
                    await self._page.mouse.click(
                        viewport['width'] * 0.75,  # 3/4 across 
                        viewport['height'] - 100,  # Near bottom
                    )
                    await self._quick_delay()
                    
                    # Try again to find the input
                    for selector in input_selectors:
                        message_input = await self._page.query_selector(selector)
                        if message_input:
                            logger.info("Found message input after click", selector=selector)
                            break
            
            if not message_input:
                # Last resort: look for any element that might be a message input
                try:
                    # Check what elements are on the page
                    element_counts = await self._page.evaluate('''
                        () => {
                            return {
                                textareas: document.querySelectorAll('textarea').length,
                                contenteditables: document.querySelectorAll('[contenteditable="true"]').length,
                                textboxes: document.querySelectorAll('[role="textbox"]').length,
                                inputs: document.querySelectorAll('input[type="text"]').length,
                            }
                        }
                    ''')
                    logger.info("Page element counts", **element_counts)
                except Exception:
                    pass
                    
                logger.error("Message input not found in current thread")
                return False
            
            # Click to focus
            await message_input.click()
            await self._quick_delay()
            
            # Type message using keyboard (more reliable than fill)
            await self._page.keyboard.type(message, delay=30)
            await self._quick_delay()
            
            # Send (press Enter or click send button)
            await self._page.keyboard.press("Enter")
            await self._quick_delay(1, 2)
            
            logger.info("DM sent in current thread")
            return True
            
        except Exception as e:
            logger.error("Failed to send DM in current thread", error=str(e))
            return False
    
    async def send_dm(
        self,
        conversation_id: str,
        message: str,
    ) -> bool:
        """Send a direct message in a conversation.
        
        Args:
            conversation_id: The Instagram conversation/thread ID
            message: The message text to send
            
        Returns:
            True if message was sent successfully
        """
        try:
            await self._ensure_browser()
            if not self._page:
                self._page = await self._context.new_page()
            
            # Navigate to conversation if not already there
            current_url = self._page.url
            target_url = f"https://www.instagram.com/direct/t/{conversation_id}/"
            
            if conversation_id not in current_url:
                logger.info("Navigating to conversation", conversation_id=conversation_id)
                await self._page.goto(target_url, wait_until="networkidle", timeout=30000)
                await self._human_delay(2, 3)
            
            # Find message input
            input_selectors = [
                'textarea[placeholder*="Message"]',
                'div[role="textbox"]',
                'input[placeholder*="Message"]',
                '[contenteditable="true"]',
            ]
            
            message_input = None
            for selector in input_selectors:
                message_input = await self._page.query_selector(selector)
                if message_input:
                    break
            
            if not message_input:
                logger.error("Message input not found")
                return False
            
            # Click to focus
            await message_input.click()
            await self._quick_delay()
            
            # Type message with human-like delay
            await message_input.fill(message)
            await self._quick_delay()
            
            # Find and click send button
            send_selectors = [
                'button[type="submit"]',
                'button:has-text("Send")',
                '[aria-label*="Send"]',
                'div[role="button"]:has-text("Send")',
            ]
            
            send_button = None
            for selector in send_selectors:
                send_button = await self._page.query_selector(selector)
                if send_button:
                    is_enabled = await send_button.is_enabled()
                    if is_enabled:
                        break
                    send_button = None
            
            if send_button:
                await send_button.click()
            else:
                # Try pressing Enter
                await message_input.press("Enter")
            
            await self._quick_delay(1, 2)
            
            # Verify message was sent (check if input is cleared)
            input_value = await message_input.input_value() if await message_input.is_visible() else ""
            if not input_value or input_value != message:
                logger.info("DM sent successfully", conversation_id=conversation_id)
                return True
            
            logger.warning("DM may not have been sent")
            return False
            
        except Exception as e:
            logger.error("Failed to send DM", error=str(e), conversation_id=conversation_id)
            return False
    
    async def send_dm_to_user(
        self,
        username: str,
        message: str,
    ) -> bool:
        """Start a new DM conversation with a user.
        
        Args:
            username: The Instagram username to message
            message: The message text to send
            
        Returns:
            True if message was sent successfully
        """
        try:
            await self._ensure_browser()
            if not self._page:
                self._page = await self._context.new_page()
            
            # Go to new message screen
            await self._page.goto("https://www.instagram.com/direct/new/", wait_until="networkidle", timeout=30000)
            await self._human_delay(2, 3)
            
            # Find user search input
            search_selectors = [
                'input[name="queryBox"]',
                'input[placeholder*="Search"]',
                'input[aria-label*="Search"]',
            ]
            
            search_input = None
            for selector in search_selectors:
                search_input = await self._page.query_selector(selector)
                if search_input:
                    break
            
            if not search_input:
                logger.error("User search input not found")
                return False
            
            # Search for user
            await search_input.fill(username)
            await self._human_delay(2, 3)  # Wait for search results
            
            # Click on user from results
            user_selectors = [
                f'[role="button"]:has-text("{username}")',
                f'div:has-text("{username}")',
                'div[role="listbox"] button',
            ]
            
            user_element = None
            for selector in user_selectors:
                elements = await self._page.query_selector_all(selector)
                for elem in elements:
                    text = await elem.text_content()
                    if username.lower() in text.lower():
                        user_element = elem
                        break
                if user_element:
                    break
            
            if not user_element:
                logger.error("User not found in search results", username=username)
                return False
            
            await user_element.click()
            await self._quick_delay()
            
            # Click Next/Chat button
            next_button = await self._page.query_selector('button:has-text("Chat"), button:has-text("Next")')
            if next_button:
                await next_button.click()
                await self._human_delay(1, 2)
            
            # Now send the message
            message_input = await self._page.query_selector('textarea[placeholder*="Message"], div[role="textbox"]')
            if message_input:
                await message_input.fill(message)
                await self._quick_delay()
                
                send_button = await self._page.query_selector('button[type="submit"], button:has-text("Send")')
                if send_button and await send_button.is_enabled():
                    await send_button.click()
                else:
                    await message_input.press("Enter")
                
                await self._quick_delay(1, 2)
                logger.info("DM sent to new user", username=username)
                return True
            
            logger.error("Failed to find message input after selecting user")
            return False
            
        except Exception as e:
            logger.error("Failed to send DM to user", error=str(e), username=username)
            return False

    async def close(self):
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        
        logger.info("Browser closed")



