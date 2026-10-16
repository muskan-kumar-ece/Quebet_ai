export type IntentType =
  | "ANALYZE_CIRCUIT"
  | "ANALYZE_SYSTEM"
  | "INVESTIGATE_FINDING"
  | "INVESTIGATE_FAILURE"
  | "PLAN_VERIFICATION"
  | "EXPLORE_DESIGN_ALTERNATIVES"
  | "EXPLORE_SYSTEM_ALTERNATIVES"
  | "COMPARE_ALTERNATIVES"
  | "CHECK_REQUIREMENTS"
  | "CHECK_CONSTRAINTS"
  | "TRACE_ENGINEERING_FACT"
  | "EXPLAIN_ENGINEERING_RESULT"
  | "REVIEW_DESIGN"
  | "UNKNOWN";

export type IntentStatus =
  | "DRAFT"
  | "CAPTURED"
  | "INTERPRETED"
  | "CLARIFICATION_REQUIRED"
  | "PLANNING_READY"
  | "PLANNING_BLOCKED";

export type PlanStatus =
  | "DRAFT"
  | "RESOLUTION_REQUIRED"
  | "READY_FOR_VALIDATION"
  | "VALIDATION_FAILED"
  | "VALIDATED"
  | "READY"
  | "EXECUTING"
  | "PARTIAL"
  | "COMPLETED"
  | "BLOCKED"
  | "STALE"
  | "FAILED";

export interface IntentEntity {
  type: string;
  value?: string | number;
  unit?: string;
  raw?: string;
  ref_des?: string;
}

export interface AmbiguityCandidate {
  ref_des: string;
  name?: string;
  value?: string;
}

export interface IntentAmbiguity {
  type: string;
  target: string;
  status: string; // DETECTED | CLARIFICATION_REQUIRED | AUTO_RESOLVED | USER_SPECIFIED
  reason: string;
  action_required?: string;
  candidates?: AmbiguityCandidate[];
  resolved_component?: string;
}

export interface EngineeringIntentPacket {
  id: string;
  tenant_id: string;
  project_id: string;
  system_id?: string | null;
  circuit_id?: string | null;
  raw_request: string;
  intent_type: IntentType;
  intent_subtype?: string | null;
  goal: string;
  requested_action?: string | null;
  entities: IntentEntity[];
  requirements: Record<string, any>[];
  constraints: Record<string, any>[];
  assumptions: Record<string, any>[];
  scenarios: Record<string, any>[];
  affected_objects: Record<string, any>[];
  urgency: string;
  scope: string;
  context_confidence: number;
  ambiguities: IntentAmbiguity[];
  missing_information: Record<string, any>[];
  source: string;
  status: IntentStatus;
  created_at: string;
  updated_at: string;
}

export interface EngineeringTask {
  id: string;
  plan_id: string;
  intent_packet_id: string;
  task_type: string;
  description: string;
  target_objects: Record<string, any>[];
  dependencies: string[];
  required_capabilities: string[];
  required_inputs: Record<string, any>;
  expected_outputs: string[];
  status: "PENDING" | "READY" | "RUNNING" | "COMPLETED" | "FAILED" | "BLOCKED";
  blocking_reason?: string | null;
  order_index: number;
  created_at: string;
  updated_at: string;
}

export interface ContextSnapshot {
  id: string;
  tenant_id: string;
  project_id: string;
  project_revision: number;
  system_id?: string | null;
  system_revision?: number | null;
  circuit_id?: string | null;
  circuit_revision?: number | null;
  analysis_id?: string | null;
  requirement_baseline_id?: string | null;
  knowledge_snapshot_id?: string | null;
  assumption_ids: string[];
  scenario_ids: string[];
  engine_versions: Record<string, any>;
  rule_set_version: string;
  context_digest: string;
  context_payload: Record<string, any>;
  created_at: string;
}

