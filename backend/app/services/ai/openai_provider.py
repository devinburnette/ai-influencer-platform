"""OpenAI provider implementation."""

from typing import List, Optional
import structlog
from openai import AsyncOpenAI

from app.config import get_settings
from app.services.ai.base import AIProvider, Message, GenerationResult, ImageContent

logger = structlog.get_logger()
settings = get_settings()


class OpenAIProvider(AIProvider):
    """OpenAI API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o",
    ):
        """Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (defaults to env var)
            model: Model to use (default: gpt-4o)
        """
        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self._client: Optional[AsyncOpenAI] = None

    @property
    def name(self) -> str:
        return "openai"

    @property
    def client(self) -> AsyncOpenAI:
        """Get or create the async client."""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate_text(
        self,
        messages: List[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
    ) -> GenerationResult:
        """Generate text using OpenAI chat completion."""
        logger.info(
            "Generating text with OpenAI",
            model=self.model,
            message_count=len(messages),
            max_tokens=max_tokens,
        )

        openai_messages = []
        for msg in messages:
            if msg.images:
                # Build content array with text and images for vision
                content = [{"type": "text", "text": msg.content}]
                for img in msg.images:
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": img.url,
                            "detail": img.detail,
                        }
                    })
                openai_messages.append({"role": msg.role, "content": content})
            else:
                openai_messages.append({"role": msg.role, "content": msg.content})

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=openai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop_sequences,
        )

        choice = response.choices[0]
        
        return GenerationResult(
            text=choice.message.content or "",
            tokens_used=response.usage.total_tokens if response.usage else 0,
            model=response.model,
            finish_reason=choice.finish_reason or "unknown",
        )

    async def generate_completion(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Generate completion using chat format."""
        messages = [Message(role="user", content=prompt)]
        return await self.generate_text(messages, max_tokens, temperature)

    async def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
    ) -> str:
        """Generate an image using DALL-E.
        
        Args:
            prompt: Image description
            size: Image size (1024x1024, 1792x1024, or 1024x1792)
            quality: Image quality (standard or hd)
            style: Image style (vivid or natural)
            
        Returns:
            URL of the generated image
        """
        logger.info("Generating image with DALL-E", prompt=prompt[:100])

        response = await self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            style=style,
            n=1,
        )

        return response.data[0].url

    async def generate_image_variation(
        self,
        image_url: str,
        n: int = 1,
        size: str = "1024x1024",
    ) -> List[str]:
        """Generate variations of an image.
        
        Args:
            image_url: URL of source image
            n: Number of variations
            size: Output size
            
        Returns:
            List of URLs for generated variations
        """
        import httpx
        
        # Download the image
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            image_data = response.content

        response = await self.client.images.create_variation(
            image=image_data,
            n=n,
            size=size,
        )

        return [img.url for img in response.data]

    async def analyze_image(self, image_url: str, prompt: str = "Describe this image in detail.") -> str:
        """Analyze an image using GPT-4 Vision.
        
        Args:
            image_url: URL of the image to analyze
            prompt: Prompt for the analysis
            
        Returns:
            Text description/analysis of the image
        """
        logger.info("Analyzing image with GPT-4 Vision", url=image_url[:100])
        
        message = Message(
            role="user",
            content=prompt,
            images=[ImageContent(url=image_url, detail="low")]  # Use low detail to save tokens
        )
        
        result = await self.generate_text([message], max_tokens=200, temperature=0.3)
        return result.text


