"""Engagement analyzer for scoring and prioritizing content."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import structlog

from app.models.persona import Persona
from app.services.ai.base import AIProvider, Message
from app.services.ai.openai_provider import OpenAIProvider
from app.services.ai.anthropic_provider import AnthropicProvider
from app.services.platforms.base import Post

logger = structlog.get_logger()


@dataclass
class EngagementScore:
    """Scoring result for a post."""
    post_id: str
    relevance: float  # 0-1: How relevant to persona's niche
    quality: float  # 0-1: Content quality score
    engagement_potential: float  # 0-1: Likelihood of getting engagement back
    overall: float  # Combined score
    should_like: bool
    should_comment: bool
    should_follow: bool
    suggested_comment: Optional[str] = None


class EngagementAnalyzer:
    """Analyzes content and determines engagement actions."""

    def __init__(self, provider: Optional[AIProvider] = None):
        """Initialize analyzer with optional AI provider."""
        self.provider = provider

    def _get_provider(self, persona: Optional[Persona] = None) -> AIProvider:
        """Get AI provider for analysis."""
        if self.provider:
            return self.provider
        
        provider_name = persona.ai_provider if persona else "openai"
        
        if provider_name == "anthropic":
            return AnthropicProvider()
        return OpenAIProvider()

    async def analyze_post(
        self,
        post: Post,
        persona: Persona,
        include_comment: bool = True,
    ) -> EngagementScore:
        """Analyze a post for engagement potential.
        
        Args:
            post: Post to analyze
            persona: Persona considering engagement
            include_comment: Whether to generate a potential comment
            
        Returns:
            EngagementScore with recommendations
        """
        provider = self._get_provider(persona)
        
        # Build analysis prompt
        voice = persona.voice
        
        messages = [
            Message(
                role="system",
                content=f"""You are analyzing social media content for an AI influencer.

Persona: {persona.name}
Niche: {', '.join(persona.niche)}
Tone: {voice.tone}

Analyze the post and provide engagement recommendations.
Respond in JSON format."""
            ),
            Message(
                role="user",
                content=f"""Analyze this post:

Author: @{post.author_username}
Content: "{post.content}"
Likes: {post.like_count}
Comments: {post.comment_count}

Score from 0-1:
1. relevance: How relevant is this to the persona's niche?
2. quality: How high quality/engaging is the content?
3. engagement_potential: How likely is engagement to result in reciprocation?

Also determine:
- should_like: Should the persona like this? (true/false)
- should_comment: Should they comment? (true/false)
- should_follow: Should they follow this user? (true/false)
{"- suggested_comment: If commenting, what should they say? (match the persona's voice)" if include_comment else ""}

Respond as JSON:
{{
    "relevance": 0.8,
    "quality": 0.7,
    "engagement_potential": 0.6,
    "should_like": true,
    "should_comment": false,
    "should_follow": false
    {"," if include_comment else ""}
    {"\"suggested_comment\": \"Great post!\"" if include_comment else ""}
}}"""
            ),
        ]
        
        try:
            result = await provider.generate_json(messages, max_tokens=300, temperature=0.5)
            
            relevance = float(result.get("relevance", 0.5))
            quality = float(result.get("quality", 0.5))
            engagement_potential = float(result.get("engagement_potential", 0.5))
            
            # Calculate overall score (weighted average)
            overall = (relevance * 0.4) + (quality * 0.3) + (engagement_potential * 0.3)
            
            return EngagementScore(
                post_id=post.id,
                relevance=relevance,
                quality=quality,
                engagement_potential=engagement_potential,
                overall=overall,
                should_like=result.get("should_like", overall >= 0.5),
                should_comment=result.get("should_comment", overall >= 0.7),
                should_follow=result.get("should_follow", overall >= 0.8),
                suggested_comment=result.get("suggested_comment"),
            )
            
        except Exception as e:
            logger.error("Post analysis failed", post_id=post.id, error=str(e))
            # Return conservative defaults
            return EngagementScore(
                post_id=post.id,
                relevance=0.5,
                quality=0.5,
                engagement_potential=0.5,
                overall=0.5,
                should_like=False,
                should_comment=False,
                should_follow=False,
            )

    async def analyze_batch(
        self,
        posts: List[Post],
        persona: Persona,
        include_comments: bool = False,
    ) -> List[EngagementScore]:
        """Analyze multiple posts in batch.
        
        Args:
            posts: Posts to analyze
            persona: Persona for context
            include_comments: Whether to generate comments
            
        Returns:
            List of EngagementScores sorted by overall score
        """
        scores = []
        
        for post in posts:
            score = await self.analyze_post(post, persona, include_comments)
            scores.append(score)
        
        # Sort by overall score descending
        scores.sort(key=lambda s: s.overall, reverse=True)
        
        return scores

    async def filter_for_engagement(
        self,
        posts: List[Post],
        persona: Persona,
        like_threshold: float = 0.5,
        comment_threshold: float = 0.7,
        max_likes: int = 20,
        max_comments: int = 5,
    ) -> Dict[str, List[EngagementScore]]:
        """Filter and prioritize posts for engagement.
        
        Args:
            posts: Posts to consider
            persona: Persona for context
            like_threshold: Minimum score to like
            comment_threshold: Minimum score to comment
            max_likes: Maximum posts to like
            max_comments: Maximum posts to comment on
            
        Returns:
            Dictionary with 'to_like' and 'to_comment' lists
        """
        scores = await self.analyze_batch(posts, persona, include_comments=True)
        
        to_like = []
        to_comment = []
        
        for score in scores:
            if score.overall >= like_threshold and len(to_like) < max_likes:
                to_like.append(score)
            
            if (
                score.overall >= comment_threshold
                and score.should_comment
                and len(to_comment) < max_comments
            ):
                to_comment.append(score)
        
        return {
            "to_like": to_like,
            "to_comment": to_comment,
        }

    async def find_influencers_to_follow(
        self,
        posts: List[Post],
        persona: Persona,
        min_followers: int = 1000,
        max_followers: int = 100000,
        limit: int = 5,
    ) -> List[str]:
        """Find relevant influencers to follow based on their content.
        
        Args:
            posts: Posts to analyze
            persona: Persona for context
            min_followers: Minimum follower count
            max_followers: Maximum follower count (avoid huge accounts)
            limit: Maximum accounts to suggest
            
        Returns:
            List of usernames to follow
        """
        scores = await self.analyze_batch(posts, persona)
        
        # Get unique users from high-scoring posts
        suggested = []
        seen_users = set()
        
        for score in scores:
            if score.should_follow and score.overall >= 0.7:
                # Find corresponding post
                post = next((p for p in posts if p.id == score.post_id), None)
                if post and post.author_username not in seen_users:
                    seen_users.add(post.author_username)
                    suggested.append(post.author_username)
                    
                    if len(suggested) >= limit:
                        break
        
        return suggested


