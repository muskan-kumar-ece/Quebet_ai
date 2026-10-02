from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import get_redis_client
from app.models.schemas.common import ApiResponse, HealthStatus

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=ApiResponse[HealthStatus])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Deep health check verifying backend runtime and backing services."""
    services = {
        "api": "up",
        "postgres": "down",
        "redis": "down",
        "openrouter": "configured" if settings.OPENROUTER_API_KEY else "unconfigured",
    }

    # 1. Probe Database
    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "up"
    except Exception:
        services["postgres"] = "error"

    # 2. Probe Redis
    try:
        redis = await get_redis_client()
        if redis and await redis.ping():
            services["redis"] = "up"
        else:
            services["redis"] = "disabled"
    except Exception:
        services["redis"] = "error"

    overall_status = "healthy" if services["postgres"] == "up" else "degraded"

    return ApiResponse(
        success=True,
        data=HealthStatus(
            status=overall_status,
            version=settings.VERSION,
            services=services,
        ),
    )
