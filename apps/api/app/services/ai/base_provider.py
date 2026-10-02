from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from pydantic import BaseModel


class ProviderResponse(BaseModel):
    """Normalized response from any LLM call."""
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    cached: bool = False


class BaseProvider(ABC):
    """Abstract interface that every LLM gateway or provider must satisfy."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: str = "json",
    ) -> ProviderResponse:
        """Execute a non-streaming completion."""
        pass

    @abstractmethod
    async def stream(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        """Yield text tokens for real-time SSE streaming."""
        pass

    @abstractmethod
    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        model: str,
        detail: str = "high",
    ) -> ProviderResponse:
        """Perform visual analysis (PCB inspection, component detection)."""
        pass
