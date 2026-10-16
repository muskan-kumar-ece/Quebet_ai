from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# Requirement Schemas
class EngineeringRequirementCreate(BaseModel):
    requirement_key: str
    title: str
    description: str
    category: str = "FUNCTIONAL"
    priority: str = "MEDIUM"
    source_type: str = "INTERNAL_SPEC"
    source_reference: Optional[str] = None
    parent_requirement_id: Optional[str] = None
    expression: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True)


class EngineeringRequirementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    source_type: Optional[str] = None
    source_reference: Optional[str] = None
    status: Optional[str] = None
    parent_requirement_id: Optional[str] = None
    expression: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True)


class EngineeringRequirementResponse(BaseModel):
    id: str
    project_id: str
    system_id: str
    parent_requirement_id: Optional[str] = None
    tenant_id: Optional[str] = None
    requirement_key: str
    title: str
    description: str
    category: str
    priority: str
    source_type: str
    source_reference: Optional[str] = None
    status: str
    revision: int
    expression: Dict[str, Any]
    created_by: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# Requirement Baseline Schemas
class EngineeringRequirementBaselineCreate(BaseModel):
    name: str
    knowledge_snapshot_id: Optional[str] = None


class EngineeringRequirementBaselineResponse(BaseModel):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    system_revision: int
    name: str
    baseline_hash: str
    requirement_ids: List[str]
    requirement_revisions: Dict[str, int]
    is_frozen: bool = True
    knowledge_snapshot_id: Optional[str] = None
    created_by: str
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# Assumption Schemas
class EngineeringAssumptionCreate(BaseModel):
    description: str
    basis: str
    value: Optional[str] = None
    unit: Optional[str] = None
    requirement_id: Optional[str] = None
    source_id: Optional[str] = None
    status: str = "ACTIVE"
    impact: str = "REVIEW_REQUIRED"
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True)


class EngineeringAssumptionUpdate(BaseModel):
    description: Optional[str] = None
    basis: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    requirement_id: Optional[str] = None
    source_id: Optional[str] = None
    status: Optional[str] = None
    impact: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True)


class EngineeringAssumptionResponse(BaseModel):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    requirement_id: Optional[str] = None
    description: str
    value: Optional[str] = None
    unit: Optional[str] = None
    basis: str
    source_id: Optional[str] = None
    status: str
    impact: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# Alternative Schemas
class EngineeringDecisionAlternativeCreate(BaseModel):
    candidate_id: Optional[str] = None
    name: str
    description: str
    status: str = "CONSIDERED"
    elimination_reason: Optional[str] = None
    engineering_effects: Optional[Dict[str, Any]] = Field(default_factory=dict)
    requirement_effects: Optional[Dict[str, Any]] = Field(default_factory=dict)
    verification_effects: Optional[Dict[str, Any]] = Field(default_factory=dict)
    failure_effects: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tradeoffs: Optional[Dict[str, Any]] = Field(default_factory=dict)
    unknowns: Optional[List[str]] = Field(default_factory=list)
    evidence_refs: Optional[List[str]] = Field(default_factory=list)


class EngineeringDecisionAlternativeResponse(BaseModel):
    id: str
    decision_id: str
    candidate_id: Optional[str] = None
    name: str
    description: str
    status: str
    elimination_reason: Optional[str] = None
    engineering_effects: Dict[str, Any]
    requirement_effects: Dict[str, Any]
    verification_effects: Dict[str, Any]
    failure_effects: Dict[str, Any]
    tradeoffs: Dict[str, Any]
    unknowns: List[str]
    evidence_refs: List[str]
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# Tradeoff Schemas
class EngineeringTradeoffCreate(BaseModel):
    dimension: str
    alternative_a_id: str
    alternative_b_id: str
    advantage_a: str
    disadvantage_a: str
    advantage_b: str
    disadvantage_b: str
    evidence: Optional[Dict[str, Any]] = Field(default_factory=dict)
    unknowns: Optional[List[str]] = Field(default_factory=list)


class EngineeringTradeoffResponse(BaseModel):
    id: str
    decision_id: str
    dimension: str
    alternative_a_id: str
    alternative_b_id: str
    advantage_a: str
    disadvantage_a: str
    advantage_b: str
    disadvantage_b: str
    evidence: Dict[str, Any]
    unknowns: List[str]
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# Decision Record Schemas
class EngineeringDecisionCreate(BaseModel):
    title: str
    decision_key: str
    description: str
    decision_type: str = "ARCHITECTURE"
    requirement_baseline_id: Optional[str] = None
    analysis_id: Optional[str] = None
    decision_context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True)


class EngineeringDecisionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    decision_type: Optional[str] = None
    status: Optional[str] = None
    decision_context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True)


class AlternativeSelectionRequest(BaseModel):
    alternative_id: str
    decision_rationale: str
    key_requirements: Optional[List[str]] = Field(default_factory=list)
    key_tradeoffs: Optional[List[str]] = Field(default_factory=list)
    accepted_unknowns: Optional[List[str]] = Field(default_factory=list)
    rejected_alternatives: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    verification_plan: Optional[str] = None
    freeform_explanation: Optional[str] = None


