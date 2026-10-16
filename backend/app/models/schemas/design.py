from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ConstraintStatus(str, Enum):
    # Hard constraint statuses
    PASS = "PASS"
    FAIL = "FAIL"
    # Soft constraint statuses
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    # Shared
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConstraintType(str, Enum):
    MAXIMUM_VOLTAGE = "maximum_voltage"
    MINIMUM_VOLTAGE = "minimum_voltage"
    MAXIMUM_CURRENT = "maximum_current"
    MINIMUM_CURRENT = "minimum_current"
    MAXIMUM_POWER = "maximum_power"
    MAXIMUM_TEMPERATURE = "maximum_temperature"
    MINIMUM_MARGIN = "minimum_margin"
    MAXIMUM_COMPONENT_COUNT = "maximum_component_count"
    PREFERRED_PACKAGE = "preferred_package"
    REQUIRED_RATING = "required_rating"
    FORBIDDEN_COMPONENT = "forbidden_component"


class EngineeringConstraint(BaseModel):
    id: str
    type: str
    value: Any
    unit: str = ""
    source: str = "USER"
    confidence: str = "HIGH"
    hard_or_soft: str = "HARD"  # HARD | SOFT


class ConstraintResult(BaseModel):
    constraint_id: str
    constraint_name: str | None = None
    hard_or_soft: str = "HARD"  # HARD | SOFT
    status: str  # Hard: PASS | FAIL | UNKNOWN; Soft: SATISFIED | NOT_SATISFIED | UNKNOWN
    actual_value: Any | None = None
    required_value: Any
    unit: str = ""
    margin: float | None = None
    provenance: str = "DETERMINISTIC_EVALUATION"
    explanation: str


class CandidateProvenance(BaseModel):
    candidate_id: str
    trigger: str | None = None
    generation_strategy: str | None = None
    source_finding: str | None = None
    affected_component: str | None = None
    affected_net: str | None = None
    old_value: Any | None = None
    new_value: Any | None = None
    old_component: dict[str, Any] | None = None
    new_component: dict[str, Any] | None = None
    rationale: str | None = None
    knowledge_sources: list[str] = Field(default_factory=list)
    engineering_assumptions: list[dict[str, Any]] = Field(default_factory=list)
    validation_analysis_id: str | None = None
    constraint_results: list[dict[str, Any]] = Field(default_factory=list)
    finding_delta: dict[str, Any] = Field(default_factory=dict)
    engineering_effects: dict[str, Any] = Field(default_factory=dict)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)
    confidence: str = "HIGH"


class EngineeringDesignObjectiveCreate(BaseModel):
    objective_type: str
    description: str | None = None
    target: dict[str, Any] = Field(default_factory=dict)
    constraints: list[EngineeringConstraint] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    affected_nets: list[str] = Field(default_factory=list)
    source: str = "USER"  # USER | AI | FINDING


class EngineeringDesignObjectiveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    circuit_id: str
    tenant_id: str | None = None
    created_by: str
    objective_type: str
    description: str | None = None
    target: dict[str, Any] = Field(default_factory=dict)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    affected_nets: list[str] = Field(default_factory=list)
    source: str
    created_at: datetime


class ProposedChange(BaseModel):
    operation: str  # ADD_COMPONENT | REMOVE_COMPONENT | UPDATE_COMPONENT_VALUE | UPDATE_COMPONENT_RATING | UPDATE_COMPONENT_PARAMETER | ADD_CONNECTION | REMOVE_CONNECTION | UPDATE_NET_LABEL | REPLACE_COMPONENT
    component_id: str | None = None
    ref_des: str | None = None
    component_type: str | None = None
    field: str | None = None
    old_value: Any | None = None
    new_value: Any | None = None
    net_name: str | None = None
    pin_number: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class EngineeringDesignAlternative(BaseModel):
    alternative_id: str
    objective_id: str
    title: str
    description: str
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    affected_nets: list[str] = Field(default_factory=list)
    before_analysis_id: str | None = None
    after_analysis_id: str | None = None
    after_analysis: dict[str, Any] | None = None  # In-memory sandboxed analysis snapshot
    engineering_effects: list[str] = Field(default_factory=list)
    findings_resolved: list[str] = Field(default_factory=list)
    findings_introduced: list[str] = Field(default_factory=list)
    remaining_findings: list[str] = Field(default_factory=list)
    hard_constraints_status: str = "PASS"  # PASS | FAIL | UNKNOWN
    soft_constraints_summary: dict[str, int] = Field(default_factory=dict)
    constraint_results: list[ConstraintResult] = Field(default_factory=list)
    electrical_effects: dict[str, Any] = Field(default_factory=dict)
    structural_effects: dict[str, Any] = Field(default_factory=dict)
    cost: str = "UNKNOWN"
    footprint: str = "UNKNOWN"
    unknowns: list[dict[str, Any]] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    status: str = "VALIDATED"  # VALIDATED | REJECTED | PARTIAL | BLOCKED
    provenance: list[str] = Field(default_factory=list)
    candidate_provenance: CandidateProvenance | dict[str, Any] | None = None
    confidence: str = "HIGH"  # Evidence quality: HIGH | MEDIUM | LOW (never a design ranking)


class ComparisonMatrixRow(BaseModel):
    alternative_id: str
    title: str
    strategy: str
    hard_constraints: str  # PASS | FAIL | UNKNOWN
    soft_constraints: str  # e.g. "2/2 SATISFIED"
    findings_resolved_count: int
    findings_introduced_count: int
    remaining_findings_count: int
    resolved_finding_ids: list[str] = Field(default_factory=list)
    introduced_finding_ids: list[str] = Field(default_factory=list)
    power_delta_w: float | None = None
    worst_margin: float | None = None
    component_count_delta: int
    footprint: str = "UNKNOWN"
    cost: str = "UNKNOWN"
    confidence: str = "HIGH"  # HIGH | MEDIUM | LOW
    tradeoffs: list[str] = Field(default_factory=list)


class DesignComparisonResponse(BaseModel):
    circuit_id: str
    base_revision: int
    baseline_metrics: dict[str, Any]
    alternatives: list[dict[str, Any]]
    comparison_table: list[dict[str, Any]]
    comparison_matrix: list[ComparisonMatrixRow] = Field(default_factory=list)
