"""
Engineering Audit Event model for Phase 3 Wave 10A: Engineering Audit Ledger Foundation.
Maintains tamper-evident, append-only records of all authoritative engineering operations
with monotonic per-project sequence numbers, canonical payload digests, and hash chaining.

STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- UNKNOWN != SATISFIED
- ZERO SYNTHETIC ENGINEERING SCORING
- Integrity digest != digital signature or proof of authorship.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, UUIDMixin


class AuditEventType(str, Enum):
    # Circuit & Schematic Domain
    CIRCUIT_CREATED = "CIRCUIT_CREATED"
    CIRCUIT_MUTATED = "CIRCUIT_MUTATED"
    CIRCUIT_VALIDATED = "CIRCUIT_VALIDATED"
    COMPONENT_ADDED = "COMPONENT_ADDED"
    COMPONENT_UPDATED = "COMPONENT_UPDATED"
    COMPONENT_DELETED = "COMPONENT_DELETED"
    NET_MUTATED = "NET_MUTATED"
    CONNECTION_MUTATED = "CONNECTION_MUTATED"

    # Proposals & Governance
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    PROPOSAL_APPROVED = "PROPOSAL_APPROVED"
    PROPOSAL_APPLIED = "PROPOSAL_APPLIED"
    PROPOSAL_REJECTED = "PROPOSAL_REJECTED"

    # PCB & Physical Layout
    BOARD_CREATED = "BOARD_CREATED"
    BOARD_MUTATED = "BOARD_MUTATED"
    DRC_EVALUATED = "DRC_EVALUATED"

    # BOM & Supply Chain
    BOM_CREATED = "BOM_CREATED"
    BOM_MUTATED = "BOM_MUTATED"
    PART_CANDIDATE_SELECTED = "PART_CANDIDATE_SELECTED"

    # Manufacturing & DFM
    DFM_RULESET_CREATED = "DFM_RULESET_CREATED"
    DFM_ANALYSIS_EXECUTED = "DFM_ANALYSIS_EXECUTED"
    DFM_PROPOSAL_APPLIED = "DFM_PROPOSAL_APPLIED"

    # Cross-Domain & System Verification
    CROSS_DOMAIN_VALIDATED = "CROSS_DOMAIN_VALIDATED"

    # Requirements, Reviews & Dispositions
    REQUIREMENT_CREATED = "REQUIREMENT_CREATED"
    REQUIREMENT_UPDATED = "REQUIREMENT_UPDATED"
    REQUIREMENT_BASELINE_CREATED = "REQUIREMENT_BASELINE_CREATED"
    REQUIREMENT_MUTATED = "REQUIREMENT_MUTATED"
    DECISION_RECORDED = "DECISION_RECORDED"
    REVIEW_FINDING_WAIVED = "REVIEW_FINDING_WAIVED"
    UNKNOWN_DISPOSED = "UNKNOWN_DISPOSED"
    PHYSICAL_EVIDENCE_RECORDED = "PHYSICAL_EVIDENCE_RECORDED"

    # Future Wave 10B/Release anchors
    RELEASE_EVALUATION_COMPLETED = "RELEASE_EVALUATION_COMPLETED"
    RELEASE_BASELINE_CREATED = "RELEASE_BASELINE_CREATED"


class EngineeringAuditEvent(Base, UUIDMixin):
    """
    Immutable, append-only record of an authoritative engineering event.
    Linked in a per-project SHA-256 hash chain with strictly monotonic sequence numbers.
    """
    __tablename__ = "engineering_audit_events"

    # Multi-tenant and project scoping
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    # Strictly monotonic sequence number per project (1, 2, 3...)
    sequence_number: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Actor attribution
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(64), nullable=False)

    # Event typing & entity references
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    entity_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Payload & Cryptographic Chain Fields
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="64-character SHA-256 hex digest of canonically serialized payload",
    )
    prev_event_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="64-character SHA-256 hex digest of immediate predecessor event in project chain, or 64 zeros for genesis",
    )
    event_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
        doc="64-character SHA-256 hex digest of canonically serialized event header and payload digest",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    project = relationship("Project")

    # Table constraints: Unique monotonic sequence per project
    __table_args__ = (
        UniqueConstraint("project_id", "sequence_number", name="uq_audit_project_sequence"),
    )