class EngineeringDecisionResponse(BaseModel):
    id: str
    system_id: str
    project_id: str
    tenant_id: Optional[str] = None
    title: str
    decision_key: str
    description: str
    decision_type: str
    status: str
    system_revision: int
    requirement_baseline_id: Optional[str] = None
    analysis_id: Optional[str] = None
    selected_alternative_id: Optional[str] = None
    decided_by: Optional[str] = None
    decided_at: Optional[datetime] = None
    superseded_by_id: Optional[str] = None
    decision_context: Dict[str, Any]
    rationale: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime
    alternatives: Optional[List[EngineeringDecisionAlternativeResponse]] = None
    tradeoffs: Optional[List[EngineeringTradeoffResponse]] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# Questions & Dispositions Schemas
class EngineeringDecisionQuestionCreate(BaseModel):
    question: str
    reason: str
    affected_object: Optional[str] = None
    affected_requirement_id: Optional[str] = None
    affected_analysis_id: Optional[str] = None
    blocking: bool = True
    review_id: Optional[str] = None


class EngineeringDecisionQuestionAnswer(BaseModel):
    answer: str
    evidence_id: Optional[str] = None


class EngineeringDecisionQuestionResponse(BaseModel):
    id: str
    decision_id: str
    review_id: Optional[str] = None
    question: str
    reason: str
    affected_object: Optional[str] = None
    affected_requirement_id: Optional[str] = None
    affected_analysis_id: Optional[str] = None
    blocking: bool
    status: str
    answer: Optional[str] = None
    answered_by: Optional[str] = None
    answered_at: Optional[datetime] = None
    evidence_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EngineeringUnknownDispositionCreate(BaseModel):
    unknown_key: str
    reason: str
    affected_requirement_id: Optional[str] = None
    status: str = "ACCEPTED"


class EngineeringUnknownDispositionResponse(BaseModel):
    id: str
    decision_id: str
    unknown_key: str
    status: str
    actor: str
    reason: str
    affected_requirement_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# Design Review Schemas
class EngineeringDesignReviewCreate(BaseModel):
    title: str
    decision_id: Optional[str] = None
    requirement_baseline_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True)


class EngineeringReviewParticipantCreate(BaseModel):
    user_id: str
    name: str
    role: str = "ENGINEER"


class EngineeringReviewParticipantResponse(BaseModel):
    id: str
    review_id: str
    user_id: str
    name: str
    role: str
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EngineeringReviewCheckpointCreate(BaseModel):
    checkpoint_name: str
    description: str
    status: str = "UNKNOWN"
    notes: Optional[str] = None


class EngineeringReviewCheckpointUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class EngineeringReviewCheckpointResponse(BaseModel):
    id: str
    review_id: str
    checkpoint_name: str
    description: str
    status: str
    notes: Optional[str] = None
    verified_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EngineeringReviewFindingCreate(BaseModel):
    source_analysis: str
    severity: str
    description: str
    finding_id: Optional[str] = None
    affected_requirement_id: Optional[str] = None
    affected_subsystem_id: Optional[str] = None


class EngineeringReviewFindingResponse(BaseModel):
    id: str
    review_id: str
    finding_id: Optional[str] = None
    source_analysis: str
    severity: str
    description: str
    affected_requirement_id: Optional[str] = None
    affected_subsystem_id: Optional[str] = None
    status: str
    waiver_rationale: Optional[str] = None
    waived_by: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EngineeringReviewActionCreate(BaseModel):
    description: str
    owner: str
    priority: str = "MEDIUM"
    due_at: Optional[datetime] = None
    linked_requirement_id: Optional[str] = None
    linked_finding_id: Optional[str] = None
    linked_verification_requirement_id: Optional[str] = None


class EngineeringReviewActionUpdate(BaseModel):
    status: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    priority: Optional[str] = None
    due_at: Optional[datetime] = None


class EngineeringReviewActionResponse(BaseModel):
    id: str
    review_id: str
    description: str
    owner: str
    priority: str
    due_at: Optional[datetime] = None
    status: str
    linked_requirement_id: Optional[str] = None
    linked_finding_id: Optional[str] = None
    linked_verification_requirement_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EngineeringDesignReviewResponse(BaseModel):
    id: str
    system_id: str
    decision_id: Optional[str] = None
    tenant_id: Optional[str] = None
    requirement_baseline_id: Optional[str] = None
    system_revision: int
    title: str
    status: str
    chairperson: str
    opened_at: datetime
    closed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime
    participants: Optional[List[EngineeringReviewParticipantResponse]] = None
    checkpoints: Optional[List[EngineeringReviewCheckpointResponse]] = None
    findings: Optional[List[EngineeringReviewFindingResponse]] = None
    actions: Optional[List[EngineeringReviewActionResponse]] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)
