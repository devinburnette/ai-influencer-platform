"""Fanvue platform adapter using browser automation."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from app.services.platforms.base import (
    PlatformAdapter,
    Post,
    PostResult,
    Analytics,
    UserProfile,
)
from app.services.platforms.fanvue.browser import FanvueBrowser

logger = structlog.get_logger()


class FanvueAdapter(PlatformAdapter):
    """Fanvue platform adapter using browser automation.
    
    Since Fanvue doesn't have a publicly available API, we use
    Playwright for browser automation to interact with the platform.
    """

    def __init__(
        self,
        session_id: str,
        email: Optional[str] = None,
        password: Optional[str] = None,
        headless: bool = True,
    ):
        """Initialize Fanvue adapter.
        
        Args:
            session_id: Unique session identifier (e.g., persona_id)
            email: Fanvue account email for login
            password: Fanvue account password for login
            headless: Whether to run browser in headless mode
        """
        self._browser = FanvueBrowser(
            session_id=session_id,
            headless=headless,
        )
        self._email = email
        self._password = password
        self._username: Optional[str] = None
        self._is_authenticated = False
        
        logger.info(
            "Fanvue adapter initialized (browser automation)",
            session_id=session_id,
            has_credentials=email is not None,
        )

    @property
    def platform_name(self) -> str:
        return "fanvue"
    
    @property
    def browser(self) -> FanvueBrowser:
        """Get the underlying browser client."""
        return self._browser
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information for persistence.
        
        Returns:
            Dict with session_id and username
        """
        return {
            "session_id": self._browser.session_id,
            "username": self._username,
            "is_authenticated": self._is_authenticated,
        }

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Fanvue using browser automation.
        
        Credentials should include one of:
            - session_cookies: Dict of cookies from database (preferred)
            - email + password: For fresh login
            - session_id: Existing session ID to resume from file
        """
        try:
            # First try to use session cookies from database
            session_cookies = credentials.get("session_cookies")
            if session_cookies and isinstance(session_cookies, dict):
                await self._browser.set_cookies_from_db(session_cookies)
                
                if await self._browser.is_logged_in():
                    self._is_authenticated = True
                    self._username = await self._browser.get_username()
                    logger.info("Fanvue session restored from cookies", username=self._username)
                    return True
                else:
                    logger.warning("Fanvue cookies invalid or expired")
            
            # Fall back to email/password login
            email = credentials.get("email") or self._email
            password = credentials.get("password") or self._password
            
            if email and password:
                # Perform login
                success = await self._browser.login(email, password)
                
                if success:
                    self._is_authenticated = True
                    self._username = await self._browser.get_username()
                    logger.info("Fanvue authentication successful", username=self._username)
                    return True
            
            # Last resort - try to resume from file-based session
            if await self._browser.is_logged_in():
                self._is_authenticated = True
                self._username = await self._browser.get_username()
                logger.info("Fanvue session resumed from file", username=self._username)
                return True
            
            return False
            
        except Exception as e:
            logger.error("Fanvue authentication failed", error=str(e))
            return False

    async def verify_connection(self) -> bool:
        """Verify the connection is still valid."""
        try:
            is_logged_in = await self._browser.is_logged_in()
            self._is_authenticated = is_logged_in
            
            if is_logged_in and not self._username:
                self._username = await self._browser.get_username()
            
            return is_logged_in
            
        except Exception as e:
            logger.warning("Fanvue connection verification failed", error=str(e))
            return False

    async def post_content(
        self,
        caption: str,
        media_paths: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
        **kwargs,
    ) -> PostResult:
        """Post content to Fanvue using browser automation.
        
        Args:
            caption: Post caption/text
            media_paths: List of media URLs to upload
            hashtags: Hashtags (will be appended to caption)
            **kwargs: Additional options:
                - is_video: bool - Whether media is video
                - schedule_time: datetime - When to schedule post
        """
        try:
            if not self._is_authenticated:
                return PostResult(
                    success=False,
                    error_message="Not authenticated with Fanvue",
                )
            
            # Combine caption with hashtags
            full_caption = caption
            if hashtags:
                hashtag_string = " ".join(f"#{tag}" for tag in hashtags)
                full_caption = f"{caption}\n\n{hashtag_string}"
            
            # Download and prepare media files
            local_media_paths = []
            if media_paths:
                is_video = kwargs.get("is_video", False)
                media_type = "video" if is_video else "image"
                
                for media_url in media_paths:
                    if not media_url.startswith("http"):
                        # Already a local path
                        local_media_paths.append(media_url)
                        continue
                    
                    # Download from URL
                    local_path = await self._browser.upload_media_from_url(
                        media_url=media_url,
                        media_type=media_type,
                    )
                    
                    if local_path:
                        local_media_paths.append(local_path)
            
            if media_paths and not local_media_paths:
                return PostResult(
                    success=False,
                    error_message="Failed to download media for Fanvue upload",
                )
            
            # Create the post via browser
            schedule_time = kwargs.get("schedule_time")
            
            success = await self._browser.create_post(
                text=full_caption,
                media_paths=local_media_paths if local_media_paths else None,
                schedule_time=schedule_time,
            )
            
            if success:
                logger.info("Fanvue post created via browser automation")
                return PostResult(
                    success=True,
                    post_id=None,  # Browser automation doesn't easily capture post ID
                    url=None,
                )
            else:
                return PostResult(
                    success=False,
                    error_message="Failed to create post via browser",
                )
            
        except Exception as e:
            logger.error("Fanvue post creation failed", error=str(e))
            return PostResult(
                success=False,
                error_message=str(e),
            )

    async def like_post(self, post_id: str) -> bool:
        """Like a post - not commonly used on Fanvue for creators."""
        logger.warning("Like post not implemented for Fanvue")
        return False

    async def unlike_post(self, post_id: str) -> bool:
        """Unlike a post - not commonly used on Fanvue for creators."""
        logger.warning("Unlike post not implemented for Fanvue")
        return False

    async def comment(self, post_id: str, text: str) -> Optional[str]:
        """Comment on a post - not commonly used on Fanvue for creators."""
        logger.warning("Comment not implemented for Fanvue")
        return None

    async def follow_user(self, user_id: str) -> bool:
        """Follow a user - not commonly used on Fanvue for creators."""
        logger.warning("Follow user not implemented for Fanvue")
        return False

    async def unfollow_user(self, user_id: str) -> bool:
        """Unfollow a user - not commonly used on Fanvue for creators."""
        logger.warning("Unfollow user not implemented for Fanvue")
        return False

    async def get_feed(
        self,
        hashtags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Post]:
        """Get feed posts - not applicable for Fanvue creators."""
        return []

    async def get_user_posts(self, user_id: str, limit: int = 20) -> List[Post]:
        """Get posts from the authenticated user."""
        # Would require navigating to profile and scraping posts
        logger.warning("Get user posts not fully implemented for Fanvue browser automation")
        return []

    async def get_user_profile(self, username: str) -> Optional[UserProfile]:
        """Get user profile - limited to self on Fanvue."""
        try:
            if self._username:
                return UserProfile(
                    id=self._browser.session_id,
                    username=self._username,
                    display_name=self._username,
                    bio=None,
                    profile_picture_url=None,
                    follower_count=0,
                    is_verified=False,
                )
            return None
            
        except Exception as e:
            logger.error("Failed to get Fanvue profile", error=str(e))
            return None

    async def get_analytics(self) -> Analytics:
        """Get analytics for the authenticated account."""
        # Would require navigating to analytics page and scraping
        logger.warning("Get analytics not fully implemented for Fanvue browser automation")
        return Analytics()

    async def search_hashtag(self, hashtag: str, limit: int = 20) -> List[Post]:
        """Search by hashtag - not applicable for Fanvue."""
        return []
    
    # ===== Fanvue-specific DM Methods =====
    
    async def get_dm_inbox(
        self,
        limit: int = 15,
        filter_unanswered: bool = True,
    ) -> List[Dict[str, Any]]:
        """Get DM inbox with optional filtering for unanswered messages.
        
        Args:
            limit: Number of conversations to fetch
            filter_unanswered: If True, only return unanswered chats
            
        Returns:
            List of chat conversation data
        """
        try:
            chats = await self._browser.get_chats(limit=limit)
            
            if filter_unanswered:
                # Filter to only unanswered chats
                chats = [c for c in chats if c.get("has_unread")]
            
            return chats
            
        except Exception as e:
            logger.error("Failed to get Fanvue DM inbox", error=str(e))
            return []
    
    async def get_conversation_messages(
        self,
        user_identifier: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get messages from a specific conversation.
        
        Args:
            user_identifier: Username or user ID
            limit: Number of messages to fetch
            
        Returns:
            List of messages
        """
        try:
            messages = await self._browser.get_chat_messages(
                user_identifier=user_identifier,
                limit=limit,
            )
            return messages
            
        except Exception as e:
            logger.error("Failed to get Fanvue conversation messages", error=str(e), user=user_identifier)
            return []
    
    async def send_dm(self, user_identifier: str, text: str) -> bool:
        """Send a DM to a user.
        
        Args:
            user_identifier: Username or user ID
            text: Message content
            
        Returns:
            True if sent successfully
        """
        try:
            success = await self._browser.send_message(
                user_identifier=user_identifier,
                text=text,
            )
            
            if success:
                logger.info("Fanvue DM sent via browser", user=user_identifier, text_preview=text[:50])
            
            return success
            
        except Exception as e:
            logger.error("Failed to send Fanvue DM", error=str(e), user=user_identifier)
            return False

    async def close(self):
        """Clean up resources."""
        await self._browser.close()
