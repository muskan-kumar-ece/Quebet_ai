from datetime import datetime
from enum import Enum
from typing import Any
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin
from app.models.db.proposal import ProposalStatus


class BOMStatus(str, Enum):
    DRAFT = "DRAFT"
    EVALUATED = "EVALUATED"
    REVIEW = "REVIEW"
    FROZEN = "FROZEN"
    ARCHIVED = "ARCHIVED"


class BOMLineStatus(str, Enum):
    UNMATCHED = "UNMATCHED"
    SOURCED = "SOURCED"
    CONFLICTING = "CONFLICTING"
    INCOMPATIBLE = "INCOMPATIBLE"


class PartLifecycleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PREVIEW = "PREVIEW"
    NRND = "NRND"  # Not Recommended for New Designs
    EOL = "EOL"    # End of Life
    OBSOLETE = "OBSOLETE"
    UNKNOWN = "UNKNOWN"


class PartAvailabilityStatus(str, Enum):
    IN_STOCK = "IN_STOCK"
    LIMITED_STOCK = "LIMITED_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


class PartCompatibilityStatus(str, Enum):
    ENGINEERING_COMPATIBLE = "ENGINEERING_COMPATIBLE"
    PARTIALLY_EVALUATED = "PARTIALLY_EVALUATED"
    UNKNOWN = "UNKNOWN"
    NOT_COMPATIBLE = "NOT_COMPATIBLE"


class ParameterEvaluationStatus(str, Enum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EngineeringBOM(Base, UUIDMixin, TimestampMixin):
    """
    Authoritative physical Bill of Materials bound to Circuit and optional EngineeringBoard.
    Maintains BOM lines, procurement candidates, and supply intelligence.
    """
    __tablename__ = "engineering_boms"

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
    circuit_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    board_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    board_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=BOMStatus.DRAFT.value,
        index=True,
        nullable=False,
    )

    total_lines: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    integrity_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    project = relationship("Project", backref="boms")
    circuit = relationship("Circuit", backref="boms")
    board = relationship("EngineeringBoard", backref="boms")
    lines = relationship(
        "EngineeringBOMLine",
        back_populates="bom",
        cascade="all, delete-orphan",
        order_by="EngineeringBOMLine.reference_designator",
    )
    substitutions = relationship(
        "BOMSubstitutionProposal",
        back_populates="bom",
        cascade="all, delete-orphan",
    )


class EngineeringBOMLine(Base, UUIDMixin, TimestampMixin):
    """
    Individual line item in the Engineering Bill of Materials.
    Separates DESIGN IDENTITY (e.g. R1, 10k, 0603) from PROCUREMENT IDENTITY (e.g. Yageo RC0603FR-0710KL).
    """
    __tablename__ = "engineering_bom_lines"

    bom_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boms.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    component_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("components.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    reference_designator: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Design Intent Identity
    component_type: Mapped[str] = mapped_column(String(64), nullable=False)
    design_value: Mapped[str] = mapped_column(String(64), nullable=False)
    design_package: Mapped[str | None] = mapped_column(String(64), nullable=True)
    design_tolerance: Mapped[str | None] = mapped_column(String(32), nullable=True)
    design_rating: Mapped[str | None] = mapped_column(String(64), nullable=True)
    footprint_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Explicit Extracted Requirements (Voltage, Current, Power, Temp, Tolerance, etc.)
    engineering_requirements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Primary Procurement Identity (Optional / Assigned)
    manufacturer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    manufacturer_part_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[str] = mapped_column(
        String(32),
        default=BOMLineStatus.UNMATCHED.value,
        nullable=False,
    )
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    bom = relationship("EngineeringBOM", back_populates="lines")
    component = relationship("Component")
    candidates = relationship(
        "ComponentPartCandidate",
        back_populates="bom_line",
        cascade="all, delete-orphan",
    )
    substitutions = relationship(
        "BOMSubstitutionProposal",
        back_populates="bom_line",
        cascade="all, delete-orphan",
    )


class ComponentPartCandidate(Base, UUIDMixin, TimestampMixin):
    """
    Sourced procurement candidate for a BOM line.
    Maintains physical engineering parameters, multi-source supply data, lifecycle, and compatibility.
    """
    __tablename__ = "component_part_candidates"

    bom_line_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_bom_lines.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    manufacturer: Mapped[str] = mapped_column(String(128), nullable=False)
    mpn: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    package: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    datasheet_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Engineering Compatibility
    compatibility_status: Mapped[str] = mapped_column(
        String(32),
        default=PartCompatibilityStatus.UNKNOWN.value,
        nullable=False,
    )
    compatibility_evaluations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Supply Chain & Lifecycle
    lifecycle_status: Mapped[str] = mapped_column(
        String(32),
        default=PartLifecycleStatus.UNKNOWN.value,
        nullable=False,
    )
    availability_status: Mapped[str] = mapped_column(
        String(32),
        default=PartAvailabilityStatus.UNKNOWN.value,
        nullable=False,
    )
    lead_time_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Multi-source dynamic supply observations (quotes, stocks, timestamps)
    supply_sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    bom_line = relationship("EngineeringBOMLine", back_populates="candidates")


class BOMSubstitutionProposal(Base, UUIDMixin, TimestampMixin):
    """
    Human-gated component substitution proposal.
    Proposes swapping a BOM line's procurement candidate with a verified alternative.
    Autonomous application is strictly blocked.
    """
    __tablename__ = "bom_substitution_proposals"

    bom_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boms.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    bom_line_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_bom_lines.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    base_bom_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    circuit_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    candidate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    proposed_mpn: Mapped[str] = mapped_column(String(128), nullable=False)
    proposed_manufacturer: Mapped[str] = mapped_column(String(128), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    # Deterministic comparison diff without synthetic scores
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

    # Relationships
    bom = relationship("EngineeringBOM", back_populates="substitutions")
    bom_line = relationship("EngineeringBOMLine", back_populates="substitutions")
