from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.model_config import ModelConfig, PlanModelAccess, PlanRateLimits


class ModelRepository:
    """Handles database queries for model catalog and plan routing."""

    async def get_models_for_plan(self, db: AsyncSession, plan: str) -> list[tuple[ModelConfig, bool]]:
        """
        Returns list of (ModelConfig, is_default) accessible to the given plan.
        """
        stmt = (
            select(ModelConfig, PlanModelAccess.is_default)
            .join(PlanModelAccess, ModelConfig.model_id == PlanModelAccess.model_id)
            .where(PlanModelAccess.plan == plan)
            .where(ModelConfig.is_active.is_(True))
            .where(PlanModelAccess.is_user_selectable.is_(True))
            .order_by(PlanModelAccess.priority.desc())
        )
        result = await db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_plan_limits(self, db: AsyncSession, plan: str) -> PlanRateLimits | None:
        stmt = select(PlanRateLimits).where(PlanRateLimits.plan == plan)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


model_repo = ModelRepository()
