from datetime import datetime
from enum import Enum
from typing import Any
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin
from app.models.db.proposal import ProposalStatus


class ManufacturingRuleCategory(str, Enum):
    FABRICATION = "FABRICATION"
    ASSEMBLY = "ASSEMBLY"
    SOLDER_MASK = "SOLDER_MASK"
    SILKSCREEN = "SILKSCREEN"
    DRILL_VIA = "DRILL_VIA"
    CLEARANCE = "CLEARANCE"
    BOM_CONSISTENCY = "BOM_CONSISTENCY"
    COMPONENT_PLACEMENT = "COMPONENT_PLACEMENT"


class ManufacturingFindingStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ManufacturingAnalysisStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    STALE = "STALE"


class ManufacturingRuleSet(Base, UUIDMixin, TimestampMixin):
    """
    Authoritative fabrication and assembly constraint ruleset.
    Contains explicit dimensional bounds, clearance limits, annular rings,
    and assembly requirements with rigorous revision and provenance tracking.
    """
    __tablename__ = "manufacturing_rule_sets"

    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source: Mapped[str] = mapped_column(String(128), default="STANDARD", nullable=False)
    source_revision: Mapped[str] = mapped_column(String(64), default="REV_A", nullable=False)
    source_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    analyses = relationship("ManufacturingAnalysisRecord", back_populates="rule_set", cascade="all, delete-orphan")


class ManufacturingAnalysisRecord(Base, UUIDMixin, TimestampMixin):
    """
    Deterministic record of DFM/DFA rule verification against a specific EngineeringBoard revision.
    Maintains categorical findings, quantitative margin differentials, and provenance digest.
    STRICT INVARIANT: No synthetic manufacturability scores (0-100) or fabricator rankings.
    """
    __tablename__ = "manufacturing_analyses"

    board_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    board_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    rule_set_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("manufacturing_rule_sets.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    rule_set_revision: Mapped[str] = mapped_column(String(64), default="REV_A", nullable=False)

    status: Mapped[str] = mapped_column(
        String(32),
        default=ManufacturingAnalysisStatus.COMPLETED.value,
        index=True,
        nullable=False,
    )

    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    provenance_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    board = relationship("EngineeringBoard", backref="dfm_analyses")
    circuit = relationship("Circuit", backref="dfm_analyses")
    rule_set = relationship("ManufacturingRuleSet", back_populates="analyses")
    proposals = relationship("ManufacturingProposalRecord", back_populates="analysis", cascade="all, delete-orphan")


class ManufacturingProposalRecord(Base, UUIDMixin, TimestampMixin):
    """
    Human-gated proposal for resolving a DFM or DFA violation or warning.
    Includes exact diff preview and atomic mutation definitions.
    STRICT INVARIANT: AI actors cannot approve or apply proposals.
    """
    __tablename__ = "manufacturing_proposals"

    board_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    board_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    analysis_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("manufacturing_analyses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    mutation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_mutations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    diff_preview: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(
        String(32),
        default=ProposalStatus.PROPOSED.value,
        index=True,
        nullable=False,
    )

    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    board = relationship("EngineeringBoard", backref="dfm_proposals")
    analysis = relationship("ManufacturingAnalysisRecord", back_populates="proposals")
