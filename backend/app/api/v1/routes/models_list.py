from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, get_optional_user
from app.models.schemas.common import ApiResponse
from app.models.schemas.model_config import ModelListResponse, ModelOption
from app.repositories.model_repo import model_repo

router = APIRouter(prefix="/models", tags=["AI Models"])

# Default fallback model catalog per plan
DEFAULT_CATALOG: dict[str, list[dict]] = {
    "free": [
        {
            "model_id": "deepseek/deepseek-chat-v3-0324",
            "display_name": "DeepSeek V3",
            "provider": "deepseek",
            "is_vision_capable": False,
            "badge": "DEFAULT",
        }
    ],
    "plus": [
        {
            "model_id": "google/gemini-2.0-flash",
            "display_name": "Gemini 2.0 Flash",
            "provider": "google",
            "is_vision_capable": True,
            "badge": "FAST",
            "is_default": True,
        },
        {
            "model_id": "openai/gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "provider": "openai",
            "is_vision_capable": True,
            "badge": "STRUCTURED",
        },
        {
            "model_id": "deepseek/deepseek-chat-v3-0324",
            "display_name": "DeepSeek V3",
            "provider": "deepseek",
            "is_vision_capable": False,
            "badge": "REASONING",
        },
    ],
    "pro": [
        {
            "model_id": "anthropic/claude-sonnet-4",
            "display_name": "Claude Sonnet 4",
            "provider": "anthropic",
            "is_vision_capable": True,
            "badge": "FLAGSHIP",
            "is_default": True,
        },
        {
            "model_id": "openai/gpt-4o",
            "display_name": "GPT-4o",
            "provider": "openai",
            "is_vision_capable": True,
            "badge": "VISION",
        },
        {
            "model_id": "google/gemini-2.5-pro",
            "display_name": "Gemini 2.5 Pro",
            "provider": "google",
            "is_vision_capable": True,
            "badge": "LONG CONTEXT",
        },
        {
            "model_id": "google/gemini-2.0-flash",
            "display_name": "Gemini 2.0 Flash",
            "provider": "google",
            "is_vision_capable": True,
            "badge": "FAST",
        },
        {
            "model_id": "openai/gpt-4o-mini",
            "display_name": "GPT-4o Mini",
            "provider": "openai",
            "is_vision_capable": True,
        },
    ],
}


@router.get("", response_model=ApiResponse[ModelListResponse])
async def list_available_models(
    current_user: AuthenticatedUser | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns accessible OpenRouter models based on the caller's verified subscription plan.
    Authorization is derived strictly from server-side authenticated identity.
    Anonymous callers default strictly to the 'free' tier catalog.
    """
    plan = current_user.plan.lower() if current_user else "free"
    can_switch = plan in ("plus", "pro", "team", "enterprise")

    # Try database first
    db_models = await model_repo.get_models_for_plan(db, plan)

    if db_models:
        options = [
            ModelOption(
                model_id=cfg.model_id,
                display_name=cfg.display_name,
                provider=cfg.provider,
                is_vision_capable=cfg.is_vision_capable,
                is_default=is_def,
            )
            for cfg, is_def in db_models
        ]
        active_model = next((o.model_id for o in options if o.is_default), options[0].model_id)
    else:
        # Fallback to in-memory plan catalog
        raw_options = DEFAULT_CATALOG.get(plan, DEFAULT_CATALOG["free"])
        options = [ModelOption(**m) for m in raw_options]
        active_model = options[0].model_id

    limits = {
        "free": 10,
        "plus": 50,
        "pro": 200,
        "team": 200,
        "enterprise": 99999,
    }

    return ApiResponse(
        success=True,
        data=ModelListResponse(
            user_plan=plan,
            active_model=active_model,
            models=options,
            can_switch_models=can_switch,
            daily_limit=limits.get(plan, 10),
            daily_used=0,
        ),
    )
