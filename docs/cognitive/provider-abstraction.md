# Provider-Neutral Model Abstraction

## 1. Provider Contract
Cognitive LLM operations are decoupled from specific model vendors via the `CognitiveModelProvider` abstract base class:

```python
class CognitiveModelProvider(ABC):
    @property
    @abstractmethod
    def provider_identifier(self) -> str: ...

    @property
    @abstractmethod
    def model_identifier(self) -> str: ...

    @abstractmethod
    async def generate_structured(self, system: str, user: str, schema: Optional[Dict[str, Any]] = None, temperature: float = 0.0) -> Dict[str, Any]: ...

    @abstractmethod
    async def generate_text(self, system: str, user: str, temperature: float = 0.2) -> str: ...
```

## 2. Standardized Error Hierarchy
Model provider operational errors are normalized into typed domain exceptions:

| Exception Class | Error Code | HTTP Status | Description |
|---|---|---|---|
| `ModelTimeoutError` | `MODEL_TIMEOUT` | 504 | Upstream inference deadline exceeded. |
| `ModelUnavailableError` | `MODEL_UNAVAILABLE` | 503 | Model service down or degraded. |
| `ModelRateLimitError` | `MODEL_RATE_LIMITED` | 429 | Upstream rate limits reached. |
| `ModelAuthError` | `MODEL_AUTH_FAILURE` | 401 | Invalid or expired API credentials. |
| `ModelInvalidResponseError` | `MODEL_INVALID_RESPONSE` | 502 | Malformed output unparseable as JSON. |
| `ModelSchemaError` | `MODEL_SCHEMA_FAILURE` | 502 | Output violates expected JSON schema. |

## 3. Implementations
- `MockCognitiveProvider`: Hermetic test double enabling simulated errors and reproducible tests without network access.
- `OpenRouterCognitiveProvider`: Production router supporting Claude, GPT-4o, and other enterprise models with streaming and fallback routing.
