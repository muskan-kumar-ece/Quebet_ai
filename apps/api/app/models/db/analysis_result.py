from typing import Any
from sqlalchemy import Boolean, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class AnalysisResult(Base, UUIDMixin, TimestampMixin):
    """Saved analysis output (Risk Score, Thermal, EMI, Failure Prediction)."""
    __tablename__ = "analysis_results"

    project_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    analysis_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # risk_score | failure_prediction | thermal
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
