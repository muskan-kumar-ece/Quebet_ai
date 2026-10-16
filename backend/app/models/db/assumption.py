from enum import Enum
from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class AssumptionSource(str, Enum):
    USER = "user"
    DATASHEET = "datasheet"
    KNOWLEDGE_BASE = "knowledge_base"
    ENGINEERING_RULE = "engineering_rule"
    AI_INFERENCE = "ai_inference"
    DEFAULT = "default"


class Assumption(Base, UUIDMixin, TimestampMixin):
    """
    Explicitly tracked engineering assumption with provenance, source confidence,
    and user confirmation tracking.
    """

    __tablename__ = "assumptions"

    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(
        String(32),
        default=AssumptionSource.AI_INFERENCE.value,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)  # 0.0 to 1.0
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    circuit = relationship("Circuit", back_populates="assumptions")
