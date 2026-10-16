"""
Database models for Phase 3 Wave 10C: Deterministic Release Gate Engine and Frozen Release Baselines.
Maintains deterministic release gate evaluation records and immutable release baselines.

STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- AUTONOMOUS MUTATION = DISABLED
- AUTONOMOUS APPROVAL = DISABLED
- AUTONOMOUS VERIFICATION = DISABLED
- UNKNOWN != SATISFIED
- CALCULATED != PHYSICALLY VERIFIED
- ZERO SYNTHETIC ENGINEERING SCORING
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, TimestampMixin, UUIDMixin


class ReleaseGateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OverallReadinessState(str, Enum):
    READY_FOR_RELEASE = "READY_FOR_RELEASE"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


class EngineeringReleaseEvaluation(Base, UUIDMixin, TimestampMixin):
    """
    Structured, deterministic record of an engineering release gate evaluation.
    Evaluates gates RG-01 through RG-09 across active engineering state.
    """
    __tablename__ = "engineering_release_evaluations"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    evaluator_version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    project_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    overall_readiness: Mapped[str] = mapped_column(
        String(32),
        default=OverallReadinessState.NOT_READY.value,
        nullable=False,
    )

    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    state_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    gate_results: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    blocking_findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    missing_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    stale_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    audit_chain_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    audit_chain_head_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audit_chain_sequence: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    audit_chain_trusted_anchor_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    evaluated_by_id: Mapped[str] = mapped_column(String(36), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    project = relationship("Project")
    baselines = relationship("EngineeringReleaseBaseline", back_populates="evaluation")


class EngineeringReleaseBaseline(Base, UUIDMixin, TimestampMixin):
    """
    Immutable, reproducible snapshot of an engineering release authorized by an authenticated human engineer.
    Freezes all 9 gate outcomes, domain entity digests, audit chain anchors, and human release authority.
    """
    __tablename__ = "engineering_release_baselines"

    release_tag: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    evaluation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_release_evaluations.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    project_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    circuit_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    circuit_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    circuit_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)

    board_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    board_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    board_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)

    bom_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    bom_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bom_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)

    audit_chain_head_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    audit_chain_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    audit_chain_trusted_anchor_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    evaluation_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    canonical_snapshot_digest: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
        doc="Deterministic SHA-256 integrity fingerprint (NOT a digital signature)",
    )

    authorized_by_id: Mapped[str] = mapped_column(String(36), nullable=False)
    authorized_by_role: Mapped[str] = mapped_column(String(64), nullable=False)
    authorized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    release_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    exceptions_approved: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "release_tag", name="uq_release_project_tag"),
    )

    project = relationship("Project")
    evaluation = relationship("EngineeringReleaseEvaluation", back_populates="baselines")
