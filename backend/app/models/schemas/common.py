from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class ApiResponse(BaseModel, Generic[DataT]):
    """Standardized API response envelope."""
    success: bool = True
    data: DataT | None = None
    error: dict[str, Any] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class HealthStatus(BaseModel):
    """Subsystem health status report."""
    status: str  # healthy | degraded | unhealthy
    version: str
    services: dict[str, str]  # postgres, redis, openrouter, etc.
