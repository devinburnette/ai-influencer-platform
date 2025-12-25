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
                ],
            )
            
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            
            # Anti-detection measures
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            self._page = await self._context.new_page()
            logger.info("Browser initialized")

    async def _human_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0):
        """Add human-like delay between actions."""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def _random_scroll(self):
        """Perform random scrolling to appear more human."""
        if self._page:
            scroll_amount = random.randint(100, 500)
            await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await self._human_delay(0.3, 0.8)

    async def load_cookies(self, cookies: Dict[str, str]):
        """Load cookies to restore session."""
        await self._ensure_browser()
        
        cookie_list = [
            {"name": name, "value": value, "domain": ".instagram.com", "path": "/"}
            for name, value in cookies.items()
        ]
        
        await self._context.add_cookies(cookie_list)
        logger.info("Cookies loaded", count=len(cookie_list))

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
            await self._human_delay(1, 2)
            
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
            await self._human_delay(2, 3)
            
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
            await self._human_delay(3, 5)
            
            # Check for successful login
            if await self.verify_session():
                self._logged_in = True
                self._session_invalid = False
                logger.info("Login successful", username=username)
                return True
            
            logger.warning("Login may have failed", username=username)
            self._logged_in = False
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
            await self._human_delay(2, 4)  # Wait longer for page to fully load
            
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
            
            # Method 1: Try to extract from page's embedded JSON data
            # Instagram embeds post data in script tags
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
                                        if username:
                                            logger.info("Extracted post author from JSON-LD", username=username)
                                            return username
                                    alt_name = author.get("alternateName")
                                    if alt_name and alt_name.startswith("@"):
                                        username = alt_name[1:]
                                        logger.info("Extracted post author from JSON-LD alternateName", username=username)
                                        return username
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                logger.debug("JSON-LD extraction failed", error=str(e))
            
            # Method 2: Look for username link in the post header area
            try:
                # Find the first link that looks like a profile link (after profile picture)
                links = await self._page.query_selector_all('a[href^="/"]')
                seen_usernames = []
                for link in links:
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    # Skip non-profile links
                    if any(x in href for x in ["/p/", "/reel/", "/explore/", "/direct/", "/accounts/", "/static/", "/stories/", "/tags/"]):
                        continue
                    # Check if it's a simple /username/ path
                    parts = [p for p in href.split("/") if p]
                    if len(parts) == 1:
                        username = parts[0]
                        # Basic validation
                        if re.match(r'^[a-zA-Z0-9_.]{1,30}$', username):
                            if username not in seen_usernames:
                                seen_usernames.append(username)
                                # The first valid username we find is usually the author
                                if len(seen_usernames) == 1:
                                    # Wait for one more to confirm
                                    continue
                                elif seen_usernames[0] == username or len(seen_usernames) >= 2:
                                    # First username appears multiple times (likely the author)
                                    logger.info("Extracted post author from profile link", username=seen_usernames[0])
                                    return seen_usernames[0]
                
                # If we found at least one username, use the first one
                if seen_usernames:
                    logger.info("Extracted post author (first found)", username=seen_usernames[0])
                    return seen_usernames[0]
            except Exception as e:
                logger.debug("Profile link extraction failed", error=str(e))
            
            # Method 3: Try meta tags and title
            try:
                # Try og:description which often contains @username
                og_desc = await self._page.query_selector('meta[property="og:description"]')
                if og_desc:
                    content = await og_desc.get_attribute("content")
                    if content:
                        match = re.search(r'@([a-zA-Z0-9_.]+)', content)
                        if match:
                            username = match.group(1)
                            logger.info("Extracted post author from og:description", username=username)
                            return username
                
                # Try page title
                title = await self._page.title()
                if title:
                    match = re.search(r'@([a-zA-Z0-9_.]+)', title)
                    if match:
                        username = match.group(1)
                        logger.info("Extracted post author from title", username=username)
                        return username
            except Exception as e:
                logger.debug("Meta/title extraction failed", error=str(e))
            
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
                await self._human_delay(2, 4)
            else:
                # If we're already on the page, just wait a moment for any dynamic updates
                await self._human_delay(1, 2)
            
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
            
            await self._human_delay(0.5, 1)
            
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
            
            await self._human_delay(0.5, 1.5)
            
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
            await self._human_delay(2, 4)
            
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
            await self._human_delay(2, 4)
            
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
            
            # Extract post links
            links = await self._page.query_selector_all('a[href*="/p/"]')
            
            seen_ids = set()
            for link in links:
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
            await self._human_delay(2, 3)
            
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
            await self._human_delay(1, 2)
            
            # Wait for the file input dialog or creation modal
            await self._human_delay(1, 2)
            
            # Find the file input for image upload
            file_input = await self._page.query_selector('input[type="file"][accept*="image"]')
            
            if not file_input:
                # Sometimes the modal needs to load - wait and try again
                await self._human_delay(2, 3)
                file_input = await self._page.query_selector('input[type="file"][accept*="image"]')
            
            if not file_input:
                # Try clicking "Select from computer" button if present
                select_button = await self._page.query_selector('button:has-text("Select from computer")')
                if select_button:
                    await select_button.click()
                    await self._human_delay(1, 2)
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
            await self._human_delay(3, 5)
            
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
            await self._human_delay(1, 2)
            
            # Click Next again to skip filters (go to caption screen)
            next_button = await self._page.wait_for_selector(
                'button:has-text("Next"), div[role="button"]:has-text("Next")',
                timeout=10000,
            )
            await next_button.click()
            await self._human_delay(1, 2)
            
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
                await self._human_delay(0.5, 1)
            
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
            await self._human_delay(3, 5)
            
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
                
                await self._human_delay(0.5, 1)
            
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

    async def close(self):
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        
        logger.info("Browser closed")


