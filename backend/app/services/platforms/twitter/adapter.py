"""Twitter/X platform adapter implementation."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import hashlib
import structlog

from app.services.platforms.base import (
    PlatformAdapter,
    Post,
    PostResult,
    Analytics,
    UserProfile,
)
from app.services.platforms.twitter.api import TwitterAPI, TwitterAPIError
from app.services.platforms.twitter.browser import TwitterBrowser

logger = structlog.get_logger()

# Cache for successful authentications to avoid rate limits
# Key: hash of access_token, Value: (is_valid, timestamp)
_auth_cache: Dict[str, tuple[bool, datetime]] = {}
AUTH_CACHE_TTL = timedelta(minutes=10)  # Cache valid auth for 10 minutes


def _get_token_hash(access_token: str) -> str:
    """Get a hash of the access token for caching."""
    return hashlib.sha256(access_token.encode()).hexdigest()[:16]


def _is_cached_valid(access_token: str) -> Optional[bool]:
    """Check if we have a cached auth result that's still valid."""
    token_hash = _get_token_hash(access_token)
    if token_hash in _auth_cache:
        is_valid, cached_at = _auth_cache[token_hash]
        if datetime.utcnow() - cached_at < AUTH_CACHE_TTL:
            logger.info("Using cached auth result", is_valid=is_valid, age_seconds=(datetime.utcnow() - cached_at).seconds)
            return is_valid
    return None


def _cache_auth_result(access_token: str, is_valid: bool):
    """Cache an auth result."""
    token_hash = _get_token_hash(access_token)
    _auth_cache[token_hash] = (is_valid, datetime.utcnow())
    logger.info("Cached auth result", is_valid=is_valid)


