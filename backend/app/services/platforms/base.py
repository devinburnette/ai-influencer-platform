"""Abstract base class for platform adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class Post:
    """Represents a social media post."""
    id: str
    author_id: str
    author_username: str
    content: str
    media_urls: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    like_count: int = 0
    comment_count: int = 0
    created_at: Optional[datetime] = None
    url: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class PostResult:
    """Result from posting content."""
    success: bool
    post_id: Optional[str] = None
    url: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class Analytics:
    """Analytics data for an account."""
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    engagement_rate: float = 0.0
    avg_likes: float = 0.0
    avg_comments: float = 0.0
    recent_posts: List[Post] = field(default_factory=list)
    raw_data: Optional[Dict[str, Any]] = None


@dataclass
class UserProfile:
    """User profile information."""
    id: str
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    is_verified: bool = False
    is_private: bool = False


class PlatformAdapter(ABC):
    """Abstract base class for social media platform adapters."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Get the platform name."""
        pass

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """Authenticate with the platform.
        
        Args:
            credentials: Authentication credentials (tokens, cookies, etc.)
            
        Returns:
            True if authentication successful
        """
        pass

    @abstractmethod
    async def verify_connection(self) -> bool:
        """Verify the connection is still valid.
        
        Returns:
            True if connected and authenticated
        """
        pass

    @abstractmethod
    async def post_content(
        self,
        caption: str,
        media_paths: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
        **kwargs,
    ) -> PostResult:
        """Post content to the platform.
        
        Args:
            caption: Post caption/text
            media_paths: Paths to media files to upload
            hashtags: Hashtags to include
            **kwargs: Platform-specific options
            
        Returns:
            PostResult with success status and post info
        """
        pass

    @abstractmethod
    async def like_post(self, post_id: str) -> bool:
        """Like a post.
        
        Args:
            post_id: ID of the post to like
            
        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def unlike_post(self, post_id: str) -> bool:
        """Unlike a post.
        
        Args:
            post_id: ID of the post to unlike
            
        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def comment(self, post_id: str, text: str) -> Optional[str]:
        """Comment on a post.
        
        Args:
            post_id: ID of the post to comment on
            text: Comment text
            
        Returns:
            Comment ID if successful, None otherwise
        """
        pass

    @abstractmethod
    async def follow_user(self, user_id: str) -> bool:
        """Follow a user.
        
        Args:
            user_id: ID of the user to follow
            
        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def unfollow_user(self, user_id: str) -> bool:
        """Unfollow a user.
        
        Args:
            user_id: ID of the user to unfollow
            
        Returns:
            True if successful
        """
        pass

    @abstractmethod
    async def get_feed(
        self,
        hashtags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Post]:
        """Get feed posts, optionally filtered by hashtags.
        
        Args:
            hashtags: Hashtags to search for
            limit: Maximum number of posts to return
            
        Returns:
            List of posts
        """
        pass

    @abstractmethod
    async def get_user_posts(
        self,
        user_id: str,
        limit: int = 20,
    ) -> List[Post]:
        """Get posts from a specific user.
        
        Args:
            user_id: User ID to get posts from
            limit: Maximum posts to return
            
        Returns:
            List of posts
        """
        pass

    @abstractmethod
    async def get_user_profile(self, username: str) -> Optional[UserProfile]:
        """Get a user's profile.
        
        Args:
            username: Username to look up
            
        Returns:
            UserProfile if found
        """
        pass

    @abstractmethod
    async def get_analytics(self) -> Analytics:
        """Get analytics for the authenticated account.
        
        Returns:
            Analytics data
        """
        pass

    @abstractmethod
    async def search_hashtag(
        self,
        hashtag: str,
        limit: int = 20,
    ) -> List[Post]:
        """Search for posts by hashtag.
        
        Args:
            hashtag: Hashtag to search (without #)
            limit: Maximum posts to return
            
        Returns:
            List of posts
        """
        pass

    async def get_post(self, post_id: str) -> Optional[Post]:
        """Get a specific post by ID.
        
        Args:
            post_id: Post ID
            
        Returns:
            Post if found
        """
        raise NotImplementedError("get_post not implemented for this platform")

    async def delete_post(self, post_id: str) -> bool:
        """Delete a post.
        
        Args:
            post_id: Post ID to delete
            
        Returns:
            True if successful
        """
        raise NotImplementedError("delete_post not implemented for this platform")

    async def close(self):
        """Clean up resources (browser sessions, etc.)."""
        pass



