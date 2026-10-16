/**
 * Phase 1 Wave 9 — Engineering Decision Intelligence & Review Orchestration
 * TypeScript Type Definitions
 */

export type RequirementCategory =
  | "FUNCTIONAL"
  | "ELECTRICAL"
  | "THERMAL"
  | "INTERFACE"
  | "SAFETY"
  | "COMPLIANCE"
  | "ENVIRONMENTAL"
  | "MANUFACTURING"
  | "RELIABILITY"
  | "OTHER";

export type RequirementPriority = "SHALL" | "SHOULD" | "MAY";

export type RequirementStatus =
  | "DRAFT"
  | "PROPOSED"
  | "APPROVED"
  | "DEPRECATED"
  | "SUPERSEDED"
  | "REJECTED";

export type CoverageStatus =
  | "COVERED"
  | "PARTIALLY_COVERED"
  | "NOT_COVERED"
  | "UNKNOWN";

export type VerificationMethod =
  | "ANALYSIS"
  | "SIMULATION"
  | "TEST"
  | "INSPECTION"
  | "DEMONSTRATION";

export type AssumptionStatus =
  | "ACTIVE"
  | "VALIDATED"
  | "INVALIDATED"
  | "SUPERSEDED"
  | "RETIRED";

export type AssumptionImpact =
  | "NEGLIGIBLE"
  | "REVIEW_REQUIRED"
  | "CRITICAL"
  | "INVALIDATES_ARCHITECTURE";

export type DecisionType =
  | "ARCHITECTURE_ALTERNATIVE"
  | "COMPONENT_SELECTION"
  | "POWER_BUDGET"
  | "PROTECTION_STRATEGY"
  | "INTERFACE_PROTOCOL"
  | "VERIFICATION_STRATEGY"
  | "DEVIATION_WAIVER";

export type DecisionStatus =
  | "DRAFT"
  | "PROPOSED"
  | "UNDER_REVIEW"
  | "DECIDED"
  | "SUPERSEDED"
  | "REJECTED";

export type AlternativeStatus =
  | "CONSIDERED"
  | "REJECTED"
  | "SELECTED_BY_ENGINEER"
  | "NOT_SELECTED"
  | "ELIMINATED";

export type ReviewStatus =
  | "PREPARATION"
  | "IN_REVIEW"
  | "ACTIONS_PENDING"
  | "ACCEPTED"
  | "REJECTED"
  | "CLOSED"
  | "CANCELLED";

export type FindingSeverity = "INFO" | "MINOR" | "MAJOR" | "CRITICAL" | "BLOCKER";

export type FindingStatus = "OPEN" | "WAIVED" | "RESOLVED" | "ACTION_REQUIRED" | "DISMISSED";

export type QuestionStatus = "OPEN" | "ANSWERED" | "DISMISSED";

export type UnknownDispositionStatus = "ACCEPTED" | "INVESTIGATING" | "DEFERRED" | "REJECTED";

export interface StructuredExpression {
  parameter?: string;
  operator?: string;
  nominal_value?: number;
  min_value?: number;
  max_value?: number;
  unit?: string;
  tolerance_percent?: number;
  conditions?: Record<string, any>;
}

