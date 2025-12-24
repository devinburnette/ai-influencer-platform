"""Engagement strategies for different growth goals."""

from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass
import random

from app.models.persona import Persona
from app.config import get_settings

settings = get_settings()


@dataclass
class EngagementPlan:
    """Daily engagement plan."""
    likes_target: int
    comments_target: int
    follows_target: int
    hashtags_to_explore: list
    engagement_windows: list  # List of (start_hour, end_hour) tuples
    comment_probability: float  # Chance to comment on liked post


class EngagementStrategy(ABC):
    """Abstract base class for engagement strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name."""
        pass

    @abstractmethod
    def create_plan(self, persona: Persona) -> EngagementPlan:
        """Create an engagement plan for the persona.
        
        Args:
            persona: The persona to plan for
            
        Returns:
            EngagementPlan with targets and parameters
        """
        pass

    @abstractmethod
    def adjust_for_performance(
        self,
        plan: EngagementPlan,
        metrics: Dict[str, Any],
    ) -> EngagementPlan:
        """Adjust plan based on performance metrics.
        
        Args:
            plan: Current engagement plan
            metrics: Performance metrics from recent activity
            
        Returns:
            Adjusted EngagementPlan
        """
        pass


class BalancedStrategy(EngagementStrategy):
    """Balanced strategy focusing on steady, organic growth."""

    @property
    def name(self) -> str:
        return "balanced"

    def create_plan(self, persona: Persona) -> EngagementPlan:
        """Create a balanced engagement plan."""
        # Use 60-80% of daily limits
        likes_target = int(settings.max_likes_per_day * random.uniform(0.6, 0.8))
        comments_target = int(settings.max_comments_per_day * random.uniform(0.5, 0.7))
        follows_target = int(settings.max_follows_per_day * random.uniform(0.3, 0.5))
        
        # Spread engagement across active hours
        start_hour = persona.engagement_hours_start
        end_hour = persona.engagement_hours_end
        
        # Create 3-4 engagement windows
        hours_range = end_hour - start_hour
        window_size = hours_range // 4
        
        windows = []
        for i in range(4):
            window_start = start_hour + (i * window_size)
            window_end = window_start + window_size
            windows.append((window_start, min(window_end, end_hour)))
        
        return EngagementPlan(
            likes_target=likes_target,
            comments_target=comments_target,
            follows_target=follows_target,
            hashtags_to_explore=persona.niche[:5],
            engagement_windows=windows,
            comment_probability=0.15,  # 15% chance to comment on liked posts
        )

    def adjust_for_performance(
        self,
        plan: EngagementPlan,
        metrics: Dict[str, Any],
    ) -> EngagementPlan:
        """Adjust based on engagement received."""
        engagement_rate = metrics.get("engagement_rate", 0)
        follower_growth = metrics.get("follower_growth", 0)
        
        # If getting good engagement, increase activity slightly
        if engagement_rate > 0.05 and follower_growth > 0:
            plan.likes_target = min(
                int(plan.likes_target * 1.1),
                settings.max_likes_per_day,
            )
            plan.comment_probability = min(plan.comment_probability * 1.2, 0.3)
        
        # If low engagement, focus more on comments
        elif engagement_rate < 0.02:
            plan.comments_target = min(
                int(plan.comments_target * 1.2),
                settings.max_comments_per_day,
            )
            plan.comment_probability = min(plan.comment_probability * 1.5, 0.4)
        
        return plan


class AggressiveGrowthStrategy(EngagementStrategy):
    """Aggressive strategy for rapid growth (use carefully to avoid bans)."""

    @property
    def name(self) -> str:
        return "aggressive"

    def create_plan(self, persona: Persona) -> EngagementPlan:
        """Create an aggressive engagement plan."""
        # Use 90-100% of daily limits
        likes_target = int(settings.max_likes_per_day * random.uniform(0.9, 1.0))
        comments_target = int(settings.max_comments_per_day * random.uniform(0.8, 1.0))
        follows_target = int(settings.max_follows_per_day * random.uniform(0.7, 0.9))
        
        # Maximize engagement windows
        start_hour = persona.engagement_hours_start
        end_hour = persona.engagement_hours_end
        
        # More frequent windows
        hours_range = end_hour - start_hour
        window_size = hours_range // 6
        
        windows = []
        for i in range(6):
            window_start = start_hour + (i * window_size)
            window_end = window_start + window_size
            windows.append((window_start, min(window_end, end_hour)))
        
        # Expand hashtags to explore
        hashtags = persona.niche.copy()
        
        return EngagementPlan(
            likes_target=likes_target,
            comments_target=comments_target,
            follows_target=follows_target,
            hashtags_to_explore=hashtags,
            engagement_windows=windows,
            comment_probability=0.25,
        )

    def adjust_for_performance(
        self,
        plan: EngagementPlan,
        metrics: Dict[str, Any],
    ) -> EngagementPlan:
        """Adjust based on rate limit warnings or restrictions."""
        rate_limit_warnings = metrics.get("rate_limit_warnings", 0)
        action_blocks = metrics.get("action_blocks", 0)
        
        # Back off if seeing warnings
        if rate_limit_warnings > 0 or action_blocks > 0:
            plan.likes_target = int(plan.likes_target * 0.7)
            plan.comments_target = int(plan.comments_target * 0.6)
            plan.follows_target = int(plan.follows_target * 0.5)
            plan.comment_probability *= 0.7
        
        return plan


class NicheExpertStrategy(EngagementStrategy):
    """Strategy focused on becoming a niche authority."""

    @property
    def name(self) -> str:
        return "niche_expert"

    def create_plan(self, persona: Persona) -> EngagementPlan:
        """Create a niche-focused engagement plan."""
        # Lower quantity, higher quality
        likes_target = int(settings.max_likes_per_day * 0.5)
        comments_target = int(settings.max_comments_per_day * 0.7)
        follows_target = int(settings.max_follows_per_day * 0.4)
        
        # Fewer but longer windows for thoughtful engagement
        start_hour = persona.engagement_hours_start
        end_hour = persona.engagement_hours_end
        
        mid_hour = (start_hour + end_hour) // 2
        
        windows = [
            (start_hour, start_hour + 2),
            (mid_hour - 1, mid_hour + 1),
            (end_hour - 2, end_hour),
        ]
        
        return EngagementPlan(
            likes_target=likes_target,
            comments_target=comments_target,
            follows_target=follows_target,
            hashtags_to_explore=persona.niche[:3],  # Focus on core niche
            engagement_windows=windows,
            comment_probability=0.35,  # Higher comment rate for expertise
        )

    def adjust_for_performance(
        self,
        plan: EngagementPlan,
        metrics: Dict[str, Any],
    ) -> EngagementPlan:
        """Adjust based on comment engagement."""
        comment_replies = metrics.get("comment_replies", 0)
        
        # If comments are getting replies, increase commenting
        if comment_replies > 5:
            plan.comments_target = min(
                int(plan.comments_target * 1.2),
                settings.max_comments_per_day,
            )
            plan.comment_probability = min(plan.comment_probability * 1.2, 0.5)
        
        return plan


def get_strategy(name: str) -> EngagementStrategy:
    """Get a strategy by name.
    
    Args:
        name: Strategy name
        
    Returns:
        EngagementStrategy instance
    """
    strategies = {
        "balanced": BalancedStrategy,
        "aggressive": AggressiveGrowthStrategy,
        "niche_expert": NicheExpertStrategy,
    }
    
    strategy_class = strategies.get(name, BalancedStrategy)
    return strategy_class()

