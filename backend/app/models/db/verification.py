from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, TimestampMixin, UUIDMixin


class DesignReviewStatus(str, Enum):
    DRAFT = "DRAFT"
    ANALYSIS_COMPLETE = "ANALYSIS_COMPLETE"
    REVIEW_IN_PROGRESS = "REVIEW_IN_PROGRESS"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    VERIFIED = "VERIFIED"
    BLOCKED = "BLOCKED"
    STALE = "STALE"


class FailureModeCategory(str, Enum):
    OVERPOWER = "OVERPOWER"
    OVERVOLTAGE = "OVERVOLTAGE"
    OVERCURRENT = "OVERCURRENT"
    THERMAL_OVERSTRESS = "THERMAL_OVERSTRESS"
    FLOATING_NODE = "FLOATING_NODE"
    VOLTAGE_DOMAIN_CONFLICT = "VOLTAGE_DOMAIN_CONFLICT"
    MISSING_DECOUPLING = "MISSING_DECOUPLING"
    COMPONENT_RATING_MARGIN = "COMPONENT_RATING_MARGIN"
    SIGNAL_INTEGRITY = "SIGNAL_INTEGRITY"
    POWER_INTEGRITY = "POWER_INTEGRITY"
    STARTUP_BEHAVIOR = "STARTUP_BEHAVIOR"
    TRANSIENT_BEHAVIOR = "TRANSIENT_BEHAVIOR"
    UNKNOWN_COMPONENT_BEHAVIOR = "UNKNOWN_COMPONENT_BEHAVIOR"


class VerificationMethod(str, Enum):
    DETERMINISTIC_CALCULATION = "DETERMINISTIC_CALCULATION"
    SCHEMATIC_REVIEW = "SCHEMATIC_REVIEW"
    DATASHEET_REVIEW = "DATASHEET_REVIEW"
    COMPONENT_RATING_CHECK = "COMPONENT_RATING_CHECK"
    THERMAL_CALCULATION = "THERMAL_CALCULATION"
    MEASUREMENT = "MEASUREMENT"
    BENCH_TEST = "BENCH_TEST"
    SIMULATION = "SIMULATION"
    LAYOUT_REVIEW = "LAYOUT_REVIEW"
    MANUAL_ENGINEERING_REVIEW = "MANUAL_ENGINEERING_REVIEW"


class VerificationStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OperatingCondition(str, Enum):
    NOMINAL = "NOMINAL"
    MINIMUM_INPUT = "MINIMUM_INPUT"
    MAXIMUM_INPUT = "MAXIMUM_INPUT"
    MINIMUM_LOAD = "MINIMUM_LOAD"
    MAXIMUM_LOAD = "MAXIMUM_LOAD"
    STARTUP = "STARTUP"
    STEADY_STATE = "STEADY_STATE"
    TRANSIENT = "TRANSIENT"
    THERMAL_EXTREME = "THERMAL_EXTREME"
    USER_DEFINED = "USER_DEFINED"


class EvidenceType(str, Enum):
    MEASUREMENT = "MEASUREMENT"
    DATASHEET = "DATASHEET"
    CALCULATION = "CALCULATION"
    SCHEMATIC_INSPECTION = "SCHEMATIC_INSPECTION"
    SIMULATION_REPORT = "SIMULATION_REPORT"
    TEST_REPORT = "TEST_REPORT"


class EvidenceStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"
    UNKNOWN = "UNKNOWN"


class EngineeringDesignReview(Base, UUIDMixin, TimestampMixin):
    """
    Authoritative Engineering Design Review domain model.
    Revision-bound to circuit_revision and analysis-bound to analysis_id.
    """
    __tablename__ = "engineering_design_reviews"

    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=DesignReviewStatus.DRAFT.value,
        nullable=False,
    )
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    failure_modes: Mapped[list["EngineeringFailureMode"]] = relationship(
        "EngineeringFailureMode",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="EngineeringFailureMode.created_at",
    )
    verification_requirements: Mapped[list["EngineeringVerificationRequirement"]] = relationship(
        "EngineeringVerificationRequirement",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="EngineeringVerificationRequirement.code",
    )
    test_points: Mapped[list["EngineeringTestPoint"]] = relationship(
        "EngineeringTestPoint",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="EngineeringTestPoint.code",
    )
    audit_events: Mapped[list["EngineeringReviewAuditEvent"]] = relationship(
        "EngineeringReviewAuditEvent",
        back_populates="review",
        cascade="all, delete-orphan",
        order_by="EngineeringReviewAuditEvent.created_at",
    )