export interface EngineeringRequirement {
  id: string;
  system_id: string;
  project_id: string;
  system_revision: number;
  requirement_key: string;
  revision: number;
  title: string;
  statement: string;
  category: RequirementCategory;
  priority: RequirementPriority;
  status: RequirementStatus;
  subsystem_id?: string | null;
  parent_requirement_id?: string | null;
  structured_expression?: StructuredExpression | null;
  verification_method?: VerificationMethod | null;
  verification_requirement_id?: string | null;
  source_id?: string | null;
  rationale?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EngineeringRequirementBaseline {
  id: string;
  system_id: string;
  system_revision: number;
  name: string;
  baseline_hash: string;
  requirement_ids: string[];
  requirement_revisions: Record<string, number>;
  is_frozen: boolean;
  knowledge_snapshot_id?: string | null;
  created_by: string;
  created_at: string;
}

export interface EngineeringAssumption {
  id: string;
  system_id: string;
  project_id: string;
  system_revision: number;
  description: string;
  basis: string;
  value?: string | null;
  unit?: string | null;
  requirement_id?: string | null;
  source_id?: string | null;
  status: AssumptionStatus;
  impact: AssumptionImpact;
  validated_by?: string | null;
  validated_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EngineeringDecisionRecord {
  id: string;
  system_id: string;
  project_id: string;
  system_revision: number;
  title: string;
  decision_key: string;
  description?: string | null;
  decision_type: DecisionType;
  status: DecisionStatus;
  requirement_baseline_id?: string | null;
  analysis_id?: string | null;
  decision_context?: Record<string, any>;
  selected_alternative_id?: string | null;
  decided_by?: string | null;
  decided_at?: string | null;
  rationale?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringDecisionAlternative {
  id: string;
  decision_id: string;
  name: string;
  description?: string | null;
  status: AlternativeStatus;
  elimination_reason?: string | null;
  engineering_effects?: Record<string, any>;
  requirement_effects?: Record<string, any>;
  verification_effects?: Record<string, any>;
  failure_effects?: Record<string, any>;
  tradeoffs?: Record<string, any>;
  unknowns: string[];
  created_at: string;
  updated_at: string;
}

export interface EngineeringTradeoff {
  id: string;
  decision_id: string;
  dimension: string;
  alternative_a_id: string;
  alternative_b_id: string;
  advantage_a?: string | null;
  disadvantage_a?: string | null;
  advantage_b?: string | null;
  disadvantage_b?: string | null;
  evidence?: Record<string, any>;
  unknowns: string[];
  created_at: string;
}

export interface EngineeringDecisionQuestion {
  id: string;
  decision_id: string;
  question: string;
  reason?: string | null;
  status: QuestionStatus;
  blocking: boolean;
  review_id?: string | null;
  affected_object?: string | null;
  affected_requirement_id?: string | null;
  affected_analysis_id?: string | null;
  answer?: string | null;
  answered_by?: string | null;
  answered_at?: string | null;
  evidence_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface EngineeringUnknownDisposition {
  id: string;
  decision_id: string;
  unknown_key: string;
  actor: string;
  reason: string;
  affected_requirement_id?: string | null;
  status: UnknownDispositionStatus;
  created_at: string;
}

export interface EngineeringDesignReviewSession {
  id: string;
  system_id: string;
  project_id: string;
  system_revision: number;
  title: string;
  status: ReviewStatus;
  decision_id?: string | null;
  requirement_baseline_id?: string | null;
  opened_at?: string | null;
  closed_at?: string | null;
  chairperson?: string | null;
  summary?: string | null;
  created_at: string;
  updated_at: string;
  participants?: EngineeringReviewParticipant[];
  checkpoints?: EngineeringReviewCheckpoint[];
  findings?: EngineeringReviewFinding[];
  actions?: EngineeringReviewAction[];
}

export interface EngineeringReviewParticipant {
  id: string;
  review_id: string;
  user_id: string;
  name: string;
  role: string;
  attended: boolean;
  voted: boolean;
  vote?: string | null;
  comments?: string | null;
}

export interface EngineeringReviewCheckpoint {
  id: string;
  review_id: string;
  checkpoint_name: string;
  description?: string | null;
  status: "PASS" | "FAIL" | "WAIVED" | "UNKNOWN";
  verified_by?: string | null;
  verified_at?: string | null;
  notes?: string | null;
}

export interface EngineeringReviewFinding {
  id: string;
  review_id: string;
  source_analysis?: string | null;
  severity: FindingSeverity;
  description: string;
  status: FindingStatus;
  finding_id?: string | null;
  affected_requirement_id?: string | null;
  affected_subsystem_id?: string | null;
  waived_by?: string | null;
  waived_at?: string | null;
  waiver_rationale?: string | null;
}

export interface EngineeringReviewAction {
  id: string;
  review_id: string;
  description: string;
  owner: string;
  status: "OPEN" | "IN_PROGRESS" | "COMPLETED" | "CANCELLED";
  priority: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  due_at?: string | null;
  linked_requirement_id?: string | null;
  linked_finding_id?: string | null;
  linked_verification_requirement_id?: string | null;
}

export interface ComparisonMatrixResponse {
  decision_id: string;
  system_revision: number;
  dimensions: string[];
  comparison_matrix: Array<{
    alternative_id: string;
    name: string;
    status: AlternativeStatus;
    engineering_effects: Record<string, any>;
    requirement_effects: Record<string, any>;
    verification_effects: Record<string, any>;
    failure_effects: Record<string, any>;
    tradeoffs: Record<string, any>;
    unknowns: string[];
  }>;
}

export interface ReviewReadinessResponse {
  review_id: string;
  overall_status: "READY" | "NOT_READY" | "BLOCKED" | "UNKNOWN";
  can_close_review: boolean;
  blockers: string[];
  dimensions: {
    checkpoints: "READY" | "BLOCKED" | "UNKNOWN";
    findings: "READY" | "NOT_READY" | "BLOCKED";
    questions: "READY" | "NOT_READY" | "BLOCKED";
    evidence: "READY" | "PARTIAL" | "NOT_READY";
    verification: "READY" | "NOT_READY";
    decision: "READY" | "NOT_READY" | "BLOCKED";
  };
}

export interface AIDecisionBriefResponse {
  origin: "AI_GENERATED";
  informational_only: boolean;
  provenance: {
    origin: "AI_GENERATED";
    model_identifier: string;
    generated_at: string;
    prompt_version: string;
    authority: string;
  };
  decision_key: string;
  title: string;
  executive_summary: string;
  requirements_summary: Array<{
    key: string;
    title: string;
    category: string;
    priority: string;
    status: string;
  }>;
  assumptions_summary: Array<{
    description: string;
    impact: string;
    status: string;
  }>;
  alternatives_summary: Array<{
    id: string;
    name: string;
    status: string;
    elimination_reason?: string;
    key_effects: Record<string, any>;
    unknowns_count: number;
  }>;
  critical_findings: Array<{
    id: string;
    severity: string;
    source?: string;
    description: string;
    status: string;
  }>;
  blocking_questions: Array<{
    id: string;
    question: string;
    reason?: string;
    blocking: boolean;
  }>;
  evidence_count: number;
  disclaimer: string;
}
