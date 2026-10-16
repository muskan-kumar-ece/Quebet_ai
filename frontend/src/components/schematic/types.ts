export type ComponentType =
  | "resistor"
  | "capacitor"
  | "inductor"
  | "diode"
  | "led"
  | "bjt"
  | "mosfet"
  | "opamp"
  | "vsource"
  | "isource"
  | "ic"
  | "regulator"
  | "mcu"
  | "connector"
  | "ground"
  | "power"
  | "generic";

export type NetType = "power" | "ground" | "signal" | "clock" | "analog" | "differential";

export interface PinDescriptor {
  pin_number: string;
  pin_name?: string;
  pin_type?: "passive" | "power_in" | "power_out" | "input" | "output" | "bidirectional";
  dx?: number;
  dy?: number;
}

export interface SchematicComponent {
  id: string;
  circuit_id: string;
  ref_des: string;
  component_type: ComponentType | string;
  value: string;
  unit?: string;
  tolerance?: string;
  rating?: string;
  package?: string;
  manufacturer?: string;
  part_number?: string;
  pins: PinDescriptor[];
  metadata?: Record<string, any>;
}

export interface SchematicNet {
  id: string;
  circuit_id: string;
  name: string;
  net_type: NetType | string;
  metadata?: Record<string, any>;
}

export interface SchematicConnection {
  id: string;
  circuit_id: string;
  component_id: string;
  pin_number: string;
  pin_name?: string;
  net_id: string;
}

export interface SchematicObject {
  id: string;
  circuit_id: string;
  object_type: "symbol" | "wire" | "junction" | "label" | "text";
  component_id?: string | null;
  net_id?: string | null;
  pos_x: number;
  pos_y: number;
  rotation: number;
  graphics?: Record<string, any>;
}

export interface WireConnection {
  id: string;
  net_id: string;
  net_name: string;
  from_component_id: string;
  from_pin: string;
  from_pos: { x: number; y: number };
  to_component_id: string;
  to_pin: string;
  to_pos: { x: number; y: number };
  path: string;
}

export type AutosaveStatus = "saved" | "saving" | "unsaved" | "error";

export interface ProposalOperation {
  op_type: "add_component" | "remove_component" | "update_component" | "add_net" | "remove_net" | "add_connection" | "remove_connection";
  payload: Record<string, any>;
  description?: string;
}

export interface EngineeringProposal {
  id: string;
  circuit_id: string;
  source: string;
  title: string;
  description?: string;
  status: "PROPOSED" | "VALIDATED" | "REJECTED" | "APPROVED" | "APPLIED" | "STALE";
  operations: ProposalOperation[];
  assumptions: Array<{ field: string; value: string; confidence?: number; rationale?: string }>;
  validation_result?: {
    status: string;
    errors?: Array<{ code: string; message: string; field_path?: string }>;
    warnings?: Array<{ code: string; message: string }>;
  };
  base_revision?: number;
  analysis_id?: string;
  objective_id?: string;
  findings_resolved?: string[];
  findings_introduced?: string[];
  constraints_evaluated?: Record<string, any>;
  engineering_effects?: Record<string, any>;
  unknowns?: Array<Record<string, any>>;
  confidence?: string;
  applied_at?: string | null;
  created_at: string;
}

export interface CalculationItem {
  id: string;
  name: string;
  category: "OHMS_LAW" | "POWER_DISSIPATION" | "VOLTAGE_DIVIDER" | "RC_TIME_CONSTANT" | "REGULATOR" | "MARGIN" | string;
  component_ids: string[];
  net_ids: string[];
  formula: string;
  inputs: Record<string, any>;
  result: Record<string, any>;
  unit: string;
  confidence: "HIGH" | "MEDIUM" | "LOW" | string;
  notes?: string | null;
}

export interface FindingItem {
  id: string;
  rule_id: string;
  title: string;
  description: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  status?: string;
  actual_value?: any;
  limit_value?: any;
  unit?: string;
  condition?: string;
  source_id?: string;
  revision?: string | number;
  component_ids: string[];
  net_ids: string[];
  pin_ids: string[];
  recommended_action?: string | null;
  provenance: string;
  verification_status?: "CALCULATED" | "UNVERIFIED" | "PHYSICALLY_VERIFIED" | string;
}

