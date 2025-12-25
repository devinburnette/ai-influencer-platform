"""Twitter browser automation using Playwright."""

import asyncio
import random
from typing import List, Optional, Dict, Any
import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class TwitterBrowser:
    """Twitter browser automation for actions not supported by free API tier."""

    def __init__(self):
        """Initialize browser automation."""
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._logged_in = False

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
            
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            
            # Anti-detection measures
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)
            
            self._page = await self._context.new_page()
            logger.info("Twitter browser initialized")

    async def _human_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0):
        """Add human-like delay between actions."""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def _random_scroll(self):
        """Perform random scrolling to appear more human."""
        if self._page:
            scroll_amount = random.randint(100, 400)
            await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await self._human_delay(0.3, 0.8)

    async def _move_mouse_naturally(self, x: int, y: int):
        """Move mouse in a natural way."""
        if self._page:
            # Add some randomness to the target
            x += random.randint(-5, 5)
            y += random.randint(-5, 5)
            await self._page.mouse.move(x, y)
            await self._human_delay(0.1, 0.3)

    async def load_cookies(self, cookies: Dict[str, str]):
        """Load cookies to restore session."""
        await self._ensure_browser()
        
        cookie_list = [
            {"name": name, "value": value, "domain": ".twitter.com", "path": "/"}
            for name, value in cookies.items()
        ]
        
        # Also add x.com domain cookies
        cookie_list.extend([
            {"name": name, "value": value, "domain": ".x.com", "path": "/"}
            for name, value in cookies.items()
        ])
        
        await self._context.add_cookies(cookie_list)
        logger.info("Twitter cookies loaded", count=len(cookies))

    async def get_cookies(self) -> Dict[str, str]:
        """Get current session cookies."""
        if not self._context:
            return {}
        
        cookies = await self._context.cookies()
        # Get cookies from both twitter.com and x.com
        return {
            c["name"]: c["value"] 
            for c in cookies 
            if "twitter.com" in c.get("domain", "") or "x.com" in c.get("domain", "")
        }

    async def login(self, username: str, password: str) -> bool:
        """Login to Twitter with username and password.
        
        Note: This may trigger 2FA or security challenges.
        """
        await self._ensure_browser()
        
        try:
            logger.info("Starting Twitter login", username=username)
            
            # Navigate to login page
            await self._page.goto("https://twitter.com/i/flow/login", wait_until="networkidle")
            await self._human_delay(2, 4)
            
            # Enter username
            username_input = await self._page.wait_for_selector(
                'input[autocomplete="username"]',
                timeout=10000
            )
            await username_input.click()
            await self._human_delay(0.3, 0.6)
            await username_input.type(username, delay=random.randint(50, 150))
            await self._human_delay(0.5, 1)
            
            # Click Next
            next_button = await self._page.query_selector('text="Next"')
            if next_button:
                await next_button.click()
                await self._human_delay(1, 2)
            
            # Check for unusual activity challenge (may ask for email/phone)
            unusual_check = await self._page.query_selector('text="Enter your phone number or email address"')
            if unusual_check:
                logger.warning("Twitter security challenge detected - may need email/phone verification")
                return False
            
            # Enter password
            password_input = await self._page.wait_for_selector(
                'input[name="password"]',
                timeout=10000
            )
            await password_input.click()
            await self._human_delay(0.3, 0.6)
            await password_input.type(password, delay=random.randint(50, 150))
            await self._human_delay(0.5, 1)
            
            # Click Login
            login_button = await self._page.query_selector('text="Log in"')
            if login_button:
                await login_button.click()
                await self._human_delay(3, 5)
            
            # Check if login was successful
            await self._page.wait_for_url("**/home", timeout=15000)
            
            self._logged_in = True
            logger.info("Twitter login successful", username=username)
            return True
            
        except Exception as e:
            logger.error("Twitter login failed", error=str(e))
            return False

    async def verify_session(self) -> bool:
        """Verify the current session is valid.
        
        Uses fast verification - just checks if we can load Twitter without login redirect.
        """
        await self._ensure_browser()
        
        try:
            # Use domcontentloaded instead of networkidle (much faster)
            await self._page.goto("https://twitter.com/home", wait_until="domcontentloaded", timeout=15000)
            await self._human_delay(1, 2)
            
            # Quick check - if we're redirected to login, we're not logged in
            current_url = self._page.url
            if "login" in current_url or "i/flow" in current_url:
                logger.info("Session invalid - redirected to login")
                self._logged_in = False
                return False
            
            # If we're still on /home, we're probably logged in
            # Don't wait for specific elements - just trust the URL
            self._logged_in = True
            logger.info("Twitter session verified via URL check", url=current_url)
            return True
            
        except Exception as e:
            logger.error("Session verification failed", error=str(e))
            # If cookies were provided, assume they're valid and try anyway
            if self._context and await self._context.cookies():
                logger.info("Assuming session valid based on cookies presence")
                self._logged_in = True
                return True
            return False

    async def like_tweet(self, tweet_url: str) -> bool:
        """Like a tweet by navigating to its URL.
        
        Args:
            tweet_url: Full URL to the tweet (e.g., https://twitter.com/user/status/123456)
            
        Returns:
            True if like was successful
        """
        await self._ensure_browser()
        
        if not self._logged_in:
            logger.warning("Not logged in, cannot like tweet")
            return False
        
        try:
            logger.info("Liking tweet via browser", url=tweet_url)
            
            # Navigate to tweet - use domcontentloaded for speed
            await self._page.goto(tweet_url, wait_until="domcontentloaded", timeout=15000)
            await self._human_delay(2, 3)
            
            # Wait for the tweet/like button to be present
            try:
                await self._page.wait_for_selector('[data-testid="like"], [data-testid="unlike"]', timeout=10000)
            except Exception:
                logger.warning("Like button not found after waiting")
            
            await self._random_scroll()
            
            # Find the like button
            like_button = await self._page.query_selector('[data-testid="like"]')
            
            if not like_button:
                # Tweet might already be liked
                unlike_button = await self._page.query_selector('[data-testid="unlike"]')
                if unlike_button:
                    logger.info("Tweet already liked", url=tweet_url)
                    return True
                logger.warning("Like button not found", url=tweet_url)
                return False
            
            # Scroll to button and click
            await like_button.scroll_into_view_if_needed()
            await self._human_delay(0.3, 0.6)
            
            # Get button position and move mouse naturally
            box = await like_button.bounding_box()
            if box:
                await self._move_mouse_naturally(
                    int(box["x"] + box["width"] / 2),
                    int(box["y"] + box["height"] / 2)
                )
            
            await like_button.click()
            await self._human_delay(0.5, 1)
            
            # Verify like was successful
            unlike_button = await self._page.query_selector('[data-testid="unlike"]')
            success = unlike_button is not None
            
            if success:
                logger.info("Tweet liked successfully", url=tweet_url)
            else:
                logger.warning("Like may have failed", url=tweet_url)
            
            return success
            
        except Exception as e:
            logger.error("Failed to like tweet", url=tweet_url, error=str(e))
            return False

    async def like_tweet_by_id(self, tweet_id: str, author_username: str = None) -> bool:
        """Like a tweet by its ID.
        
        Args:
            tweet_id: The tweet ID
            author_username: Optional author username for URL construction
            
        Returns:
            True if like was successful
        """
        # If we have the author username, construct the full URL
        if author_username:
            tweet_url = f"https://twitter.com/{author_username}/status/{tweet_id}"
        else:
            # Use twitter.com/i/status which redirects
            tweet_url = f"https://twitter.com/i/status/{tweet_id}"
        
        return await self.like_tweet(tweet_url)

    async def follow_user(self, username: str) -> bool:
        """Follow a user by their username.
        
        Args:
            username: Twitter username (without @)
            
        Returns:
            True if follow was successful
        """
        await self._ensure_browser()
        
        if not self._logged_in:
            logger.warning("Not logged in, cannot follow user")
            return False
        
        try:
            logger.info("Following user via browser", username=username)
            
            # Navigate to user profile - use domcontentloaded for speed
            await self._page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded", timeout=15000)
            await self._human_delay(2, 3)
            
            # Wait for follow button
            try:
                await self._page.wait_for_selector('[data-testid$="-follow"], [data-testid$="-unfollow"]', timeout=10000)
            except Exception:
                logger.warning("Follow button not found after waiting")
            
            # Find the follow button
            follow_button = await self._page.query_selector('[data-testid$="-follow"]')
            
            if not follow_button:
                # Check if already following
                following_button = await self._page.query_selector('[data-testid$="-unfollow"]')
                if following_button:
                    logger.info("Already following user", username=username)
                    return True
                logger.warning("Follow button not found", username=username)
                return False
            
            # Check button text to make sure it's "Follow" not "Following"
            button_text = await follow_button.inner_text()
            if "Following" in button_text:
                logger.info("Already following user", username=username)
                return True
            
            # Click follow
            await follow_button.scroll_into_view_if_needed()
            await self._human_delay(0.3, 0.6)
            await follow_button.click()
            await self._human_delay(1, 2)
            
            # Verify follow was successful
            following_button = await self._page.query_selector('[data-testid$="-unfollow"]')
            success = following_button is not None
            
            if success:
                logger.info("User followed successfully", username=username)
            else:
                logger.warning("Follow may have failed", username=username)
            
            return success
            
        except Exception as e:
            logger.error("Failed to follow user", username=username, error=str(e))
            return False

    async def unfollow_user(self, username: str) -> bool:
        """Unfollow a user by their username.
        
        Args:
            username: Twitter username (without @)
            
        Returns:
            True if unfollow was successful
        """
        await self._ensure_browser()
        
        if not self._logged_in:
            logger.warning("Not logged in, cannot unfollow user")
            return False
        
        try:
            logger.info("Unfollowing user via browser", username=username)
            
            # Navigate to user profile - use domcontentloaded for speed
            await self._page.goto(f"https://twitter.com/{username}", wait_until="domcontentloaded", timeout=15000)
            await self._human_delay(2, 3)
            
            # Wait for unfollow button
            try:
                await self._page.wait_for_selector('[data-testid$="-unfollow"]', timeout=10000)
            except Exception:
                logger.warning("Unfollow button not found after waiting")

            # Find the following/unfollow button
            following_button = await self._page.query_selector('[data-testid$="-unfollow"]')
            
            if not following_button:
                logger.info("Not following user", username=username)
                return True
            
            # Click to unfollow (this opens a confirmation)
            await following_button.click()
            await self._human_delay(0.5, 1)
            
            # Confirm unfollow in the popup
            confirm_button = await self._page.query_selector('[data-testid="confirmationSheetConfirm"]')
            if confirm_button:
                await confirm_button.click()
                await self._human_delay(1, 2)
            
            # Verify unfollow was successful
            follow_button = await self._page.query_selector('[data-testid$="-follow"]')
            success = follow_button is not None
            
            if success:
                logger.info("User unfollowed successfully", username=username)
            
            return success
            
        except Exception as e:
            logger.error("Failed to unfollow user", username=username, error=str(e))
            return False

    async def post_tweet(
        self,
        text: str,
        media_path: Optional[str] = None,
        reply_to_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Post a tweet using browser automation.
        
        Args:
            text: Tweet text content
            media_path: Optional path to local media file to attach
            reply_to_url: Optional tweet URL to reply to
            
        Returns:
            Dict with 'success', 'tweet_id', 'url', and 'error' fields
        """
        await self._ensure_browser()
        
        if not self._logged_in:
            logger.warning("Not logged in, cannot post tweet")
            return {"success": False, "error": "Not logged in"}
        
        try:
            logger.info("Posting tweet via browser", text_length=len(text), has_media=media_path is not None)
            
            if reply_to_url:
                # Navigate to tweet we're replying to
                await self._page.goto(reply_to_url, wait_until="domcontentloaded", timeout=30000)
                await self._human_delay(2, 3)
                
                # Click the reply button to open reply composer
                try:
                    await self._page.wait_for_selector('[data-testid="reply"]', timeout=10000)
                except Exception:
                    logger.warning("Reply button not found, trying alternative")
                    
                reply_button = await self._page.query_selector('[data-testid="reply"]')
                if reply_button:
                    await reply_button.click()
                    await self._human_delay(1, 2)
            else:
                # Navigate to home page first (reliable login check)
                await self._page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                await self._human_delay(3, 4)
                
                # Find and click the compose tweet button (usually in the left sidebar or header)
                compose_button = None
                compose_selectors = [
                    '[data-testid="SideNav_NewTweet_Button"]',  # Sidebar compose button
                    '[href="/compose/tweet"]',  # Link to compose
                    'a[aria-label*="Post"]',  # Post button by aria label
                    'a[aria-label*="Tweet"]',  # Tweet button by aria label
                ]
                
                for selector in compose_selectors:
                    compose_button = await self._page.query_selector(selector)
                    if compose_button:
                        logger.info("Found compose button", selector=selector)
                        break
                
                if compose_button:
                    await compose_button.click()
                    await self._human_delay(1, 2)
                else:
                    # Try navigating directly to compose URL as fallback
                    logger.info("Compose button not found, trying direct navigation")
                    await self._page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=30000)
                    await self._human_delay(2, 3)
            
            # Wait for the tweet composer to appear with extended timeout
            composer = None
            composer_selectors = [
                '[data-testid="tweetTextarea_0"]',
                '[data-testid="tweetTextarea_0RichTextInputContainer"]',
                '[role="textbox"][data-testid]',
                'div[contenteditable="true"][role="textbox"]',
                '.public-DraftEditor-content',
            ]
            
            for selector in composer_selectors:
                try:
                    composer = await self._page.wait_for_selector(selector, timeout=8000)
                    if composer:
                        logger.info("Found tweet composer", selector=selector)
                        break
                except Exception:
                    continue
            
            if not composer:
                # Last resort: try any contenteditable
                composer = await self._page.query_selector('[contenteditable="true"]')
                if composer:
                    logger.info("Found generic contenteditable for composer")
            
            if not composer:
                # Take screenshot for debugging
                logger.error("Could not find tweet composer after trying all selectors")
                return {"success": False, "error": "Tweet composer not found - please check browser session"}
            
            # Click and type the tweet text
            await composer.click()
            await self._human_delay(0.3, 0.6)
            
            # Type the text with human-like delays (faster for longer text)
            type_delay = max(10, min(50, 2000 // len(text))) if len(text) > 0 else 30
            await composer.type(text, delay=type_delay)
            await self._human_delay(0.5, 1)
            
            # Upload media if provided
            if media_path:
                try:
                    # Find the media upload input (it's a hidden file input)
                    media_input = await self._page.query_selector('input[type="file"][accept*="image"], input[type="file"][accept*="video"]')
                    if media_input:
                        await media_input.set_input_files(media_path)
                        logger.info("Media file selected", path=media_path)
                        # Wait for upload to complete (longer for larger files)
                        await self._human_delay(5, 8)
                        
                        # Wait for media preview to appear
                        try:
                            await self._page.wait_for_selector('[data-testid="attachments"], [data-testid="mediaPreview"]', timeout=15000)
                            logger.info("Media uploaded successfully")
                        except Exception:
                            logger.warning("Media preview not detected, but continuing")
                    else:
                        logger.warning("Media upload input not found, posting without media")
                except Exception as e:
                    logger.warning("Media upload failed, posting without media", error=str(e))
            
            # Find and click the Post/Tweet button
            post_button = None
            post_selectors = [
                '[data-testid="tweetButton"]',
                '[data-testid="tweetButtonInline"]',
                'button[data-testid*="tweet"]',
            ]
            
            for selector in post_selectors:
                post_button = await self._page.query_selector(selector)
                if post_button:
                    logger.info("Found post button", selector=selector)
                    break
            
            if not post_button:
                logger.error("Post button not found")
                return {"success": False, "error": "Post button not found"}
            
            # Check if button is enabled
            is_disabled = await post_button.get_attribute("aria-disabled")
            if is_disabled == "true":
                logger.error("Post button is disabled")
                return {"success": False, "error": "Post button disabled - tweet may be invalid"}
            
            # Click the post button with no-wait-after to prevent hanging on navigation
            logger.info("Clicking post button")
            try:
                # Use dispatch click event to avoid waiting for navigation
                await post_button.dispatch_event("click")
            except Exception as click_error:
                logger.warning("dispatch_event click failed, trying regular click", error=str(click_error))
                try:
                    await post_button.click(timeout=5000, no_wait_after=True)
                except Exception:
                    # Even if click times out, the tweet might have been posted
                    logger.warning("Click timed out but tweet may have been posted")
            
            # Wait for tweet to be posted - look for success indicators
            logger.info("Waiting for post confirmation")
            await self._human_delay(3, 5)
            
            # Check for success toast notification
            try:
                # Twitter shows a "Your post was sent" or similar toast
                toast = await self._page.query_selector('[data-testid="toast"]')
                if toast:
                    toast_text = await toast.inner_text()
                    logger.info("Toast message found", text=toast_text)
                    if "sent" in toast_text.lower() or "posted" in toast_text.lower():
                        logger.info("Tweet posted successfully (toast confirmation)")
                        return {"success": True, "tweet_id": None, "url": None}
            except Exception:
                pass
            
            # Check current URL for tweet ID
            current_url = self._page.url
            tweet_id = None
            tweet_url = None
            
            if "/status/" in current_url:
                parts = current_url.split("/status/")
                if len(parts) > 1:
                    tweet_id = parts[1].split("?")[0].split("/")[0]
                    tweet_url = current_url
                    logger.info("Tweet posted successfully", tweet_id=tweet_id, url=tweet_url)
                    return {"success": True, "tweet_id": tweet_id, "url": tweet_url}
            
            # Check if compose modal is closed (indicates success)
            await self._human_delay(1, 2)
            composer_still_open = await self._page.query_selector('[data-testid="tweetTextarea_0"]')
            
            # If composer has text, check if it's empty (cleared after posting)
            if composer_still_open:
                try:
                    composer_text = await composer_still_open.inner_text()
                    if not composer_text.strip():
                        logger.info("Tweet posted successfully (composer cleared)")
                        return {"success": True, "tweet_id": None, "url": None}
                except Exception:
                    pass
            
            # If we're back on home or composer is gone, assume success
            if not composer_still_open or "home" in self._page.url.lower():
                logger.info("Tweet posted successfully (composer closed/returned to home)")
                return {"success": True, "tweet_id": None, "url": None}
            
            # Check for error message
            error_el = await self._page.query_selector('[data-testid="toast"]')
            if error_el:
                try:
                    error_text = await error_el.inner_text()
                    if "error" in error_text.lower() or "fail" in error_text.lower():
                        logger.error("Tweet posting error", error=error_text)
                        return {"success": False, "error": error_text}
                except Exception:
                    pass
            
            # If we got here without errors, assume success (tweet was likely posted)
            logger.info("Tweet likely posted (no errors detected)")
            return {"success": True, "tweet_id": None, "url": None}
            
        except Exception as e:
            logger.error("Failed to post tweet", error=str(e))
            return {"success": False, "error": str(e)}

    async def reply_to_tweet(self, tweet_url: str, text: str) -> Dict[str, Any]:
        """Reply to a tweet.
        
        Args:
            tweet_url: URL of the tweet to reply to
            text: Reply text
            
        Returns:
            Dict with 'success', 'tweet_id', 'url', and 'error' fields
        """
        return await self.post_tweet(text=text, reply_to_url=tweet_url)

    async def search_tweets(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for tweets using browser.
        
        Args:
            query: Search query (can include hashtags)
            limit: Maximum number of tweets to return
            
        Returns:
            List of tweet data dictionaries
        """
        await self._ensure_browser()
        
        if not self._logged_in:
            logger.warning("Not logged in, search may be limited")
        
        try:
            import urllib.parse
            
            # Ensure hashtag format and URL encode
            if not query.startswith("#"):
                query = f"#{query}"
            
            # URL encode the query
            encoded_query = urllib.parse.quote(query)
            
            logger.info("Searching tweets via browser", query=query, encoded=encoded_query)
            
            # Navigate to search - use "Top" results for better relevance (remove f=live)
            # or use f=live for latest. Let's try without f= to get "Top" results which are more relevant
            search_url = f"https://twitter.com/search?q={encoded_query}&src=typed_query"
            await self._page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
            
            # Wait a bit for tweets to load (they load via JS)
            await self._human_delay(3, 5)
            
            # Wait for tweets to appear
            try:
                await self._page.wait_for_selector('[data-testid="tweet"]', timeout=10000)
            except Exception:
                logger.warning("No tweets found on page, might need to scroll or page is empty")
            
            tweets = []
            scroll_attempts = 0
            max_scrolls = 2  # Reduced scrolls for speed
            
            while len(tweets) < limit and scroll_attempts < max_scrolls:
                # Find tweet articles
                tweet_elements = await self._page.query_selector_all('[data-testid="tweet"]')
                
                for tweet_el in tweet_elements:
                    if len(tweets) >= limit:
                        break
                    
                    try:
                        # Extract tweet data
                        # Get the tweet link to extract ID
                        time_link = await tweet_el.query_selector('time')
                        if time_link:
                            parent_link = await time_link.evaluate('el => el.parentElement.href')
                            tweet_id = parent_link.split('/')[-1] if parent_link else None
                        else:
                            tweet_id = None
                        
                        # Skip if we already have this tweet
                        if tweet_id and any(t.get('id') == tweet_id for t in tweets):
                            continue
                        
                        # Get tweet text
                        text_el = await tweet_el.query_selector('[data-testid="tweetText"]')
                        text = await text_el.inner_text() if text_el else ""
                        
                        # Get author
                        author_el = await tweet_el.query_selector('[data-testid="User-Name"]')
                        author_text = await author_el.inner_text() if author_el else ""
                        author_lines = author_text.split('\n')
                        author_username = author_lines[1].replace('@', '') if len(author_lines) > 1 else ""
                        
                        if tweet_id:
                            tweets.append({
                                'id': tweet_id,
                                'text': text,
                                'author_username': author_username,
                                'url': f"https://twitter.com/{author_username}/status/{tweet_id}",
                            })
                            
                    except Exception as e:
                        logger.debug("Failed to extract tweet data", error=str(e))
                        continue
                
                # Scroll for more tweets
                await self._random_scroll()
                await self._random_scroll()
                await self._human_delay(1, 2)
                scroll_attempts += 1
            
            logger.info("Search completed", query=query, found=len(tweets))
            return tweets[:limit]
            
        except Exception as e:
            logger.error("Tweet search failed", query=query, error=str(e))
            return []

    async def close(self):
        """Close the browser."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None
            self._logged_in = False
        
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        
        logger.info("Twitter browser closed")

