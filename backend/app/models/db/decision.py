from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
import uuid
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, UUIDMixin, TimestampMixin, AuditTimestampMixin


class RequirementCategory(str, Enum):
    FUNCTIONAL = "FUNCTIONAL"
    ELECTRICAL = "ELECTRICAL"
    POWER = "POWER"
    THERMAL = "THERMAL"
    MECHANICAL = "MECHANICAL"
    PERFORMANCE = "PERFORMANCE"
    TIMING = "TIMING"
    COMMUNICATION = "COMMUNICATION"
    SAFETY = "SAFETY"
    RELIABILITY = "RELIABILITY"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    REGULATORY = "REGULATORY"
    INTERFACE = "INTERFACE"
    SECURITY = "SECURITY"
    MAINTAINABILITY = "MAINTAINABILITY"
    COST = "COST"
    SIZE = "SIZE"
    WEIGHT = "WEIGHT"
    OTHER = "OTHER"


class RequirementPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RequirementSourceType(str, Enum):
    CUSTOMER_SPEC = "CUSTOMER_SPEC"
    STANDARD = "STANDARD"
    DATASHEET = "DATASHEET"
    INTERNAL_SPEC = "INTERNAL_SPEC"
    SAFETY_NORM = "SAFETY_NORM"
    DERIVED = "DERIVED"
    OTHER = "OTHER"


class RequirementStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SATISFIED = "SATISFIED"
    PARTIALLY_SATISFIED = "PARTIALLY_SATISFIED"
    VIOLATED = "VIOLATED"
    UNKNOWN = "UNKNOWN"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"


class AssumptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INVALIDATED = "INVALIDATED"
    VERIFIED = "VERIFIED"
    UNKNOWN = "UNKNOWN"
    SUPERSEDED = "SUPERSEDED"


class AssumptionImpact(str, Enum):
    NON_BLOCKING = "NON_BLOCKING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKING = "BLOCKING"


class DecisionType(str, Enum):
    ARCHITECTURE = "ARCHITECTURE"
    COMPONENT_SELECTION = "COMPONENT_SELECTION"
    INTERFACE = "INTERFACE"
    POWER = "POWER"
    THERMAL = "THERMAL"
    SAFETY = "SAFETY"
    RELIABILITY = "RELIABILITY"
    PERFORMANCE = "PERFORMANCE"
    COST = "COST"
    TRADEOFF = "TRADEOFF"
    REQUIREMENT = "REQUIREMENT"
    OTHER = "OTHER"