export interface EngineeringUnknown {
  id: string;
  component_id?: string | null;
  net_id?: string | null;
  field: string;
  reason: string;
  impact: string;
}

export interface GraphSummary {
  total_components: number;
  total_nets: number;
  total_connections: number;
  floating_pins: Array<{
    component_id: string;
    component_name?: string;
    pin_id?: string;
    pin_name?: string;
    pin_number?: string;
    net_id?: string;
    reason: string;
  }>;
  power_nets: string[];
  ground_nets: string[];
  isolated_subgraphs: number;
}

export interface CircuitAnalysis {
  id: string;
  circuit_id: string;
  circuit_version: number;
  tenant_id?: string | null;
  created_by: string;
  status: "COMPLETE" | "PARTIAL" | "BLOCKED" | "INVALID" | string;
  confidence: "HIGH" | "MEDIUM" | "LOW" | string;
  graph_summary: GraphSummary;
  calculations: CalculationItem[];
  findings: FindingItem[];
  unknowns: EngineeringUnknown[];
  assumptions: Array<Record<string, any>>;
  execution_time_ms: number;
  created_at: string;
}

export interface ExplainResponse {
  circuit_id: string;
  explanation: string;
  identified_mechanisms: string[];
  engineering_tradeoffs: string[];
  recommended_actions: string[];
  verified_calculations_used: string[];
}

export interface EngineeringConstraint {
  name: string;
  constraint_type: "MAX_POWER" | "VOLTAGE_RANGE" | "CURRENT_LIMIT" | "PART_FAMILY" | "EFFICIENCY_MIN" | "MAX_COST" | "FOOTPRINT_RESTRICTION" | "THERMAL_MAX";
  target_component_id?: string | null;
  target_net_id?: string | null;
  target_property?: string | null;
  min_value?: number | null;
  max_value?: number | null;
  expected_value?: string | null;
  unit?: string | null;
  is_hard_constraint: boolean;
}

export interface ConstraintResult {
  constraint_id?: string;
  constraint_name: string;
  hard_or_soft?: "HARD" | "SOFT" | string;
  is_hard?: boolean;
  status?: "PASS" | "FAIL" | "SATISFIED" | "NOT_SATISFIED" | "UNKNOWN" | string;
  satisfied?: boolean;
  actual_value?: string | number | null;
  target_value?: string | number | null;
  required_value?: string | number | null;
  margin?: string | number | null;
  notes?: string | null;
  explanation?: string;
}

export interface EngineeringDesignObjective {
  id: string;
  circuit_id: string;
  tenant_id?: string | null;
  created_by: string;
  title: string;
  description?: string | null;
  objective_type: "RESOLVE_FINDING" | "REDUCE_POWER" | "OPTIMIZE_MARGIN" | "COMPONENT_REPLACEMENT" | "ISOLATE_DOMAINS" | "ADD_DECOUPLING" | "CUSTOM" | string;
  target_finding_ids: string[];
  target_component_ids: string[];
  target_net_ids: string[];
  constraints: EngineeringConstraint[];
  status: "ACTIVE" | "COMPLETED" | "ABANDONED";
  created_at: string;
  updated_at: string;
}

export interface ProposedChange {
  operation?: string;
  change_type?: string;
  component_id?: string | null;
  ref_des?: string | null;
  field?: string | null;
  old_value?: any;
  new_value?: any;
  payload?: Record<string, any>;
  details?: Record<string, any>;
  description?: string | null;
}

export interface CandidateProvenance {
  candidate_id: string;
  trigger?: string | null;
  generation_strategy?: string | null;
  source_finding?: string | null;
  affected_component?: string | null;
  affected_net?: string | null;
  old_value?: any;
  new_value?: any;
  old_component?: Record<string, any> | null;
  new_component?: Record<string, any> | null;
  rationale?: string | null;
  knowledge_sources?: string[];
  engineering_assumptions?: Array<Record<string, any>>;
  validation_analysis_id?: string | null;
  constraint_results?: Array<Record<string, any>>;
  finding_delta?: Record<string, any>;
  engineering_effects?: Record<string, any>;
  unknowns?: Array<Record<string, any>>;
  confidence?: string;
}

