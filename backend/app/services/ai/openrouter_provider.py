import time
from collections.abc import AsyncGenerator
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.exceptions import AIServiceError
from app.services.ai.base_provider import BaseProvider, ProviderResponse


class OpenRouterProvider(BaseProvider):
    """
    Unified LLM provider routed via OpenRouter (api.openrouter.ai).
    Uses the OpenAI-compatible SDK with dynamic model selection.
    """

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.client = AsyncOpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=self.api_key or "sk-or-placeholder-key-for-local-testing",
            default_headers={
                "HTTP-Referer": "https://quebet.ai",
                "X-Title": "QUEBET AI",
            },
        )

    async def complete(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        response_format: str = "json",
    ) -> ProviderResponse:
        start_time = time.perf_counter()

        try:
            extra_params = {}
            if response_format == "json":
                extra_params["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                **extra_params,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            choice = response.choices[0]
            usage = response.usage

            return ProviderResponse(
                content=choice.message.content or "",
                model=response.model or model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                latency_ms=latency_ms,
                cost_usd=0.0,  # Computed from model_configs table if needed
                cached=False,
            )
        except Exception as e:
            raise AIServiceError(message=f"OpenRouter inference failed: {str(e)}") from e

    async def stream(
        self,
        system: str,
        user: str,
        model: str,
        temperature: float = 0.2,
    ) -> AsyncGenerator[str, None]:
        try:
            response_stream = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                stream=True,
            )
            async for chunk in response_stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise AIServiceError(message=f"OpenRouter streaming failed: {str(e)}") from e

    async def analyze_image(
        self,
        image_url: str,
        prompt: str,
        model: str,
        detail: str = "high",
    ) -> ProviderResponse:
        start_time = time.perf_counter()
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url, "detail": detail},
                            },
                        ],
                    }
                ],
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            choice = response.choices[0]
            usage = response.usage

            return ProviderResponse(
                content=choice.message.content or "",
                model=response.model or model,
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                latency_ms=latency_ms,
            )
        except Exception as e:
            raise AIServiceError(message=f"Vision analysis failed: {str(e)}") from e
