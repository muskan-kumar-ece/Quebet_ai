from abc import ABC, abstractmethod
import json
import re
from typing import Any, Dict, Optional
from pydantic import BaseModel


class CognitiveModelError(Exception):
    """Base error for cognitive model provider failures."""
    def __init__(self, code: str, message: str):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class ModelTimeoutError(CognitiveModelError):
    def __init__(self, message: str = "Model inference timed out"):
        super().__init__("MODEL_TIMEOUT", message)


class ModelUnavailableError(CognitiveModelError):
    def __init__(self, message: str = "Model service is unavailable"):
        super().__init__("MODEL_UNAVAILABLE", message)


class ModelRateLimitError(CognitiveModelError):
    def __init__(self, message: str = "Model rate limit exceeded"):
        super().__init__("MODEL_RATE_LIMITED", message)


class ModelAuthError(CognitiveModelError):
    def __init__(self, message: str = "Model authentication failed"):
        super().__init__("MODEL_AUTH_FAILURE", message)


class ModelInvalidResponseError(CognitiveModelError):
    def __init__(self, message: str = "Model output could not be parsed as valid JSON"):
        super().__init__("MODEL_INVALID_RESPONSE", message)


class ModelSchemaError(CognitiveModelError):
    def __init__(self, message: str = "Model output violated expected schema"):
        super().__init__("MODEL_SCHEMA_FAILURE", message)


class CognitiveModelProvider(ABC):
    """
    Provider-neutral interface for LLM operations in the Cognitive Engineering Layer.
    Decouples intent resolution, decomposition, and explanation from specific provider SDKs.
    """

    @property
    @abstractmethod
    def provider_identifier(self) -> str:
        pass

    @property
    @abstractmethod
    def model_identifier(self) -> str:
        pass

    @abstractmethod
    async def generate_structured(
        self,
        system: str,
        user: str,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """Generate a structured response adhering to schema with JSON repair."""
        pass

    @abstractmethod
    async def generate_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> str:
        """Generate unconstrained natural language text."""
        pass


class MockCognitiveProvider(CognitiveModelProvider):
    """
    Hermetic test provider for unit tests and deterministic simulation.
    Allows injecting predetermined responses or error modes.
    """

    def __init__(
        self,
        provider_id: str = "mock-provider",
        model_id: str = "mock-model-v1",
        preset_structured: Optional[Dict[str, Any]] = None,
        preset_text: Optional[str] = None,
        simulate_error: Optional[str] = None,
    ):
        self._provider_id = provider_id
        self._model_id = model_id
        self.preset_structured = preset_structured or {}
        self.preset_text = preset_text or "Mock AI explanation"
        self.simulate_error = simulate_error

    @property
    def provider_identifier(self) -> str:
        return self._provider_id

    @property
    def model_identifier(self) -> str:
        return self._model_id

    async def generate_structured(
        self,
        system: str,
        user: str,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        if self.simulate_error == "MODEL_TIMEOUT":
            raise ModelTimeoutError()
        elif self.simulate_error == "MODEL_UNAVAILABLE":
            raise ModelUnavailableError()
        elif self.simulate_error == "MODEL_RATE_LIMITED":
            raise ModelRateLimitError()
        elif self.simulate_error == "MODEL_AUTH_FAILURE":
            raise ModelAuthError()
        elif self.simulate_error == "MODEL_INVALID_RESPONSE":
            raise ModelInvalidResponseError()
        elif self.simulate_error == "MODEL_SCHEMA_FAILURE":
            raise ModelSchemaError()

        return self.preset_structured

    async def generate_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> str:
        if self.simulate_error == "MODEL_UNAVAILABLE":
            raise ModelUnavailableError()
        return self.preset_text


class OpenRouterCognitiveProvider(CognitiveModelProvider):
    """
    OpenRouter integration utilizing BaseProvider infrastructure.
    """

    def __init__(self, model_id: str = "anthropic/claude-3.5-sonnet"):
        self._model_id = model_id
        self._provider_id = "openrouter"

    @property
    def provider_identifier(self) -> str:
        return self._provider_id

    @property
    def model_identifier(self) -> str:
        return self._model_id

    async def generate_structured(
        self,
        system: str,
        user: str,
        schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        from app.services.ai.openrouter_provider import OpenRouterProvider
        router = OpenRouterProvider()
        try:
            resp = await router.complete(
                system=system,
                user=user,
                model=self._model_id,
                temperature=temperature,
                response_format="json",
            )
            raw = resp.content
            # Structured Model Contract: Clean & parse JSON
            cleaned = self._clean_json(raw)
            return json.loads(cleaned)
        except json.JSONDecodeError as jde:
            raise ModelInvalidResponseError(f"Failed to parse model JSON: {jde}")
        except Exception as e:
            if "timeout" in str(e).lower():
                raise ModelTimeoutError(str(e))
            if "rate limit" in str(e).lower():
                raise ModelRateLimitError(str(e))
            if "auth" in str(e).lower():
                raise ModelAuthError(str(e))
            raise ModelUnavailableError(str(e))

    async def generate_text(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> str:
        from app.services.ai.openrouter_provider import OpenRouterProvider
        router = OpenRouterProvider()
        try:
            resp = await router.complete(
                system=system,
                user=user,
                model=self._model_id,
                temperature=temperature,
                response_format="text",
            )
            return resp.content
        except Exception as e:
            raise ModelUnavailableError(str(e))

    def _clean_json(self, raw: str) -> str:
        text = raw.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()