export interface EngineeringTaskPlan {
  id: string;
  tenant_id: string;
  intent_packet_id: string;
  project_id: string;
  system_id?: string | null;
  circuit_id?: string | null;
  base_revision: number;
  context_snapshot_id?: string | null;
  context_snapshot: Record<string, any>;
  execution_policy: Record<string, any>;
  status: PlanStatus;
  blocking_reasons: string[];
  tasks: EngineeringTask[];
  validated_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlanValidationResult {
  plan_id: string;
  status: string;
  is_valid: boolean;
  structural_valid: boolean;
  context_valid: boolean;
  engineering_valid: boolean;
  security_valid: boolean;
  governance_valid: boolean;
  blocking_reasons: string[];
  task_graph: Record<string, string[]>;
  validated_at: string;
}

export interface CognitiveProvenance {
  id: string;
  cognitive_execution_id: string;
  intent_packet_id: string;
  plan_id: string;
  context_snapshot_id?: string | null;
  project_id: string;
  system_id?: string | null;
  circuit_id?: string | null;
  base_revision: number;
  model_provider: string;
  model_identifier: string;
  prompt_id: string;
  prompt_version: string;
  schema_version: string;
  capability_versions: Record<string, any>;
  deterministic_engine_versions: Record<string, any>;
  rule_set_version: string;
  knowledge_snapshot_id?: string | null;
  input_digest: string;
  output_digest: string;
  created_at: string;
}

export interface CognitiveExecution {
  id: string;
  tenant_id: string;
  plan_id: string;
  intent_packet_id: string;
  execution_status: "SUCCESS" | "FAILED" | "PARTIAL" | "RUNNING";
  started_at: string;
  completed_at?: string | null;
  results: Record<string, any>[];
  findings: Record<string, any>[];
  unknowns: Record<string, any>[];
  requirements_affected: Record<string, any>[];
  constraints_affected: Record<string, any>[];
  verification_impacts: Record<string, any>[];
  traceability: Record<string, any>[];
  human_actions_required: string[];
  blocking_reasons: string[];
  explanation?: string | null;
  provenance?: CognitiveProvenance | null;
}

export interface CognitiveExplanation {
  execution_id: string;
  explanation: string;
  origin: string; // AI_GENERATED
  authority: string; // INFORMATIONAL_ONLY
  provenance_trace: {
    model: string;
    prompt_version: string;
    base_revision: number;
    input_digest: string;
  };
}

export type ReasoningFindingType =
  | "MISSING_INFORMATION"
  | "UNRESOLVED_UNKNOWN"
  | "CONTRADICTORY_RESULT"
  | "INSUFFICIENT_EVIDENCE"
  | "REQUIREMENT_GAP"
  | "VERIFICATION_GAP"
  | "ASSUMPTION_CONFLICT"
  | "KNOWLEDGE_GAP"
  | "STALE_CONTEXT"
  | "INCOMPLETE_ANALYSIS"
  | "CONSTRAINT_GAP"
  | "TRACEABILITY_GAP";

export type ReasoningFindingSeverity = "INFO" | "WARNING" | "CRITICAL";

export interface EngineeringReasoningFinding {
  id: string;
  reflection_id: string;
  finding_type: ReasoningFindingType;
  severity: ReasoningFindingSeverity;
  title: string;
  description: string;
  affected_entity_type: string;
  affected_entity_id?: string | null;
  evidence_references: any[];
  deterministic_facts: Record<string, any>;
  recommended_remedy?: string | null;
  follow_up_capability?: string | null;
  created_at: string;
}

export interface EngineeringReflectionProvenance {
  id: string;
  tenant_id: string;
  reflection_id: string;
  execution_id: string;
  plan_id: string;
  context_snapshot_id?: string | null;
  project_id: string;
  base_revision: number;
  input_digest: string;
  output_digest: string;
  prompt_id: string;
  prompt_version: string;
  rule_set_version: string;
  engine_versions: Record<string, any>;
  created_at: string;
}

export interface EngineeringReflection {
  id: string;
  tenant_id: string;
  project_id: string;
  system_id?: string | null;
  circuit_id?: string | null;
  base_revision: number;
  execution_id: string;
  plan_id: string;
  context_snapshot_id?: string | null;
  status: "PENDING" | "ANALYZING" | "COMPLETE" | "ADDITIONAL_WORK_REQUIRED" | "BLOCKED" | "STALE" | "FAILED";
  reflection_cycle: number;
  summary?: string | null;
  has_contradictions: boolean;
  has_unresolved_unknowns: boolean;
  has_evidence_gaps: boolean;
  has_requirement_gaps: boolean;
  has_verification_gaps: boolean;
  additional_work_required: boolean;
  proposed_follow_up_tasks: Record<string, any>[];
  follow_up_plan_id?: string | null;
  evaluated_at?: string | null;
  completed_at?: string | null;
  created_at: string;
  findings: EngineeringReasoningFinding[];
  provenance?: EngineeringReflectionProvenance | null;
}

export interface ReflectionReplanResult {
  reflection_id: string;
  follow_up_plan_id: string;
  reflection_cycle: number;
  status: string;
  tasks_count: number;
  created_at: string;
}

// ============================================================================
// PHASE 2 WAVE 3: CONTROLLED ENGINEERING DECISION BRIEF TYPES
// ============================================================================

export type DecisionBriefStatus =
  | "DRAFT"
  | "ANALYZING"
  | "READY_FOR_REVIEW"
  | "DECIDED"
  | "BLOCKED"
  | "STALE"
  | "SUPERSEDED";

export type HumanDecisionType =
  | "ACCEPT_ALTERNATIVE"
  | "ADOPT_ALTERNATIVE"
  | "REJECT_ALTERNATIVES"
  | "REJECT_ALL"
  | "REQUEST_MORE_ANALYSIS"
  | "REQUEST_MORE_EVIDENCE"
  | "DEFER_DECISION"
  | "CHANGE_REQUIREMENT"
  | "CHANGE_CONSTRAINT";

export interface DecisionAlternative {
  id: string;
  name: string;
  description?: string;
  topology?: string;
  parameters?: Record<string, any>;
  engineering_effects?: Record<string, any>;
  affected_components?: string[];
  affected_subsystems?: string[];
  affected_interfaces?: string[];
  unknowns?: string[];
  evidence_gaps?: string[];
  verification_gaps?: string[];
  tradeoffs?: {
    advantages?: string[];
    disadvantages?: string[];
  };
}

export interface DecisionQuestion {
  id: string;
  question: string;
  origin: "AI_GENERATED" | "HUMAN_ENGINEER" | "SYSTEM_AUDIT";
  status: "INFORMATIONAL" | "RESOLVED" | "DEFERRED";
  human_response_required: boolean;
  context?: string;
}

export interface EngineeringDecisionBriefProvenance {
  id: string;
  tenant_id: string;
  decision_brief_id: string;
  context_snapshot_id?: string | null;
  reflection_id?: string | null;
  project_id: string;
  base_revision: number;
  input_digest: string;
  output_digest: string;
  prompt_id: string;
  prompt_version: string;
  rule_set_version: string;
  engine_versions: Record<string, any>;
  created_at: string;
}

export interface EngineeringDecisionBrief {
  id: string;
  tenant_id: string;
  project_id: string;
  system_id?: string | null;
  circuit_id?: string | null;
  base_revision: number;
  context_snapshot_id?: string | null;
  reflection_id?: string | null;
  question: string;
  scope: string;
  status: DecisionBriefStatus;
  alternative_ids: string[];
  alternatives_data: DecisionAlternative[];
  requirement_summary: Record<string, any>;
  constraint_summary: Record<string, any>;
  tradeoff_summary: Record<string, any>;
  risk_findings: Record<string, any>[];
  unknowns: Record<string, any>[];
  evidence_gaps: Record<string, any>[];
  verification_gaps: Record<string, any>[];
  consequences: Record<string, any>;
  decision_questions: DecisionQuestion[];
  human_decision_required: boolean;
  selected_alternative_id?: string | null;
  decision_record_id?: string | null;
  created_at: string;
  provenance?: EngineeringDecisionBriefProvenance | null;
}

export type MemoryType =
  | "DECISION_HISTORY"
  | "DESIGN_FINDING"
  | "VERIFICATION_LESSON"
  | "FAILURE_LESSON"
  | "ASSUMPTION_HISTORY"
  | "REQUIREMENT_HISTORY"
  | "TRADEOFF_HISTORY"
  | "ENGINEERING_PATTERN";

export type HistoricalOutcome =
  | "VERIFIED_SUCCESS"
  | "VERIFIED_FAILURE"
  | "PARTIAL_RESULT"
  | "UNRESOLVED"
  | "SUPERSEDED";

export type MemoryApplicability =
  | "APPLICABLE"
  | "POTENTIALLY_APPLICABLE"
  | "NOT_APPLICABLE"
  | "UNKNOWN";

export type MemoryFeedbackType =
  | "USEFUL"
  | "NOT_RELEVANT"
  | "INCORRECT_HISTORY"
  | "OUTDATED"
  | "APPLICABLE"
  | "NOT_APPLICABLE";

export interface EngineeringMemoryFeedback {
  id: string;
  tenant_id: string;
  memory_id: string;
  engineer_identity: string;
  feedback_type: MemoryFeedbackType;
  notes?: string | null;
  created_at: string;
}

export interface EngineeringMemoryRecord {
  id: string;
  tenant_id: string;
  memory_type: MemoryType;
  source_entity_type: string;
  source_entity_id: string;
  project_id: string;
  system_id?: string | null;
  circuit_id?: string | null;
  engineering_domain: string;
  summary: string;
  applicability_conditions: Record<string, any>;
  revision_context: Record<string, any>;
  historical_outcome: HistoricalOutcome;
  is_conflicting: boolean;
  conflict_details: Record<string, any>;
  created_at: string;
  updated_at: string;
  feedback?: EngineeringMemoryFeedback[];
}

export interface SurfacedMemoryItem {
  memory: EngineeringMemoryRecord;
  applicability: MemoryApplicability;
  why_surfaced: string;
  historical_outcome: HistoricalOutcome;
  current_relevance: string;
  is_conflicting: boolean;
  conflict_details: Record<string, any>;
  warnings: string[];
}

export interface MemoryRetrievalResponse {
  project_id: string;
  total_surfaced: number;
  memories: SurfacedMemoryItem[];
  retrieval_notes?: string | null;
}

// ============================================================================
// Phase 2 Wave 5: Engineering Context Synthesis & Cognitive State
// ============================================================================

export type ContextSnapshotStatus = "CURRENT" | "STALE" | "SUPERSEDED";

export type ContextConflictCategory =
  | "SPECIFICATION_CONFLICT"
  | "ANALYSIS_CONFLICT"
  | "EVIDENCE_CONFLICT"
  | "DECISION_CONFLICT"
  | "ASSUMPTION_CONFLICT"
  | "MEMORY_CONFLICT"
  | "REVISION_CONFLICT";

export interface EngineeringContextConflict {
  id: string;
  category: ContextConflictCategory;
  source_a_type: string;
  source_a_id: string;
  source_b_type: string;
  source_b_id: string;
  description: string;
  requires_human_review: boolean;
}

export interface EngineeringContextSnapshot {
  id: string;
  tenant_id: string;
  project_id: string;
  system_id?: string | null;
  circuit_id?: string | null;
  base_revision: number;
  context_snapshot_id?: string | null;
  status: ContextSnapshotStatus;
  canonical_digest: string;
  current_state: Record<string, any>;
  authoritative_facts: Record<string, any>[];
  deterministic_results: Record<string, any>[];
  requirements: Record<string, any>[];
  constraints: Record<string, any>[];
  assumptions: Record<string, any>[];
  findings: Record<string, any>[];
  unknowns: Record<string, any>[];
  evidence_state: Record<string, any>;
  verification_state: Record<string, any>;
  decision_history: Record<string, any>[];
  historical_memory: Record<string, any>[];
  traceability_state: Record<string, any>;
  reflection_state: Record<string, any>;
  conflicts: EngineeringContextConflict[];
  created_at: string;
  updated_at: string;
}

export interface ContextSynthesisRequest {
  project_id: string;
  system_id?: string | null;
  circuit_id?: string | null;
  include_historical_memory?: boolean;
}

export interface ContextExplainRequest {
  user_query: string;
  focus_areas?: string[];
  max_tokens?: number;
}

export interface ContextExplanationResponse {
  context_id: string;
  explanation: string;
  referenced_ids: string[];
  confidence_notice: string;
  model_id: string;
}

export type CognitiveWorkflowStatus =
  | "RECEIVED"
  | "INTENT_RESOLVED"
  | "CONTEXT_RESOLVED"
  | "PLAN_READY"
  | "EXECUTING"
  | "REFLECTING"
  | "ADDITIONAL_WORK_REQUIRED"
  | "DECISION_PREPARATION"
  | "CONTEXT_SYNTHESIS"
  | "AWAITING_HUMAN"
  | "COMPLETED"
  | "BLOCKED"
  | "STALE"
  | "FAILED";

export interface WorkflowTimelineStep {
  step: string;
  status: string;
  details?: Record<string, any>;
  timestamp: string;
}

export interface EngineeringCognitiveWorkflow {
  id: string;
  tenant_id: string;
  project_id: string;
  system_id?: string | null;
  circuit_id?: string | null;
  base_revision: number;
  status: CognitiveWorkflowStatus;
  current_step: string;
  user_request: string;
  intent_packet_id?: string | null;
  context_snapshot_id?: string | null;
  plan_id?: string | null;
  execution_id?: string | null;
  reflection_id?: string | null;
  decision_brief_id?: string | null;
  synthesized_context_id?: string | null;
  reflection_cycles: number;
  blocking_reasons: string[];
  timeline: WorkflowTimelineStep[];
  integrity_digest: string;
  created_at: string;
  updated_at: string;
}

export interface WorkflowStartRequest {
  project_id: string;
  circuit_id?: string | null;
  system_id?: string | null;
  user_request: string;
  scope?: string;
  urgency?: string;
}

export interface WorkflowContinueRequest {
  clarifications?: Record<string, any>;
  selected_alternative_id?: string;
  decision_notes?: string;
  action?: string;
}

// ============================================================================
// Phase 2 Wave 7: Engineering Cognitive Interaction & Explainability Types
// ============================================================================

export type ExplanationCategory =
  | "WHY"
  | "WHAT_CHANGED"
  | "WHAT_IS_UNKNOWN"
  | "WHAT_SUPPORTS_THIS"
  | "WHAT_CONFLICTS"
  | "WHAT_REQUIREMENTS_ARE_AFFECTED"
  | "WHAT_EVIDENCE_IS_MISSING"
  | "WHAT_REQUIRES_VERIFICATION"
  | "WHAT_REQUIRES_HUMAN_DECISION"
  | "WHY_IS_THIS_BLOCKED"
  | "WHY_IS_THIS_STALE";

export interface EvidenceChainNode {
  step: string;
  entity_type: string;
  entity_id: string;
  description: string;
  is_physical: boolean;
  is_calculation: boolean;
}

export interface HumanActionItem {
  action_type: string;
  title: string;
  description: string;
  target_entity_type?: string | null;
  target_entity_id?: string | null;
  urgency: string;
}

export interface EngineeringExplanationRequest {
  category?: ExplanationCategory | string;
  user_query?: string;
  target_entity_type?: string;
  target_entity_id?: string;
  focus_areas?: string[];
  asserted_references?: string[];
  candidate_statements?: string[];
}

export interface EngineeringExplanationResponse {
  context_id?: string | null;
  workflow_id?: string | null;
  category: string;
  statement: string;
  explanation: string;
  source_entity_type?: string | null;
  source_entity_id?: string | null;
  base_revision: number;
  is_stale: boolean;
  stale_factors: string[];
  evidence_refs: string[];
  requirement_refs: string[];
  finding_refs: string[];
  assumption_refs: string[];
  decision_refs: string[];
  verification_refs: string[];
  unknowns: string[];
  evidence_chain: EvidenceChainNode[];
  human_actions: HumanActionItem[];
  changes_detected: Record<string, any>[];
  origin: string;
  authority: string;
  traceable_references: Record<string, any>[];
  unreferenced_assertions: string[];
  created_at: string;
}

export type EvidenceSufficiencyStatus =
  | "SUFFICIENT"
  | "INSUFFICIENT"
  | "MISSING"
  | "UNKNOWN"
  | "NOT_APPLICABLE";

export interface EvidenceRegisterRequest {
  evidence_type: string;
  source: string;
  description: string;
  value?: string;
  unit?: string;
  reference?: string;
  is_physical?: boolean;
  instrument?: string;
  instrument_model?: string;
  instrument_serial?: string;
  calibration_reference?: string;
  calibration_status?: string;
  bound_entity_type?: string;
  bound_entity_id?: string;
  metadata?: Record<string, any>;
}

export interface VerificationCloseRequest {
  decision: "VERIFIED" | "FAILED" | "WAIVED" | string;
  rationale: string;
  actor: string;
  waiver_reason?: string;
  current_revision?: number;
}

export interface VerificationWorkspaceObligation {
  verification_requirement_id: string;
  code: string;
  title: string;
  reason: string;
  method: string;
  operating_condition: string;
  is_mandatory: boolean;
  status: string;
  related_requirement_id?: string | null;
  related_requirement_code?: string | null;
  related_finding_id?: string | null;
  required_evidence_types: string[];
  attached_evidence_items: Record<string, any>[];
  sufficiency: string;
  is_physical_required: boolean;
  has_physical_evidence: boolean;
  is_stale: boolean;
  stale_reasons: string[];
  human_action_required?: string | null;
}

export interface VerificationWorkspaceSummary {
  total_obligations: number;
  verified_count: number;
  pending_count: number;
  blocked_count: number;
  stale_count: number;
  missing_evidence_count: number;
  insufficient_evidence_count: number;
  physical_tests_pending: number;
  unresolved_unknowns_count: number;
  outstanding_human_actions: string[];
}

export interface VerificationWorkspaceResponse {
  workspace_id: string;
  workflow_id?: string | null;
  review_id?: string | null;
  project_id: string;
  circuit_id?: string | null;
  system_id?: string | null;
  base_revision: number;
  is_stale: boolean;
  stale_factors: string[];
  obligations: VerificationWorkspaceObligation[];
  summary: VerificationWorkspaceSummary;
  provenance_integrity_digest: string;
  created_at: string;
}

export type ActionCenterCategory =
  | "ALL"
  | "BLOCKED"
  | "DECISIONS"
  | "EVIDENCE"
  | "VERIFICATION"
  | "REVIEWS"
  | "UNKNOWN"
  | "STALE";

export interface EngineeringActionItem {
  action_id: string;
  action_type: string;
  category: string;
  title: string;
  description: string;
  source_entity_type: string;
  source_entity_id: string;
  project_id: string;
  circuit_id?: string | null;
  system_id?: string | null;
  revision: number;
  current_status: string;
  required_human_action: string;
  blocking_reason?: string | null;
  related_entity_refs: Record<string, any>[];
  blocked_by: string[];
  depends_on: string[];
  is_stale: boolean;
  stale_factors: string[];
  route_target: string;
  created_at: string;
}

export interface EngineeringActionCenterSummary {
  total_actions: number;
  blocked_count: number;
  decisions_count: number;
  evidence_count: number;
  verification_count: number;
  reviews_count: number;
  unknowns_count: number;
  stale_count: number;
  outstanding_categories: string[];
}

export interface EngineeringActionCenterResponse {
  project_id: string;
  circuit_id?: string | null;
  system_id?: string | null;
  base_revision: number;
  actions: EngineeringActionItem[];
  summary: EngineeringActionCenterSummary;
  provenance_integrity_digest: string;
  created_at: string;
}