class EngineeringFailureMode(Base, UUIDMixin):
    """
    Structured engineering failure mode derived deterministically from circuit topology,
    KB parameters, operating limits, and findings.
    """
    __tablename__ = "engineering_failure_modes"

    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger: Mapped[str] = mapped_column(String(255), nullable=False)
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    consequence: Mapped[str] = mapped_column(Text, nullable=False)
    likelihood: Mapped[str] = mapped_column(String(32), default="MEDIUM", nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="WARNING", nullable=False)
    affected_components: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    affected_nets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    unknowns: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_findings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_rules: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    verification_requirement_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    review: Mapped["EngineeringDesignReview"] = relationship(
        "EngineeringDesignReview",
        back_populates="failure_modes",
    )


class EngineeringVerificationRequirement(Base, UUIDMixin):
    """
    Specific verification item required before an engineering concern is verified.
    """
    __tablename__ = "engineering_verification_requirements"

    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # VR-001, VR-002, etc.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    operating_condition: Mapped[str] = mapped_column(
        String(64),
        default=OperatingCondition.NOMINAL.value,
        nullable=False,
    )
    required_evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=VerificationStatus.NOT_STARTED.value,
        nullable=False,
    )
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    not_applicable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_components: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    affected_nets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    related_rule_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    related_finding_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    unknowns: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    review: Mapped["EngineeringDesignReview"] = relationship(
        "EngineeringDesignReview",
        back_populates="verification_requirements",
    )
    evidence_items: Mapped[list["EngineeringEvidence"]] = relationship(
        "EngineeringEvidence",
        back_populates="requirement",
        cascade="all, delete-orphan",
        order_by="EngineeringEvidence.provided_at",
    )


class EngineeringEvidence(Base, UUIDMixin):
    """
    Evidence record attached to a verification requirement.
    """
    __tablename__ = "engineering_evidence"

    verification_requirement_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_verification_requirements.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=EvidenceStatus.VALID.value,
        nullable=False,
    )
    confidence: Mapped[str] = mapped_column(String(32), default="HIGH", nullable=False)
    provided_by: Mapped[str] = mapped_column(String(36), nullable=False)
    provided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    source_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    instrument: Mapped[str | None] = mapped_column(String(128), nullable=True)
    instrument_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    instrument_serial: Mapped[str | None] = mapped_column(String(128), nullable=True)
    calibration_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    calibration_status: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    measurement_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    circuit_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    circuit_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    requirement: Mapped["EngineeringVerificationRequirement"] = relationship(
        "EngineeringVerificationRequirement",
        back_populates="evidence_items",
    )


class EngineeringTestPoint(Base, UUIDMixin):
    """
    Suggested physical test point or measurement node for laboratory verification.
    """
    __tablename__ = "engineering_test_points"

    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)  # TP-001, TP-002, etc.
    target_net: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_component: Mapped[str | None] = mapped_column(String(128), nullable=True)
    measurement: Mapped[str] = mapped_column(String(255), nullable=False)
    expected_basis: Mapped[str] = mapped_column(Text, nullable=False)
    instrumentation: Mapped[str] = mapped_column(String(128), nullable=False)
    operating_condition: Mapped[str] = mapped_column(
        String(64),
        default=OperatingCondition.NOMINAL.value,
        nullable=False,
    )
    related_requirement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    review: Mapped["EngineeringDesignReview"] = relationship(
        "EngineeringDesignReview",
        back_populates="test_points",
    )


class EngineeringReviewAuditEvent(Base, UUIDMixin):
    """
    Immutable audit event tracking lifecycle, evidence, and verification actions.
    """
    __tablename__ = "engineering_review_audit_events"

    review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_design_reviews.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    previous_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    review: Mapped["EngineeringDesignReview"] = relationship(
        "EngineeringDesignReview",
        back_populates="audit_events",
    )
