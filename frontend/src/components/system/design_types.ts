export type ObjectiveStatus = "ACTIVE" | "ACHIEVED" | "ABANDONED";

export type ConstraintType = "HARD" | "SOFT";

export type ConstraintStatus = "PENDING" | "SATISFIED" | "VIOLATED" | "UNKNOWN";

export type ScenarioType =
  | "OPERATING"
  | "FAILURE"
  | "STRESS"
  | "TRANSITION"
  | "DEGRADED";

export type ScenarioConditionType =
  | "OPERATING_MODE"
  | "POWER_LOAD"
  | "INTERFACE_INPUT"
  | "AMBIENT_CONDITION"
  | "SUBSYSTEM_FAULT"
  | "INTERFACE_FAULT";

export type ScenarioResultStatus = "SUCCESS" | "BLOCKED" | "FAILED" | "UNKNOWN";

export type CandidateStatus = "GENERATED" | "EVALUATED" | "PROPOSED" | "REJECTED";

export type SystemProposalStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "APPLIED"
  | "STALE";

export interface EngineeringSystemDesignConstraint {
  id: string;
  objective_id: string;
  constraint_type: ConstraintType;
  metric: string;
  operator: string;
  target_value: number;
  unit?: string;
  status: ConstraintStatus;
  description?: string;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface EngineeringSystemDesignObjective {
  id: string;
  system_id: string;
  tenant_id?: string;
  title: string;
  description?: string;
  target_subsystems: string[];
  parameters: Record<string, any>;
  status: ObjectiveStatus;
  constraints?: EngineeringSystemDesignConstraint[];
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringScenarioCondition {
  id: string;
  scenario_id: string;
  condition_type: ScenarioConditionType;
  target_id: string;
  parameter_name: string;
  value: any;
  is_mandatory: boolean;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface EngineeringScenario {
  id: string;
  system_id: string;
  tenant_id?: string;
  name: string;
  description?: string;
  scenario_type: ScenarioType;
  preconditions: Record<string, any>;
  is_active: boolean;
  conditions?: EngineeringScenarioCondition[];
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringScenarioSnapshot {
  id: string;
  scenario_id: string;
  system_revision: number;
  snapshot_hash: string;
  captured_state: Record<string, any>;
  created_at: string;
}

export interface EngineeringScenarioResult {
  id: string;
  scenario_id: string;
  snapshot_id?: string;
  system_revision: number;
  execution_status: ScenarioResultStatus;
  preconditions_evaluation: {
    satisfied: boolean;
    missing_preconditions: string[];
    details: Record<string, any>;
  };
  metrics: Record<string, any>;
  consequences: {
    interface_evaluations?: any[];
    power_evaluations?: any[];
    failure_evaluations?: any[];
    requirement_deltas?: Record<string, any>;
    verification_deltas?: Record<string, any>;
    unknowns?: string[];
  };
  unknowns: string[];
  created_at: string;
}

export interface EngineeringSystemCandidate {
  id: string;
  objective_id: string;
  system_revision: number;
  title: string;
  strategy: string;
  operations: Array<{
    op_type: string;
    payload: Record<string, any>;
  }>;
  rationale: string;
  trade_offs: Record<string, any>;
  consequences: {
    simulation_result?: {
      interface_evaluations?: any[];
      power_tree_evaluations?: any[];
      failure_propagation?: any[];
      unknowns?: string[];
    };
    requirement_impact?: Record<string, any>;
    verification_impact?: Record<string, any>;
    constraint_evaluations?: Array<{
      metric: string;
      constraint_type: ConstraintType;
      status: ConstraintStatus;
      actual_value?: any;
      target_value?: any;
      reason: string;
    }>;
  };
  provenance: Record<string, any>;
  status: CandidateStatus;
  created_at: string;
}

export interface EngineeringSystemProposal {
  id: string;
  system_id: string;
  candidate_id?: string;
  base_revision: number;
  title: string;
  operations: Array<{
    op_type: string;
    payload: Record<string, any>;
  }>;
  generation_strategy?: string;
  rationale?: string;
  status: SystemProposalStatus;
  approved_by?: string;
  approved_at?: string;
  applied_at?: string;
  metadata?: Record<string, any>;
  created_at: string;
}
