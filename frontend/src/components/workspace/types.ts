/**
 * Phase 3 Wave 9: Unified Engineering Project Workspace Types
 * STRICT INVARIANTS:
 * - AI ENGINEERING AUTHORITY = NONE
 * - UNKNOWN != PASS
 * - MISSING != CONFIGURED
 * - ZERO SYNTHETIC SCORING
 */

export type DomainStatus =
  | "MISSING"
  | "CONFIGURED"
  | "INCOMPLETE"
  | "STALE"
  | "FAILING_RULES"
  | "UNKNOWN";

export interface DomainInventoryItem {
  domain_name: string;
  display_name: string;
  entity_count: number;
  latest_entity_id: string | null;
  latest_revision: number | null;
  status: DomainStatus;
  status_reason: string;
  last_updated_at: string | null;
}

export interface CrossDomainSummary {
  record_id: string | null;
  evaluated_at: string | null;
  status: string | null;
  is_stale: boolean;
  staleness_reasons: string[];
  rule_counts: {
    total: number;
    pass: number;
    fail: number;
    warning: number;
    unknown: number;
  };
  snapshot_digest: string | null;
}

export interface ProjectWorkspaceStateResponse {
  project_id: string;
  project_name: string;
  project_status: string;
  active_circuit_version: number | null;
  domains: DomainInventoryItem[];
  cross_domain_validation: CrossDomainSummary | null;
  workspace_digest: string;
  generated_at: string;
}

export interface BoundEntityRef {
  entity_id: string;
  entity_type: string;
  name_or_type: string;
  entity_version: number | null;
  bound_circuit_version: number | null;
  status: string;
  created_at: string;
}

export interface CircuitRevisionLineageItem {
  circuit_id: string;
  circuit_version: number;
  is_current: boolean;
  validation_status: string;
  created_at: string;
  boards: BoundEntityRef[];
  boms: BoundEntityRef[];
  simulations: BoundEntityRef[];
  manufacturing_analyses: BoundEntityRef[];
  design_reviews: BoundEntityRef[];
}

export interface ProjectRevisionLineageResponse {
  project_id: string;
  active_circuit_version: number | null;
  circuit_revisions: CircuitRevisionLineageItem[];
  unbound_entities: BoundEntityRef[];
  generated_at: string;
}

export type TimelineCategory =
  | "CIRCUIT"
  | "BOARD"
  | "BOM"
  | "SIMULATION"
  | "MANUFACTURING"
  | "REQUIREMENT"
  | "REVIEW"
  | "CROSS_DOMAIN_VALIDATION";

export interface ProjectActivityItem {
  event_id: string;
  category: TimelineCategory;
  event_type: string;
  entity_id: string;
  entity_name: string;
  revision_or_version: number | null;
  timestamp: string;
  summary: string;
  details?: Record<string, unknown> | null;
}

export interface ProjectActivityTimelineResponse {
  project_id: string;
  events: ProjectActivityItem[];
  total_events: number;
  limit: number;
  has_more: boolean;
}
