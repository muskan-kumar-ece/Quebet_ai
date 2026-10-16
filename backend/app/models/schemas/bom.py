from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.db.bom import (
    BOMLineStatus,
    BOMStatus,
    ParameterEvaluationStatus,
    PartAvailabilityStatus,
    PartCompatibilityStatus,
    PartLifecycleStatus,
)


class SupplySourceObservation(BaseModel):
    supplier: str
    supplier_pn: Optional[str] = None
    stock: int = Field(ge=0)
    unit_price: Optional[float] = None
    currency: str = "USD"
    qty_break: int = 1
    observed_at: str
    source_url: Optional[str] = None
    source_trust: str = "COMMERCIAL_OBSERVATION"


class ParameterCompatibilityEvaluation(BaseModel):
    parameter: str
    required_value: Any
    actual_value: Any
    status: str = ParameterEvaluationStatus.UNKNOWN.value  # SATISFIED, NOT_SATISFIED, UNKNOWN, NOT_APPLICABLE
    unit: Optional[str] = None
    message: Optional[str] = None


class ComponentPartCandidateBase(BaseModel):
    manufacturer: str
    mpn: str
    package: Optional[str] = None
    description: Optional[str] = None
    datasheet_url: Optional[str] = None
    lifecycle_status: str = PartLifecycleStatus.UNKNOWN.value
    availability_status: str = PartAvailabilityStatus.UNKNOWN.value
    lead_time_weeks: Optional[int] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    supply_sources: list[SupplySourceObservation] = Field(default_factory=list)
    is_primary: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)


class ComponentPartCandidateCreate(ComponentPartCandidateBase):
    pass


class ComponentPartCandidateResponse(ComponentPartCandidateBase):
    id: str
    bom_line_id: str
    compatibility_status: str = PartCompatibilityStatus.UNKNOWN.value
    compatibility_evaluations: list[ParameterCompatibilityEvaluation] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EngineeringBOMLineBase(BaseModel):
    reference_designator: str
    quantity: int = 1
    component_type: str
    design_value: str
    design_package: Optional[str] = None
    design_tolerance: Optional[str] = None
    design_rating: Optional[str] = None
    footprint_name: Optional[str] = None
    engineering_requirements: dict[str, Any] = Field(default_factory=dict)
    manufacturer: Optional[str] = None
    manufacturer_part_number: Optional[str] = None
    description: Optional[str] = None


class EngineeringBOMLineResponse(EngineeringBOMLineBase):
    id: str
    bom_id: str
    component_id: Optional[str] = None
    status: str = BOMLineStatus.UNMATCHED.value
    provenance: dict[str, Any] = Field(default_factory=dict)
    candidates: list[ComponentPartCandidateResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EngineeringBOMCreate(BaseModel):
    circuit_id: str
    name: Optional[str] = None
    board_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class EngineeringBOMResponse(BaseModel):
    id: str
    project_id: str
    circuit_id: str
    circuit_version: int
    board_id: Optional[str] = None
    board_version: Optional[int] = None
    tenant_id: Optional[str] = None
    name: str
    version: int
    status: str
    total_lines: int
    integrity_digest: Optional[str] = None
    lines: list[EngineeringBOMLineResponse] = Field(default_factory=list)
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BOMSubstitutionProposalCreate(BaseModel):
    bom_line_id: str
    candidate_id: str
    proposed_mpn: str
    proposed_manufacturer: str
    rationale: str


class BOMSubstitutionProposalResponse(BaseModel):
    id: str
    bom_id: str
    bom_line_id: str
    base_bom_revision: int
    circuit_version: int
    tenant_id: Optional[str] = None
    candidate_id: str
    proposed_mpn: str
    proposed_manufacturer: str
    rationale: str
    diff_preview: dict[str, Any]
    status: str
    created_by: str
    approved_by: Optional[str] = None
    applied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BOMCompatibilityResponse(BaseModel):
    bom_id: str
    bom_revision: int
    provenance_digest: str
    total_lines: int
    summary: dict[str, int]
    lines: list[EngineeringBOMLineResponse]
    classification: str = "BOM_COMPATIBILITY_EVALUATION"


class BOMSnapshotResponse(BaseModel):
    bom_id: str
    bom_version: int
    circuit_id: str
    circuit_version: int
    snapshot_digest: str
    provenance_label: str = "PROVENANCE_AND_INTEGRITY_DIGEST"
    content: dict[str, Any]