export interface EngineeringDesignAlternative {
  id: string;
  alternative_id?: string;
  objective_id: string;
  title: string;
  description: string;
  approach?: string;
  proposed_changes: ProposedChange[];
  affected_components?: string[];
  affected_nets?: string[];
  findings_resolved: string[];
  findings_introduced: string[];
  remaining_findings?: string[];
  hard_constraints_status?: "PASS" | "FAIL" | "UNKNOWN" | string;
  soft_constraints_summary?: {
    satisfied: number;
    not_satisfied: number;
    unknown: number;
    total: number;
  };
  constraint_results: ConstraintResult[];
  engineering_effects?: Record<string, any>;
  electrical_effects?: Record<string, any>;
  structural_effects?: Record<string, any>;
  cost?: string;
  footprint?: string;
  unknowns: EngineeringUnknown[];
  tradeoffs: string[];
  status?: string;
  provenance?: string[];
  candidate_provenance?: CandidateProvenance | Record<string, any> | null;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  is_valid?: boolean;
}

export interface ComparisonMatrixRow {
  alternative_id: string;
  title: string;
  strategy: string;
  hard_constraints: "PASS" | "FAIL" | "UNKNOWN" | string;
  soft_constraints: string;
  findings_resolved_count: number;
  findings_introduced_count: number;
  remaining_findings_count: number;
  resolved_finding_ids?: string[];
  introduced_finding_ids?: string[];
  power_delta_w: number | null;
  worst_margin?: number | null;
  component_count_delta: number;
  footprint: string;
  cost: string;
  confidence: "HIGH" | "MEDIUM" | "LOW" | string;
  tradeoffs?: string[];
}

export interface DesignComparisonResponse {
  circuit_id: string;
  base_revision: number;
  baseline_metrics?: Record<string, any>;
  alternatives: EngineeringDesignAlternative[];
  comparison_matrix: ComparisonMatrixRow[];
  comparison_table?: Array<Record<string, any>>;
}

// ============================================================================
// Phase 1 Wave 5: Engineering Verification, Design Review & Failure Analysis
// ============================================================================

export type DesignReviewStatus =
  | "DRAFT"
  | "ANALYSIS_COMPLETE"
  | "REVIEW_IN_PROGRESS"
  | "VERIFICATION_REQUIRED"
  | "PARTIALLY_VERIFIED"
  | "VERIFIED"
  | "BLOCKED"
  | "STALE";

export type VerificationStatus =
  | "NOT_STARTED"
  | "IN_PROGRESS"
  | "SATISFIED"
  | "FAILED"
  | "BLOCKED"
  | "UNKNOWN"
  | "NOT_APPLICABLE";

export type OperatingCondition =
  | "NOMINAL"
  | "MINIMUM_INPUT"
  | "MAXIMUM_INPUT"
  | "MINIMUM_LOAD"
  | "MAXIMUM_LOAD"
  | "STARTUP"
  | "STEADY_STATE"
  | "TRANSIENT"
  | "THERMAL_EXTREME"
  | "USER_DEFINED";

export interface EngineeringEvidence {
  id: string;
  verification_requirement_id: string;
  review_id: string;
  evidence_type: "MEASUREMENT" | "DATASHEET" | "CALCULATION" | "SCHEMATIC_INSPECTION" | "SIMULATION_REPORT" | "TEST_REPORT" | string;
  source: string;
  description: string;
  value?: string | null;
  unit?: string | null;
  reference?: string | null;
  status: "VALID" | "INVALID" | "INCOMPLETE" | "UNKNOWN" | string;
  confidence: "HIGH" | "MEDIUM" | "LOW" | string;
  provided_by: string;
  provided_at: string;
  source_id?: string | null;
  instrument?: string | null;
  instrument_model?: string | null;
  instrument_serial?: string | null;
  calibration_reference?: string | null;
  calibration_status?: string | null;
  measurement_timestamp?: string | null;
  circuit_id?: string | null;
  circuit_revision?: number | null;
  analysis_id?: string | null;
  is_stale?: boolean;
  metadata?: Record<string, any>;
}

export interface VerificationRequirement {
  id: string;
  review_id: string;
  code: string;
  title: string;
  reason: string;
  trigger?: string | null;
  method: string;
  operating_condition: OperatingCondition | string;
  required_evidence: string[];
  status: VerificationStatus | string;
  is_mandatory: boolean;
  not_applicable_reason?: string | null;
  affected_components: string[];
  affected_nets: string[];
  related_rule_id?: string | null;
  related_finding_id?: string | null;
  unknowns: string[];
  created_at: string;
  updated_at: string;
  evidence_items?: EngineeringEvidence[];
}

