"""Twitter API v2 client wrapper."""

import os
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx
import structlog

from app.services.platforms.base import Post, PostResult, UserProfile

logger = structlog.get_logger()

# Twitter API v2 endpoints
BASE_URL = "https://api.twitter.com/2"


class TwitterAPIError(Exception):
    """Twitter API error."""
    
    def __init__(self, message: str, status_code: int = None, response: Dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class TwitterAPI:
    """Twitter API v2 client.
    
    Uses OAuth 2.0 Bearer Token for read operations and
    OAuth 1.0a User Context for write operations.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
        bearer_token: Optional[str] = None,
    ):
        """Initialize Twitter API client.
        
        Args:
            api_key: Twitter API Key (Consumer Key)
            api_secret: Twitter API Secret (Consumer Secret)
            access_token: OAuth 1.0a Access Token
            access_token_secret: OAuth 1.0a Access Token Secret
            bearer_token: OAuth 2.0 Bearer Token (optional, for read-only ops)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.access_token_secret = access_token_secret
        self.bearer_token = bearer_token
        
        self._client: Optional[httpx.AsyncClient] = None
        self._user_id: Optional[str] = None
        self._username: Optional[str] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    def _get_oauth1_header(self, method: str, url: str, params: Dict = None) -> Dict[str, str]:
        """Generate OAuth 1.0a authorization header.
        
        This is a simplified version - in production, use a proper OAuth library.
        For now, we'll use httpx-oauth or implement proper OAuth 1.0a signing.
        """
        import time
        import uuid
        import hmac
        import hashlib
        import base64
        from urllib.parse import quote, urlencode
        
        oauth_params = {
            "oauth_consumer_key": self.api_key,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self.access_token,
            "oauth_version": "1.0",
        }
        
        # Combine all parameters for signature base
        all_params = {**oauth_params}
        if params:
            all_params.update(params)
        
        # Sort and encode parameters
        sorted_params = sorted(all_params.items())
        param_string = urlencode(sorted_params, quote_via=quote)
        
        # Create signature base string
        base_string = f"{method.upper()}&{quote(url, safe='')}&{quote(param_string, safe='')}"
        
        # Create signing key
        signing_key = f"{quote(self.api_secret, safe='')}&{quote(self.access_token_secret, safe='')}"
        
        # Generate signature
        signature = base64.b64encode(
            hmac.new(
                signing_key.encode(),
                base_string.encode(),
                hashlib.sha1
            ).digest()
        ).decode()
        
        oauth_params["oauth_signature"] = signature
        
        # Build Authorization header
        auth_header = "OAuth " + ", ".join(
            f'{quote(k, safe="")}="{quote(v, safe="")}"'
            for k, v in sorted(oauth_params.items())
        )
        
        return {"Authorization": auth_header}

    def _get_bearer_header(self) -> Dict[str, str]:
        """Get Bearer token authorization header."""
        return {"Authorization": f"Bearer {self.bearer_token}"}

    async def verify_credentials(self) -> bool:
        """Verify the API credentials are valid.
        
        Returns:
            True if credentials are valid
            
        Raises:
            TwitterAPIError: If rate limited (429) - caller should treat as valid
        """
        try:
            client = await self._get_client()
            url = f"{BASE_URL}/users/me"
            
            headers = self._get_oauth1_header("GET", url)
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                self._user_id = data["data"]["id"]
                self._username = data["data"]["username"]
                logger.info(
                    "Twitter credentials verified",
                    user_id=self._user_id,
                    username=self._username,
                )
                return True
            
            # Handle rate limit specially - raise so caller can decide
            if response.status_code == 429:
                logger.warning("Rate limited during credential verification")
                raise TwitterAPIError("Rate limited", status_code=429, response=response.json())
            
            logger.error(
                "Twitter credential verification failed",
                status_code=response.status_code,
                response=response.text,
            )
            return False
            
        except TwitterAPIError:
            raise  # Re-raise rate limit errors
        except Exception as e:
            logger.error("Twitter credential verification error", error=str(e))
            return False

    async def get_me(self) -> Optional[UserProfile]:
        """Get the authenticated user's profile.
        
        Returns:
            UserProfile for the authenticated user
        """
        try:
            client = await self._get_client()
            url = f"{BASE_URL}/users/me"
            params = {
                "user.fields": "id,name,username,description,profile_image_url,public_metrics,verified"
            }
            
            headers = self._get_oauth1_header("GET", url, params)
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()["data"]
                metrics = data.get("public_metrics", {})
                
                return UserProfile(
                    id=data["id"],
                    username=data["username"],
                    display_name=data.get("name"),
                    bio=data.get("description"),
                    profile_picture_url=data.get("profile_image_url"),
                    follower_count=metrics.get("followers_count", 0),
                    following_count=metrics.get("following_count", 0),
                    post_count=metrics.get("tweet_count", 0),
                    is_verified=data.get("verified", False),
                    is_private=False,  # Twitter doesn't have private in this endpoint
                )
            
            return None
            
        except Exception as e:
            logger.error("Get me failed", error=str(e))
            return None

    async def create_tweet(
        self,
        text: str,
        media_ids: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        quote_tweet_id: Optional[str] = None,
    ) -> PostResult:
        """Create a new tweet.
        
        Args:
            text: Tweet text (up to 280 characters)
            media_ids: List of media IDs to attach
            reply_to: Tweet ID to reply to
            quote_tweet_id: Tweet ID to quote
            
        Returns:
            PostResult with success status
        """
        try:
            client = await self._get_client()
            url = f"{BASE_URL}/tweets"
            
            payload: Dict[str, Any] = {"text": text}
            
            if media_ids:
                payload["media"] = {"media_ids": media_ids}
            
            if reply_to:
                payload["reply"] = {"in_reply_to_tweet_id": reply_to}
            
            if quote_tweet_id:
                payload["quote_tweet_id"] = quote_tweet_id
            
            headers = self._get_oauth1_header("POST", url)
            headers["Content-Type"] = "application/json"
            
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code in (200, 201):
                data = response.json()["data"]
                tweet_id = data["id"]
                
                return PostResult(
                    success=True,
                    post_id=tweet_id,
                    url=f"https://twitter.com/i/status/{tweet_id}",
                    raw_response=data,
                )
            
            error_data = response.json()
            return PostResult(
                success=False,
                error_message=error_data.get("detail", str(error_data)),
                raw_response=error_data,
            )
            
        except Exception as e:
            logger.error("Create tweet failed", error=str(e))
            return PostResult(success=False, error_message=str(e))

    async def upload_media(self, file_path_or_url: str) -> Optional[str]:
        """Upload media to Twitter using tweepy for proper OAuth 1.0a.
        
        Note: Media upload uses v1.1 API endpoint with tweepy.
        
        Args:
            file_path_or_url: Path to the media file OR a URL to download from
            
        Returns:
            Media ID if successful
        """
        import tempfile
        import tweepy
        
        temp_file_path = None
        try:
            # Check if it's a URL or local file
            if file_path_or_url.startswith(("http://", "https://")):
                # Download the image from URL
                logger.info("Downloading media from URL", url=file_path_or_url[:100])
                client = await self._get_client()
                response = await client.get(file_path_or_url, follow_redirects=True)
                
                if response.status_code != 200:
                    logger.error(
                        "Failed to download media from URL",
                        url=file_path_or_url[:100],
                        status_code=response.status_code,
                    )
                    return None
                
                # Save to temp file
                import os
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                temp_file.write(response.content)
                temp_file.close()
                temp_file_path = temp_file.name
                logger.info("Downloaded media", size=len(response.content), path=temp_file_path)
            else:
                temp_file_path = file_path_or_url
            
            # Use tweepy's v1.1 API for media upload (handles OAuth 1.0a properly)
            auth = tweepy.OAuth1UserHandler(
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_token_secret,
            )
            api = tweepy.API(auth)
            
            # Upload media using tweepy
            media = api.media_upload(filename=temp_file_path)
            media_id = str(media.media_id)
            
            logger.info("Media uploaded successfully via tweepy", media_id=media_id)
            return media_id
            
        except tweepy.TweepyException as e:
            logger.error("Tweepy media upload failed", error=str(e))
            return None
        except Exception as e:
            logger.error("Media upload error", error=str(e))
            return None
        finally:
            # Clean up temp file if we created one
            if temp_file_path and file_path_or_url.startswith(("http://", "https://")):
                try:
                    import os
                    os.unlink(temp_file_path)
                except:
                    pass

    async def delete_tweet(self, tweet_id: str) -> bool:
        """Delete a tweet.
        
        Args:
            tweet_id: ID of the tweet to delete
            
        Returns:
            True if successful
        """
        try:
            client = await self._get_client()
            url = f"{BASE_URL}/tweets/{tweet_id}"
            
            headers = self._get_oauth1_header("DELETE", url)
            response = await client.delete(url, headers=headers)
            
            return response.status_code in (200, 204)
            
        except Exception as e:
            logger.error("Delete tweet failed", tweet_id=tweet_id, error=str(e))
            return False

    async def like_tweet(self, tweet_id: str) -> bool:
        """Like a tweet.
        
        Args:
            tweet_id: ID of the tweet to like
            
        Returns:
            True if successful
        """
        try:
            if not self._user_id:
                await self.verify_credentials()
            
            client = await self._get_client()
            url = f"{BASE_URL}/users/{self._user_id}/likes"
            
            headers = self._get_oauth1_header("POST", url)
            headers["Content-Type"] = "application/json"
            
            response = await client.post(
                url,
                headers=headers,
                json={"tweet_id": tweet_id},
            )
            
            return response.status_code in (200, 201)
            
        except Exception as e:
            logger.error("Like tweet failed", tweet_id=tweet_id, error=str(e))
            return False

    async def unlike_tweet(self, tweet_id: str) -> bool:
        """Unlike a tweet.
        
        Args:
            tweet_id: ID of the tweet to unlike
            
        Returns:
            True if successful
        """
        try:
            if not self._user_id:
                await self.verify_credentials()
            
            client = await self._get_client()
            url = f"{BASE_URL}/users/{self._user_id}/likes/{tweet_id}"
            
            headers = self._get_oauth1_header("DELETE", url)
            response = await client.delete(url, headers=headers)
            
            return response.status_code in (200, 204)
            
        except Exception as e:
            logger.error("Unlike tweet failed", tweet_id=tweet_id, error=str(e))
            return False

    async def retweet(self, tweet_id: str) -> bool:
        """Retweet a tweet.
        
        Args:
            tweet_id: ID of the tweet to retweet
            
        Returns:
            True if successful
        """
        try:
            if not self._user_id:
                await self.verify_credentials()
            
            client = await self._get_client()
            url = f"{BASE_URL}/users/{self._user_id}/retweets"
            
            headers = self._get_oauth1_header("POST", url)
            headers["Content-Type"] = "application/json"
            
            response = await client.post(
                url,
                headers=headers,
                json={"tweet_id": tweet_id},
            )
            
            return response.status_code in (200, 201)
            
        except Exception as e:
            logger.error("Retweet failed", tweet_id=tweet_id, error=str(e))
            return False

    async def unretweet(self, tweet_id: str) -> bool:
        """Remove a retweet.
        
        Args:
            tweet_id: ID of the tweet to unretweet
            
        Returns:
            True if successful
        """
        try:
            if not self._user_id:
                await self.verify_credentials()
            
            client = await self._get_client()
            url = f"{BASE_URL}/users/{self._user_id}/retweets/{tweet_id}"
            
            headers = self._get_oauth1_header("DELETE", url)
            response = await client.delete(url, headers=headers)
            
            return response.status_code in (200, 204)
            
        except Exception as e:
            logger.error("Unretweet failed", tweet_id=tweet_id, error=str(e))
            return False

    async def follow_user(self, user_id: str) -> bool:
        """Follow a user.
        
        Args:
            user_id: ID of the user to follow
            
        Returns:
            True if successful
        """
        try:
            if not self._user_id:
                await self.verify_credentials()
            
            client = await self._get_client()
            url = f"{BASE_URL}/users/{self._user_id}/following"
            
            headers = self._get_oauth1_header("POST", url)
            headers["Content-Type"] = "application/json"
            
            response = await client.post(
                url,
                headers=headers,
                json={"target_user_id": user_id},
            )
            
            return response.status_code in (200, 201)
            
        except Exception as e:
            logger.error("Follow user failed", user_id=user_id, error=str(e))
            return False

    async def unfollow_user(self, user_id: str) -> bool:
        """Unfollow a user.
        
        Args:
            user_id: ID of the user to unfollow
            
        Returns:
            True if successful
        """
        try:
            if not self._user_id:
                await self.verify_credentials()
            
            client = await self._get_client()
            url = f"{BASE_URL}/users/{self._user_id}/following/{user_id}"
            
            headers = self._get_oauth1_header("DELETE", url)
            response = await client.delete(url, headers=headers)
            
            return response.status_code in (200, 204)
            
        except Exception as e:
            logger.error("Unfollow user failed", user_id=user_id, error=str(e))
            return False

    async def get_user_by_username(self, username: str) -> Optional[UserProfile]:
        """Get a user profile by username.
        
        Args:
            username: Twitter username (without @)
            
        Returns:
            UserProfile if found
        """
        try:
            client = await self._get_client()
            url = f"{BASE_URL}/users/by/username/{username}"
            params = {
                "user.fields": "id,name,username,description,profile_image_url,public_metrics,verified,protected"
            }
            
            # Use bearer token for read operations if available
            if self.bearer_token:
                headers = self._get_bearer_header()
            else:
                headers = self._get_oauth1_header("GET", url, params)
            
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()["data"]
                metrics = data.get("public_metrics", {})
                
                return UserProfile(
                    id=data["id"],
                    username=data["username"],
                    display_name=data.get("name"),
                    bio=data.get("description"),
                    profile_picture_url=data.get("profile_image_url"),
                    follower_count=metrics.get("followers_count", 0),
                    following_count=metrics.get("following_count", 0),
                    post_count=metrics.get("tweet_count", 0),
                    is_verified=data.get("verified", False),
                    is_private=data.get("protected", False),
                )
            
            return None
            
        except Exception as e:
            logger.error("Get user by username failed", username=username, error=str(e))
            return None

    async def get_user_tweets(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[Post]:
        """Get tweets from a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of tweets to return
            
        Returns:
            List of posts
        """
        try:
            client = await self._get_client()
            url = f"{BASE_URL}/users/{user_id}/tweets"
            params = {
                "max_results": min(limit, 100),
                "tweet.fields": "id,text,created_at,public_metrics,entities",
                "expansions": "author_id",
                "user.fields": "username",
            }
            
            if self.bearer_token:
                headers = self._get_bearer_header()
            else:
                headers = self._get_oauth1_header("GET", url, params)
            
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                tweets = data.get("data", [])
                
                # Get author info from includes
                users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                
                posts = []
                for tweet in tweets:
                    author = users.get(tweet.get("author_id"), {})
                    metrics = tweet.get("public_metrics", {})
                    entities = tweet.get("entities", {})
                    
                    # Extract hashtags
                    hashtags = [h["tag"] for h in entities.get("hashtags", [])]
                    
                    posts.append(Post(
                        id=tweet["id"],
                        author_id=tweet.get("author_id", user_id),
                        author_username=author.get("username", ""),
                        content=tweet["text"],
                        hashtags=hashtags,
                        like_count=metrics.get("like_count", 0),
                        comment_count=metrics.get("reply_count", 0),
                        created_at=datetime.fromisoformat(
                            tweet["created_at"].replace("Z", "+00:00")
                        ) if "created_at" in tweet else None,
                        url=f"https://twitter.com/i/status/{tweet['id']}",
                        raw_data=tweet,
                    ))
                
                return posts
            
            return []
            
        except Exception as e:
            logger.error("Get user tweets failed", user_id=user_id, error=str(e))
            return []

    async def search_tweets(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Post]:
        """Search for tweets.
        
        Args:
            query: Search query (can include hashtags)
            limit: Maximum number of tweets to return
            
        Returns:
            List of posts
        """
        try:
            client = await self._get_client()
            url = f"{BASE_URL}/tweets/search/recent"
            params = {
                "query": query,
                "max_results": min(max(limit, 10), 100),  # API requires 10-100
                "tweet.fields": "id,text,created_at,public_metrics,entities",
                "expansions": "author_id",
                "user.fields": "username",
            }
            
            if self.bearer_token:
                headers = self._get_bearer_header()
            else:
                headers = self._get_oauth1_header("GET", url, params)
            
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                tweets = data.get("data", [])
                
                users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                
                posts = []
                for tweet in tweets:
                    author = users.get(tweet.get("author_id"), {})
                    metrics = tweet.get("public_metrics", {})
                    entities = tweet.get("entities", {})
                    
                    hashtags = [h["tag"] for h in entities.get("hashtags", [])]
                    
                    posts.append(Post(
                        id=tweet["id"],
                        author_id=tweet.get("author_id", ""),
                        author_username=author.get("username", ""),
                        content=tweet["text"],
                        hashtags=hashtags,
                        like_count=metrics.get("like_count", 0),
                        comment_count=metrics.get("reply_count", 0),
                        created_at=datetime.fromisoformat(
                            tweet["created_at"].replace("Z", "+00:00")
                        ) if "created_at" in tweet else None,
                        url=f"https://twitter.com/i/status/{tweet['id']}",
                        raw_data=tweet,
                    ))
                
                return posts
            
            return []
            
        except Exception as e:
            logger.error("Search tweets failed", query=query, error=str(e))
            return []

    async def get_home_timeline(self, limit: int = 20) -> List[Post]:
        """Get the authenticated user's home timeline.
        
        Note: This requires elevated API access.
        
        Args:
            limit: Maximum number of tweets to return
            
        Returns:
            List of posts
        """
        try:
            if not self._user_id:
                await self.verify_credentials()
            
            client = await self._get_client()
            url = f"{BASE_URL}/users/{self._user_id}/timelines/reverse_chronological"
            params = {
                "max_results": min(max(limit, 10), 100),
                "tweet.fields": "id,text,created_at,public_metrics,entities",
                "expansions": "author_id",
                "user.fields": "username",
            }
            
            headers = self._get_oauth1_header("GET", url, params)
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                tweets = data.get("data", [])
                
                users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}
                
                posts = []
                for tweet in tweets:
                    author = users.get(tweet.get("author_id"), {})
                    metrics = tweet.get("public_metrics", {})
                    entities = tweet.get("entities", {})
                    
                    hashtags = [h["tag"] for h in entities.get("hashtags", [])]
                    
                    posts.append(Post(
                        id=tweet["id"],
                        author_id=tweet.get("author_id", ""),
                        author_username=author.get("username", ""),
                        content=tweet["text"],
                        hashtags=hashtags,
                        like_count=metrics.get("like_count", 0),
                        comment_count=metrics.get("reply_count", 0),
                        created_at=datetime.fromisoformat(
                            tweet["created_at"].replace("Z", "+00:00")
                        ) if "created_at" in tweet else None,
                        url=f"https://twitter.com/i/status/{tweet['id']}",
                        raw_data=tweet,
                    ))
                
                return posts
            
            logger.warning(
                "Get home timeline failed",
                status_code=response.status_code,
                response=response.text[:500],
            )
            return []
            
        except Exception as e:
            logger.error("Get home timeline failed", error=str(e))
            return []

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

