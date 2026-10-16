from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.db.cognitive import (
    IntentType,
    IntentStatus,
    PlanStatus,
    TaskStatus,
    ExecutionStatus,
    ReflectionStatus,
    ReasoningFindingType,
    DecisionBriefStatus,
    HumanDecisionType,
    MemoryType,
    HistoricalOutcome,
    MemoryApplicability,
    MemoryFeedbackType,
    ContextSnapshotStatus,
    ContextConflictCategory,
)




# ============================================================================
# 1. INTENT PACKET SCHEMAS
# ============================================================================

class IntentResolveRequest(BaseModel):
    raw_request: str
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    scope: str = "CIRCUIT"
    urgency: str = "NORMAL"

    model_config = ConfigDict(populate_by_name=True)


class IntentPacketCreate(BaseModel):
    project_id: str
    raw_request: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    intent_type: str = IntentType.UNKNOWN.value
    intent_subtype: Optional[str] = None
    goal: str
    requested_action: Optional[str] = None
    entities: List[Dict[str, Any]] = Field(default_factory=list)
    requirements: List[Dict[str, Any]] = Field(default_factory=list)
    constraints: List[Dict[str, Any]] = Field(default_factory=list)
    assumptions: List[Dict[str, Any]] = Field(default_factory=list)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    affected_objects: List[Dict[str, Any]] = Field(default_factory=list)
    urgency: str = "NORMAL"
    scope: str = "CIRCUIT"
    context_confidence: float = 1.0
    ambiguities: List[Dict[str, Any]] = Field(default_factory=list)
    missing_information: List[Dict[str, Any]] = Field(default_factory=list)
    source: str = "USER_PROMPT"

    model_config = ConfigDict(populate_by_name=True)


