from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.db.assumption import AssumptionSource
from app.models.db.circuit import CircuitValidationStatus


class ComponentCreate(BaseModel):
    ref_des: str = Field(..., min_length=1, max_length=32, description="e.g. R1, C1, U1")
    component_type: str = Field(..., description="resistor, capacitor, ic, regulator, mcu")
    manufacturer: str | None = None
    part_number: str | None = None
    value: str = Field(..., description="e.g. 10k, 100nF, LM7805")
    unit: str | None = None
    tolerance: str | None = None
    rating: str | None = None
    package: str | None = None
    pins: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_source: str = "USER"


class ComponentUpdate(BaseModel):
    ref_des: str | None = None
    component_type: str | None = None
    manufacturer: str | None = None
    part_number: str | None = None
    value: str | None = None
    unit: str | None = None
    tolerance: str | None = None
    rating: str | None = None
    package: str | None = None
    pins: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


class ComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    circuit_id: str
    ref_des: str
    component_type: str
    manufacturer: str | None
    part_number: str | None
    value: str
    unit: str | None
    tolerance: str | None
    rating: str | None
    package: str | None
    pins: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_source: str
    created_at: datetime


class NetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="e.g. VCC, GND, SIGNAL_1")
    net_type: str = Field(default="signal", description="power, ground, signal, clock")
    metadata: dict[str, Any] = Field(default_factory=dict)


class NetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    net_type: str | None = None
    metadata: dict[str, Any] | None = None


class NetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    circuit_id: str
    name: str
    net_type: str
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime


class ConnectionCreate(BaseModel):
    component_id: str
    pin_number: str
    pin_name: str | None = None
    net_id: str


class ConnectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    circuit_id: str
    component_id: str
    pin_number: str
    pin_name: str | None
    net_id: str
    created_at: datetime


class SchematicObjectCreate(BaseModel):
    object_type: str = Field(..., description="symbol, wire, junction, label, text")
    component_id: str | None = None
    net_id: str | None = None
    pos_x: float = 0.0
    pos_y: float = 0.0
    rotation: float = 0.0
    graphics: dict[str, Any] = Field(default_factory=dict)


class SchematicObjectUpdate(BaseModel):
    pos_x: float | None = None
    pos_y: float | None = None
    rotation: float | None = None
    graphics: dict[str, Any] | None = None


class SchematicObjectBatchItem(BaseModel):
    id: str
    pos_x: float | None = None
    pos_y: float | None = None
    rotation: float | None = None
    graphics: dict[str, Any] | None = None


class SchematicObjectBatchUpdate(BaseModel):
    items: list[SchematicObjectBatchItem] = Field(..., min_length=1)


class SchematicObjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    circuit_id: str
    object_type: str
    component_id: str | None
    net_id: str | None
    pos_x: float
    pos_y: float
    rotation: float
    graphics: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AssumptionCreate(BaseModel):
    field: str
    value: str
    unit: str | None = None
    source: AssumptionSource = AssumptionSource.AI_INFERENCE
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    user_confirmed: bool = False
    rationale: str | None = None


class AssumptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    circuit_id: str
    field: str
    value: str
    unit: str | None
    source: str
    confidence: float
    user_confirmed: bool
    rationale: str | None
    created_at: datetime


class CircuitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    components: list[ComponentCreate] = Field(default_factory=list)
    nets: list[NetCreate] = Field(default_factory=list)
    connections: list[ConnectionCreate] = Field(default_factory=list)
    schematic_objects: list[SchematicObjectCreate] = Field(default_factory=list)
    assumptions: list[AssumptionCreate] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CircuitUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    version: int | None = None
    validation_status: CircuitValidationStatus | None = None
    metadata: dict[str, Any] | None = None


class CircuitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    project_id: str
    tenant_id: str | None
    name: str
    description: str | None
    version: int
    validation_status: str
    created_by: str
    created_source: str
    source_request_id: str | None
    created_at: datetime
    updated_at: datetime


class CircuitDetailResponse(CircuitResponse):
    components: list[ComponentResponse] = Field(default_factory=list)
    nets: list[NetResponse] = Field(default_factory=list)
    connections: list[ConnectionResponse] = Field(default_factory=list)
    schematic_objects: list[SchematicObjectResponse] = Field(default_factory=list)
    assumptions: list[AssumptionResponse] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
