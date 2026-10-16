"""
Pydantic schemas for Phase 3 Wave 8: Advanced Engineering Validation, Cross-Domain Consistency & System-Level Verification.
Enforces categorical statuses, explicit margins, zero synthetic scoring, and canonical provenance tracking.
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.models.db.cross_domain import (
    CrossDomainSeverity,
    CrossDomainStatus,
    CrossDomainValidationStatus,
    SourceClassification,
    ValidationDomain,
)


class CrossDomainFinding(BaseModel):
    finding_id: str
    tenant_id: Optional[str] = None
    project_id: str
    validation_id: Optional[str] = None
    domain_a: str
    domain_b: str
    affected_entity_ids: list[str] = Field(default_factory=list)
    rule_id: str
    status: CrossDomainStatus
    severity: CrossDomainSeverity
    engineering_claim: str
    explanation: str
    quantitative_values: dict[str, Any] = Field(default_factory=dict)
    margin: Optional[float] = None
    source_references: list[dict[str, Any]] = Field(default_factory=list)
    source_classification: SourceClassification = SourceClassification.CALCULATED
    snapshot_digest: Optional[str] = None
    created_at: Optional[datetime] = None


class CrossDomainValidationSummary(BaseModel):
    total_findings: int = 0
    pass_count: int = 0
    fail_count: int = 0
    warning_count: int = 0
    unknown_count: int = 0
    not_applicable_count: int = 0
    severity_breakdown: dict[str, int] = Field(default_factory=dict)
    domain_breakdown: dict[str, dict[str, int]] = Field(default_factory=dict)
    rule_results: dict[str, str] = Field(default_factory=dict)


class CrossDomainValidationRequest(BaseModel):
    circuit_id: Optional[str] = None
    board_id: Optional[str] = None
    bom_id: Optional[str] = None
    include_simulation: bool = True
    include_requirements: bool = True
    include_verification: bool = True
    include_dfm: bool = True


class CrossDomainValidationResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    project_id: str
    circuit_id: Optional[str] = None
    board_id: Optional[str] = None
    bom_id: Optional[str] = None
    validation_status: str
    summary: CrossDomainValidationSummary
    findings: list[CrossDomainFinding]
    domain_snapshots: dict[str, Any] = Field(default_factory=dict)
    is_stale: bool = False
    staleness_reasons: list[str] = Field(default_factory=list)
    snapshot_digest: str
    created_at: datetime

    model_config = {"from_attributes": True}
