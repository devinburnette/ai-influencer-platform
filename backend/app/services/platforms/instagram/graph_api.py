"""Instagram Graph API client for business accounts."""

from typing import List, Optional, Dict, Any
import structlog
import httpx

from app.services.platforms.base import Post, PostResult

logger = structlog.get_logger()

BASE_URL = "https://graph.facebook.com/v18.0"


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

    async def create_media_post(
        self,
        media_url: str,
        caption: str,
        is_carousel: bool = False,
    ) -> PostResult:
        """Create a media post using Graph API.
        
        Note: Media must be hosted on a public URL accessible by Facebook.
        
        Args:
            media_url: Public URL of the image/video
            caption: Post caption
            is_carousel: Whether this is a carousel post
            
        Returns:
            PostResult with post ID and status
        """
        try:
            # Step 1: Create media container
            container_response = await self.client.post(
                f"/{self.instagram_account_id}/media",
                data={
                    "image_url": media_url,
                    "caption": caption,
                },
            )
            container_response.raise_for_status()
            container_data = container_response.json()
            container_id = container_data["id"]
            
            logger.info("Media container created", container_id=container_id)
            
            # Step 2: Publish the media
            publish_response = await self.client.post(
                f"/{self.instagram_account_id}/media_publish",
                data={"creation_id": container_id},
            )
            publish_response.raise_for_status()
            publish_data = publish_response.json()
            
            post_id = publish_data["id"]
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


