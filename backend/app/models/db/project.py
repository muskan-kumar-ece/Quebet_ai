from typing import Any
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class Project(Base, UUIDMixin, TimestampMixin):
    """User electronic hardware project."""
    __tablename__ = "projects"

    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    module_type: Mapped[str] = mapped_column(String(64), default="design", nullable=False)  # design | analysis | troubleshoot
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    circuit_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
