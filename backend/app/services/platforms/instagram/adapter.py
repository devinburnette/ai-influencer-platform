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
        
        Uses Graph API (requires business/creator account).
        """
        # Instagram REQUIRES an image - there's no text-only posting
        if not media_paths or len(media_paths) == 0:
            logger.error("Instagram requires an image for every post")
            return PostResult(
                success=False,
                error_message="Instagram requires an image for every post. Please attach an image URL to post to Instagram.",
            )
        
        # Combine caption with hashtags
        full_caption = caption
        if hashtags:
            hashtag_string = " ".join(f"#{tag}" for tag in hashtags)
            full_caption = f"{caption}\n\n{hashtag_string}"
        
        # Use Graph API (required for posting)
        if not self._graph_api:
            logger.error("Instagram Graph API not configured")
            return PostResult(
                success=False,
                error_message="Instagram Graph API not configured. Please check your access token and account ID.",
            )
        
        try:
            # media_paths should contain publicly accessible URLs
            media_url = media_paths[0]
            
            # Validate that it looks like a URL
            if not media_url.startswith("http"):
                return PostResult(
                    success=False,
                    error_message=f"Invalid image URL: {media_url}. Instagram requires a publicly accessible image URL (must start with http:// or https://).",
                )
            
            result = await self._graph_api.create_media_post(
                media_url,
                full_caption,
            )
            
            if result.success:
                logger.info("Instagram post created successfully", post_id=result.post_id)
            else:
                logger.error("Instagram Graph API posting failed", error=result.error_message)
            
            return result
            
        except Exception as e:
            logger.error("Instagram posting failed", error=str(e))
            return PostResult(success=False, error_message=f"Instagram posting failed: {str(e)}")

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

    async def comment(self, post_id: str, text: str) -> Optional[str]:
        """Comment on a post.
        
        Uses Graph API for own posts, browser for others.
        """
        # Try Graph API for commenting on own posts
        if self._graph_api:
            try:
                comment_id = await self._graph_api.create_comment(post_id, text)
                if comment_id:
                    return comment_id
            except Exception:
                pass
        
        # Use browser automation
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
        
        # Try Graph API for business insights
        if self._graph_api:
            try:
                insights = await self._graph_api.get_insights()
                analytics.follower_count = insights.get("followers_count", 0)
                analytics.engagement_rate = insights.get("engagement_rate", 0)
                analytics.raw_data = insights
            except Exception:
                pass
        
        # Supplement with browser data
        if self.use_browser and self.session_cookies:
            try:
                browser = await self._get_browser()
                profile = await browser.get_own_profile()
                if profile:
                    analytics.follower_count = profile.follower_count
                    analytics.following_count = profile.following_count
                    analytics.post_count = profile.post_count
            except Exception:
                pass
        
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


