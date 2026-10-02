from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class Job(Base, UUIDMixin, TimestampMixin):
    """Async heavy computation job record."""
    __tablename__ = "jobs"

    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)  # simulation | pcb_vision | risk_analysis
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending | running | done | failed
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0 to 100
    celery_task_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
