"""
Database models for Phase 3 Wave 8: Advanced Engineering Validation, Cross-Domain Consistency & System-Level Verification.
Maintains canonical cross-domain validation records, multi-domain integrity tracking, and staleness detection.
STRICT INVARIANT: UNKNOWN != PASS. Zero synthetic engineering scoring.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base, TimestampMixin, UUIDMixin


class CrossDomainStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CrossDomainSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CrossDomainValidationStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    STALE = "STALE"


class SourceClassification(str, Enum):
    CALCULATED = "CALCULATED"
    SIMULATED = "SIMULATED"
    HISTORICAL = "HISTORICAL"
    USER_ASSERTED = "USER_ASSERTED"
    PHYSICALLY_MEASURED = "PHYSICALLY_MEASURED"
    HARDWARE_VERIFIED = "HARDWARE_VERIFIED"
    MANUFACTURER_CONFIRMED = "MANUFACTURER_CONFIRMED"
    UNKNOWN = "UNKNOWN"


class ValidationDomain(str, Enum):
    SCHEMATIC = "SCHEMATIC"
    PCB = "PCB"
    BOM = "BOM"
    SIMULATION = "SIMULATION"
    DFM = "DFM"
    REQUIREMENTS = "REQUIREMENTS"
    VERIFICATION = "VERIFICATION"
    POWER_THERMAL = "POWER_THERMAL"
    DATASHEET = "DATASHEET"


class CrossDomainValidationRecord(Base, UUIDMixin, TimestampMixin):
    """
    Immutable or revisable record of a cross-domain engineering validation execution.
    Tracks contradictory assumptions and inconsistencies across schematic, PCB, BOM,
    simulation, DFM, requirements, and verification domains.
    """
    __tablename__ = "cross_domain_validation_records"

    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    board_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    bom_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_boms.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    validation_status: Mapped[str] = mapped_column(
        String(32),
        default=CrossDomainValidationStatus.COMPLETED,
        nullable=False,
    )
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    domain_snapshots: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    staleness_reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    snapshot_digest: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
        doc="64-character SHA-256 canonical digest (PROVENANCE_AND_INTEGRITY_DIGEST; NOT a digital signature)",
    )

    # Relationships
    project = relationship("Project")
    circuit = relationship("Circuit")
    board = relationship("EngineeringBoard")
    bom = relationship("EngineeringBOM")
