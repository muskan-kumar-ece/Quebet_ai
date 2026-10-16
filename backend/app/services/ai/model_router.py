import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.db.model_config import ModelConfig, PlanModelAccess

logger = logging.getLogger(__name__)

# Fallback in-memory defaults if DB is cold
PLAN_DEFAULTS = {
    "free": settings.DEFAULT_FREE_MODEL,
    "plus": settings.DEFAULT_PLUS_MODEL,
    "pro": settings.DEFAULT_PRO_MODEL,
    "team": settings.DEFAULT_PRO_MODEL,
    "enterprise": settings.DEFAULT_PRO_MODEL,
}


class ModelRouter:
    """
    Dynamically resolves the OpenRouter model ID based on user subscription plan,
    task type, user preference, and admin-managed routing matrix.
    """

    async def get_model(
        self,
        plan: str,
        task_type: str = "default",
        user_preferred: str | None = None,
        db: AsyncSession | None = None,
    ) -> str:
        # 1. If user selected a preference and their plan allows switching (Plus, Pro, Enterprise)
        if user_preferred and plan in ("plus", "pro", "team", "enterprise"):
            return user_preferred

        # 2. Check Redis cache
        cache_key = f"model_route:{plan}:{task_type}"
        redis = await get_redis_client()
        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    return cached
            except Exception as e:
                logger.warning(f"Redis get failed for {cache_key}: {e}")

        # 3. Query DB routing table if session provided
        if db:
            try:
                stmt = (
                    select(PlanModelAccess.model_id)
                    .join(ModelConfig, PlanModelAccess.model_id == ModelConfig.model_id)
                    .where(PlanModelAccess.plan == plan)
                    .where(PlanModelAccess.task_type == task_type)
                    .where(PlanModelAccess.is_default.is_(True))
                    .where(ModelConfig.is_active.is_(True))
                    .where(ModelConfig.deleted_at.is_(None))
                    .where(PlanModelAccess.deleted_at.is_(None))
                    .order_by(PlanModelAccess.priority.desc())
                    .limit(1)
                )
                result = await db.execute(stmt)
                model_id = result.scalar_one_or_none()
                if model_id:
                    if redis:
                        try:
                            await redis.set(cache_key, model_id, ex=300)
                        except Exception:
                            pass
                    return model_id
            except Exception as e:
                logger.warning(f"DB model route query failed: {e}")

        # 4. Fallback to plan defaults
        return PLAN_DEFAULTS.get(plan, settings.DEFAULT_FREE_MODEL)


model_router = ModelRouter()
