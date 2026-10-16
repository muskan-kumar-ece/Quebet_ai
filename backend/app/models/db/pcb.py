from datetime import datetime
from enum import Enum
from typing import Any
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin
from app.models.db.proposal import ProposalStatus


class BoardStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    FROZEN = "FROZEN"


class LayerType(str, Enum):
    COPPER = "COPPER"
    DIELECTRIC = "DIELECTRIC"
    SILKSCREEN = "SILKSCREEN"
    SOLDERMASK = "SOLDERMASK"
    PASTE = "PASTE"


class PadType(str, Enum):
    SMD = "SMD"
    THROUGH_HOLE = "THROUGH_HOLE"
    EDGE_CONNECTOR = "EDGE_CONNECTOR"
    THERMAL_PAD = "THERMAL_PAD"


class ViaType(str, Enum):
    THROUGH = "THROUGH"
    BLIND = "BLIND"
    BURIED = "BURIED"
    MICROVIA = "MICROVIA"


class EngineeringBoard(Base, UUIDMixin, TimestampMixin):
    """
    Authoritative physical PCB engineering representation.
    Binds to schematic Circuit and maintains layer stackup, component footprints,
    pads, routing segments, vias, and geometric outline.
    """
    __tablename__ = "engineering_boards"

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
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        default=BoardStatus.DRAFT.value,
        index=True,
        nullable=False,
    )

    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    units: Mapped[str] = mapped_column(String(16), default="mm", nullable=False)
    board_outline: Mapped[list[dict[str, float]]] = mapped_column(JSON, default=list, nullable=False)

    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    integrity_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=dict, nullable=True)

    # Relationships
    project = relationship("Project", backref="boards")
    circuit = relationship("Circuit", backref="boards")
    layers = relationship(
        "BoardLayer",
        back_populates="board",
        cascade="all, delete-orphan",
        order_by="BoardLayer.layer_order",
    )
    footprints = relationship("BoardFootprint", back_populates="board", cascade="all, delete-orphan")
    traces = relationship("BoardTraceSegment", back_populates="board", cascade="all, delete-orphan")
    vias = relationship("BoardVia", back_populates="board", cascade="all, delete-orphan")
    analyses = relationship("PCBAnalysisRecord", back_populates="board", cascade="all, delete-orphan")
    proposals = relationship("PCBProposalRecord", back_populates="board", cascade="all, delete-orphan")


class BoardLayer(Base, UUIDMixin, TimestampMixin):
    """
    Physical layer in the PCB stackup sequence.
    """
    __tablename__ = "board_layers"

    board_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    layer_type: Mapped[str] = mapped_column(String(32), default=LayerType.COPPER.value, nullable=False)
    layer_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_copper: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    thickness_um: Mapped[float | None] = mapped_column(Float, nullable=True)
    dielectric_constant: Mapped[float | None] = mapped_column(Float, nullable=True)
    copper_weight_oz: Mapped[float | None] = mapped_column(Float, nullable=True)

    board = relationship("EngineeringBoard", back_populates="layers")


class BoardFootprint(Base, UUIDMixin, TimestampMixin):
    """
    Physical package footprint placed on the PCB, bound to schematic Component.
    """
    __tablename__ = "board_footprints"

    board_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    component_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("components.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    ref_des: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    footprint_name: Mapped[str] = mapped_column(String(128), nullable=False)
    pos_x: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rotation: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    side: Mapped[str] = mapped_column(String(16), default="TOP", nullable=False)

    package_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)
    source_provenance: Mapped[str] = mapped_column(String(128), default="GENERIC", nullable=False)

    board = relationship("EngineeringBoard", back_populates="footprints")
    pads = relationship("BoardPad", back_populates="footprint", cascade="all, delete-orphan")


class BoardPad(Base, UUIDMixin, TimestampMixin):
    """
    Physical copper land or through-hole pad belonging to a footprint.
    """
    __tablename__ = "board_pads"

    board_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    footprint_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("board_footprints.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pad_number: Mapped[str] = mapped_column(String(32), nullable=False)
    pad_type: Mapped[str] = mapped_column(String(32), default=PadType.SMD.value, nullable=False)

    pos_x: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    width: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    height: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    drill: Mapped[float | None] = mapped_column(Float, nullable=True)
    shape: Mapped[str] = mapped_column(String(32), default="RECT", nullable=False)
    layer: Mapped[str] = mapped_column(String(64), default="F.Cu", nullable=False)

    net_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("nets.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    net_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    footprint = relationship("BoardFootprint", back_populates="pads")


class BoardTraceSegment(Base, UUIDMixin, TimestampMixin):
    """
    Physical routed copper trace segment on a specific layer.
    """
    __tablename__ = "board_trace_segments"

    board_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    start_x: Mapped[float] = mapped_column(Float, nullable=False)
    start_y: Mapped[float] = mapped_column(Float, nullable=False)
    end_x: Mapped[float] = mapped_column(Float, nullable=False)
    end_y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, default=0.25, nullable=False)
    layer: Mapped[str] = mapped_column(String(64), default="F.Cu", nullable=False)

    net_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("nets.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    net_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    board = relationship("EngineeringBoard", back_populates="traces")


class BoardVia(Base, UUIDMixin, TimestampMixin):
    """
    Physical vertical interconnect access bridging copper layers.
    """
    __tablename__ = "board_vias"

    board_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pos_x: Mapped[float] = mapped_column(Float, nullable=False)
    pos_y: Mapped[float] = mapped_column(Float, nullable=False)
    drill: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    diameter: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    start_layer: Mapped[str] = mapped_column(String(64), default="F.Cu", nullable=False)
    end_layer: Mapped[str] = mapped_column(String(64), default="B.Cu", nullable=False)
    via_type: Mapped[str] = mapped_column(String(32), default=ViaType.THROUGH.value, nullable=False)

    net_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("nets.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    net_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    board = relationship("EngineeringBoard", back_populates="vias")


class PCBAnalysisRecord(Base, UUIDMixin, TimestampMixin):
    """
    Structured outcome of a deterministic PCB Design Rule Check & constraint analysis.
    Explicit epistemic invariant: PCB analysis results are PCB_ANALYSIS and NOT_VERIFIED.
    """
    __tablename__ = "pcb_analyses"

    board_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    board_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="COMPLETED", nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(32), default="1.0-deterministic", nullable=False)
    snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    classification: Mapped[str] = mapped_column(String(32), default="PCB_ANALYSIS", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="NOT_VERIFIED", nullable=False)

    board = relationship("EngineeringBoard", back_populates="analyses")


class PCBProposalRecord(Base, UUIDMixin, TimestampMixin):
    """
    Human-gated layout proposal generated by AI or heuristic engines.
    Cannot directly mutate board state without explicit human approval.
    """
    __tablename__ = "pcb_proposals"

    board_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("engineering_boards.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    base_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    circuit_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        default=ProposalStatus.PROPOSED.value,
        index=True,
        nullable=False,
    )

    operations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None, nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    board = relationship("EngineeringBoard", back_populates="proposals")