class DecisionStatus(str, Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    PENDING_DECISION = "PENDING_DECISION"
    DECIDED = "DECIDED"
    RATIFIED = "RATIFIED"
    IMPLEMENTATION_REQUIRED = "IMPLEMENTATION_REQUIRED"
    IMPLEMENTED = "IMPLEMENTED"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    CLOSED = "CLOSED"
    SUPERSEDED = "SUPERSEDED"
    STALE = "STALE"
    BLOCKED = "BLOCKED"


class AlternativeStatus(str, Enum):
    CONSIDERED = "CONSIDERED"
    ELIMINATED = "ELIMINATED"
    SELECTED_BY_ENGINEER = "SELECTED_BY_ENGINEER"
    NOT_SELECTED = "NOT_SELECTED"
    PENDING = "PENDING"


class EliminationReason(str, Enum):
    HARD_CONSTRAINT_VIOLATION = "HARD_CONSTRAINT_VIOLATION"
    REQUIREMENT_VIOLATION = "REQUIREMENT_VIOLATION"
    INTERFACE_INCOMPATIBILITY = "INTERFACE_INCOMPATIBILITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNSUPPORTED_OPERATING_RANGE = "UNSUPPORTED_OPERATING_RANGE"
    VERIFICATION_BURDEN = "VERIFICATION_BURDEN"
    UNRESOLVED_UNKNOWN = "UNRESOLVED_UNKNOWN"
    USER_REJECTED = "USER_REJECTED"


class ReviewStatus(str, Enum):
    OPEN = "OPEN"
    IN_REVIEW = "IN_REVIEW"
    BLOCKED = "BLOCKED"
    DECISION_PENDING = "DECISION_PENDING"
    DECIDED = "DECIDED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    CLOSED = "CLOSED"
    STALE = "STALE"


class ReviewRole(str, Enum):
    ENGINEER = "ENGINEER"
    SYSTEM_ARCHITECT = "SYSTEM_ARCHITECT"
    ELECTRICAL_ENGINEER = "ELECTRICAL_ENGINEER"
    FIRMWARE_ENGINEER = "FIRMWARE_ENGINEER"
    MECHANICAL_ENGINEER = "MECHANICAL_ENGINEER"
    THERMAL_ENGINEER = "THERMAL_ENGINEER"
    SAFETY_REVIEWER = "SAFETY_REVIEWER"
    VERIFICATION_ENGINEER = "VERIFICATION_ENGINEER"
    OBSERVER = "OBSERVER"


class CheckpointStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ReviewFindingStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    RESOLVED = "RESOLVED"
    WAIVED = "WAIVED"
    SUPERSEDED = "SUPERSEDED"


class ReviewActionStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETE = "COMPLETE"
    CANCELLED = "CANCELLED"


class QuestionStatus(str, Enum):
    OPEN = "OPEN"
    ANSWERED = "ANSWERED"
    BLOCKED = "BLOCKED"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"


class UnknownDispositionStatus(str, Enum):
    OPEN = "OPEN"
    ACCEPTED = "ACCEPTED"
    RESOLVED = "RESOLVED"
    BLOCKING = "BLOCKING"
    SUPERSEDED = "SUPERSEDED"


# 1. EngineeringRequirement
class EngineeringRequirement(Base, UUIDMixin, AuditTimestampMixin):
    """
    First-class engineering requirement supporting functional, quantitative,
    relational, conditional, and scenario-specific expressions with hierarchical decomposition.
    """
    __tablename__ = "engineering_requirements"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    parent_requirement_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_requirements.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    requirement_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(64),
        default=RequirementCategory.FUNCTIONAL.value,
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(
        String(32),
        default=RequirementPriority.MEDIUM.value,
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(64),
        default=RequirementSourceType.INTERNAL_SPEC.value,
        nullable=False,
    )
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=RequirementStatus.ACTIVE.value,
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    expression: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Self-referential hierarchy
    parent_requirement = relationship(
        "EngineeringRequirement",
        remote_side="EngineeringRequirement.id",
        backref="derived_requirements",
    )


# 2. EngineeringRequirementBaseline
class EngineeringRequirementBaseline(Base, UUIDMixin):
    """
    Immutable requirement baseline frozen at a specific system revision.
    Historical design decisions must remain bound to the baseline under which they were decided.
    """
    __tablename__ = "engineering_requirement_baselines"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    system_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    baseline_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # SHA-256
    requirement_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    requirement_revisions: Mapped[dict[str, int]] = mapped_column(JSON, default=dict, nullable=False)
    knowledge_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# 3. EngineeringAssumption
class EngineeringAssumption(Base, UUIDMixin, AuditTimestampMixin):
    """
    Formal system-level engineering assumption with provenance, basis, status,
    and impact severity (BLOCKING, REVIEW_REQUIRED, NON_BLOCKING).
    """
    __tablename__ = "engineering_assumptions"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    requirement_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_requirements.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    basis: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=AssumptionStatus.ACTIVE.value,
        nullable=False,
    )
    impact: Mapped[str] = mapped_column(
        String(32),
        default=AssumptionImpact.REVIEW_REQUIRED.value,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)


