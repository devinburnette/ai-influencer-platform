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
            await self._page.goto("https://www.instagram.com/", wait_until="networkidle")
            await self._human_delay()
            
            # Check if we're logged in by looking for the profile icon
            logged_in = await self._page.query_selector('[aria-label="Profile"]') is not None
            
            if not logged_in:
                # Also check for feed content as an indicator
                logged_in = await self._page.query_selector('[role="feed"]') is not None
            
            logger.info("Session verified", logged_in=logged_in)
            return logged_in
            
        except Exception as e:
            logger.error("Session verification failed", error=str(e))
            return False

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
                logger.info("Login successful", username=username)
                return True
            
            logger.warning("Login may have failed", username=username)
            return False
            
        except Exception as e:
            logger.error("Login failed", error=str(e))
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
            
            await self._page.goto(post_url, wait_until="networkidle")
            await self._human_delay()
            
            # Find and click the like button
            like_button = await self._page.query_selector(
                '[aria-label="Like"][role="button"], '
                'svg[aria-label="Like"]'
            )
            
            if like_button:
                await like_button.click()
                await self._human_delay()
                logger.info("Post liked", url=post_url)
                return True
            
            # Already liked
            unlike_button = await self._page.query_selector(
                '[aria-label="Unlike"][role="button"]'
            )
            if unlike_button:
                logger.info("Post already liked", url=post_url)
                return True
            
            logger.warning("Like button not found", url=post_url)
            return False
            
        except Exception as e:
            logger.error("Like failed", error=str(e))
            return False

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
            
            await self._page.goto(post_url, wait_until="networkidle")
            await self._human_delay()
            
            # Find comment input
            comment_input = await self._page.query_selector(
                'textarea[aria-label="Add a comment…"]'
            )
            
            if comment_input:
                await comment_input.click()
                await self._human_delay()
                await comment_input.type(text, delay=random.randint(30, 80))
                await self._human_delay()
                
                # Click post button
                post_button = await self._page.query_selector(
                    'div[role="button"]:has-text("Post")'
                )
                if post_button:
                    await post_button.click()
                    await self._human_delay()
                    logger.info("Comment posted", url=post_url)
                    return "comment_posted"
            
            return None
            
        except Exception as e:
            logger.error("Comment failed", error=str(e))
            return None

    async def follow_user(self, username: str) -> bool:
        """Follow a user."""
        await self._ensure_browser()
        
        try:
            await self._page.goto(
                f"https://www.instagram.com/{username}/",
                wait_until="networkidle",
            )
            await self._human_delay()
            
            follow_button = await self._page.query_selector(
                'button:has-text("Follow")'
            )
            
            if follow_button:
                await follow_button.click()
                await self._human_delay()
                logger.info("Followed user", username=username)
                return True
            
            # Check if already following
            following_button = await self._page.query_selector(
                'button:has-text("Following")'
            )
            if following_button:
                logger.info("Already following", username=username)
                return True
            
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
            await self._page.goto(
                f"https://www.instagram.com/explore/tags/{hashtag}/",
                wait_until="networkidle",
            )
            await self._human_delay()
            
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
                            posts.append(Post(
                                id=post_id,
                                author_id="",
                                author_username="",
                                content="",
                                hashtags=[hashtag],
                                url=f"https://www.instagram.com{href}",
                            ))
                except Exception:
                    continue
            
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
        media_paths: Optional[List[str]] = None,
    ) -> PostResult:
        """Create a post using browser automation.
        
        Note: This is complex and may not work reliably.
        Consider using Graph API for posting when possible.
        """
        logger.warning(
            "Browser-based posting is not fully implemented. "
            "Use Graph API for reliable posting."
        )
        return PostResult(
            success=False,
            error_message="Browser posting not implemented - use Graph API",
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

