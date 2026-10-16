from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    VALIDATING = "VALIDATING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    STALE = "STALE"


class EngineeringProposal(Base, UUIDMixin, TimestampMixin):
    """
    Typed engineering proposal abstraction.
    Acts as the authoritative bridge between AI agents / user drafts and deterministic circuit state.
    AI proposals cannot mutate circuit data without explicit validation and user approval.
    Tied to base_revision and analysis_id for stale proposal protection.
    """

    __tablename__ = "engineering_proposals"

    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="AI", nullable=False)  # AI | USER | HEURISTIC
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ProposalStatus.PROPOSED.value,
        index=True,
        nullable=False,
    )
    base_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    objective_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    operations: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    assumptions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    validation_result: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    findings_resolved: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    findings_introduced: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    constraints_evaluated: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    engineering_effects: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    unknowns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), default="HIGH", nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, nullable=True)

    # Relationships
    circuit = relationship("Circuit", back_populates="proposals")
