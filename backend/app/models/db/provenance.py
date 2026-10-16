from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, UUIDMixin, AuditTimestampMixin


class KnowledgeClassification(str, Enum):
    AUTHORITATIVE_SOURCE = "AUTHORITATIVE_SOURCE"
    DERIVED_ENGINEERING_FACT = "DERIVED_ENGINEERING_FACT"
    CALCULATED_RESULT = "CALCULATED_RESULT"
    HISTORICAL_EXPERIENCE = "HISTORICAL_EXPERIENCE"
    AI_GENERATED_EXPLANATION = "AI_GENERATED_EXPLANATION"
    USER_ASSERTION = "USER_ASSERTION"
    UNKNOWN = "UNKNOWN"


class ParameterCategory(str, Enum):
    OPERATING_LIMIT = "OPERATING_LIMIT"
    ABSOLUTE_MAXIMUM = "ABSOLUTE_MAXIMUM"
    TYPICAL_VALUE = "TYPICAL_VALUE"
    MINIMUM = "MINIMUM"
    MAXIMUM = "MAXIMUM"
    PIN_DEFINITION = "PIN_DEFINITION"
    APPLICATION_CONSTRAINT = "APPLICATION_CONSTRAINT"
    REFERENCE_DESIGN = "REFERENCE_DESIGN"


class SourceType(str, Enum):
    DATASHEET = "DATASHEET"
    APPLICATION_NOTE = "APPLICATION_NOTE"
    REFERENCE_DESIGN = "REFERENCE_DESIGN"
    ENGINEERING_STANDARD = "ENGINEERING_STANDARD"
    TEXTBOOK = "TEXTBOOK"
    MANUFACTURER_DOCUMENT = "MANUFACTURER_DOCUMENT"
    MEASUREMENT = "MEASUREMENT"
    SIMULATION = "SIMULATION"
    USER_PROVIDED = "USER_PROVIDED"
    INTERNAL_ENGINEERING_RECORD = "INTERNAL_ENGINEERING_RECORD"


class SourceTrustLevel(str, Enum):
    MANUFACTURER_PRIMARY = "MANUFACTURER_PRIMARY"
    STANDARD_BODY = "STANDARD_BODY"
    MEASURED_ENGINEERING_DATA = "MEASURED_ENGINEERING_DATA"
    INTERNAL_VALIDATED = "INTERNAL_VALIDATED"
    SECONDARY_REFERENCE = "SECONDARY_REFERENCE"
    USER_PROVIDED = "USER_PROVIDED"
    UNVERIFIED = "UNVERIFIED"


class SourceStatus(str, Enum):
    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"
    DEPRECATED = "DEPRECATED"
    DRAFT = "DRAFT"


class KnowledgeStatus(str, Enum):
    VERIFIED = "VERIFIED"
    VALIDATED = "VALIDATED"
    USER_PROVIDED = "USER_PROVIDED"
    INFERRED = "INFERRED"
    UNKNOWN = "UNKNOWN"
    SUPERSEDED = "SUPERSEDED"
    REJECTED = "REJECTED"


class KnowledgeApplicability(str, Enum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONDITIONALLY_APPLICABLE = "CONDITIONALLY_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class CalibrationStatus(str, Enum):
    CALIBRATED = "CALIBRATED"
    EXPIRED = "EXPIRED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


class EngineeringSource(Base, UUIDMixin, AuditTimestampMixin):
    """
    Authoritative reference document supporting engineering parameters, ratings, and rules.
    Carries deterministic document digest (SHA-256), trust level, revision, and supersession links.
    """
    __tablename__ = "engineering_sources"

    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), nullable=False)
    document_identifier: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    revision: Mapped[str] = mapped_column(String(64), default="Rev A", nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    publication_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uri: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256
    trust_level: Mapped[str] = mapped_column(
        String(64),
        default=SourceTrustLevel.UNVERIFIED.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=SourceStatus.CURRENT.value,
        nullable=False,
    )
    supersedes_source_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    knowledge_records = relationship(
        "EngineeringKnowledgeRecord",
        back_populates="source",
        cascade="all, delete-orphan",
    )


class EngineeringKnowledgeRecord(Base, UUIDMixin, AuditTimestampMixin):
    """
    Atomic engineering fact or specification extracted from an engineering source.
    Stores parameter, value, unit, operating conditions, and validity status.
    """
    __tablename__ = "engineering_knowledge_records"

    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    source_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_sources.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    domain: Mapped[str] = mapped_column(String(64), default="SEMICONDUCTOR", nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), default="COMPONENT", nullable=False)
    subject_identifier: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    parameter: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    classification: Mapped[str] = mapped_column(
        String(64),
        default=KnowledgeClassification.AUTHORITATIVE_SOURCE.value,
        nullable=False,
    )
    parameter_category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    raw_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_location: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_conflicting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    conflict_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    valid_range: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=KnowledgeStatus.VERIFIED.value,
        nullable=False,
    )
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    supersedes_knowledge_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_knowledge_records.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    source = relationship("EngineeringSource", back_populates="knowledge_records", lazy="selectin")


class EngineeringKnowledgeSnapshot(Base, UUIDMixin):
    """
    Immutable snapshot of knowledge records active during a specific circuit analysis.
    Guarantees strict reproducibility of deterministic engineering evaluations.
    """
    __tablename__ = "engineering_knowledge_snapshots"

    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    snapshot_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # SHA-256
    knowledge_record_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class EngineeringAnalysisProvenance(Base, UUIDMixin):
    """
    Immutable provenance record binding a circuit analysis to its exact engine versions,
    rule-set version, knowledge snapshot, inputs, and assumptions.
    """
    __tablename__ = "engineering_analysis_provenances"

    analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuit_analyses.id", ondelete="CASCADE"),
        index=True,
        unique=True,
        nullable=False,
    )
    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    engine_versions: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    knowledge_snapshot_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_knowledge_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_values: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    assumptions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    calculation_methods: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
