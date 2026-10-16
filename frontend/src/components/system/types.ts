export type SystemStatus =
  | "DRAFT"
  | "ACTIVE"
  | "UNDER_REVIEW"
  | "VERIFICATION_REQUIRED"
  | "PARTIALLY_VERIFIED"
  | "VERIFIED"
  | "BLOCKED"
  | "STALE"
  | "ARCHIVED";

export type SubsystemType =
  | "POWER"
  | "PROTECTION"
  | "REGULATION"
  | "PROCESSING"
  | "SENSING"
  | "COMMUNICATION"
  | "STORAGE"
  | "ACTUATION"
  | "USER_INTERFACE"
  | "CLOCK"
  | "ANALOG"
  | "DIGITAL"
  | "RF"
  | "SAFETY"
  | "OTHER";

export type InterfaceType =
  | "POWER"
  | "GROUND"
  | "ANALOG_SIGNAL"
  | "DIGITAL_SIGNAL"
  | "CLOCK"
  | "DATA"
  | "CONTROL"
  | "COMMUNICATION"
  | "RF"
  | "MECHANICAL"
  | "THERMAL"
  | "OTHER";

export type DependencyType =
  | "POWER_DEPENDS_ON"
  | "SIGNAL_DEPENDS_ON"
  | "DATA_DEPENDS_ON"
  | "CONTROL_DEPENDS_ON"
  | "CLOCK_DEPENDS_ON"
  | "THERMALLY_DEPENDS_ON"
  | "COMMUNICATION_DEPENDS_ON";

export type FindingSeverity = "INFO" | "WARNING" | "CRITICAL";

export interface EngineeringSystem {
  id: string;
  project_id: string;
  tenant_id?: string;
  name: string;
  description?: string;
  revision: number;
  status: SystemStatus;
  created_by: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringSubsystem {
  id: string;
  system_id: string;
  parent_subsystem_id?: string | null;
  tenant_id?: string;
  name: string;
  description?: string;
  subsystem_type: SubsystemType;
  circuit_id?: string | null;
  revision: number;
  status: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringSystemInterface {
  id: string;
  system_id: string;
  tenant_id?: string;
  source_subsystem_id: string;
  destination_subsystem_id: string;
  name: string;
  interface_type: InterfaceType;
  description?: string;
  status: string;
  contract: Record<string, any>;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringPowerDomain {
  id: string;
  system_id: string;
  tenant_id?: string;
  name: string;
  nominal_voltage: number;
  min_voltage?: number;
  max_voltage?: number;
  source_subsystem_id: string;
  regulator_subsystem_id?: string;
  current_capacity_a?: number;
  status: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringSystemDependency {
  id: string;
  system_id: string;
  tenant_id?: string;
  source_subsystem_id: string;
  target_subsystem_id: string;
  dependency_type: DependencyType;
  description?: string;
  status: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringOperatingMode {
  id: string;
  system_id: string;
  tenant_id?: string;
  name: string;
  description?: string;
  active_subsystem_ids: string[];
  inactive_subsystem_ids: string[];
  expected_power_domain_ids: string[];
  relevant_interface_ids: string[];
  operating_conditions: Record<string, any>;
  status: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringModeTransition {
  id: string;
  system_id: string;
  tenant_id?: string;
  source_mode_id: string;
  destination_mode_id: string;
  trigger: string;
  conditions: Record<string, any>;
  required_subsystems: string[];
  forbidden_conditions: Record<string, any>;
  status: string;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringSystemRequirement {
  id: string;
  system_id: string;
  tenant_id?: string;
  code: string;
  title: string;
  description: string;
  requirement_type: string;
  source?: string;
  status: "UNKNOWN" | "SUPPORTED" | "VIOLATED" | "PARTIALLY_SUPPORTED" | "VERIFICATION_REQUIRED";
  constraints: Record<string, any>;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringSystemFinding {
  id: string;
  analysis_id: string;
  system_id: string;
  rule_id: string;
  category: string;
  severity: FindingSeverity;
  title: string;
  description: string;
  affected_subsystems: string[];
  affected_interfaces: string[];
  affected_power_domains: string[];
  inputs: Record<string, any>;
  calculation: Record<string, any>;
  provenance: Record<string, any>;
  unknowns: string[];
  status: string;
  created_at: string;
}

export interface EngineeringSystemAnalysis {
  id: string;
  system_id: string;
  tenant_id?: string;
  system_revision: number;
  subsystem_revisions: Record<string, number>;
  circuit_revisions: Record<string, number>;
  engine_versions: Record<string, string>;
  rule_set_version: string;
  knowledge_snapshot_id?: string;
  inputs_digest: string;
  status: string;
  is_stale: boolean;
  findings: EngineeringSystemFinding[];
  metadata?: Record<string, any>;
  created_at: string;
}

export interface SystemDetailResponse extends EngineeringSystem {
  subsystems: EngineeringSubsystem[];
  interfaces: EngineeringSystemInterface[];
  power_domains: EngineeringPowerDomain[];
  dependencies: EngineeringSystemDependency[];
  operating_modes: EngineeringOperatingMode[];
  mode_transitions: EngineeringModeTransition[];
  requirements: EngineeringSystemRequirement[];
  latest_analysis?: EngineeringSystemAnalysis | null;
}

export interface FailurePropagationResult {
  root_cause: Record<string, any>;
  upstream_affected_subsystems: string[];
  downstream_affected_subsystems: string[];
  affected_interfaces: string[];
  affected_power_domains: string[];
  containment_barriers: Array<{
    type: string;
    interface_id?: string;
    interface_name?: string;
    subsystem_id?: string;
    subsystem_name?: string;
    barrier: string;
    protected_subsystem_id?: string;
    protected_subsystem_name?: string;
  }>;
  loss_of_functions: string[];
  unknowns: string[];
}

export interface ChangeImpactResult {
  target_id: string;
  target_type: string;
  affected_subsystems: string[];
  affected_interfaces: string[];
  affected_power_domains: string[];
  affected_analyses: string[];
  affected_verification_requirements: string[];
  stale_analyses_count: number;
  blast_radius_summary: string;
}

export interface SystemSnapshotResponse {
  id: string;
  system_id: string;
  system_revision: number;
  snapshot_hash: string;
  content: Record<string, any>;
  created_at: string;
}
