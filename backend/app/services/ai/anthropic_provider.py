"""Anthropic Claude provider implementation."""

from typing import List, Optional
import base64
import structlog
import httpx
from anthropic import AsyncAnthropic

from app.config import get_settings
from app.services.ai.base import AIProvider, Message, GenerationResult, ImageContent

logger = structlog.get_logger()
settings = get_settings()


class AnthropicProvider(AIProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize Anthropic provider.
        
        Args:
            api_key: Anthropic API key (defaults to env var)
            model: Model to use (default: claude-3-5-sonnet)
        """
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model
        self._client: Optional[AsyncAnthropic] = None

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def client(self) -> AsyncAnthropic:
        """Get or create the async client."""
        if self._client is None:
            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def generate_text(
        self,
        messages: List[Message],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stop_sequences: Optional[List[str]] = None,
    ) -> GenerationResult:
        """Generate text using Claude."""
        logger.info(
            "Generating text with Anthropic",
            model=self.model,
            message_count=len(messages),
            max_tokens=max_tokens,
        )

        # Separate system message from conversation
        system_message = None
        conversation_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                if msg.images:
                    # Build content array with text and images for vision
                    content = []
                    for img in msg.images:
                        # Claude requires base64 or URL with media type
                        content.append({
                            "type": "image",
                            "source": {
                                "type": "url",
                                "url": img.url,
                            }
                        })
                    content.append({"type": "text", "text": msg.content})
                    conversation_messages.append({
                        "role": msg.role,
                        "content": content,
                    })
                else:
                    conversation_messages.append({
                        "role": msg.role,
                        "content": msg.content,
                    })

        # Ensure conversation starts with user message
        if not conversation_messages or conversation_messages[0]["role"] != "user":
            conversation_messages.insert(0, {
                "role": "user",
                "content": "Please proceed with the task.",
            })

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": conversation_messages,
        }
        
        if system_message:
            kwargs["system"] = system_message
        
        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences

        response = await self.client.messages.create(**kwargs)

        # Extract text from content blocks
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        return GenerationResult(
            text=text,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            model=response.model,
            finish_reason=response.stop_reason or "unknown",
        )

    async def generate_completion(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> GenerationResult:
        """Generate completion using message format."""
        messages = [Message(role="user", content=prompt)]
        return await self.generate_text(messages, max_tokens, temperature)

    async def analyze_image(self, image_url: str, prompt: str = "Describe this image in detail.") -> str:
        """Analyze an image using Claude Vision.
        
        Downloads the image first and sends as base64 to avoid robots.txt blocking.
        
        Args:
            image_url: URL of the image to analyze
            prompt: Prompt for the analysis
            
        Returns:
            Text description/analysis of the image
        """
        logger.info("Analyzing image with Claude Vision", url=image_url[:100])
        
        # Download image and convert to base64 (Instagram CDN blocks direct URL access)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(image_url, timeout=15.0, follow_redirects=True)
                response.raise_for_status()
                image_data = response.content
                
                # Determine media type from content-type header or URL
                content_type = response.headers.get("content-type", "image/jpeg")
                if "jpeg" in content_type or "jpg" in content_type:
                    media_type = "image/jpeg"
                elif "png" in content_type:
                    media_type = "image/png"
                elif "gif" in content_type:
                    media_type = "image/gif"
                elif "webp" in content_type:
                    media_type = "image/webp"
                else:
                    media_type = "image/jpeg"  # Default fallback
                
                base64_image = base64.b64encode(image_data).decode("utf-8")
                
                logger.debug(
                    "Image downloaded for analysis",
                    size_kb=round(len(image_data) / 1024, 1),
                )
            except Exception as e:
                logger.error("Failed to download image for analysis", error=str(e))
                raise
        
        # Build message with base64 image content
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=200,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64_image,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        
        # Extract text from response
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        
        return text



