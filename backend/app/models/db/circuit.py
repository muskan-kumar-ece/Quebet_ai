from enum import Enum
from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class CircuitValidationStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    VALID = "VALID"
    INVALID = "INVALID"
    NEEDS_INPUT = "NEEDS_INPUT"


class Circuit(Base, UUIDMixin, TimestampMixin):
    """
    Structured circuit engineering representation belonging to a Project.
    Encapsulates electrical components, nets, connections, assumptions, and schematic models.
    """

    __tablename__ = "circuits"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        String(32),
        default=CircuitValidationStatus.DRAFT.value,
        nullable=False,
    )

    # Provenance fields
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_source: Mapped[str] = mapped_column(String(32), default="USER", nullable=False)  # USER | AI | IMPORT | SYSTEM
    source_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="circuits")
    components = relationship("Component", back_populates="circuit", cascade="all, delete-orphan")
    nets = relationship("Net", back_populates="circuit", cascade="all, delete-orphan")
    connections = relationship("Connection", back_populates="circuit", cascade="all, delete-orphan")
    schematic_objects = relationship("SchematicObject", back_populates="circuit", cascade="all, delete-orphan")
    assumptions = relationship("Assumption", back_populates="circuit", cascade="all, delete-orphan")
    proposals = relationship("EngineeringProposal", back_populates="circuit", cascade="all, delete-orphan")
    analyses = relationship("CircuitAnalysis", back_populates="circuit", cascade="all, delete-orphan")
    design_objectives = relationship("EngineeringDesignObjective", back_populates="circuit", cascade="all, delete-orphan")
    simulations = relationship("SimulationJob", back_populates="circuit", cascade="all, delete-orphan")
    simulation_results = relationship("SimulationResultRecord", back_populates="circuit", cascade="all, delete-orphan")