export interface FailureMode {
  id: string;
  review_id: string;
  category: string;
  trigger: string;
  mechanism: string;
  consequence: string;
  likelihood: "LOW" | "MEDIUM" | "HIGH" | string;
  severity: "INFO" | "WARNING" | "CRITICAL" | string;
  affected_components: string[];
  affected_nets: string[];
  evidence: string[];
  unknowns: string[];
  related_findings: string[];
  related_rules: string[];
  verification_requirement_ids: string[];
  created_at: string;
}

export interface TestPoint {
  id: string;
  review_id: string;
  code: string;
  target_net?: string | null;
  target_component?: string | null;
  measurement: string;
  expected_basis: string;
  instrumentation: string;
  operating_condition: OperatingCondition | string;
  related_requirement_id?: string | null;
  created_at: string;
}

export interface VerificationMatrixItem {
  requirement_id: string;
  requirement_code: string;
  title: string;
  reason: string;
  method: string;
  operating_condition: string;
  evidence_count: number;
  latest_evidence_summary?: string | null;
  status: VerificationStatus | string;
  is_mandatory: boolean;
  unknowns: string[];
  affected_components: string[];
  affected_nets: string[];
}

export interface VerificationMatrixData {
  review_id: string;
  circuit_id: string;
  circuit_revision: number;
  status: DesignReviewStatus | string;
  total_requirements: number;
  satisfied_count: number;
  in_progress_count: number;
  unknown_count: number;
  blocked_count: number;
  failed_count: number;
  not_applicable_count: number;
  is_stale: boolean;
  matrix: VerificationMatrixItem[];
}

export interface DesignReview {
  id: string;
  tenant_id?: string | null;
  project_id: string;
  circuit_id: string;
  circuit_revision: number;
  analysis_id: string;
  status: DesignReviewStatus | string;
  created_by: string;
  created_at: string;
  updated_at: string;
  failure_modes: FailureMode[];
  verification_requirements: VerificationRequirement[];
  test_points: TestPoint[];
  evidence_summary: Record<string, number>;
  unresolved_findings_count: number;
  unknowns: string[];
  is_stale: boolean;
}

// ============================================================================
// Phase 1 Wave 6: Engineering Knowledge & Traceability Types
// ============================================================================

