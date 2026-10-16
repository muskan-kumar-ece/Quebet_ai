from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# -------------------------------------------------------------
# System Design Objectives & Constraints
# -------------------------------------------------------------

class SystemDesignConstraintBase(BaseModel):
    constraint_type: str = Field(..., description="HARD or SOFT")
    parameter: str = Field(..., max_length=64)
    operator: str = Field(..., description="LTE, GTE, EQ, IN, CONTAINS, RANGE")
    value: Dict[str, Any]
    unit: Optional[str] = None
    weight: Optional[float] = 1.0
    status: str = "ACTIVE"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SystemDesignConstraintCreate(SystemDesignConstraintBase):
    pass


class SystemDesignConstraintResponse(SystemDesignConstraintBase):
    id: str
    objective_id: str
    system_id: str
    tenant_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SystemDesignObjectiveBase(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    objective_type: str = "POWER_OPTIMIZATION"
    priority: str = "MEDIUM"
    target: Dict[str, Any] = Field(default_factory=dict)
    affected_subsystems: List[str] = Field(default_factory=list)
    relevant_modes: List[str] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SystemDesignObjectiveCreate(SystemDesignObjectiveBase):
    constraints: Optional[List[SystemDesignConstraintCreate]] = Field(default_factory=list)


class SystemDesignObjectiveUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    objective_type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    target: Optional[Dict[str, Any]] = None
    affected_subsystems: Optional[List[str]] = None
    relevant_modes: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SystemDesignObjectiveResponse(SystemDesignObjectiveBase):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    constraints: List[SystemDesignConstraintResponse] = Field(default_factory=list)


# -------------------------------------------------------------
# Scenarios & Scenario Conditions
# -------------------------------------------------------------

class ScenarioConditionBase(BaseModel):
    condition_type: str = Field(..., description="PRECONDITION, OPERATING_CONDITION, FAULT_INJECTION")
    target_type: str = Field(..., description="SYSTEM, SUBSYSTEM, INTERFACE, POWER_DOMAIN")
    target_id: Optional[str] = None
    parameter: str = Field(..., max_length=64)
    value: Dict[str, Any]
    unit: Optional[str] = None
    source: Optional[str] = None
    confidence: float = 1.0
    provenance: Dict[str, Any] = Field(default_factory=dict)
    mandatory: bool = True
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ScenarioConditionCreate(ScenarioConditionBase):
    pass


class ScenarioConditionResponse(ScenarioConditionBase):
    id: str
    scenario_id: str
    tenant_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ScenarioBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    scenario_type: str = "NORMAL_OPERATION"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ScenarioCreate(ScenarioBase):
    conditions: Optional[List[ScenarioConditionCreate]] = Field(default_factory=list)


class ScenarioUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    scenario_type: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ScenarioResponse(ScenarioBase):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    status: str
    system_revision: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    conditions: List[ScenarioConditionResponse] = Field(default_factory=list)


class ScenarioSnapshotResponse(BaseModel):
    id: str
    scenario_id: str
    system_id: str
    tenant_id: Optional[str] = None
    system_revision: int
    system_snapshot_id: Optional[str] = None
    scenario_conditions: List[Dict[str, Any]] = Field(default_factory=list)
    engine_versions: Dict[str, str] = Field(default_factory=dict)
    rule_set_version: str
    knowledge_snapshot_id: Optional[str] = None
    inputs_digest: str
    execution_timestamp: datetime
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ScenarioResultResponse(BaseModel):
    id: str
    scenario_id: str
    execution_id: str
    system_id: str
    tenant_id: Optional[str] = None
    status: str
    system_revision: int
    precondition_status: str
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    requirement_results: List[Dict[str, Any]] = Field(default_factory=list)
    power_results: Dict[str, Any] = Field(default_factory=dict)
    interface_results: Dict[str, Any] = Field(default_factory=dict)
    failure_results: Dict[str, Any] = Field(default_factory=dict)
    unknowns: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ScenarioExecuteRequest(BaseModel):
    scenario_id: str
    force_recompute: bool = False


class ScenarioComparisonRequest(BaseModel):
    baseline_scenario_id: str
    alternative_scenario_id: str


class ScenarioComparisonResponse(BaseModel):
    baseline_scenario_id: str
    alternative_scenario_id: str
    power_delta: Dict[str, Any]
    current_delta: Dict[str, Any]
    constraint_changes: List[Dict[str, Any]]
    finding_changes: Dict[str, Any]
    requirement_changes: List[Dict[str, Any]]
    failure_propagation_changes: Dict[str, Any]
    affected_subsystems: List[str]
    affected_interfaces: List[str]
    affected_power_domains: List[str]
    unknown_changes: List[str]
    summary: str


# -------------------------------------------------------------
# System Candidates & What-If Simulation
# -------------------------------------------------------------

class SystemWhatIfOperation(BaseModel):
    op_type: str = Field(..., description="ADD_SUBSYSTEM, REMOVE_SUBSYSTEM, REPLACE_SUBSYSTEM, UPDATE_SUBSYSTEM, ADD_INTERFACE, etc.")
    payload: Dict[str, Any]


class SystemWhatIfRequest(BaseModel):
    operations: List[SystemWhatIfOperation]
    scenario_ids: Optional[List[str]] = Field(default_factory=list)


class SystemWhatIfResponse(BaseModel):
    status: str  # VALIDATED, INVALID, BLOCKED
    base_revision: int
    operations: List[Dict[str, Any]]
    interface_compatibility: Dict[str, Any]
    power_analysis: Dict[str, Any]
    failure_impact: Dict[str, Any]
    requirement_impact: List[Dict[str, Any]]
    verification_impact: List[Dict[str, Any]]
    unknowns: List[str]
    errors: List[str] = Field(default_factory=list)


class SystemCandidateGenerateRequest(BaseModel):
    objective_id: str
    strategies: Optional[List[str]] = None
    scenario_ids: Optional[List[str]] = Field(default_factory=list)


class SystemCandidateResponse(BaseModel):
    id: str
    objective_id: str
    system_id: str
    tenant_id: Optional[str] = None
    candidate_name: str
    generation_strategy: str
    status: str
    base_revision: int
    operations: List[Dict[str, Any]]
    rationale: str
    assumptions: List[Dict[str, Any]]
    hard_constraints_result: str
    soft_constraints_result: str
    constraints_evaluation: List[Dict[str, Any]]
    requirement_effects: List[Dict[str, Any]]
    verification_effects: List[Dict[str, Any]]
    failure_effects: Dict[str, Any]
    power_effects: Dict[str, Any]
    unknowns: List[str]
    provenance: Dict[str, Any]
    created_by: str
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SystemArchitectureCompareRequest(BaseModel):
    candidate_ids: List[str]
    objective_id: Optional[str] = None


class SystemArchitectureCompareResponse(BaseModel):
    objective_id: Optional[str] = None
    baseline_revision: int
    candidates: List[SystemCandidateResponse]
    comparison_matrix: Dict[str, Any]
    dimensions: List[str]


# -------------------------------------------------------------
# System Proposals
# -------------------------------------------------------------

class SystemProposalCreate(BaseModel):
    candidate_id: Optional[str] = None
    objective_id: Optional[str] = None
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    base_revision: int
    operations: List[Dict[str, Any]]
    generation_strategy: str = "MANUAL"
    rationale: str
    scenario_ids: Optional[List[str]] = Field(default_factory=list)
    engineering_effects: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    requirement_effects: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    verification_effects: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    failure_effects: Optional[Dict[str, Any]] = Field(default_factory=dict)
    unknowns: Optional[List[str]] = Field(default_factory=list)
    provenance: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SystemProposalResponse(BaseModel):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    candidate_id: Optional[str] = None
    objective_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: str
    base_revision: int
    system_analysis_id: Optional[str] = None
    scenario_ids: List[str] = Field(default_factory=list)
    operations: List[Dict[str, Any]]
    generation_strategy: str
    rationale: str
    engineering_effects: List[Dict[str, Any]] = Field(default_factory=list)
    requirement_effects: List[Dict[str, Any]] = Field(default_factory=list)
    verification_effects: List[Dict[str, Any]] = Field(default_factory=list)
    failure_effects: Dict[str, Any] = Field(default_factory=dict)
    unknowns: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_by: str
    approved_by: Optional[str] = None
    applied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
