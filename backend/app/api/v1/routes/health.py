from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.neo4j_client import neo4j_client
from app.core.redis_client import get_redis_client
from app.core.vector_store import vector_store_client
from app.models.schemas.common import ApiResponse, HealthStatus

router = APIRouter(prefix="/health", tags=["Health & Readiness"])


@router.get("/live", response_model=ApiResponse[dict[str, str]])
async def liveness_check():
    """
    Lightweight liveness probe for container orchestrators and load balancers.
    Returns 200 OK immediately if the FastAPI process is alive.
    """
    return ApiResponse(
        success=True,
        data={"status": "alive", "version": settings.VERSION},
    )


@router.get("", response_model=ApiResponse[HealthStatus])
@router.get("/ready", response_model=ApiResponse[HealthStatus])
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Comprehensive readiness probe verifying backing infrastructure dependencies:
    - PostgreSQL (Primary Relational Store)
    - Redis (Cache & Token Bucket Rate Limiter)
    - Neo4j (Component Knowledge Graph)
    - Vector Store (ChromaDB Component Embeddings)

    Distinguishes:
    - 'healthy': All core and backing services fully operational.
    - 'degraded': Core relational store operational; auxiliary datastores offline/disabled.
    - 'unavailable': Primary database inaccessible.
    """
    services: dict[str, str] = {
        "api": "up",
        "postgres": "down",
        "redis": "disabled",
        "neo4j": "disabled",
        "vector_store": "disabled",
        "openrouter": "configured" if settings.OPENROUTER_API_KEY else "unconfigured",
    }

    # 1. Probe PostgreSQL
    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "up"
    except Exception:
        services["postgres"] = "down"

    # 2. Probe Redis
    try:
        redis = await get_redis_client()
        if redis and await redis.ping():
            services["redis"] = "up"
        else:
            services["redis"] = "down"
    except Exception:
        services["redis"] = "down"

    # 3. Probe Neo4j
    try:
        neo4j_ok = await neo4j_client.verify_connectivity()
        services["neo4j"] = "up" if neo4j_ok else "down"
    except Exception:
        services["neo4j"] = "down"

    # 4. Probe Vector Store
    try:
        vs_ok = await vector_store_client.verify_connectivity()
        services["vector_store"] = "up" if vs_ok else "down"
    except Exception:
        services["vector_store"] = "down"

    # Determine overall readiness status
    if services["postgres"] != "up":
        overall_status = "unavailable"
    elif all(services[k] == "up" for k in ("postgres", "redis", "neo4j", "vector_store")):
        overall_status = "healthy"
    else:
        overall_status = "degraded"

    return ApiResponse(
        success=overall_status != "unavailable",
        data=HealthStatus(
            status=overall_status,
            version=settings.VERSION,
            services=services,
        ),
    )