class IntentPacketResponse(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    raw_request: str
    intent_type: str
    intent_subtype: Optional[str] = None
    goal: str
    requested_action: Optional[str] = None
    entities: List[Dict[str, Any]]
    requirements: List[Dict[str, Any]]
    constraints: List[Dict[str, Any]]
    assumptions: List[Dict[str, Any]]
    scenarios: List[Dict[str, Any]]
    affected_objects: List[Dict[str, Any]]
    urgency: str
    scope: str
    context_confidence: float
    ambiguities: List[Dict[str, Any]]
    missing_information: List[Dict[str, Any]]
    source: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# ============================================================================
# 2. CAPABILITY SCHEMAS
# ============================================================================

class CapabilityDeclaration(BaseModel):
    capability_id: str
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    required_context: List[str]
    required_permissions: List[str]
    deterministic: bool = True
    mutates_state: bool = False
    human_gate_required: bool = False
    cognitive_execution_allowed: bool = True
    supports_circuit: bool = True
    supports_system: bool = True
    supports_verification: bool = False
    supports_requirements: bool = False
    version: str = "1.0.0"
    status: str = "ACTIVE"

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# 3. TASK & PLAN SCHEMAS
# ============================================================================

class EngineeringTaskCreate(BaseModel):
    task_type: str
    description: str
    target_objects: List[Dict[str, Any]] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    required_inputs: Dict[str, Any] = Field(default_factory=dict)
    expected_outputs: List[str] = Field(default_factory=list)
    order_index: int = 0

    model_config = ConfigDict(populate_by_name=True)


class EngineeringTaskResponse(BaseModel):
    id: str
    plan_id: str
    intent_packet_id: str
    task_type: str
    description: str
    target_objects: List[Dict[str, Any]]
    dependencies: List[str]
    required_capabilities: List[str]
    required_inputs: Dict[str, Any]
    expected_outputs: List[str]
    status: str
    blocking_reason: Optional[str] = None
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class TaskPlanCreateRequest(BaseModel):
    intent_packet_id: str
    execution_policy: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class EngineeringTaskPlanResponse(BaseModel):
    id: str
    tenant_id: str
    intent_packet_id: str
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    base_revision: int
    context_snapshot_id: Optional[str] = None
    context_snapshot: Dict[str, Any]
    execution_policy: Dict[str, Any]
    status: str
    blocking_reasons: List[str]
    validated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    tasks: List[EngineeringTaskResponse] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ContextSnapshotResponse(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    project_revision: int
    system_id: Optional[str] = None
    system_revision: Optional[int] = None
    circuit_id: Optional[str] = None
    circuit_revision: Optional[int] = None
    analysis_id: Optional[str] = None
    requirement_baseline_id: Optional[str] = None
    knowledge_snapshot_id: Optional[str] = None
    assumption_ids: List[str] = Field(default_factory=list)
    scenario_ids: List[str] = Field(default_factory=list)
    engine_versions: Dict[str, Any] = Field(default_factory=dict)
    rule_set_version: str = "v1.0.0"
    context_digest: str
    context_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PlanValidationResponse(BaseModel):
    plan_id: str
    status: str  # PLAN_READY, PLAN_BLOCKED, PLAN_INVALID
    is_valid: bool
    structural_valid: bool
    context_valid: bool
    engineering_valid: bool
    security_valid: bool
    governance_valid: bool
    blocking_reasons: List[str] = Field(default_factory=list)
    task_graph: Dict[str, List[str]] = Field(default_factory=dict)
    validated_at: datetime

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# 4. EXECUTION & PROVENANCE SCHEMAS
# ============================================================================

class CognitivePlanExecuteRequest(BaseModel):
    force_revalidation: bool = False

    model_config = ConfigDict(populate_by_name=True)


class CognitiveProvenanceResponse(BaseModel):
    id: str
    cognitive_execution_id: str
    intent_packet_id: str
    plan_id: str
    context_snapshot_id: Optional[str] = None
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    base_revision: int
    model_provider: str
    model_identifier: str
    prompt_id: str = "intent_resolver"
    prompt_version: str
    schema_version: str
    capability_versions: Dict[str, Any]
    deterministic_engine_versions: Dict[str, Any]
    rule_set_version: str = "v1.0.0"
    knowledge_snapshot_id: Optional[str] = None
    input_digest: str
    output_digest: str
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class CognitiveExecutionResponse(BaseModel):
    id: str
    tenant_id: str
    plan_id: str
    intent_packet_id: str
    execution_status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    results: List[Dict[str, Any]]
    findings: List[Dict[str, Any]]
    unknowns: List[Dict[str, Any]]
    requirements_affected: List[Dict[str, Any]]
    constraints_affected: List[Dict[str, Any]]
    verification_impacts: List[Dict[str, Any]]
    traceability: List[Dict[str, Any]]
    human_actions_required: List[str]
    blocking_reasons: List[str]
    explanation: Optional[str] = None
    provenance: Optional[CognitiveProvenanceResponse] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# ============================================================================
# 5. EXPLANATION SCHEMAS
# ============================================================================

class CognitiveExplanationRequest(BaseModel):
    execution_id: str
    user_query: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class CognitiveExplanationResponse(BaseModel):
    execution_id: str
    explanation: str
    origin: str = "AI_GENERATED"
    authority: str = "INFORMATIONAL_ONLY"
    provenance_trace: Dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# 6. REFLECTION & ENGINEERING REASONING SCHEMAS
# ============================================================================

class EngineeringReasoningFindingResponse(BaseModel):
    id: str
    reflection_id: str
    finding_type: str
    severity: str
    title: str
    description: str
    affected_entity_type: str
    affected_entity_id: Optional[str] = None
    evidence_references: List[Any] = Field(default_factory=list)
    deterministic_facts: Dict[str, Any] = Field(default_factory=dict)
    recommended_remedy: Optional[str] = None
    follow_up_capability: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EngineeringReflectionProvenanceResponse(BaseModel):
    id: str
    tenant_id: str
    reflection_id: str
    execution_id: str
    plan_id: str
    context_snapshot_id: Optional[str] = None
    project_id: str
    base_revision: int
    input_digest: str
    output_digest: str
    prompt_id: str
    prompt_version: str
    rule_set_version: str
    engine_versions: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EngineeringReflectionResponse(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    base_revision: int
    execution_id: str
    plan_id: str
    context_snapshot_id: Optional[str] = None
    status: str
    reflection_cycle: int
    summary: Optional[str] = None
    has_contradictions: bool
    has_unresolved_unknowns: bool
    has_evidence_gaps: bool
    has_requirement_gaps: bool
    has_verification_gaps: bool
    additional_work_required: bool
    proposed_follow_up_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    follow_up_plan_id: Optional[str] = None
    evaluated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    findings: List[EngineeringReasoningFindingResponse] = Field(default_factory=list)
    provenance: Optional[EngineeringReflectionProvenanceResponse] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ReflectionTriggerRequest(BaseModel):
    user_focus: Optional[str] = None
    force_reevaluation: bool = False

    model_config = ConfigDict(populate_by_name=True)


class ReflectionReplanRequest(BaseModel):
    selected_finding_ids: Optional[List[str]] = None
    execution_policy: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class ReflectionReplanResponse(BaseModel):
    reflection_id: str
    follow_up_plan_id: str
    reflection_cycle: int
    status: str
    tasks_count: int
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# 7. CONTROLLED ENGINEERING DECISION BRIEF SCHEMAS
# ============================================================================

class DecisionBriefCreateRequest(BaseModel):
    project_id: str
    question: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    scope: str = "SYSTEM"
    reflection_id: Optional[str] = None
    context_snapshot_id: Optional[str] = None
    alternative_ids: Optional[List[str]] = None
    alternatives: Optional[List[Dict[str, Any]]] = None
    requirements: Optional[List[Dict[str, Any]]] = None
    constraints: Optional[List[Dict[str, Any]]] = None
    base_revision: Optional[int] = None

    model_config = ConfigDict(populate_by_name=True)


class HumanDecisionRecordRequest(BaseModel):
    decision_type: str = HumanDecisionType.ACCEPT_ALTERNATIVE.value
    selected_alternative_id: Optional[str] = None
    rationale: Any = ""
    notes: Optional[str] = None
    actor: Optional[str] = None
    current_revision: Optional[Any] = None

    model_config = ConfigDict(populate_by_name=True)


class EngineeringDecisionBriefProvenanceResponse(BaseModel):
    id: str
    tenant_id: str
    decision_brief_id: str
    context_snapshot_id: Optional[str] = None
    reflection_id: Optional[str] = None
    project_id: str
    base_revision: int
    input_digest: str
    output_digest: str
    prompt_id: str
    prompt_version: str
    rule_set_version: str
    engine_versions: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EngineeringDecisionBriefResponse(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    base_revision: int
    context_snapshot_id: Optional[str] = None
    reflection_id: Optional[str] = None
    question: str
    scope: str
    status: str
    alternative_ids: List[str] = Field(default_factory=list)
    alternatives_data: List[Dict[str, Any]] = Field(default_factory=list)
    requirement_summary: Dict[str, Any] = Field(default_factory=dict)
    constraint_summary: Dict[str, Any] = Field(default_factory=dict)
    tradeoff_summary: Dict[str, Any] = Field(default_factory=dict)
    risk_findings: List[Dict[str, Any]] = Field(default_factory=list)
    unknowns: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    verification_gaps: List[Dict[str, Any]] = Field(default_factory=list)
    consequences: Dict[str, Any] = Field(default_factory=dict)
    decision_questions: List[Dict[str, Any]] = Field(default_factory=list)
    human_decision_required: bool = True
    selected_alternative_id: Optional[str] = None
    decision_record_id: Optional[str] = None
    created_at: datetime
    provenance: Optional[EngineeringDecisionBriefProvenanceResponse] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# ============================================================================
# 8. ENGINEERING MEMORY & CONTEXTUAL LEARNING SCHEMAS
# ============================================================================

class MemoryRecordCreateRequest(BaseModel):
    project_id: str
    memory_type: str = MemoryType.DECISION_HISTORY.value
    source_entity_type: str
    source_entity_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    engineering_domain: str = "general"
    summary: str
    applicability_conditions: Optional[Dict[str, Any]] = None
    revision_context: Optional[Dict[str, Any]] = None
    historical_outcome: str = HistoricalOutcome.UNRESOLVED.value
    actor: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class MemoryFeedbackRequest(BaseModel):
    feedback_type: str = MemoryFeedbackType.USEFUL.value
    engineer_identity: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class MemoryRetrievalRequest(BaseModel):
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    engineering_domain: Optional[str] = None
    component_family: Optional[str] = None
    voltage_domain: Optional[str] = None
    current_range: Optional[str] = None
    temperature_range: Optional[str] = None
    frequency_range: Optional[str] = None
    circuit_type: Optional[str] = None
    operating_mode: Optional[str] = None
    current_parameters: Optional[Dict[str, Any]] = None
    limit: Optional[int] = 20

    model_config = ConfigDict(populate_by_name=True)


class EngineeringMemoryFeedbackResponse(BaseModel):
    id: str
    tenant_id: str
    memory_id: str
    engineer_identity: str
    feedback_type: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class EngineeringMemoryRecordResponse(BaseModel):
    id: str
    tenant_id: str
    memory_type: str
    source_entity_type: str
    source_entity_id: str
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    engineering_domain: str
    summary: str
    applicability_conditions: Dict[str, Any] = Field(default_factory=dict)
    revision_context: Dict[str, Any] = Field(default_factory=dict)
    historical_outcome: str
    is_conflicting: bool = False
    conflict_details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    feedback: Optional[List[EngineeringMemoryFeedbackResponse]] = None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SurfacedMemoryItemResponse(BaseModel):
    memory: EngineeringMemoryRecordResponse
    applicability: str
    why_surfaced: str
    historical_outcome: str
    current_relevance: str
    is_conflicting: bool = False
    conflict_details: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class MemoryRetrievalResponse(BaseModel):
    project_id: str
    total_surfaced: int
    memories: List[SurfacedMemoryItemResponse]
    retrieval_notes: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# 9. ENGINEERING CONTEXT SYNTHESIS SCHEMAS
# ============================================================================

class EngineeringContextConflict(BaseModel):
    id: str
    category: str
    source_a_type: str
    source_a_id: str
    source_b_type: str
    source_b_id: str
    description: str
    requires_human_review: bool = True

    model_config = ConfigDict(populate_by_name=True)


class ContextSynthesisRequest(BaseModel):
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    include_historical_memory: bool = True

    model_config = ConfigDict(populate_by_name=True)


class ContextExplainRequest(BaseModel):
    user_query: Optional[str] = None
    focus_areas: Optional[List[str]] = None

    model_config = ConfigDict(populate_by_name=True)


class EngineeringContextSnapshotResponse(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    base_revision: int
    context_snapshot_id: Optional[str] = None
    status: str
    canonical_digest: str
    current_state: Dict[str, Any] = Field(default_factory=dict)
    authoritative_facts: List[Dict[str, Any]] = Field(default_factory=list)
    deterministic_results: List[Dict[str, Any]] = Field(default_factory=list)
    requirements: List[Dict[str, Any]] = Field(default_factory=list)
    constraints: List[Dict[str, Any]] = Field(default_factory=list)
    assumptions: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    unknowns: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_state: Dict[str, Any] = Field(default_factory=dict)
    verification_state: Dict[str, Any] = Field(default_factory=dict)
    decision_history: List[Dict[str, Any]] = Field(default_factory=list)
    historical_memory: List[Dict[str, Any]] = Field(default_factory=list)
    traceability_state: Dict[str, Any] = Field(default_factory=dict)
    reflection_state: Dict[str, Any] = Field(default_factory=dict)
    conflicts: List[EngineeringContextConflict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ContextExplanationResponse(BaseModel):
    context_id: str
    explanation: str
    origin: str = "AI_GENERATED"
    authority: str = "INFORMATIONAL_ONLY"
    traceable_references: List[Dict[str, Any]] = Field(default_factory=list)
    unreferenced_assertions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# 10. WORKFLOW ORCHESTRATION SCHEMAS
# ============================================================================

class WorkflowStartRequest(BaseModel):
    project_id: str
    circuit_id: Optional[str] = None
    system_id: Optional[str] = None
    user_request: str
    scope: Optional[str] = "CIRCUIT"
    urgency: Optional[str] = "NORMAL"

    model_config = ConfigDict(populate_by_name=True)


class WorkflowContinueRequest(BaseModel):
    clarifications: Optional[Dict[str, Any]] = None
    selected_alternative_id: Optional[str] = None
    decision_notes: Optional[str] = None
    action: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class WorkflowTimelineStep(BaseModel):
    step: str
    status: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str

    model_config = ConfigDict(populate_by_name=True)


class EngineeringCognitiveWorkflowResponse(BaseModel):
    id: str
    tenant_id: str
    project_id: str
    system_id: Optional[str] = None
    circuit_id: Optional[str] = None
    base_revision: int
    status: str
    current_step: str
    user_request: str

    intent_packet_id: Optional[str] = None
    context_snapshot_id: Optional[str] = None
    plan_id: Optional[str] = None
    execution_id: Optional[str] = None
    reflection_id: Optional[str] = None
    decision_brief_id: Optional[str] = None
    synthesized_context_id: Optional[str] = None

    reflection_cycles: int = 0
    blocking_reasons: List[str] = Field(default_factory=list)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    integrity_digest: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# ============================================================================
# 11. INTERACTION & EXPLAINABILITY SCHEMAS (Phase 2 Wave 7)
# ============================================================================

class ExplanationCategory(str, Enum):
    WHY = "WHY"
    WHAT_CHANGED = "WHAT_CHANGED"
    WHAT_IS_UNKNOWN = "WHAT_IS_UNKNOWN"
    WHAT_SUPPORTS_THIS = "WHAT_SUPPORTS_THIS"
    WHAT_CONFLICTS = "WHAT_CONFLICTS"
    WHAT_REQUIREMENTS_ARE_AFFECTED = "WHAT_REQUIREMENTS_ARE_AFFECTED"
    WHAT_EVIDENCE_IS_MISSING = "WHAT_EVIDENCE_IS_MISSING"
    WHAT_REQUIRES_VERIFICATION = "WHAT_REQUIRES_VERIFICATION"
    WHAT_REQUIRES_HUMAN_DECISION = "WHAT_REQUIRES_HUMAN_DECISION"
    WHY_IS_THIS_BLOCKED = "WHY_IS_THIS_BLOCKED"
    WHY_IS_THIS_STALE = "WHY_IS_THIS_STALE"


class EngineeringExplanationRequest(BaseModel):
    category: str = "WHY"
    user_query: Optional[str] = None
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[str] = None
    focus_areas: Optional[List[str]] = Field(default_factory=list)
    asserted_references: Optional[List[str]] = Field(default_factory=list)
    candidate_statements: Optional[List[str]] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class EvidenceChainNode(BaseModel):
    step: str
    entity_type: str
    entity_id: str
    description: str
    is_physical: bool = False
    is_calculation: bool = False

    model_config = ConfigDict(populate_by_name=True)


class HumanActionItem(BaseModel):
    action_type: str
    title: str
    description: str
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[str] = None
    urgency: str = "NORMAL"

    model_config = ConfigDict(populate_by_name=True)


class EngineeringExplanationResponse(BaseModel):
    context_id: Optional[str] = None
    workflow_id: Optional[str] = None
    category: str
    statement: str
    explanation: str  # For backward compatibility with ContextExplanationResponse
    source_entity_type: Optional[str] = None
    source_entity_id: Optional[str] = None
    base_revision: int = 1
    is_stale: bool = False
    stale_factors: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    requirement_refs: List[str] = Field(default_factory=list)
    finding_refs: List[str] = Field(default_factory=list)
    assumption_refs: List[str] = Field(default_factory=list)
    decision_refs: List[str] = Field(default_factory=list)
    verification_refs: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    evidence_chain: List[EvidenceChainNode] = Field(default_factory=list)
    human_actions: List[HumanActionItem] = Field(default_factory=list)
    changes_detected: List[Dict[str, Any]] = Field(default_factory=list)
    origin: str = "AI_GROUNDED_EXPLANATION"
    authority: str = "INFORMATIONAL_ONLY"
    traceable_references: List[Dict[str, Any]] = Field(default_factory=list)
    unreferenced_assertions: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# 12. VERIFICATION & EVIDENCE WORKSPACE SCHEMAS (Phase 2 Wave 8)
# ============================================================================

class EvidenceSufficiencyStatus(str, Enum):
    SUFFICIENT = "SUFFICIENT"
    INSUFFICIENT = "INSUFFICIENT"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceRegisterRequest(BaseModel):
    evidence_type: str = "MEASUREMENT"  # MEASUREMENT, LAB_OBSERVATION, TEST_REPORT, CALCULATION, SIMULATION_REPORT, DATASHEET
    source: str
    description: str
    value: Optional[str] = None
    unit: Optional[str] = None
    reference: Optional[str] = None
    is_physical: bool = False
    instrument: Optional[str] = None
    instrument_model: Optional[str] = None
    instrument_serial: Optional[str] = None
    calibration_reference: Optional[str] = None
    calibration_status: Optional[str] = "CALIBRATED"
    bound_entity_type: Optional[str] = None
    bound_entity_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class VerificationCloseRequest(BaseModel):
    decision: str = "VERIFIED"  # VERIFIED, FAILED, WAIVED
    rationale: str
    actor: str
    waiver_reason: Optional[str] = None
    current_revision: Optional[int] = None

    model_config = ConfigDict(populate_by_name=True)


class VerificationWorkspaceObligation(BaseModel):
    verification_requirement_id: str
    code: str
    title: str
    reason: str
    method: str
    operating_condition: str
    is_mandatory: bool = True
    status: str
    related_requirement_id: Optional[str] = None
    related_requirement_code: Optional[str] = None
    related_finding_id: Optional[str] = None
    required_evidence_types: List[str] = Field(default_factory=list)
    attached_evidence_items: List[Dict[str, Any]] = Field(default_factory=list)
    sufficiency: str
    is_physical_required: bool = False
    has_physical_evidence: bool = False
    is_stale: bool = False
    stale_reasons: List[str] = Field(default_factory=list)
    human_action_required: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class VerificationWorkspaceSummary(BaseModel):
    total_obligations: int
    verified_count: int
    pending_count: int
    blocked_count: int
    stale_count: int
    missing_evidence_count: int
    insufficient_evidence_count: int
    physical_tests_pending: int
    unresolved_unknowns_count: int
    outstanding_human_actions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class VerificationWorkspaceResponse(BaseModel):
    workspace_id: str
    workflow_id: Optional[str] = None
    review_id: Optional[str] = None
    project_id: str
    circuit_id: Optional[str] = None
    system_id: Optional[str] = None
    base_revision: int = 1
    is_stale: bool = False
    stale_factors: List[str] = Field(default_factory=list)
    obligations: List[VerificationWorkspaceObligation] = Field(default_factory=list)
    summary: VerificationWorkspaceSummary
    provenance_integrity_digest: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True)


# ============================================================================
# 13. COGNITIVE ENGINEERING ACTION & CLOSURE CENTER SCHEMAS (Phase 2 Wave 9)
# ============================================================================

class ActionCenterCategory(str, Enum):
    ALL = "ALL"
    BLOCKED = "BLOCKED"
    DECISIONS = "DECISIONS"
    EVIDENCE = "EVIDENCE"
    VERIFICATION = "VERIFICATION"
    REVIEWS = "REVIEWS"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"


class EngineeringActionItem(BaseModel):
    action_id: str
    action_type: str  # CLARIFICATION_REQUIRED, UNKNOWN, REQUIREMENT_GAP, CONSTRAINT_GAP, ASSUMPTION_REVIEW, FINDING_REVIEW, EVIDENCE_REQUIRED, VERIFICATION_REQUIRED, VERIFICATION_CLOSURE, DECISION_REQUIRED, REVIEW_ACTION_REQUIRED, STALE_CONTEXT, STALE_EVIDENCE, BLOCKED_WORKFLOW
    category: str     # BLOCKED, DECISIONS, EVIDENCE, VERIFICATION, REVIEWS, UNKNOWN, STALE
    title: str
    description: str
    source_entity_type: str
    source_entity_id: str
    project_id: str
    circuit_id: Optional[str] = None
    system_id: Optional[str] = None
    revision: int = 1
    current_status: str
    required_human_action: str
    blocking_reason: Optional[str] = None
    related_entity_refs: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_by: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    is_stale: bool = False
    stale_factors: List[str] = Field(default_factory=list)
    route_target: str  # "VERIFICATION_WORKSPACE", "DECISION_BRIEF", "DESIGN_REVIEW", "WORKFLOW", "CIRCUIT", "SYSTEM"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True)


class EngineeringActionCenterSummary(BaseModel):
    total_actions: int
    blocked_count: int
    decisions_count: int
    evidence_count: int
    verification_count: int
    reviews_count: int
    unknowns_count: int
    stale_count: int
    outstanding_categories: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class EngineeringActionCenterResponse(BaseModel):
    project_id: str
    circuit_id: Optional[str] = None
    system_id: Optional[str] = None
    base_revision: int = 1
    actions: List[EngineeringActionItem] = Field(default_factory=list)
    summary: EngineeringActionCenterSummary
    provenance_integrity_digest: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(populate_by_name=True)




