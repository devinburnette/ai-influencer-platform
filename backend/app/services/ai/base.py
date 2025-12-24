"""Abstract base class for AI providers."""

from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Message:
    """A message in a conversation."""
    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class GenerationResult:
    """Result from text generation."""
    text: str
    tokens_used: int
    model: str
    finish_reason: str


class AIProvider(ABC):
    """Abstract base class for AI providers (OpenAI, Anthropic, etc.)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        messages: List[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
    ) -> GenerationResult:
        """Generate text from a conversation.
        
        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            stop_sequences: Optional sequences to stop generation
            
        Returns:
            GenerationResult with generated text and metadata
        """
        pass

    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Generate a completion from a simple prompt.
        
        Args:
            prompt: The prompt to complete
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            
        Returns:
            GenerationResult with generated text and metadata
        """
        pass

    async def generate_json(
        self,
        messages: List[Message],
        max_tokens: int = 1000,
        temperature: float = 0.5,
    ) -> dict:
        """Generate structured JSON output.
        
        Args:
            messages: List of conversation messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Parsed JSON dictionary
        """
        import json
        
        result = await self.generate_text(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        
        # Try to extract JSON from the response
        text = result.text.strip()
        
        # Handle markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        return json.loads(text.strip())

    async def analyze_sentiment(self, text: str) -> dict:
        """Analyze sentiment of text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with sentiment analysis
        """
        messages = [
            Message(
                role="system",
                content="Analyze the sentiment of the following text. "
                "Respond with JSON containing: sentiment (positive/negative/neutral), "
                "confidence (0-1), and key_emotions (list of emotions)."
            ),
            Message(role="user", content=text),
        ]
        
        return await self.generate_json(messages, temperature=0.3)

    async def score_relevance(
        self,
        content: str,
        topics: List[str],
    ) -> float:
        """Score how relevant content is to given topics.
        
        Args:
            content: Content to score
            topics: List of topics to match against
            
        Returns:
            Relevance score from 0 to 1
        """
        messages = [
            Message(
                role="system",
                content=f"Score how relevant the following content is to these topics: {', '.join(topics)}. "
                "Respond with only a number between 0 and 1, where 1 is highly relevant."
            ),
            Message(role="user", content=content),
        ]
        
        result = await self.generate_text(messages, max_tokens=10, temperature=0.1)
        
        try:
            score = float(result.text.strip())
            return max(0.0, min(1.0, score))
        except ValueError:
            return 0.5

