"""Instagram Graph API client for business accounts."""

from typing import List, Optional, Dict, Any
import structlog
import httpx

from app.config import get_settings
from app.services.platforms.base import Post, PostResult

logger = structlog.get_logger()
settings = get_settings()

# Use configurable Graph API version
BASE_URL = f"https://graph.facebook.com/{settings.meta_graph_api_version}"


class InstagramGraphAPI:
    """Instagram Graph API client for business/creator accounts."""

    def __init__(self, access_token: str, instagram_account_id: str):
        """Initialize Graph API client.
        
        Args:
            access_token: Meta Graph API access token
            instagram_account_id: Instagram Business/Creator Account ID
        """
        self.access_token = access_token
        self.instagram_account_id = instagram_account_id
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                params={"access_token": self.access_token},
                timeout=30.0,
            )
        return self._client

    async def verify_token(self) -> bool:
        """Verify the access token is valid."""
        try:
            response = await self.client.get(
                f"/{self.instagram_account_id}",
                params={"fields": "id,username"},
            )
            return response.status_code == 200
        except Exception as e:
            logger.error("Token verification failed", error=str(e))
            return False

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        response = await self.client.get(
            f"/{self.instagram_account_id}",
            params={
                "fields": "id,username,name,biography,followers_count,"
                "follows_count,media_count,profile_picture_url"
            },
        )
        response.raise_for_status()
        return response.json()

    async def get_media(self, limit: int = 20) -> List[Post]:
        """Get recent media posts."""
        response = await self.client.get(
            f"/{self.instagram_account_id}/media",
            params={
                "fields": "id,caption,media_type,media_url,permalink,"
                "timestamp,like_count,comments_count",
                "limit": limit,
            },
        )
        response.raise_for_status()
        data = response.json()
        
        posts = []
        for item in data.get("data", []):
            posts.append(Post(
                id=item["id"],
                author_id=self.instagram_account_id,
                author_username="",  # Not included in this endpoint
                content=item.get("caption", ""),
                media_urls=[item.get("media_url")] if item.get("media_url") else [],
                like_count=item.get("like_count", 0),
                comment_count=item.get("comments_count", 0),
                url=item.get("permalink"),
                raw_data=item,
            ))
        
        return posts

    async def _wait_for_container_ready(
        self,
        container_id: str,
        max_attempts: int = 30,
        poll_interval: float = 2.0,
    ) -> bool:
        """Wait for media container to be ready for publishing.
        
        Instagram processes images asynchronously. We need to poll the container
        status until it's ready (status_code = FINISHED).
        
        Args:
            container_id: The media container ID
            max_attempts: Maximum number of polling attempts
            poll_interval: Seconds between polls
            
        Returns:
            True if container is ready, False otherwise
        """
        import asyncio
        
        for attempt in range(max_attempts):
            try:
                response = await self.client.get(
                    f"/{container_id}",
                    params={"fields": "status_code,status"},
                )
                
                if response.status_code == 200:
                    data = response.json()
                    status_code = data.get("status_code")
                    status = data.get("status")
                    
                    logger.info(
                        "Container status check",
                        container_id=container_id,
                        status_code=status_code,
                        status=status,
                        attempt=attempt + 1,
                    )
                    
                    if status_code == "FINISHED":
                        return True
                    elif status_code == "ERROR":
                        logger.error("Container processing failed", status=status)
                        return False
                    elif status_code == "EXPIRED":
                        logger.error("Container expired")
                        return False
                    # IN_PROGRESS - keep polling
                    
                await asyncio.sleep(poll_interval)
                
            except Exception as e:
                logger.warning("Container status check failed", error=str(e))
                await asyncio.sleep(poll_interval)
        
        logger.error("Container not ready after max attempts", container_id=container_id)
        return False

    async def create_media_post(
        self,
        media_url: str,
        caption: str,
        is_carousel: bool = False,
        is_video: bool = False,
        content_type: Optional[Any] = None,
    ) -> PostResult:
        """Create a media post using Graph API.
        
        Note: Media must be hosted on a public URL accessible by Facebook.
        
        Args:
            media_url: Public URL of the image/video
            caption: Post caption
            is_carousel: Whether this is a carousel post
            is_video: Whether the media is a video
            content_type: ContentType enum (REEL, STORY, POST, etc.)
            
        Returns:
            PostResult with post ID and status
        """
        try:
            # Build the request data based on media type
            data = {"caption": caption}
            
            # Import ContentType here to check content type
            from app.models.content import ContentType
            
            if is_video:
                data["video_url"] = media_url
                # Determine the media type based on content_type
                if content_type == ContentType.STORY:
                    data["media_type"] = "STORIES"
                    logger.info("Creating STORY container", video_url=media_url[:100])
                elif content_type == ContentType.REEL:
                    data["media_type"] = "REELS"
                    logger.info("Creating REEL container", video_url=media_url[:100])
                else:
                    # Regular video post - use REELS format (Instagram requires this for feed videos)
                    data["media_type"] = "REELS"
                    logger.info("Creating video post as REEL", video_url=media_url[:100])
            else:
                data["image_url"] = media_url
                # Check if this is an image story
                if content_type == ContentType.STORY:
                    data["media_type"] = "STORIES"
                    logger.info("Creating image STORY container", image_url=media_url[:100])
                else:
                    logger.info("Creating image container", image_url=media_url[:100])
            
            # Step 1: Create media container
            container_response = await self.client.post(
                f"/{self.instagram_account_id}/media",
                data=data,
            )
            
            # Check for errors in container creation
            if container_response.status_code != 200:
                error_data = container_response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
                logger.error("Container creation failed", status=container_response.status_code, error=error_msg)
                return PostResult(
                    success=False,
                    error_message=f"Failed to create media container: {error_msg}",
                    raw_response=error_data,
                )
            
            container_data = container_response.json()
            container_id = container_data.get("id")
            
            if not container_id:
                logger.error("No container ID in response", response=container_data)
                return PostResult(
                    success=False,
                    error_message="No container ID returned from Instagram",
                    raw_response=container_data,
                )
            
            logger.info("Media container created", container_id=container_id)
            
            # Step 2: Wait for container to be ready
            # Videos take longer to process - use more attempts
            if is_video:
                max_attempts = 90  # 3 minutes for video processing
                poll_interval = 2.0
            else:
                max_attempts = 30  # 1 minute for images
                poll_interval = 2.0
            
            is_ready = await self._wait_for_container_ready(
                container_id, 
                max_attempts=max_attempts,
                poll_interval=poll_interval
            )
            if not is_ready:
                return PostResult(
                    success=False,
                    error_message="Media container not ready for publishing (processing failed or timed out)",
                )
            
            # Step 3: Publish the media
            publish_response = await self.client.post(
                f"/{self.instagram_account_id}/media_publish",
                data={"creation_id": container_id},
            )
            
            if publish_response.status_code != 200:
                error_data = publish_response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown error")
                logger.error("Publish failed", error=error_msg)
                return PostResult(
                    success=False,
                    error_message=f"Failed to publish: {error_msg}",
                    raw_response=error_data,
                )
            
            publish_data = publish_response.json()
            post_id = publish_data.get("id")
            
            if not post_id:
                logger.error("No post ID in publish response", response=publish_data)
                return PostResult(
                    success=False,
                    error_message="No post ID returned from Instagram",
                    raw_response=publish_data,
                )
            
            logger.info("Media published", post_id=post_id)
            
            return PostResult(
                success=True,
                post_id=post_id,
                url=f"https://www.instagram.com/p/{post_id}/",
                raw_response=publish_data,
            )
            
        except httpx.HTTPStatusError as e:
            error_data = e.response.json() if e.response else {}
            error_msg = error_data.get("error", {}).get("message", str(e))
            logger.error("Graph API posting failed", error=error_msg)
            return PostResult(
                success=False,
                error_message=error_msg,
                raw_response=error_data,
            )
        except Exception as e:
            logger.error("Posting failed", error=str(e))
            return PostResult(success=False, error_message=str(e))

    async def create_comment(self, media_id: str, text: str) -> Optional[str]:
        """Create a comment on a media post.
        
        Note: Can only comment on own posts via Graph API.
        """
        try:
            response = await self.client.post(
                f"/{media_id}/comments",
                data={"message": text},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("id")
        except Exception as e:
            logger.error("Comment creation failed", error=str(e))
            return None

    async def get_insights(self) -> Dict[str, Any]:
        """Get account insights (business/creator accounts only)."""
        try:
            response = await self.client.get(
                f"/{self.instagram_account_id}/insights",
                params={
                    "metric": "impressions,reach,profile_views,follower_count",
                    "period": "day",
                },
            )
            response.raise_for_status()
            data = response.json()
            
            insights = {}
            for item in data.get("data", []):
                name = item["name"]
                values = item.get("values", [])
                if values:
                    insights[name] = values[0].get("value", 0)
            
            return insights
        except Exception as e:
            logger.error("Insights fetch failed", error=str(e))
            return {}

    async def search_hashtag(self, hashtag: str, limit: int = 20) -> List[Post]:
        """Search for posts by hashtag.
        
        Note: Requires special approval from Meta for hashtag search API.
        """
        try:
            # First, get hashtag ID
            hashtag_response = await self.client.get(
                "/ig_hashtag_search",
                params={"user_id": self.instagram_account_id, "q": hashtag},
            )
            hashtag_response.raise_for_status()
            hashtag_data = hashtag_response.json()
            
            if not hashtag_data.get("data"):
                return []
            
            hashtag_id = hashtag_data["data"][0]["id"]
            
            # Then get recent media
            media_response = await self.client.get(
                f"/{hashtag_id}/recent_media",
                params={
                    "user_id": self.instagram_account_id,
                    "fields": "id,caption,media_type,permalink,like_count,comments_count",
                    "limit": limit,
                },
            )
            media_response.raise_for_status()
            media_data = media_response.json()
            
            posts = []
            for item in media_data.get("data", []):
                posts.append(Post(
                    id=item["id"],
                    author_id="",
                    author_username="",
                    content=item.get("caption", ""),
                    like_count=item.get("like_count", 0),
                    comment_count=item.get("comments_count", 0),
                    url=item.get("permalink"),
                    raw_data=item,
                ))
            
            return posts
            
        except Exception as e:
            logger.error("Hashtag search failed", hashtag=hashtag, error=str(e))
            return []

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None



