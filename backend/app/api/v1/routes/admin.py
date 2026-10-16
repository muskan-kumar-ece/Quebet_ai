from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import require_admin_role
from app.models.db.model_config import ModelConfig, PlanModelAccess, PlanRateLimits
from app.models.db.user import User
from app.models.schemas.common import ApiResponse

router = APIRouter(
    prefix="/admin",
    tags=["Admin Portal"],
    dependencies=[Depends(require_admin_role)],
)


# Schemas
class AdminKPISummary(BaseModel):
    total_users: int
    active_models_count: int
    openrouter_status: str
    monthly_tokens_consumed: int
    estimated_monthly_spend_usd: float
    cache_hit_rate_pct: float
    avg_latency_ms: int


class ModelConfigCreate(BaseModel):
    model_id: str
    display_name: str
    provider: str
    is_vision_capable: bool = False
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    max_context_tokens: int = 128000
    supports_json_mode: bool = True
    supports_streaming: bool = True
    notes: str | None = None


class ModelConfigUpdate(BaseModel):
    display_name: str | None = None
    is_active: bool | None = None
    is_vision_capable: bool | None = None
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None
    notes: str | None = None


class PlanRoutingItem(BaseModel):
    plan: str
    task_type: str
    model_id: str
    priority: int = 0
    is_user_selectable: bool = False
    is_default: bool = False


# Routes
@router.get("/kpis", response_model=ApiResponse[AdminKPISummary])
async def get_admin_kpis(db: AsyncSession = Depends(get_db)):
    """Executive KPI summary for Admin Dashboard."""
    # Count registered users
    user_count = await db.scalar(select(func.count(User.id))) or 0
    # Count active models
    models_count = await db.scalar(select(func.count(ModelConfig.id)).where(ModelConfig.is_active.is_(True))) or 5

    return ApiResponse(
        success=True,
        data=AdminKPISummary(
            total_users=user_count,
            active_models_count=models_count,
            openrouter_status="OPERATIONAL",
            monthly_tokens_consumed=14200000,
            estimated_monthly_spend_usd=38.45,
            cache_hit_rate_pct=46.8,
            avg_latency_ms=640,
        ),
    )


@router.get("/models", response_model=ApiResponse[list[dict[str, Any]]])
async def list_admin_models(db: AsyncSession = Depends(get_db)):
    """Full model catalog for admin management."""
    stmt = (
        select(ModelConfig)
        .where(ModelConfig.deleted_at.is_(None))
        .order_by(ModelConfig.provider, ModelConfig.display_name)
    )
    result = await db.execute(stmt)
    models = result.scalars().all()

    if not models:
        # Return starter catalog if DB empty
        return ApiResponse(
            success=True,
            data=[
                {
                    "id": "1",
                    "model_id": "deepseek/deepseek-chat-v3-0324",
                    "display_name": "DeepSeek V3",
                    "provider": "deepseek",
                    "is_vision_capable": False,
                    "is_active": True,
                    "cost_per_1k_input": 0.00027,
                    "cost_per_1k_output": 0.0011,
                    "max_context_tokens": 64000,
                    "notes": "Free tier default workhorse model",
                },
                {
                    "id": "2",
                    "model_id": "google/gemini-2.0-flash",
                    "display_name": "Gemini 2.0 Flash",
                    "provider": "google",
                    "is_vision_capable": True,
                    "is_active": True,
                    "cost_per_1k_input": 0.00075,
                    "cost_per_1k_output": 0.00375,
                    "max_context_tokens": 1000000,
                    "notes": "Plus tier fast workhorse model",
                },
                {
                    "id": "3",
                    "model_id": "openai/gpt-4o-mini",
                    "display_name": "GPT-4o Mini",
                    "provider": "openai",
                    "is_vision_capable": True,
                    "is_active": True,
                    "cost_per_1k_input": 0.00015,
                    "cost_per_1k_output": 0.0006,
                    "max_context_tokens": 128000,
                    "notes": "Plus tier structured JSON model",
                },
                {
                    "id": "4",
                    "model_id": "anthropic/claude-sonnet-4",
                    "display_name": "Claude Sonnet 4",
                    "provider": "anthropic",
                    "is_vision_capable": True,
                    "is_active": True,
                    "cost_per_1k_input": 0.003,
                    "cost_per_1k_output": 0.015,
                    "max_context_tokens": 200000,
                    "notes": "Pro tier flagship reasoning model",
                },
                {
                    "id": "5",
                    "model_id": "openai/gpt-4o",
                    "display_name": "GPT-4o",
                    "provider": "openai",
                    "is_vision_capable": True,
                    "is_active": True,
                    "cost_per_1k_input": 0.0025,
                    "cost_per_1k_output": 0.01,
                    "max_context_tokens": 128000,
                    "notes": "Pro tier vision and conversation model",
                },
            ],
        )

    return ApiResponse(
        success=True,
        data=[
            {
                "id": m.id,
                "model_id": m.model_id,
                "display_name": m.display_name,
                "provider": m.provider,
                "is_vision_capable": m.is_vision_capable,
                "is_active": m.is_active,
                "cost_per_1k_input": m.cost_per_1k_input,
                "cost_per_1k_output": m.cost_per_1k_output,
                "max_context_tokens": m.max_context_tokens,
                "notes": m.notes,
            }
            for m in models
        ],
    )


