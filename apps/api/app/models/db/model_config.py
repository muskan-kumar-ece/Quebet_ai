from sqlalchemy import Boolean, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class ModelConfig(Base, UUIDMixin, TimestampMixin):
    """Catalog of registered OpenRouter models."""
    __tablename__ = "model_configs"

    model_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)  # anthropic, openai, google, deepseek
    is_vision_capable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    cost_per_1k_input: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_1k_output: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_context_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supports_json_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PlanModelAccess(Base, UUIDMixin, TimestampMixin):
    """Mapping of subscription plans and task types to candidate models."""
    __tablename__ = "plan_model_access"

    plan: Mapped[str] = mapped_column(String(32), index=True, nullable=False)  # free, plus, pro, team, enterprise
    task_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # default, risk_score, vision, etc.
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Higher priority executed first
    is_user_selectable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("plan", "task_type", "model_id", name="uq_plan_task_model"),
    )


class PlanRateLimits(Base, UUIDMixin, TimestampMixin):
    """Configurable rate limits per subscription plan."""
    __tablename__ = "plan_rate_limits"

    plan: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    daily_generations: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_vision_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = unlimited
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bff_requests_per_minute: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    api_calls_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = no API access
    max_simulation_components: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_projects: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