class TwitterAdapter(PlatformAdapter):
    """Twitter/X platform adapter using Twitter API v2 with browser fallback."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None,
        bearer_token: Optional[str] = None,
        session_cookies: Optional[Dict[str, str]] = None,
    ):
        """Initialize Twitter adapter.
        
        Args:
            api_key: Twitter API Key (Consumer Key)
            api_secret: Twitter API Secret (Consumer Secret)
            access_token: OAuth 1.0a Access Token
            access_token_secret: OAuth 1.0a Access Token Secret
            bearer_token: OAuth 2.0 Bearer Token (optional)
            session_cookies: Browser session cookies for fallback automation
        """
        self._api: Optional[TwitterAPI] = None
        self._browser: Optional[TwitterBrowser] = None
        self._session_cookies = session_cookies
        # Use browser if we have cookies (avoids API rate limits on free tier)
        self._use_browser_for_engagement = session_cookies is not None and len(session_cookies) > 0
        # Track if the browser session was found to be invalid
        self._session_invalid = False
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.bearer_token = bearer_token
        
        # Initialize API if we have credentials
        if all([api_key, api_secret, access_token, access_token_secret]):
            self._api = TwitterAPI(
                api_key=api_key,
                api_secret=api_secret,
                access_token=access_token,
                access_token_secret=access_token_secret,
                bearer_token=bearer_token,
            )
        
        logger.info(
            "Twitter adapter initialized",
            has_api=self._api is not None,
            has_cookies=session_cookies is not None,
        )

    @property
    def platform_name(self) -> str:
        return "twitter"

    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with Twitter.
        
        Uses a cache to avoid hitting rate limits on repeated auth checks.
        
        Credentials should include:
        - api_key: Twitter API Key
        - api_secret: Twitter API Secret
        - access_token: OAuth 1.0a Access Token
        - access_token_secret: OAuth 1.0a Access Token Secret
        - bearer_token: (optional) OAuth 2.0 Bearer Token
        """
        try:
            required = ["api_key", "api_secret", "access_token", "access_token_secret"]
            if not all(key in credentials for key in required):
                logger.error("Missing required Twitter credentials")
                return False
            
            self.api_key = credentials["api_key"]
            self.api_secret = credentials["api_secret"]
            self.access_token = credentials["access_token"]
            self.access_token_secret = credentials["access_token_secret"]
            self.bearer_token = credentials.get("bearer_token")
            
            self._api = TwitterAPI(
                api_key=self.api_key,
                api_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
                bearer_token=self.bearer_token,
            )
            
            # Check if we have a cached auth result
            cached_result = _is_cached_valid(self.access_token)
            if cached_result is not None:
                return cached_result
            
            # Verify the credentials work
            try:
                if await self._api.verify_credentials():
                    logger.info("Twitter authentication successful")
                    _cache_auth_result(self.access_token, True)
                    return True
                else:
                    _cache_auth_result(self.access_token, False)
                    return False
            except TwitterAPIError as api_error:
                # If it's a rate limit error, assume auth is valid
                if api_error.status_code == 429:
                    logger.warning("Rate limited during auth verification, assuming valid")
                    _cache_auth_result(self.access_token, True)
                    return True
                raise
            except Exception as verify_error:
                # Check for rate limit in generic errors too
                error_str = str(verify_error).lower()
                if "429" in error_str or "rate" in error_str or "too many" in error_str:
                    logger.warning("Rate limited during auth verification, assuming valid")
                    _cache_auth_result(self.access_token, True)
                    return True
                raise
            
        except Exception as e:
            logger.error("Twitter authentication failed", error=str(e))
            return False

    async def verify_connection(self) -> bool:
        """Verify the connection is still valid."""
        if not self._api:
            return False
        return await self._api.verify_credentials()

    async def post_content(
        self,
        caption: str,
        media_paths: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
        **kwargs,
    ) -> PostResult:
        """Post a tweet.
        
        Args:
            caption: Tweet text (max 280 characters)
            media_paths: Paths to media files to upload (up to 4 images or 1 video)
            hashtags: Hashtags to include (will be appended to caption)
            **kwargs: Additional options:
                - reply_to: Tweet ID to reply to
                - quote_tweet_id: Tweet ID to quote
                - use_browser: Force browser posting (bypasses API rate limits)
        """
        # Build tweet text with hashtags
        tweet_text = caption
        if hashtags:
            hashtag_string = " ".join(f"#{tag}" for tag in hashtags)
            tweet_text = f"{caption} {hashtag_string}"
        
        # Check character limit
        if len(tweet_text) > 280:
            logger.warning(
                "Tweet exceeds 280 characters, truncating",
                length=len(tweet_text),
            )
            tweet_text = tweet_text[:277] + "..."
        
        # Determine if we should use browser for posting
        use_browser = kwargs.get("use_browser", False)
        
        # Try API first if available and not forcing browser
        if self._api and not use_browser:
            try:
                # Upload media if provided
                media_ids = None
                if media_paths:
                    media_ids = []
                    for path in media_paths[:4]:  # Twitter allows max 4 images
                        media_id = await self._api.upload_media(path)
                        if media_id:
                            media_ids.append(media_id)
                        else:
                            logger.warning("Failed to upload media", path=path)
                
                # Create tweet via API
                result = await self._api.create_tweet(
                    text=tweet_text,
                    media_ids=media_ids if media_ids else None,
                    reply_to=kwargs.get("reply_to"),
                    quote_tweet_id=kwargs.get("quote_tweet_id"),
                )
                
                # Check for rate limit error - if so, fall back to browser
                if not result.success and result.error_message and "Too Many Requests" in result.error_message:
                    logger.warning("API rate limited, falling back to browser posting")
                else:
                    return result
                    
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "rate" in error_str or "too many" in error_str:
                    logger.warning("API rate limited, falling back to browser posting")
                else:
                    logger.error("API posting failed", error=str(e))
                    return PostResult(success=False, error_message=str(e))
        
        # Browser fallback for posting
        if self._session_cookies:
            if await self._ensure_browser():
                logger.info("Attempting to post via browser automation")
                
                # For browser posting, we need a local file path for media
                # If media_paths contains URLs, we need to download them first
                local_media_path = None
                if media_paths:
                    first_media = media_paths[0]
                    if first_media.startswith(("http://", "https://")):
                        # Download the media to a temp file
                        import tempfile
                        import httpx
                        try:
                            async with httpx.AsyncClient() as client:
                                response = await client.get(first_media, follow_redirects=True)
                                if response.status_code == 200:
                                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                                    temp_file.write(response.content)
                                    temp_file.close()
                                    local_media_path = temp_file.name
                                    logger.info("Downloaded media for browser posting", path=local_media_path)
                        except Exception as e:
                            logger.warning("Failed to download media for browser posting", error=str(e))
                    else:
                        local_media_path = first_media
                
                # Post via browser
                browser_result = await self._browser.post_tweet(
                    text=tweet_text,
                    media_path=local_media_path,
                )
                
                # Clean up temp file if we created one
                if local_media_path and media_paths and media_paths[0].startswith(("http://", "https://")):
                    try:
                        import os
                        os.unlink(local_media_path)
                    except:
                        pass
                
                if browser_result.get("success"):
                    logger.info("Tweet posted successfully via browser")
                    return PostResult(
                        success=True,
                        post_id=browser_result.get("tweet_id"),
                        url=browser_result.get("url"),
                    )
                else:
                    error_msg = browser_result.get("error", "Browser posting failed")
                    logger.error("Browser posting failed", error=error_msg)
                    return PostResult(success=False, error_message=error_msg)
            else:
                logger.warning("Browser session not available for posting")
        
        # If we get here, neither API nor browser worked
        if not self._api:
            return PostResult(success=False, error_message="Not authenticated and no browser session")
        
        return PostResult(success=False, error_message="API rate limited and browser fallback unavailable")

    async def _ensure_browser(self) -> bool:
        """Initialize browser with session cookies if available."""
        if self._browser is None and self._session_cookies:
            self._browser = TwitterBrowser()
            await self._browser.load_cookies(self._session_cookies)
            if await self._browser.verify_session():
                logger.info("Twitter browser session verified")
                return True
            else:
                logger.warning("Twitter browser session invalid")
                self._session_invalid = True  # Mark session as invalid for caller
                return False
        return self._browser is not None and self._browser._logged_in
    
    @property
    def session_needs_refresh(self) -> bool:
        """Check if the browser session was found to be invalid and needs refreshing."""
        return self._session_invalid

    async def like_post(self, post_id: str, author_username: str = None) -> bool:
        """Like a tweet. Falls back to browser automation if API fails.
        
        Args:
            post_id: Tweet ID to like
            author_username: Optional author username for browser fallback
        """
        # Try API first if not disabled
        if self._api and not self._use_browser_for_engagement:
            try:
                result = await self._api.like_tweet(post_id)
                if result:
                    return True
                # API failed, maybe tier restriction - try browser
                logger.info("API like failed, trying browser fallback")
            except Exception as e:
                logger.warning("API like error, trying browser fallback", error=str(e))
        
        # Browser fallback
        if self._session_cookies:
            if await self._ensure_browser():
                result = await self._browser.like_tweet_by_id(post_id, author_username)
                if result:
                    self._use_browser_for_engagement = True  # Remember to use browser
                    logger.info("Like successful via browser")
                return result
            else:
                logger.warning("Browser session not available for like")
        
        return False

    async def unlike_post(self, post_id: str) -> bool:
        """Unlike a tweet."""
        if not self._api:
            return False
        return await self._api.unlike_tweet(post_id)

    async def comment(self, post_id: str, text: str, author_username: str = None) -> Optional[str]:
        """Reply to a tweet. Falls back to browser if API is rate limited.
        
        Args:
            post_id: Tweet ID to reply to
            text: Reply text
            author_username: Optional author username for browser fallback
            
        Returns:
            Reply tweet ID if successful
        """
        # Try API first if not using browser for engagement
        if self._api and not self._use_browser_for_engagement:
            try:
                result = await self._api.create_tweet(text=text, reply_to=post_id)
                if result.success:
                    return result.post_id
                
                # Check for rate limit error
                if result.error_message and "Too Many Requests" in result.error_message:
                    logger.warning("API rate limited for comment, trying browser fallback")
                else:
                    return None
                    
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "rate" in error_str or "too many" in error_str:
                    logger.warning("API rate limited for comment, trying browser fallback")
                else:
                    logger.error("API comment failed", error=str(e))
                    return None
        
        # Browser fallback for commenting/replying
        if self._session_cookies:
            if await self._ensure_browser():
                # Construct tweet URL for reply
                if author_username:
                    tweet_url = f"https://twitter.com/{author_username}/status/{post_id}"
                else:
                    tweet_url = f"https://twitter.com/i/status/{post_id}"
                
                logger.info("Replying via browser", tweet_url=tweet_url)
                browser_result = await self._browser.reply_to_tweet(tweet_url, text)
                
                if browser_result.get("success"):
                    self._use_browser_for_engagement = True  # Remember to use browser
                    logger.info("Reply posted successfully via browser")
                    return browser_result.get("tweet_id")
                else:
                    logger.warning("Browser reply failed", error=browser_result.get("error"))
        
        return None

    async def follow_user(self, user_id_or_username: str) -> bool:
        """Follow a user. Falls back to browser automation if API fails.
        
        Args:
            user_id_or_username: User ID (for API) or username (for browser)
        """
        # Try API first if not disabled
        if self._api and not self._use_browser_for_engagement:
            try:
                result = await self._api.follow_user(user_id_or_username)
                if result:
                    return True
                logger.info("API follow failed, trying browser fallback")
            except Exception as e:
                logger.warning("API follow error, trying browser fallback", error=str(e))
        
        # Browser fallback - needs username, not user ID
        if self._session_cookies:
            if await self._ensure_browser():
                # If it looks like a user ID (all digits), we can't use browser directly
                if user_id_or_username.isdigit():
                    logger.warning("Browser follow requires username, not user ID")
                    return False
                result = await self._browser.follow_user(user_id_or_username)
                if result:
                    self._use_browser_for_engagement = True
                    logger.info("Follow successful via browser")
                return result
        
        return False

    async def unfollow_user(self, user_id_or_username: str) -> bool:
        """Unfollow a user. Falls back to browser automation if API fails."""
        # Try API first
        if self._api and not self._use_browser_for_engagement:
            try:
                result = await self._api.unfollow_user(user_id_or_username)
                if result:
                    return True
            except Exception as e:
                logger.warning("API unfollow error, trying browser fallback", error=str(e))
        
        # Browser fallback
        if self._session_cookies:
            if await self._ensure_browser():
                if user_id_or_username.isdigit():
                    logger.warning("Browser unfollow requires username, not user ID")
                    return False
                return await self._browser.unfollow_user(user_id_or_username)
        
        return False

    async def get_feed(
        self,
        hashtags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Post]:
        """Get feed posts.
        
        If hashtags are provided, searches for those hashtags.
        Otherwise returns home timeline.
        """
        if not self._api:
            return []
        
        if hashtags:
            # Search for hashtags
            posts = []
            per_hashtag = max(limit // len(hashtags), 10)
            for hashtag in hashtags:
                hashtag_posts = await self.search_hashtag(hashtag, limit=per_hashtag)
                posts.extend(hashtag_posts)
            return posts[:limit]
        
        # Get home timeline
        return await self._api.get_home_timeline(limit)

    async def get_user_posts(self, user_id: str, limit: int = 20) -> List[Post]:
        """Get tweets from a specific user."""
        if not self._api:
            return []
        return await self._api.get_user_tweets(user_id, limit)

    async def get_user_profile(self, username: str) -> Optional[UserProfile]:
        """Get a user's profile by username."""
        if not self._api:
            return None
        return await self._api.get_user_by_username(username)

    async def get_analytics(self) -> Analytics:
        """Get analytics for the authenticated account.
        
        Uses API first, falls back to browser scraping if API is rate limited.
        """
        analytics = Analytics()
        api_success = False
        
        # Try API first
        if self._api:
            try:
                # Get own profile
                profile = await self._api.get_me()
                if profile:
                    analytics.follower_count = profile.follower_count
                    analytics.following_count = profile.following_count
                    analytics.post_count = profile.post_count
                    api_success = True
                
                # Get recent posts for engagement metrics
                if self._api._user_id:
                    recent_posts = await self._api.get_user_tweets(
                        self._api._user_id,
                        limit=20,
                    )
                    analytics.recent_posts = recent_posts
                    
                    if recent_posts:
                        total_likes = sum(p.like_count for p in recent_posts)
                        total_comments = sum(p.comment_count for p in recent_posts)
                        analytics.avg_likes = total_likes / len(recent_posts)
                        analytics.avg_comments = total_comments / len(recent_posts)
                        
                        # Calculate engagement rate
                        if analytics.follower_count > 0:
                            total_engagement = total_likes + total_comments
                            analytics.engagement_rate = (
                                total_engagement / (len(recent_posts) * analytics.follower_count)
                            ) * 100
                
            except Exception as e:
                logger.warning("API analytics failed, will try browser fallback", error=str(e))
        
        # Fall back to browser if API didn't get profile stats
        if not api_success and self._use_browser_for_engagement and self._session_cookies:
            try:
                if await self._ensure_browser():
                    profile_stats = await self._browser.get_own_profile()
                    if profile_stats:
                        analytics.follower_count = profile_stats.get("follower_count", 0)
                        analytics.following_count = profile_stats.get("following_count", 0)
                        analytics.post_count = profile_stats.get("post_count", 0)
                        logger.info(
                            "Got Twitter analytics via browser fallback",
                            followers=analytics.follower_count,
                            following=analytics.following_count,
                        )
            except Exception as e:
                logger.error("Browser analytics fallback failed", error=str(e))
        
        return analytics

    async def search_hashtag(self, hashtag: str, limit: int = 20) -> List[Post]:
        """Search for tweets by hashtag. Uses browser if API fails or cookies available."""
        # Ensure hashtag has # prefix for search
        query = f"#{hashtag}" if not hashtag.startswith("#") else hashtag
        
        # Prefer browser search if we have cookies (avoids API rate limits)
        if self._session_cookies and self._use_browser_for_engagement:
            if await self._ensure_browser():
                logger.info("Using browser for hashtag search", hashtag=hashtag)
                browser_results = await self._browser.search_tweets(query, limit)
                # Convert browser results to Post objects
                posts = []
                for result in browser_results:
                    posts.append(Post(
                        id=result.get('id', ''),
                        content=result.get('text', ''),
                        url=result.get('url', ''),
                        author_id=None,
                        author_username=result.get('author_username', ''),
                    ))
                return posts
        
        # Try API if available
        if self._api:
            try:
                return await self._api.search_tweets(query, limit)
            except Exception as e:
                logger.warning("API search failed, trying browser fallback", error=str(e))
                # Fall through to browser
        
        # Browser fallback
        if self._session_cookies:
            if await self._ensure_browser():
                logger.info("Using browser fallback for hashtag search", hashtag=hashtag)
                browser_results = await self._browser.search_tweets(query, limit)
                posts = []
                for result in browser_results:
                    posts.append(Post(
                        id=result.get('id', ''),
                        content=result.get('text', ''),
                        url=result.get('url', ''),
                        author_id=None,
                        author_username=result.get('author_username', ''),
                    ))
                return posts
        
        return []

    async def get_post(self, post_id: str) -> Optional[Post]:
        """Get a specific tweet by ID."""
        if not self._api:
            return None
        
        # Search for the specific tweet
        # Note: Twitter API v2 has a dedicated endpoint for this
        # For now, we'll use search as a workaround
        # In production, implement proper get tweet by ID
        return None

    async def delete_post(self, post_id: str) -> bool:
        """Delete a tweet."""
        if not self._api:
            return False
        return await self._api.delete_tweet(post_id)

    async def retweet(self, tweet_id: str) -> bool:
        """Retweet a tweet (Twitter-specific method)."""
        if not self._api:
            return False
        return await self._api.retweet(tweet_id)

    async def unretweet(self, tweet_id: str) -> bool:
        """Remove a retweet (Twitter-specific method)."""
        if not self._api:
            return False
        return await self._api.unretweet(tweet_id)

    async def quote_tweet(
        self,
        tweet_id: str,
        text: str,
        hashtags: Optional[List[str]] = None,
    ) -> PostResult:
        """Quote tweet (Twitter-specific method).
        
        Args:
            tweet_id: Tweet ID to quote
            text: Quote text
            hashtags: Optional hashtags
            
        Returns:
            PostResult
        """
        if not self._api:
            return PostResult(success=False, error_message="Not authenticated")
        
        # Build text with hashtags
        tweet_text = text
        if hashtags:
            hashtag_string = " ".join(f"#{tag}" for tag in hashtags)
            tweet_text = f"{text} {hashtag_string}"
        
        return await self._api.create_tweet(
            text=tweet_text,
            quote_tweet_id=tweet_id,
        )

    async def close(self):
        """Clean up resources."""
        if self._api:
            await self._api.close()
            self._api = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None

