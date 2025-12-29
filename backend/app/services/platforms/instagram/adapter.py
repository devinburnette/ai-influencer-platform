"""Instagram platform adapter - hybrid approach using Graph API and browser automation."""

from typing import Dict, Any, List, Optional
import structlog

from app.services.platforms.base import (
    PlatformAdapter,
    Post,
    PostResult,
    Analytics,
    UserProfile,
)
from app.services.platforms.instagram.graph_api import InstagramGraphAPI
from app.services.platforms.instagram.browser import InstagramBrowser

logger = structlog.get_logger()


class InstagramAdapter(PlatformAdapter):
    """Instagram adapter using hybrid Graph API + browser automation approach."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        instagram_account_id: Optional[str] = None,
        session_cookies: Optional[Dict[str, str]] = None,
        use_browser: bool = True,
    ):
        """Initialize Instagram adapter.
        
        Args:
            access_token: Meta Graph API access token
            instagram_account_id: Instagram Business Account ID
            session_cookies: Browser session cookies for automation
            use_browser: Whether to use browser automation for unsupported features
        """
        self._graph_api: Optional[InstagramGraphAPI] = None
        self._browser: Optional[InstagramBrowser] = None
        self._session_invalid = False
        
        self.access_token = access_token
        self.instagram_account_id = instagram_account_id
        self.session_cookies = session_cookies
        self.use_browser = use_browser
        
        if access_token and instagram_account_id:
            self._graph_api = InstagramGraphAPI(access_token, instagram_account_id)
        
        logger.info(
            "Instagram adapter initialized",
            has_graph_api=self._graph_api is not None,
            use_browser=use_browser,
        )
    
    @property
    def session_needs_refresh(self) -> bool:
        """Check if the browser session needs to be refreshed."""
        if self._browser:
            return self._browser.session_needs_refresh
        return self._session_invalid

    @property
    def platform_name(self) -> str:
        return "instagram"

    async def _get_browser(self) -> InstagramBrowser:
        """Get or create browser instance."""
        if self._browser is None:
            self._browser = InstagramBrowser()
            if self.session_cookies:
                await self._browser.load_cookies(self.session_cookies)
        return self._browser

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Instagram.
        
        Credentials can include:
        - access_token + instagram_account_id: For Graph API
        - username + password: For browser automation
        - session_cookies: For resuming browser session
        """
        try:
            # Try Graph API authentication
            if "access_token" in credentials and "instagram_account_id" in credentials:
                self.access_token = credentials["access_token"]
                self.instagram_account_id = credentials["instagram_account_id"]
                self._graph_api = InstagramGraphAPI(
                    self.access_token,
                    self.instagram_account_id,
                )
                
                # Verify the token works
                if await self._graph_api.verify_token():
                    logger.info("Graph API authentication successful")
                    return True
            
            # Try browser authentication
            if self.use_browser:
                browser = await self._get_browser()
                
                if "session_cookies" in credentials:
                    await browser.load_cookies(credentials["session_cookies"])
                    if await browser.verify_session():
                        logger.info("Browser session authentication successful")
                        return True
                
                if "username" in credentials and "password" in credentials:
                    success = await browser.login(
                        credentials["username"],
                        credentials["password"],
                    )
                    if success:
                        self.session_cookies = await browser.get_cookies()
                        logger.info("Browser login successful")
                        return True
            
            return False
            
        except Exception as e:
            logger.error("Authentication failed", error=str(e))
            return False

    async def verify_connection(self) -> bool:
        """Verify the connection is still valid."""
        if self._graph_api:
            return await self._graph_api.verify_token()
        
        if self._browser:
            return await self._browser.verify_session()
        
        return False

    async def post_content(
        self,
        caption: str,
        media_paths: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
        **kwargs,
    ) -> PostResult:
        """Post content to Instagram.
        
        IMPORTANT: Instagram requires an image for every post.
        Text-only posts are not supported on Instagram.
        
        Uses Graph API first (requires business/creator account),
        falls back to browser automation if Graph API fails or is not available.
        
        Args:
            caption: Post caption
            media_paths: List of media URLs (images or videos)
            hashtags: List of hashtags
            is_video: Whether the media is a video (from kwargs)
            content_type: ContentType enum (from kwargs)
        """
        # Extract video-related kwargs
        is_video = kwargs.get("is_video", False)
        content_type = kwargs.get("content_type")
        
        # Instagram REQUIRES media - there's no text-only posting
        if not media_paths or len(media_paths) == 0:
            logger.error("Instagram requires media for every post")
            return PostResult(
                success=False,
                error_message="Instagram requires media for every post. Please attach a media URL.",
            )
        
        # Combine caption with hashtags
        full_caption = caption
        if hashtags:
            hashtag_string = " ".join(f"#{tag}" for tag in hashtags)
            full_caption = f"{caption}\n\n{hashtag_string}"
        
        # media_paths should contain publicly accessible URLs
        media_url = media_paths[0]
        
        # Validate that it looks like a URL
        if not media_url.startswith("http"):
            return PostResult(
                success=False,
                error_message=f"Invalid media URL: {media_url}. Instagram requires a publicly accessible URL (must start with http:// or https://).",
            )
        
        # Try Graph API first if configured
        if self._graph_api:
            try:
                result = await self._graph_api.create_media_post(
                    media_url,
                    full_caption,
                    is_video=is_video,
                    content_type=content_type,
                )
                
                if result.success:
                    logger.info("Instagram post created successfully via Graph API", post_id=result.post_id)
                    return result
                else:
                    logger.warning(
                        "Instagram Graph API posting failed, will try browser fallback",
                        error=result.error_message,
                    )
                    
            except Exception as e:
                logger.warning(
                    "Instagram Graph API posting failed, will try browser fallback",
                    error=str(e),
                )
        else:
            logger.info("Instagram Graph API not configured, using browser automation")
        
        # Fall back to browser automation
        if not self.use_browser:
            return PostResult(
                success=False,
                error_message="Instagram Graph API failed and browser automation is disabled.",
            )
        
        try:
            browser = await self._get_browser()
            
            # Verify session first
            session_valid = await browser.verify_session()
            if not session_valid:
                logger.error("Instagram browser session is invalid")
                self._session_invalid = True
                return PostResult(
                    success=False,
                    error_message="Instagram browser session is invalid. Please re-authenticate.",
                )
            
            # Download the image for browser-based posting
            # (browser automation needs local files, not URLs)
            local_image_path = await browser.download_image_for_post(media_url)
            
            if not local_image_path:
                return PostResult(
                    success=False,
                    error_message="Failed to download image for browser posting.",
                )
            
            try:
                # Create the post using browser
                result = await browser.create_post(
                    caption=full_caption,
                    media_path=local_image_path,
                )
                
                if result.success:
                    logger.info("Instagram post created successfully via browser", post_id=result.post_id)
                else:
                    logger.error("Instagram browser posting failed", error=result.error_message)
                
                return result
                
            finally:
                # Clean up temp file
                import os
                try:
                    if local_image_path and os.path.exists(local_image_path):
                        os.remove(local_image_path)
                        logger.debug("Cleaned up temp image file", path=local_image_path)
                except Exception as cleanup_error:
                    logger.warning("Failed to clean up temp image file", error=str(cleanup_error))
            
        except Exception as e:
            logger.error("Instagram browser posting failed", error=str(e))
            return PostResult(success=False, error_message=f"Instagram browser posting failed: {str(e)}")

    async def like_post(self, post_id: str) -> bool:
        """Like a post using browser automation."""
        if not self.use_browser:
            logger.warning("Like requires browser automation")
            return False
        
        try:
            browser = await self._get_browser()
            return await browser.like_post(post_id)
        except Exception as e:
            logger.error("Like failed", post_id=post_id, error=str(e))
            return False

    async def get_post_author(self) -> Optional[str]:
        """Get the author username of the current post page.
        
        Call this after like_post to get the author of the liked post.
        """
        if not self._browser:
            return None
        
        try:
            return await self._browser.get_post_author()
        except Exception as e:
            logger.debug("Failed to get post author", error=str(e))
            return None

    async def get_post_image_url(self) -> Optional[str]:
        """Get the main image URL of the current post page.
        
        Call this after like_post to get the image for vision analysis.
        """
        if not self._browser:
            return None
        
        try:
            return await self._browser.get_post_image_url()
        except Exception as e:
            logger.debug("Failed to get post image URL", error=str(e))
            return None

    async def unlike_post(self, post_id: str) -> bool:
        """Unlike a post using browser automation."""
        if not self.use_browser:
            return False
        
        try:
            browser = await self._get_browser()
            return await browser.unlike_post(post_id)
        except Exception as e:
            logger.error("Unlike failed", post_id=post_id, error=str(e))
            return False

    async def comment(self, post_id: str, text: str, author_username: Optional[str] = None) -> Optional[str]:
        """Comment on a post.
        
        Uses Graph API for own posts (with numeric media ID), browser for others.
        
        Args:
            post_id: Post ID (numeric) or URL to comment on
            text: Comment text
            author_username: Optional username (not used for Instagram but accepted for API compatibility)
        """
        # Check if this is a URL or a numeric ID
        is_url = post_id.startswith("http")
        
        # Try Graph API only if we have a numeric media ID (not a URL)
        # Graph API can only comment on posts you own, and requires numeric ID
        if self._graph_api and not is_url:
            try:
                comment_id = await self._graph_api.create_comment(post_id, text)
                if comment_id:
                    return comment_id
            except Exception as e:
                logger.debug("Graph API comment failed, falling back to browser", error=str(e))
        
        # Use browser automation for URLs or when Graph API fails
        if self.use_browser:
            try:
                browser = await self._get_browser()
                return await browser.comment_on_post(post_id, text)
            except Exception as e:
                logger.error("Comment failed", post_id=post_id, error=str(e))
        
        return None

    async def follow_user(self, user_id: str) -> bool:
        """Follow a user using browser automation."""
        if not self.use_browser:
            return False
        
        try:
            browser = await self._get_browser()
            return await browser.follow_user(user_id)
        except Exception as e:
            logger.error("Follow failed", user_id=user_id, error=str(e))
            return False

    async def unfollow_user(self, user_id: str) -> bool:
        """Unfollow a user using browser automation."""
        if not self.use_browser:
            return False
        
        try:
            browser = await self._get_browser()
            return await browser.unfollow_user(user_id)
        except Exception as e:
            logger.error("Unfollow failed", user_id=user_id, error=str(e))
            return False

    async def get_feed(
        self,
        hashtags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Post]:
        """Get feed posts, optionally filtered by hashtags."""
        posts = []
        
        if hashtags:
            for hashtag in hashtags:
                hashtag_posts = await self.search_hashtag(hashtag, limit=limit // len(hashtags))
                posts.extend(hashtag_posts)
        else:
            if self.use_browser:
                try:
                    browser = await self._get_browser()
                    posts = await browser.get_home_feed(limit)
                except Exception as e:
                    logger.error("Get feed failed", error=str(e))
        
        return posts[:limit]

    async def get_user_posts(self, user_id: str, limit: int = 20) -> List[Post]:
        """Get posts from a specific user."""
        # Try Graph API first for own account
        if self._graph_api and user_id == self.instagram_account_id:
            try:
                return await self._graph_api.get_media(limit)
            except Exception:
                pass
        
        # Use browser
        if self.use_browser:
            try:
                browser = await self._get_browser()
                return await browser.get_user_posts(user_id, limit)
            except Exception as e:
                logger.error("Get user posts failed", user_id=user_id, error=str(e))
        
        return []

    async def get_user_profile(self, username: str) -> Optional[UserProfile]:
        """Get a user's profile."""
        if self.use_browser:
            try:
                browser = await self._get_browser()
                return await browser.get_user_profile(username)
            except Exception as e:
                logger.error("Get profile failed", username=username, error=str(e))
        
        return None

    async def get_analytics(self) -> Analytics:
        """Get analytics for the authenticated account."""
        analytics = Analytics()
        
        # Try Graph API for account info (more reliable than insights)
        if self._graph_api:
            try:
                profile_info = await self._graph_api.get_account_info()
                analytics.follower_count = profile_info.get("followers_count", 0)
                analytics.following_count = profile_info.get("follows_count", 0)
                analytics.post_count = profile_info.get("media_count", 0)
                analytics.raw_data = profile_info
                logger.info(
                    "Got Instagram analytics from Graph API",
                    followers=analytics.follower_count,
                    following=analytics.following_count,
                )
            except Exception as e:
                logger.warning("Graph API profile info failed", error=str(e))
        
        # Supplement with browser data if Graph API didn't work
        if analytics.follower_count == 0 and self.use_browser and self.session_cookies:
            try:
                browser = await self._get_browser()
                profile = await browser.get_own_profile()
                if profile:
                    analytics.follower_count = profile.follower_count
                    analytics.following_count = profile.following_count
                    analytics.post_count = profile.post_count
                    logger.info(
                        "Got Instagram analytics from browser",
                        followers=analytics.follower_count,
                        following=analytics.following_count,
                    )
            except Exception as e:
                logger.warning("Browser profile fetch failed", error=str(e))
        
        return analytics

    async def search_hashtag(self, hashtag: str, limit: int = 20) -> List[Post]:
        """Search for posts by hashtag."""
        # Try Graph API hashtag search
        if self._graph_api:
            try:
                return await self._graph_api.search_hashtag(hashtag, limit)
            except Exception:
                pass
        
        # Use browser
        if self.use_browser:
            try:
                browser = await self._get_browser()
                return await browser.search_hashtag(hashtag, limit)
            except Exception as e:
                logger.error("Hashtag search failed", hashtag=hashtag, error=str(e))
        
        return []

    async def close(self):
        """Clean up resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None


