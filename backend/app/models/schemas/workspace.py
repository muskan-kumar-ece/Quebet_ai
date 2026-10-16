"""
Pydantic Schemas for Phase 3 Wave 9: Unified Engineering Project Workspace,
Revision Navigation & State Synthesis.

STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- UNKNOWN != PASS
- UNKNOWN != CONFIGURED
- MISSING != CONFIGURED
- ZERO SYNTHETIC SCORING (No confidence_percentage, readiness_score, health_score, 0-100 metrics).
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DomainStatus(str, Enum):
    MISSING = "MISSING"
    CONFIGURED = "CONFIGURED"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    FAILING_RULES = "FAILING_RULES"
    UNKNOWN = "UNKNOWN"


class DomainInventoryItem(BaseModel):
    domain_name: str = Field(..., description="Engineering domain identifier: schematic, pcb, bom, simulation, manufacturing, requirements, design_review, cross_domain")
    display_name: str = Field(..., description="Human-readable domain title")
    entity_count: int = Field(0, description="Total count of persisted entities in this domain")
    latest_entity_id: Optional[str] = Field(None, description="Identifier of the latest persisted entity")
    latest_revision: Optional[int] = Field(None, description="Revision or version number of latest entity")
    status: DomainStatus = Field(DomainStatus.MISSING, description="Authoritative posture state supported by persisted evidence")
    status_reason: str = Field(..., description="Deterministic justification for domain status")
    last_updated_at: Optional[datetime] = Field(None, description="Timestamp of latest entity creation or mutation")


class CrossDomainSummary(BaseModel):
    record_id: Optional[str] = None
    evaluated_at: Optional[datetime] = None
    status: Optional[str] = None
    is_stale: bool = False
    staleness_reasons: List[str] = Field(default_factory=list)
    rule_counts: Dict[str, int] = Field(
        default_factory=lambda: {"total": 0, "pass": 0, "fail": 0, "warning": 0, "unknown": 0}
    )
    snapshot_digest: Optional[str] = None


class ProjectWorkspaceStateResponse(BaseModel):
    project_id: str
    project_name: str
    project_status: str
    active_circuit_version: Optional[int] = None
    domains: List[DomainInventoryItem] = Field(default_factory=list)
    cross_domain_validation: Optional[CrossDomainSummary] = None
    workspace_digest: str = Field(..., description="Deterministic SHA-256 digest of project workspace inventory and revisions")
    generated_at: datetime


class BoundEntityRef(BaseModel):
    entity_id: str
    entity_type: str = Field(..., description="Entity category: board, bom, simulation, manufacturing_analysis, design_review")
    name_or_type: str
    entity_version: Optional[int] = None
    bound_circuit_version: Optional[int] = None
    status: str
    created_at: datetime


class CircuitRevisionLineageItem(BaseModel):
    circuit_id: str
    circuit_version: int
    is_current: bool
    validation_status: str
    created_at: datetime
    boards: List[BoundEntityRef] = Field(default_factory=list)
    boms: List[BoundEntityRef] = Field(default_factory=list)
    simulations: List[BoundEntityRef] = Field(default_factory=list)
    manufacturing_analyses: List[BoundEntityRef] = Field(default_factory=list)
    design_reviews: List[BoundEntityRef] = Field(default_factory=list)


class ProjectRevisionLineageResponse(BaseModel):
    project_id: str
    active_circuit_version: Optional[int] = None
    circuit_revisions: List[CircuitRevisionLineageItem] = Field(default_factory=list)
    unbound_entities: List[BoundEntityRef] = Field(default_factory=list)
    generated_at: datetime


class TimelineCategory(str, Enum):
    CIRCUIT = "CIRCUIT"
    BOARD = "BOARD"
    BOM = "BOM"
    SIMULATION = "SIMULATION"
    MANUFACTURING = "MANUFACTURING"
    REQUIREMENT = "REQUIREMENT"
    REVIEW = "REVIEW"
    CROSS_DOMAIN_VALIDATION = "CROSS_DOMAIN_VALIDATION"


class ProjectActivityItem(BaseModel):
    event_id: str
    category: TimelineCategory
    event_type: str
    entity_id: str
    entity_name: str
    revision_or_version: Optional[int] = None
    timestamp: datetime
    summary: str
    details: Optional[Dict[str, Any]] = None


class ProjectActivityTimelineResponse(BaseModel):
    project_id: str
    events: List[ProjectActivityItem] = Field(default_factory=list)
    total_events: int = 0
    limit: int = 50
    has_more: bool = False
