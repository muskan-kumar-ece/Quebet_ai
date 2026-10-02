from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class PlanType(str, Enum):
    FREE = "free"
    PLUS = "plus"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Nullable for OAuth users
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(String(32), default=PlanType.FREE.value, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    skill_level: Mapped[str] = mapped_column(String(32), default="beginner", nullable=False)
    preferred_model: Mapped[str | None] = mapped_column(String(128), nullable=True)  # User custom OpenRouter model

    daily_generation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_count_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
