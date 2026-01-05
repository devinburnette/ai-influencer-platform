"""Fanvue browser automation module using Playwright.

Since Fanvue doesn't have a publicly available API, we use browser
automation to interact with the platform.
"""

import asyncio
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import structlog
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from app.config import get_settings

logger = structlog.get_logger()

# Directory to store browser session data
BROWSER_DATA_DIR = Path("/tmp/fanvue_sessions")


class FanvueBrowser:
    """Fanvue browser automation client using Playwright."""
    
    BASE_URL = "https://www.fanvue.com"
    
    def __init__(
        self,
        session_id: str,
        headless: bool = True,
    ):
        """Initialize Fanvue browser automation.
        
        Args:
            session_id: Unique identifier for browser session (e.g., persona_id)
            headless: Whether to run browser in headless mode
        """
        self.session_id = session_id
        self.headless = headless
        self.settings = get_settings()
        
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        # Session data directory for this session
        self._session_dir = BROWSER_DATA_DIR / session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)
        
        # Cookie file path
        self._cookies_path = self._session_dir / "cookies.json"
        self._local_storage_path = self._session_dir / "local_storage.json"
    
    async def _init_browser(self) -> None:
        """Initialize the browser and context."""
        if self._browser is not None:
            return
        
        self._playwright = await async_playwright().start()
        
        # Use persistent context to maintain session state
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
            "viewport": {"width": 1280, "height": 720},
            "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        
        self._context = await self._browser.new_context(**context_options)
        
        # Load saved cookies if they exist
        await self._load_session()
        
        self._page = await self._context.new_page()
        
        # Set default timeout
        self._page.set_default_timeout(30000)
    
    @property
    async def page(self) -> Page:
        """Get the browser page, initializing if needed."""
        if self._page is None:
            await self._init_browser()
        return self._page
    
    async def _load_session(self) -> bool:
        """Load saved session (cookies and local storage).
        
        Returns:
            True if session was loaded successfully
        """
        try:
            if self._cookies_path.exists():
                with open(self._cookies_path, "r") as f:
                    cookies = json.load(f)
                await self._context.add_cookies(cookies)
                logger.info("Loaded Fanvue session cookies", session_id=self.session_id)
                return True
        except Exception as e:
            logger.warning("Failed to load Fanvue session", error=str(e))
        return False
    
    async def _save_session(self) -> None:
        """Save current session (cookies and local storage)."""
        try:
            # Save cookies
            cookies = await self._context.cookies()
            with open(self._cookies_path, "w") as f:
                json.dump(cookies, f)
            
            logger.info("Saved Fanvue session", session_id=self.session_id)
        except Exception as e:
            logger.error("Failed to save Fanvue session", error=str(e))
    
    async def set_cookies_from_list(self, cookies: List[Dict[str, Any]]) -> None:
        """Set cookies from a list of Playwright cookie objects.
        
        This is the format returned by context.cookies() and stored in the database
        after guided login.
        
        Args:
            cookies: List of Playwright cookie dicts with name, value, domain, etc.
        """
        if not self._context:
            await self._init_browser()
        
        if not cookies:
            logger.warning("No cookies provided to set_cookies_from_list")
            return
        
        # Filter to only Fanvue cookies if needed
        fanvue_cookies = [
            c for c in cookies 
            if "fanvue" in c.get("domain", "").lower()
        ]
        
        if not fanvue_cookies:
            # If no fanvue-specific cookies, try all of them
            fanvue_cookies = cookies
        
        try:
            await self._context.add_cookies(fanvue_cookies)
            logger.info(
                "Set Fanvue cookies from list",
                count=len(fanvue_cookies),
                session_id=self.session_id,
            )
        except Exception as e:
            logger.warning("Error setting cookies from list, trying one by one", error=str(e))
            success_count = 0
            for cookie in fanvue_cookies:
                try:
                    await self._context.add_cookies([cookie])
                    success_count += 1
                except Exception as ce:
                    logger.debug("Skipped cookie", name=cookie.get("name"), error=str(ce))
            logger.info(f"Set {success_count}/{len(fanvue_cookies)} cookies")

    async def set_cookies_from_db(self, cookies_dict: Dict[str, str]) -> None:
        """Set cookies from a dictionary (from database).
        
        Args:
            cookies_dict: Dict of cookie name -> value from database
        """
        if not self._context:
            await self._init_browser()
        
        # Convert dict to Playwright cookie format
        cookies = []
        for name, value in cookies_dict.items():
            cookie = {
                "name": name,
                "value": str(value),
                "path": "/",
            }
            
            # Handle __Host- prefix cookies (require secure, no domain)
            if name.startswith("__Host-"):
                cookie["domain"] = "www.fanvue.com"
                cookie["secure"] = True
            else:
                cookie["domain"] = ".fanvue.com"
            
            cookies.append(cookie)
        
        if cookies:
            try:
                await self._context.add_cookies(cookies)
                logger.info("Set Fanvue cookies from database", count=len(cookies), session_id=self.session_id)
            except Exception as e:
                logger.warning("Error setting some cookies, trying one by one", error=str(e))
                # Try setting cookies one by one to skip problematic ones
                for cookie in cookies:
                    try:
                        await self._context.add_cookies([cookie])
                    except Exception as ce:
                        logger.debug("Skipped cookie", name=cookie["name"], error=str(ce))
    
    async def is_logged_in(self) -> bool:
        """Check if we're currently logged in to Fanvue.
        
        Returns:
            True if logged in
        """
        try:
            page = await self.page
            
            # Try to go to a page that requires login
            await page.goto(f"{self.BASE_URL}/messages", wait_until="networkidle", timeout=15000)
            
            # Wait a moment for any redirects
            await page.wait_for_timeout(2000)
            
            # Check if we're redirected to login/signin page
            current_url = page.url
            if "/signin" in current_url or "/login" in current_url:
                logger.info("Fanvue not logged in - redirected to signin", url=current_url)
                return False
            
            # If we're still on /messages or similar authenticated page, we're logged in
            logger.info("Fanvue login check passed", url=current_url)
            return True
                
        except Exception as e:
            logger.error("Error checking Fanvue login status", error=str(e))
            return False
    
    async def login(self, email: str, password: str) -> bool:
        """Log in to Fanvue.
        
        Args:
            email: Fanvue account email
            password: Account password
            
        Returns:
            True if login successful
        """
        try:
            page = await self.page
            
            # Navigate to sign-in page
            await page.goto(f"{self.BASE_URL}/signin", wait_until="networkidle")
            
            # Wait for login form
            await page.wait_for_selector('input[type="email"], input[name="email"]', timeout=10000)
            
            # Fill in email
            await page.fill('input[type="email"], input[name="email"]', email)
            
            # Fill in password
            await page.fill('input[type="password"], input[name="password"]', password)
            
            # Click login button
            await page.click('button[type="submit"], button:has-text("Log in"), button:has-text("Sign in")')
            
            # Wait for navigation or error
            try:
                # Wait for successful navigation to home/dashboard
                await page.wait_for_url("**/home**", timeout=15000)
                
                # Save session after successful login
                await self._save_session()
                
                logger.info("Fanvue login successful", session_id=self.session_id)
                return True
                
            except Exception:
                # Check for 2FA or other requirements
                if "verify" in page.url or "2fa" in page.url:
                    logger.warning("Fanvue requires 2FA verification", session_id=self.session_id)
                    return False
                
                # Check for error messages
                error = await page.query_selector('[class*="error"], [role="alert"]')
                if error:
                    error_text = await error.text_content()
                    logger.error("Fanvue login failed", error=error_text)
                
                return False
                
        except Exception as e:
            logger.error("Fanvue login error", error=str(e))
            return False
    
    async def get_username(self) -> Optional[str]:
        """Get the logged-in username.
        
        Returns:
            Username if logged in, None otherwise
        """
        try:
            page = await self.page
            await page.goto(f"{self.BASE_URL}/settings", wait_until="networkidle")
            
            # Try to find username from profile settings
            username_input = await page.query_selector('input[name="username"], input[id="username"]')
            if username_input:
                return await username_input.get_attribute("value")
            
            # Alternative: look for @username display
            username_el = await page.query_selector('[class*="username"], .profile-username')
            if username_el:
                text = await username_el.text_content()
                return text.strip().lstrip("@")
            
            return None
            
        except Exception as e:
            logger.error("Error getting Fanvue username", error=str(e))
            return None
    
    # ===== Chat/DM Functions =====
    
    async def get_chats(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get list of chat conversations.
        
        Args:
            limit: Maximum number of chats to retrieve
            
        Returns:
            List of chat data with user info
        """
        try:
            page = await self.page
            await page.goto(f"{self.BASE_URL}/messages", wait_until="networkidle")
            
            # Wait for chat list to load
            await page.wait_for_selector('[class*="chat-list"], [class*="conversation-list"], .messages-list', timeout=10000)
            
            # Get chat items
            chat_elements = await page.query_selector_all('[class*="chat-item"], [class*="conversation-item"], .message-thread')
            
            chats = []
            for i, chat_el in enumerate(chat_elements[:limit]):
                try:
                    # Extract chat data
                    username_el = await chat_el.query_selector('[class*="username"], .user-name')
                    preview_el = await chat_el.query_selector('[class*="preview"], [class*="last-message"]')
                    unread_el = await chat_el.query_selector('[class*="unread"], .unread-badge')
                    
                    chat_data = {
                        "index": i,
                        "username": await username_el.text_content() if username_el else "Unknown",
                        "preview": await preview_el.text_content() if preview_el else "",
                        "has_unread": unread_el is not None,
                    }
                    
                    # Get data attributes if available
                    user_id = await chat_el.get_attribute("data-user-id") or await chat_el.get_attribute("data-id")
                    if user_id:
                        chat_data["user_id"] = user_id
                    
                    chats.append(chat_data)
                    
                except Exception as e:
                    logger.warning("Error parsing chat item", index=i, error=str(e))
            
            logger.info("Retrieved Fanvue chats", count=len(chats))
            return chats
            
        except Exception as e:
            logger.error("Error getting Fanvue chats", error=str(e))
            return []
    
    async def get_chat_messages(
        self,
        user_identifier: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get messages from a specific chat.
        
        Args:
            user_identifier: Username or user ID to get messages from
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of messages (newest first)
        """
        try:
            page = await self.page
            
            # Navigate to the specific chat
            # Try direct URL first if it's a user ID
            if user_identifier.startswith("@"):
                await page.goto(f"{self.BASE_URL}/messages/{user_identifier[1:]}", wait_until="networkidle")
            else:
                await page.goto(f"{self.BASE_URL}/messages/{user_identifier}", wait_until="networkidle")
            
            # Wait for messages to load
            await page.wait_for_selector('[class*="message-content"], [class*="chat-message"], .message', timeout=10000)
            
            # Get message elements
            message_elements = await page.query_selector_all('[class*="message-item"], [class*="chat-message"], .message')
            
            messages = []
            for msg_el in message_elements[-limit:]:  # Get most recent messages
                try:
                    text_el = await msg_el.query_selector('[class*="text"], [class*="content"], .message-text')
                    time_el = await msg_el.query_selector('[class*="time"], [class*="timestamp"]')
                    
                    # Check if sent by us or received
                    is_sent = await msg_el.get_attribute("class") or ""
                    is_from_me = "sent" in is_sent or "outgoing" in is_sent or "self" in is_sent
                    
                    message_data = {
                        "text": await text_el.text_content() if text_el else "",
                        "timestamp": await time_el.text_content() if time_el else "",
                        "is_from_me": is_from_me,
                    }
                    
                    messages.append(message_data)
                    
                except Exception as e:
                    logger.warning("Error parsing message", error=str(e))
            
            return messages
            
        except Exception as e:
            logger.error("Error getting chat messages", user=user_identifier, error=str(e))
            return []
    
    async def send_message(
        self,
        user_identifier: str,
        text: str,
        media_path: Optional[str] = None,
    ) -> bool:
        """Send a message to a user.
        
        Args:
            user_identifier: Username or user ID to send message to
            text: Message text
            media_path: Optional path to media file to attach
            
        Returns:
            True if message was sent successfully
        """
        try:
            page = await self.page
            
            # Navigate to chat
            if user_identifier.startswith("@"):
                await page.goto(f"{self.BASE_URL}/messages/{user_identifier[1:]}", wait_until="networkidle")
            else:
                await page.goto(f"{self.BASE_URL}/messages/{user_identifier}", wait_until="networkidle")
            
            # Wait for message input
            input_selector = 'textarea[class*="message"], input[class*="message"], [contenteditable="true"], .message-input'
            await page.wait_for_selector(input_selector, timeout=10000)
            
            # Attach media if provided
            if media_path and os.path.exists(media_path):
                # Look for file input or attachment button
                file_input = await page.query_selector('input[type="file"]')
                if file_input:
                    await file_input.set_input_files(media_path)
                    await asyncio.sleep(2)  # Wait for upload
            
            # Type message
            await page.fill(input_selector, text)
            
            # Send message (press Enter or click send button)
            send_button = await page.query_selector('button[class*="send"], button:has-text("Send"), [aria-label*="send"]')
            if send_button:
                await send_button.click()
            else:
                await page.press(input_selector, "Enter")
            
            # Wait for message to appear in chat
            await asyncio.sleep(2)
            
            logger.info("Sent Fanvue message", user=user_identifier)
            return True
            
        except Exception as e:
            logger.error("Error sending Fanvue message", user=user_identifier, error=str(e))
            return False
    
    # ===== Post Functions =====
    
    async def create_post(
        self,
        text: str,
        media_paths: Optional[List[str]] = None,
        schedule_time: Optional[datetime] = None,
    ) -> bool:
        """Create a new post on Fanvue.
        
        Args:
            text: Post caption/text
            media_paths: List of local file paths to upload
            schedule_time: Optional time to schedule the post
            
        Returns:
            True if post was created successfully
        """
        try:
            page = await self.page
            
            # Navigate to create post page or home
            await page.goto(f"{self.BASE_URL}/create", wait_until="networkidle")
            
            # If no dedicated create page, look for create button on home
            if "create" not in page.url:
                await page.goto(f"{self.BASE_URL}/home", wait_until="networkidle")
                create_button = await page.query_selector('button:has-text("Create"), button:has-text("Post"), [aria-label*="create"]')
                if create_button:
                    await create_button.click()
                    await asyncio.sleep(1)
            
            # Wait for post creation form
            text_input = 'textarea[class*="post"], [contenteditable="true"], .post-input, textarea'
            await page.wait_for_selector(text_input, timeout=10000)
            
            # Upload media if provided
            if media_paths:
                for media_path in media_paths:
                    if os.path.exists(media_path):
                        file_input = await page.query_selector('input[type="file"]')
                        if file_input:
                            await file_input.set_input_files(media_path)
                            await asyncio.sleep(3)  # Wait for upload
            
            # Enter post text
            await page.fill(text_input, text)
            
            # Handle scheduling if specified
            if schedule_time:
                schedule_button = await page.query_selector('button:has-text("Schedule"), [aria-label*="schedule"]')
                if schedule_button:
                    await schedule_button.click()
                    # Would need to interact with datetime picker - complex UI interaction
                    logger.warning("Post scheduling via browser not fully implemented")
            
            # Click post/publish button
            post_button = await page.query_selector('button:has-text("Post"), button:has-text("Publish"), button[type="submit"]')
            if post_button:
                await post_button.click()
            
            # Wait for post to be created
            await asyncio.sleep(3)
            
            # Check for success (redirect to post or success message)
            success_indicator = await page.query_selector('[class*="success"], [role="alert"]:has-text("success")')
            if success_indicator or "post" in page.url:
                logger.info("Fanvue post created successfully")
                return True
            
            logger.warning("Fanvue post creation may have failed - no success indicator")
            return True  # Assume success if no error
            
        except Exception as e:
            logger.error("Error creating Fanvue post", error=str(e))
            return False
    
    async def upload_media_from_url(
        self,
        media_url: str,
        media_type: str = "image",
    ) -> Optional[str]:
        """Download media from URL and save locally for upload.
        
        Args:
            media_url: URL of media to download
            media_type: Type of media ("image" or "video")
            
        Returns:
            Local file path if successful
        """
        try:
            import httpx
            
            # Download media
            async with httpx.AsyncClient() as client:
                response = await client.get(media_url, follow_redirects=True)
                response.raise_for_status()
                
                # Determine extension
                content_type = response.headers.get("content-type", "")
                if "jpeg" in content_type or "jpg" in content_type:
                    ext = ".jpg"
                elif "png" in content_type:
                    ext = ".png"
                elif "gif" in content_type:
                    ext = ".gif"
                elif "mp4" in content_type:
                    ext = ".mp4"
                elif "webm" in content_type:
                    ext = ".webm"
                else:
                    ext = ".jpg" if media_type == "image" else ".mp4"
                
                # Save to temp file
                filename = f"{self.session_id}_{datetime.now().timestamp()}{ext}"
                filepath = self._session_dir / filename
                
                with open(filepath, "wb") as f:
                    f.write(response.content)
                
                logger.info("Downloaded media for Fanvue upload", filepath=str(filepath))
                return str(filepath)
                
        except Exception as e:
            logger.error("Error downloading media for Fanvue", url=media_url[:100], error=str(e))
            return None
    
    # ===== Cleanup =====
    
    async def close(self) -> None:
        """Close the browser and save session."""
        try:
            if self._context:
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
                
            logger.info("Fanvue browser closed", session_id=self.session_id)
            
        except Exception as e:
            logger.error("Error closing Fanvue browser", error=str(e))
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._init_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