# 4. EngineeringDecisionRecord
class EngineeringDecisionRecord(Base, UUIDMixin, AuditTimestampMixin):
    """
    Formal record of an engineering decision made by an authorized human engineer.
    Bound to system revision and requirement baseline.
    """
    __tablename__ = "engineering_decision_records"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    decision_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    decision_type: Mapped[str] = mapped_column(
        String(64),
        default=DecisionType.ARCHITECTURE.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=DecisionStatus.DRAFT.value,
        nullable=False,
    )
    system_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    requirement_baseline_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_requirement_baselines.id", ondelete="SET NULL"),
        nullable=True,
    )
    analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    selected_alternative_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_decision_records.id", ondelete="SET NULL"),
        nullable=True,
    )

    decision_context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    rationale: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    alternatives = relationship(
        "EngineeringDecisionAlternative",
        back_populates="decision",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tradeoffs = relationship(
        "EngineeringTradeoff",
        back_populates="decision",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    questions = relationship(
        "EngineeringDecisionQuestion",
        back_populates="decision",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# 5. EngineeringDecisionAlternative
class EngineeringDecisionAlternative(Base, UUIDMixin):
    """
    Design alternative considered within an engineering decision.
    References Wave 8 candidates where available.
    """
    __tablename__ = "engineering_decision_alternatives"

    decision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_decision_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    candidate_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_system_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=AlternativeStatus.CONSIDERED.value,
        nullable=False,
    )
    elimination_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    engineering_effects: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    requirement_effects: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    verification_effects: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    failure_effects: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    tradeoffs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    unknowns: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    decision = relationship("EngineeringDecisionRecord", back_populates="alternatives")


# 6. EngineeringTradeoff
class EngineeringTradeoff(Base, UUIDMixin):
    """
    Structured pairwise engineering trade-off comparison between two alternatives
    along a specific engineering dimension. Zero composite scoring.
    """
    __tablename__ = "engineering_tradeoffs"

    decision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_decision_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    dimension: Mapped[str] = mapped_column(String(64), nullable=False)
    alternative_a_id: Mapped[str] = mapped_column(String(36), nullable=False)
    alternative_b_id: Mapped[str] = mapped_column(String(36), nullable=False)
    advantage_a: Mapped[str] = mapped_column(Text, nullable=False)
    disadvantage_a: Mapped[str] = mapped_column(Text, nullable=False)
    advantage_b: Mapped[str] = mapped_column(Text, nullable=False)
    disadvantage_b: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    unknowns: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    decision = relationship("EngineeringDecisionRecord", back_populates="tradeoffs")


# 7. EngineeringDesignReviewSession
class EngineeringDesignReviewSession(Base, UUIDMixin, AuditTimestampMixin):
    """
    Formal engineering design review grouping participants, checkpoints, findings,
    actions, and decision records for a system revision.
    """
    __tablename__ = "engineering_design_review_sessions"

    system_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_systems.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    decision_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_decision_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    requirement_baseline_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_requirement_baselines.id", ondelete="SET NULL"),
        nullable=True,
    )
    system_revision: Mapped[int] = mapped_column(Integer, nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ReviewStatus.OPEN.value,
        nullable=False,
    )
    chairperson: Mapped[str] = mapped_column(String(36), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    participants = relationship(
        "EngineeringReviewParticipant",
        back_populates="review",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    checkpoints = relationship(
        "EngineeringReviewCheckpoint",
        back_populates="review",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    findings = relationship(
        "EngineeringReviewFinding",
        back_populates="review",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    actions = relationship(
        "EngineeringReviewAction",
        back_populates="review",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


# 8. EngineeringReviewParticipant
class EngineeringReviewParticipant(Base, UUIDMixin):
    """
    Participant in a design review with assigned engineering role.
    """
    __tablename__ = "engineering_review_participants"

    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_design_review_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(
        String(64),
        default=ReviewRole.ENGINEER.value,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    review = relationship("EngineeringDesignReviewSession", back_populates="participants")


# 9. EngineeringReviewCheckpoint
class EngineeringReviewCheckpoint(Base, UUIDMixin):
    """
    Formal review checklist checkpoint. UNKNOWN != PASS.
    """
    __tablename__ = "engineering_review_checkpoints"

    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_design_review_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    checkpoint_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=CheckpointStatus.UNKNOWN.value,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    review = relationship("EngineeringDesignReviewSession", back_populates="checkpoints")


# 10. EngineeringReviewFinding
class EngineeringReviewFinding(Base, UUIDMixin):
    """
    Review finding linked to Wave 5 or Wave 7/8 findings.
    Waiving a finding requires explicit human authorization.
    """
    __tablename__ = "engineering_review_findings"

    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_design_review_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    finding_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_analysis: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_requirement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    affected_subsystem_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ReviewFindingStatus.OPEN.value,
        nullable=False,
    )
    waiver_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    waived_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    review = relationship("EngineeringDesignReviewSession", back_populates="findings")


# 11. EngineeringReviewAction
class EngineeringReviewAction(Base, UUIDMixin, AuditTimestampMixin):
    """
    Formal action item assigned during design review.
    """
    __tablename__ = "engineering_review_actions"

    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_design_review_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="MEDIUM", nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ReviewActionStatus.OPEN.value,
        nullable=False,
    )
    linked_requirement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    linked_finding_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    linked_verification_requirement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    review = relationship("EngineeringDesignReviewSession", back_populates="actions")


# 12. EngineeringDecisionQuestion
class EngineeringDecisionQuestion(Base, UUIDMixin):
    """
    First-class unresolved information item. Blocking questions prevent decision closure.
    """
    __tablename__ = "engineering_decision_questions"

    decision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_decision_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    review_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    affected_object: Mapped[str | None] = mapped_column(String(128), nullable=True)
    affected_requirement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    affected_analysis_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    blocking: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=QuestionStatus.OPEN.value,
        nullable=False,
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    decision = relationship("EngineeringDecisionRecord", back_populates="questions")


# 13. EngineeringUnknownDisposition
class EngineeringUnknownDisposition(Base, UUIDMixin):
    """
    Explicit human acceptance or disposition of an unknown.
    AI cannot accept unknowns autonomously.
    """
    __tablename__ = "engineering_unknown_dispositions"

    decision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_decision_records.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    unknown_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=UnknownDispositionStatus.ACCEPTED.value,
        nullable=False,
    )
    actor: Mapped[str] = mapped_column(String(36), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    affected_requirement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