export interface EngineeringSource {
  id: string;
  tenant_id?: string | null;
  source_type: string;
  title: string;
  publisher: string;
  document_identifier: string;
  revision: string;
  version: string;
  publication_date?: string | null;
  effective_date?: string | null;
  uri?: string | null;
  document_hash?: string | null;
  trust_level: string;
  status: "CURRENT" | "SUPERSEDED" | "DEPRECATED" | "DRAFT" | string;
  supersedes_source_id?: string | null;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface EngineeringKnowledgeRecord {
  id: string;
  tenant_id?: string | null;
  source_id?: string | null;
  domain: string;
  subject_type: string;
  subject_identifier: string;
  parameter: string;
  value: string;
  unit?: string | null;
  conditions: Record<string, any>;
  valid_range?: { min?: number; max?: number } | null;
  status: "VERIFIED" | "VALIDATED" | "USER_PROVIDED" | "INFERRED" | "UNKNOWN" | "SUPERSEDED" | "REJECTED" | string;
  provenance: Record<string, any>;
  supersedes_knowledge_id?: string | null;
  created_at: string;
  updated_at: string;
  source?: EngineeringSource | null;
}

export interface AnalysisTraceabilityData {
  analysis_id: string;
  circuit_id: string;
  circuit_revision: number;
  engine_versions: Record<string, string>;
  rule_set_version: string;
  knowledge_snapshot_id?: string | null;
  input_values: Record<string, any>;
  assumptions: any[];
  calculation_methods: string[];
  knowledge_records: EngineeringKnowledgeRecord[];
  sources: EngineeringSource[];
  created_at: string;
}

export interface FindingTraceabilityData {
  finding_id: string;
  rule_id: string;
  analysis_id: string;
  affected_components: string[];
  affected_nets: string[];
  knowledge_records: EngineeringKnowledgeRecord[];
  sources: EngineeringSource[];
  input_values: Record<string, any>;
  calculation_result: Record<string, any>;
}

export interface RequirementTraceabilityData {
  requirement_id: string;
  requirement_code: string;
  related_finding_id?: string | null;
  related_rule_id?: string | null;
  knowledge_records: EngineeringKnowledgeRecord[];
  sources: EngineeringSource[];
  evidence_count: number;
}

export interface EvidenceTraceabilityData {
  evidence_id: string;
  requirement_id: string;
  evidence_type: string;
  source: string;
  source_id?: string | null;
  source_document?: EngineeringSource | null;
  instrument?: string | null;
  instrument_model?: string | null;
  instrument_serial?: string | null;
  calibration_reference?: string | null;
  calibration_status: string;
  circuit_id?: string | null;
  circuit_revision?: number | null;
  is_stale: boolean;
  status: string;
}

export interface KnowledgeImpactData {
  knowledge_id: string;
  parameter: string;
  subject_identifier: string;
  status: string;
  affected_components: string[];
  affected_analyses: string[];
  affected_findings: string[];
  affected_verification_requirements: string[];
  affected_design_reviews: string[];
  affected_proposals: string[];
  recommendation: string;
}

export type SimulationType = "DC_OPERATING_POINT" | "DC_SWEEP" | "AC_SMALL_SIGNAL" | "TRANSIENT";
export type SimulationStatus = "CREATED" | "VALIDATING" | "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "TIMEOUT" | "CANCELLED" | "INVALID" | "STALE";

export interface SimulationDiscrepancy {
  element_or_node: string;
  parameter: string;
  analytical_value: number;
  simulation_value: number;
  unit: string;
  relative_delta: number;
  flag: string;
  description: string;
}

export interface SimulationConstraintEvaluation {
  constraint_id: string;
  component_id?: string | null;
  parameter: string;
  simulated_value: number;
  limit_value: number;
  unit: string;
  limit_type: string;
  status: string;
  margin?: number | null;
  note?: string | null;
}

export interface SimulationResult {
  id: string;
  simulation_job_id: string;
  convergence_status: string;
  node_voltages: Record<string, number>;
  branch_currents: Record<string, number>;
  waveforms: Record<string, any>;
  metrics: Record<string, any>;
  raw_output?: string | null;
  classification: string;
  verification_status: string;
  discrepancies: SimulationDiscrepancy[];
  constraint_evaluations: SimulationConstraintEvaluation[];
}

export interface SimulationJob {
  id: string;
  circuit_id: string;
  simulation_type: SimulationType;
  status: SimulationStatus;
  simulator: string;
  execution_mode: string;
  netlist_digest?: string | null;
  model_digest?: string | null;
  execution_time_ms: number;
  result?: SimulationResult | null;
}

export interface BoardLayer {
  id: string;
  board_id: string;
  layer_name: string;
  layer_type: "SIGNAL" | "PLANE" | "DIELECTRIC" | "SILKSCREEN" | "SOLDERMASK";
  layer_order: number;
  copper_thickness_um?: number | null;
  dielectric_thickness_um?: number | null;
  dielectric_constant_er?: number | null;
}

export interface BoardPad {
  id: string;
  footprint_id: string;
  pad_number: string;
  pad_type: "SMD" | "THROUGH_HOLE" | "BGA";
  net_name?: string | null;
  pos_x: number;
  pos_y: number;
  width: number;
  height: number;
  drill_size?: number | null;
  shape?: string;
  layer?: string;
}

export interface BoardFootprint {
  id: string;
  board_id: string;
  component_id?: string | null;
  ref_des: string;
  footprint_name: string;
  pos_x: number;
  pos_y: number;
  rotation: number;
  side: "TOP" | "BOTTOM";
  courtyard_width?: number | null;
  courtyard_height?: number | null;
  pads?: BoardPad[];
}

export interface BoardTraceSegment {
  id: string;
  board_id: string;
  net_name: string;
  layer: string;
  start_x: number;
  start_y: number;
  end_x: number;
  end_y: number;
  width: number;
  length?: number | null;
}

export interface BoardVia {
  id: string;
  board_id: string;
  net_name: string;
  pos_x: number;
  pos_y: number;
  drill_diameter: number;
  pad_diameter: number;
  start_layer: string;
  end_layer: string;
}

export interface EngineeringBoard {
  id: string;
  project_id: string;
  circuit_id: string;
  name: string;
  revision: number;
  version?: number;
  width_mm: number;
  height_mm: number;
  units: "MM" | "MILS";
  layer_count: number;
  board_outline?: Array<{ x: number; y: number }>;
  keepouts?: Array<Record<string, any>>;
  layers?: BoardLayer[];
  footprints?: BoardFootprint[];
  traces?: BoardTraceSegment[];
  vias?: BoardVia[];
  provenance_digest?: string;
}

export interface PCBFinding {
  rule_id: string;
  category: string;
  severity: "ERROR" | "WARNING" | "INFO";
  status: "SATISFIED" | "VIOLATED" | "UNKNOWN";
  element_type: string;
  element_ref: string;
  message: string;
  details?: Record<string, any>;
  suggested_action?: string;
}

export interface PCBConstraintEvaluation {
  constraint_name: string;
  constraint_type: string;
  target_element: string;
  status: "SATISFIED" | "VIOLATED" | "UNKNOWN";
  limit_value?: any;
  actual_value?: any;
  margin?: any;
  notes?: string;
}

export interface PCBAnalysisRecord {
  id: string;
  board_id: string;
  circuit_id: string;
  board_revision: number;
  provenance_digest: string;
  findings: PCBFinding[];
  constraint_evaluations: PCBConstraintEvaluation[];
  summary: {
    total_findings: number;
    errors: number;
    warnings: number;
    unknowns: number;
  };
  classification: "PCB_ANALYSIS";
  created_at?: string;
}

export interface PCBProposal {
  id: string;
  board_id: string;
  title: string;
  description: string;
  mutation_type: string;
  proposed_mutations: Array<Record<string, any>>;
  status: "STAGED" | "APPROVED" | "REJECTED" | "APPLIED";
  diff_preview: {
    additions: number;
    modifications: number;
    deletions: number;
    summary: string[];
  };
}

// ==========================================
// Phase 3 Wave 6: BOM & Supply-Chain Types
// ==========================================

export type BOMStatus = "DRAFT" | "EVALUATED" | "REVIEW" | "FROZEN" | "ARCHIVED";
export type BOMLineStatus = "UNMATCHED" | "SOURCED" | "CONFLICTING" | "INCOMPATIBLE";
export type PartLifecycleStatus = "ACTIVE" | "PREVIEW" | "NRND" | "EOL" | "OBSOLETE" | "UNKNOWN";
export type PartAvailabilityStatus = "IN_STOCK" | "LIMITED_STOCK" | "OUT_OF_STOCK" | "UNKNOWN" | "CONFLICTING";
export type PartCompatibilityStatus = "ENGINEERING_COMPATIBLE" | "PARTIALLY_EVALUATED" | "UNKNOWN" | "NOT_COMPATIBLE";

export interface SupplySourceObservation {
  supplier: string;
  supplier_pn?: string;
  stock: number;
  unit_price?: number;
  currency: string;
  qty_break?: number;
  observed_at: string;
  source_url?: string;
  source_trust?: string;
}

export interface ParameterCompatibilityEvaluation {
  parameter: string;
  required_value: any;
  actual_value: any;
  status: "SATISFIED" | "NOT_SATISFIED" | "CONFLICT" | "UNKNOWN" | "NOT_APPLICABLE";
  unit?: string;
  message?: string;
}

export interface ComponentPartCandidate {
  id: string;
  bom_line_id: string;
  manufacturer: string;
  mpn: string;
  package?: string;
  description?: string;
  datasheet_url?: string;
  lifecycle_status: PartLifecycleStatus;
  availability_status: PartAvailabilityStatus;
  compatibility_status: PartCompatibilityStatus;
  compatibility_evaluations: ParameterCompatibilityEvaluation[];
  parameters: Record<string, any>;
  lead_time_weeks?: number;
  supply_sources: SupplySourceObservation[];
  is_primary: boolean;
  provenance: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface EngineeringBOMLine {
  id: string;
  bom_id: string;
  component_id?: string;
  reference_designator: string;
  quantity: number;
  component_type: string;
  design_value: string;
  design_package?: string;
  design_tolerance?: string;
  design_rating?: string;
  footprint_name?: string;
  engineering_requirements: Record<string, any>;
  manufacturer?: string;
  manufacturer_part_number?: string;
  description?: string;
  status: BOMLineStatus;
  provenance: Record<string, any>;
  candidates: ComponentPartCandidate[];
  created_at?: string;
  updated_at?: string;
}

export interface BOMSubstitutionProposal {
  id: string;
  bom_id: string;
  bom_line_id: string;
  base_bom_revision: number;
  circuit_version: number;
  tenant_id?: string;
  candidate_id: string;
  proposed_mpn: string;
  proposed_manufacturer: string;
  rationale: string;
  diff_preview: Record<string, any>;
  status: "PROPOSED" | "REVIEW" | "APPROVED" | "REJECTED" | "APPLIED" | "SUPERSEDED" | "STALE";
  created_by: string;
  approved_by?: string;
  applied_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface EngineeringBOM {
  id: string;
  project_id: string;
  circuit_id: string;
  circuit_version: number;
  board_id?: string;
  board_version?: number;
  tenant_id?: string;
  name: string;
  version: number;
  status: BOMStatus;
  total_lines: number;
  integrity_digest?: string;
  lines: EngineeringBOMLine[];
  substitutions?: BOMSubstitutionProposal[];
  created_by: string;
  created_at?: string;
  updated_at?: string;
}

export interface BOMSnapshot {
  bom_id: string;
  bom_version: number;
  circuit_id: string;
  circuit_version: number;
  snapshot_digest: string;
  provenance_label: string;
  content: Record<string, any>;
}

// -------------------------------------------------------------
// Phase 3 Wave 7: Manufacturing / DFM & Assembly Intelligence
// -------------------------------------------------------------

export type ManufacturingRuleCategory =
  | "FABRICATION"
  | "ASSEMBLY"
  | "SOLDER_MASK"
  | "SILKSCREEN"
  | "DRILL_VIA"
  | "CLEARANCE"
  | "BOM_CONSISTENCY"
  | "COMPONENT_PLACEMENT";

export type ManufacturingFindingStatus =
  | "PASS"
  | "FAIL"
  | "WARNING"
  | "UNKNOWN"
  | "NOT_EVALUATED"
  | "NOT_APPLICABLE";

export type ManufacturingAnalysisStatus = "COMPLETED" | "FAILED" | "PENDING" | "STALE";

export interface ManufacturingFinding {
  finding_id: string;
  rule_id: string;
  rule_name: string;
  category: ManufacturingRuleCategory;
  status: ManufacturingFindingStatus;
  severity: "ERROR" | "WARNING" | "INFO";
  message: string;
  element_type: string;
  element_ids?: string[];
  ref_des?: string;
  location?: { x: number; y: number };
  layer?: string;
  measured_value?: number;
  required_value?: number;
  margin?: number;
  unit?: string;
  proposal_available: boolean;
  evidence?: Record<string, any>;
}

export interface ManufacturingAnalysisSummary {
  total_rules_evaluated: number;
  pass_count: number;
  fail_count: number;
  warning_count: number;
  unknown_count: number;
  critical_violations: string[];
  status: string;
}

export interface ManufacturingAnalysisResponse {
  id: string;
  board_id: string;
  board_revision: number;
  circuit_id: string;
  circuit_revision: number;
  tenant_id?: string;
  rule_set_id: string;
  rule_set_revision: string;
  status: string;
  findings: ManufacturingFinding[];
  summary: ManufacturingAnalysisSummary;
  provenance_digest?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ManufacturingProposalResponse {
  id: string;
  board_id: string;
  board_revision: number;
  tenant_id?: string;
  analysis_id: string;
  rule_id: string;
  title: string;
  description: string;
  mutation_type: string;
  proposed_mutations: Array<Record<string, any>>;
  diff_preview: Record<string, any>;
  status: "PROPOSED" | "APPROVED" | "REJECTED" | "APPLIED" | "STALE";
  created_by: string;
  approved_by?: string;
  applied_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ManufacturingRuleSetResponse {
  id: string;
  tenant_id?: string;
  name: string;
  version: number;
  source: string;
  source_revision: string;
  source_digest?: string;
  rules: Record<string, any>;
  is_default: boolean;
  effective_from?: string;
  created_at: string;
  updated_at: string;
}

export interface DFMSnapshotResponse {
  board_id: string;
  board_revision: number;
  analysis_id: string;
  rule_set_id: string;
  rule_set_revision: string;
  canonical_digest: string;
  computed_at: string;
  invariants_verified: string[];
}

// ==========================================
// Phase 3 Wave 8: Cross-Domain Validation Types
// ==========================================

export type CrossDomainStatus = "PASS" | "FAIL" | "WARNING" | "UNKNOWN" | "NOT_APPLICABLE";
export type CrossDomainSeverity = "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type CrossDomainValidationStatus = "COMPLETED" | "FAILED" | "PARTIAL" | "STALE";

export interface CrossDomainFinding {
  finding_id: string;
  project_id: string;
  domain_a: string;
  domain_b: string;
  affected_entity_ids: string[];
  rule_id: string;
  status: CrossDomainStatus;
  severity: CrossDomainSeverity;
  engineering_claim: string;
  explanation: string;
  quantitative_values: Record<string, any>;
  margin?: number | null;
  source_classification: string;
}

export interface CrossDomainValidationSummary {
  total_findings: number;
  pass_count: number;
  fail_count: number;
  warning_count: number;
  unknown_count: number;
  not_applicable_count: number;
  critical_failure_count: number;
  domains_evaluated: string[];
  status: CrossDomainValidationStatus;
}

export interface CrossDomainValidationResponse {
  id: string;
  project_id: string;
  status?: CrossDomainValidationStatus;
  validation_status?: string;
  is_stale?: boolean;
  staleness_reasons?: string[];
  snapshot_digest: string;
  summary: CrossDomainValidationSummary;
  findings: CrossDomainFinding[];
  created_by?: string;
  created_at: string;
  updated_at?: string;
}

// ==========================================
// Phase 3 Wave 10C/10D: Release Governance Types
// ==========================================

export type ReleaseGateStatus = "PASS" | "FAIL" | "BLOCKED" | "UNKNOWN" | "STALE" | "NOT_APPLICABLE";
export type OverallReadinessState = "READY_FOR_RELEASE" | "NOT_READY" | "BLOCKED" | "STALE";

export interface ReleaseGateDetail {
  gate_id: string;
  name: string;
  status: ReleaseGateStatus;
  definition_version: string;
  applicable_scope: string;
  is_applicable: boolean;
  not_applicable_reason?: string | null;
  authoritative_sources: string[];
  evidence_identifiers: Record<string, any>[];
  failure_reasons: string[];
  missing_evidence: string[];
  stale_reasons: string[];
  waived: boolean;
  waiver_rationale?: string | null;
  waived_by?: string | null;
  evaluated_at: string;
}

export interface ReleaseEvaluationResponse {
  id: string;
  project_id: string;
  tenant_id?: string | null;
  evaluator_version: string;
  project_revision: number;
  overall_readiness: OverallReadinessState;
  is_stale: boolean;
  state_fingerprint: string;
  gate_results: Record<string, ReleaseGateDetail>;
  blocking_findings: Array<{ gate_id: string; reasons: string[] }>;
  missing_evidence: Array<{ gate_id: string; items: string[] }>;
  stale_evidence: Array<{ gate_id: string; reasons: string[] }>;
  audit_chain_verified: boolean;
  audit_chain_head_hash?: string | null;
  audit_chain_sequence?: number | null;
  audit_chain_trusted_anchor_checked: boolean;
  evaluated_by_id: string;
  evaluated_at: string;
}

export interface ReleaseBaselineResponse {
  id: string;
  release_tag: string;
  project_id: string;
  tenant_id?: string | null;
  evaluation_id: string;
  project_revision: number;
  circuit_id?: string | null;
  circuit_version?: number | null;
  circuit_digest?: string | null;
  board_id?: string | null;
  board_version?: number | null;
  board_digest?: string | null;
  bom_id?: string | null;
  bom_version?: number | null;
  bom_digest?: string | null;
  audit_chain_head_hash: string;
  audit_chain_sequence: number;
  audit_chain_trusted_anchor_checked: boolean;
  evaluation_snapshot: Record<string, any>;
  canonical_snapshot_digest: string;
  authorized_by_id: string;
  authorized_by_role: string;
  authorized_at: string;
  release_rationale: string;
  exceptions_approved: Record<string, any>[];
  created_at: string;
}
