from pydantic import BaseModel


class ModelOption(BaseModel):
    """User-selectable model for UI dropdowns."""
    model_id: str
    display_name: str
    provider: str
    is_vision_capable: bool
    is_default: bool = False
    badge: str | None = None  # e.g., "FAST", "FLAGSHIP", "REASONING"


class ModelListResponse(BaseModel):
    """Available models response tailored to the requesting user's plan."""
    user_plan: str
    active_model: str
    models: list[ModelOption]
    can_switch_models: bool
    daily_limit: int
    daily_used: int
