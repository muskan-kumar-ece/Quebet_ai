from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.db.pcb import BoardStatus, LayerType, PadType, ViaType
from app.models.db.proposal import ProposalStatus


class BoardLayerCreate(BaseModel):
    name: str
    layer_type: LayerType = LayerType.COPPER
    layer_order: int = 1
    is_copper: bool = True
    thickness_um: float | None = None
    dielectric_constant: float | None = None
    copper_weight_oz: float | None = None


class BoardLayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    board_id: str
    name: str
    layer_type: str
    layer_order: int
    is_copper: bool
    thickness_um: float | None = None
    dielectric_constant: float | None = None
    copper_weight_oz: float | None = None


class BoardPadCreate(BaseModel):
    pad_number: str
    pad_type: PadType = PadType.SMD
    pos_x: float = 0.0
    pos_y: float = 0.0
    width: float = 1.0
    height: float = 1.0
    drill: float | None = None
    shape: str = "RECT"
    layer: str = "F.Cu"
    net_id: str | None = None
    net_name: str | None = None


class BoardPadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    board_id: str
    footprint_id: str
    pad_number: str
    pad_type: str
    pos_x: float
    pos_y: float
    width: float
    height: float
    drill: float | None = None
    shape: str
    layer: str
    net_id: str | None = None
    net_name: str | None = None


class BoardFootprintCreate(BaseModel):
    component_id: str | None = None
    ref_des: str
    footprint_name: str
    pos_x: float = 0.0
    pos_y: float = 0.0
    rotation: float = 0.0
    side: str = "TOP"
    package_metadata: dict[str, Any] | None = None
    source_provenance: str = "GENERIC"
    pads: list[BoardPadCreate] = Field(default_factory=list)


class BoardFootprintResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    board_id: str
    component_id: str | None = None
    ref_des: str
    footprint_name: str
    pos_x: float
    pos_y: float
    rotation: float
    side: str
    package_metadata: dict[str, Any] | None = None
    source_provenance: str
    pads: list[BoardPadResponse] = Field(default_factory=list)


class BoardTraceCreate(BaseModel):
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    width: float = 0.25
    layer: str = "F.Cu"
    net_id: str | None = None
    net_name: str | None = None


class BoardTraceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    board_id: str
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    width: float
    layer: str
    net_id: str | None = None
    net_name: str | None = None


class BoardViaCreate(BaseModel):
    pos_x: float
    pos_y: float
    drill: float = 0.3
    diameter: float = 0.6
    start_layer: str = "F.Cu"
    end_layer: str = "B.Cu"
    via_type: ViaType = ViaType.THROUGH
    net_id: str | None = None
    net_name: str | None = None


class BoardViaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    board_id: str
    pos_x: float
    pos_y: float
    drill: float
    diameter: float
    start_layer: str
    end_layer: str
    via_type: str
    net_id: str | None = None
    net_name: str | None = None


class EngineeringBoardCreate(BaseModel):
    circuit_id: str
    name: str
    dimensions: dict[str, Any] = Field(
        default_factory=lambda: {"width_mm": 100.0, "height_mm": 80.0, "thickness_mm": 1.6}
    )
    units: str = "mm"
    board_outline: list[dict[str, float]] = Field(default_factory=list)
    metadata: dict[str, Any] | None = None


class EngineeringBoardUpdate(BaseModel):
    name: str | None = None
    dimensions: dict[str, Any] | None = None
    units: str | None = None
    board_outline: list[dict[str, float]] | None = None
    metadata: dict[str, Any] | None = None


class EngineeringBoardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    circuit_id: str
    circuit_version: int
    tenant_id: str | None = None
    name: str
    version: int
    status: BoardStatus
    dimensions: dict[str, Any]
    units: str
    board_outline: list[dict[str, float]]
    integrity_digest: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    created_at: datetime
    updated_at: datetime
    layers: list[BoardLayerResponse] = Field(default_factory=list)
    footprints: list[BoardFootprintResponse] = Field(default_factory=list)
    traces: list[BoardTraceResponse] = Field(default_factory=list)
    vias: list[BoardViaResponse] = Field(default_factory=list)


class PCBFinding(BaseModel):
    rule_id: str = Field(description="Deterministic DRC Rule ID (PCB001-PCB016)")
    severity: str = Field(description="ERROR | WARNING | INFO")
    category: str = Field(description="SCHEMATIC_SYNC | CONNECTIVITY | CLEARANCE | TRACE_WIDTH | PLACEMENT | DECOUPLING | THERMAL | HIGH_SPEED")
    element_ref: str
    actual_value: float | str | None = None
    required_limit: float | str | None = None
    unit: str | None = None
    status: str = Field(description="VIOLATED | SATISFIED | UNKNOWN")
    message: str


class PCBConstraintEvaluation(BaseModel):
    constraint_type: str = Field(description="KEEP_IN | KEEP_OUT | COMPONENT_CLEARANCE | EDGE_CLEARANCE | TRACE_WIDTH | RELATIVE_PLACEMENT")
    target_refs: list[str] = Field(default_factory=list)
    actual_value: float | None = None
    limit_value: float | None = None
    unit: str | None = None
    status: str = Field(description="SATISFIED | VIOLATED | UNKNOWN")
    note: str | None = None


class PCBAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    board_id: str
    board_version: int
    circuit_id: str
    circuit_version: int
    tenant_id: str | None = None
    is_stale: bool = False
    status: str
    ruleset_version: str
    snapshot_digest: str
    findings: list[PCBFinding] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    classification: str = "PCB_ANALYSIS"
    verification_status: str = "NOT_VERIFIED"
    epistemic_warning: str = (
        "PCB_ANALYSIS != PCB_FABRICATION != PCB_INSPECTION != HARDWARE_TEST. "
        "A design rule check is a geometric and model constraint analysis and does NOT constitute physical board verification."
    )
    created_at: datetime


class PCBProposalCreate(BaseModel):
    title: str
    description: str | None = None
    operations: list[dict[str, Any]] = Field(
        description="Structured proposal operations: move_footprint, change_trace_width, reroute_trace, add_via, change_layer"
    )


class PCBProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    board_id: str
    base_revision: int
    circuit_version: int
    tenant_id: str | None = None
    created_by: str
    title: str
    description: str | None = None
    status: ProposalStatus
    operations: list[dict[str, Any]]
    validation_result: dict[str, Any] | None = None
    is_stale: bool = False
    applied_at: datetime | None = None
    created_at: datetime


class PCBSnapshotResponse(BaseModel):
    board_id: str
    board_version: int
    circuit_id: str
    circuit_version: int
    snapshot_digest: str
    provenance_label: str = "PROVENANCE_AND_INTEGRITY_DIGEST"
    content: dict[str, Any]
