from enum import Enum
from sqlalchemy import Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class AnalysisStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


class AnalysisConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CircuitAnalysis(Base, UUIDMixin, TimestampMixin):
    """
    Immutable snapshot of deterministic engineering analysis performed on a circuit revision.
    Contains verified graph metrics, deterministic physical calculations, rule engine findings,
    explicit unknowns, and engineering assumptions.
    """

    __tablename__ = "circuit_analyses"

    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=AnalysisStatus.COMPLETE.value,
        index=True,
        nullable=False,
    )
    confidence: Mapped[str] = mapped_column(
        String(32),
        default=AnalysisConfidence.HIGH.value,
        nullable=False,
    )
    graph_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    calculations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    findings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    unknowns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    assumptions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Relationships
    circuit = relationship("Circuit", back_populates="analyses")