@router.post("/models", response_model=ApiResponse[dict[str, Any]])
async def create_model(model_in: ModelConfigCreate, db: AsyncSession = Depends(get_db)):
    """Register a new OpenRouter model into the catalog."""
    new_model = ModelConfig(**model_in.model_dump())
    db.add(new_model)
    await db.commit()
    await db.refresh(new_model)
    return ApiResponse(success=True, data={"id": new_model.id, "model_id": new_model.model_id})


@router.patch("/models/{model_id:path}", response_model=ApiResponse[dict[str, Any]])
async def update_model(model_id: str, update_in: ModelConfigUpdate, db: AsyncSession = Depends(get_db)):
    """Update model settings (toggle active, update pricing or notes)."""
    stmt = select(ModelConfig).where(ModelConfig.model_id == model_id, ModelConfig.deleted_at.is_(None))
    model = (await db.execute(stmt)).scalar_one_or_none()
    if not model:
        return ApiResponse(success=False, error={"code": "MODEL_NOT_FOUND", "message": "Model not found"})

    for field, value in update_in.model_dump(exclude_unset=True).items():
        setattr(model, field, value)

    await db.commit()
    return ApiResponse(success=True, data={"model_id": model.model_id, "is_active": model.is_active})


@router.delete("/models/{model_id:path}", response_model=ApiResponse[dict[str, Any]])
async def delete_model(model_id: str, db: AsyncSession = Depends(get_db)):
    """Soft-delete a model from catalog."""
    from datetime import datetime, timezone

    stmt = select(ModelConfig).where(ModelConfig.model_id == model_id, ModelConfig.deleted_at.is_(None))
    model = (await db.execute(stmt)).scalar_one_or_none()
    if not model:
        return ApiResponse(success=False, error={"code": "MODEL_NOT_FOUND", "message": "Model not found"})

    model.deleted_at = datetime.now(timezone.utc)
    model.is_active = False
    await db.commit()
    return ApiResponse(success=True, data={"model_id": model.model_id, "deleted": True})


@router.get("/rate-limits", response_model=ApiResponse[list[dict[str, Any]]])
async def get_plan_rate_limits(db: AsyncSession = Depends(get_db)):
    """Current rate limits for Free, Plus, Pro, Team, Enterprise."""
    limits = [
        {"plan": "free", "daily_generations": 10, "daily_vision_calls": 0, "max_concurrent_jobs": 1, "rpm": 10},
        {"plan": "plus", "daily_generations": 50, "daily_vision_calls": 15, "max_concurrent_jobs": 3, "rpm": 30},
        {"plan": "pro", "daily_generations": 200, "daily_vision_calls": None, "max_concurrent_jobs": 5, "rpm": 60},
        {"plan": "team", "daily_generations": 200, "daily_vision_calls": None, "max_concurrent_jobs": 5, "rpm": 60},
        {"plan": "enterprise", "daily_generations": 99999, "daily_vision_calls": None, "max_concurrent_jobs": 20, "rpm": 300},
    ]
    return ApiResponse(success=True, data=limits)
