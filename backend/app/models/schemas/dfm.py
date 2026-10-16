from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.db.dfm import (
    ManufacturingAnalysisStatus,
    ManufacturingFindingStatus,
    ManufacturingRuleCategory,
)
from app.models.db.proposal import ProposalStatus


class ManufacturingRule(BaseModel):
    rule_id: str
    name: str
    category: ManufacturingRuleCategory
    description: str
    severity: str = "ERROR"  # ERROR, WARNING, INFO
    parameters: dict[str, Any] = Field(default_factory=dict)
    standard_reference: Optional[str] = None


class ManufacturingRuleSetCreate(BaseModel):
    name: str
    source: str = "STANDARD"
    source_revision: str = "REV_A"
    source_digest: Optional[str] = None
    rules: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    effective_from: Optional[datetime] = None
    metadata: Optional[dict[str, Any]] = None


class ManufacturingRuleSetResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    name: str
    version: int
    source: str
    source_revision: str
    source_digest: Optional[str] = None
    rules: dict[str, Any] = Field(default_factory=dict)
    is_default: bool
    effective_from: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManufacturingFinding(BaseModel):
    finding_id: str
    rule_id: str
    rule_name: str
    category: ManufacturingRuleCategory
    status: ManufacturingFindingStatus
    severity: str = "ERROR"  # ERROR, WARNING, INFO
    message: str
    element_type: str  # TRACE, PAD, VIA, FOOTPRINT, BOARD_EDGE, BOM_LINE, SOLDER_MASK, SILKSCREEN
    element_ids: list[str] = Field(default_factory=list)
    ref_des: Optional[str] = None
    location: Optional[dict[str, float]] = None
    layer: Optional[str] = None
    measured_value: Optional[float] = None
    required_value: Optional[float] = None
    margin: Optional[float] = None
    unit: Optional[str] = None
    proposal_available: bool = False
    evidence: Optional[dict[str, Any]] = None


class ManufacturingAnalysisCreate(BaseModel):
    board_id: str
    board_revision: Optional[int] = None
    circuit_id: Optional[str] = None
    rule_set_id: Optional[str] = None
    include_bom_check: bool = True
    bom_id: Optional[str] = None


class ManufacturingAnalysisSummary(BaseModel):
    total_rules_evaluated: int
    pass_count: int
    fail_count: int
    warning_count: int
    unknown_count: int
    critical_violations: list[str] = Field(default_factory=list)
    status: str = ManufacturingAnalysisStatus.COMPLETED.value
    # STRICT EPISTEMIC INVARIANT: Zero synthetic score, zero fabricator ranking.


class ManufacturingAnalysisResponse(BaseModel):
    id: str
    board_id: str
    board_revision: int
    circuit_id: str
    circuit_revision: int
    tenant_id: Optional[str] = None
    rule_set_id: str
    rule_set_revision: str
    status: str
    findings: list[ManufacturingFinding] = Field(default_factory=list)
    summary: ManufacturingAnalysisSummary
    provenance_digest: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManufacturingProposalCreate(BaseModel):
    analysis_id: str
    rule_id: str
    title: str
    description: str
    mutation_type: str
    proposed_mutations: list[dict[str, Any]] = Field(default_factory=list)
    diff_preview: dict[str, Any] = Field(default_factory=dict)


class ManufacturingProposalResponse(BaseModel):
    id: str
    board_id: str
    board_revision: int
    tenant_id: Optional[str] = None
    analysis_id: str
    rule_id: str
    title: str
    description: str
    mutation_type: str
    proposed_mutations: list[dict[str, Any]] = Field(default_factory=list)
    diff_preview: dict[str, Any] = Field(default_factory=dict)
    status: str = ProposalStatus.PROPOSED.value
    created_by: str
    approved_by: Optional[str] = None
    applied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DFMSnapshotResponse(BaseModel):
    board_id: str
    board_revision: int
    analysis_id: str
    rule_set_id: str
    rule_set_revision: str
    canonical_digest: str
    computed_at: str
    invariants_verified: list[str] = Field(default_factory=list)
