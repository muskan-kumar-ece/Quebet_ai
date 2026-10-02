from app.services.ai.base_provider import BaseProvider
from app.services.ai.openrouter_provider import OpenRouterProvider

# Global singleton instance
_provider_instance: BaseProvider | None = None


def get_ai_provider() -> BaseProvider:
    """Dependency injection helper returning the active OpenRouter provider."""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = OpenRouterProvider()
    return _provider_instance
