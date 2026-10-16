"""
Pydantic schemas for Phase 3 Wave 10C: Deterministic Release Gate Engine and Frozen Release Baselines.
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.db.release import OverallReadinessState, ReleaseGateStatus


class ReleaseGateDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    gate_id: str = Field(..., description="Gate identifier: RG-01 through RG-09")
    name: str = Field(..., description="Descriptive gate name")
    status: ReleaseGateStatus = Field(..., description="Deterministic status: PASS, FAIL, BLOCKED, UNKNOWN, STALE, NOT_APPLICABLE")
    definition_version: str = Field(default="1.0.0", description="Evaluator definition version")
    applicable_scope: str = Field(..., description="Applicable engineering domain or artifact scope")
    is_applicable: bool = Field(default=True, description="Whether the gate is applicable to this project")
    not_applicable_reason: Optional[str] = Field(default=None, description="Explicit engineering reason if NOT_APPLICABLE")
    
    authoritative_sources: list[str] = Field(default_factory=list, description="Authoritative models/records evaluated")
    evidence_identifiers: list[dict[str, Any]] = Field(default_factory=list, description="Exact entity IDs, versions, and digests")
    
    failure_reasons: list[str] = Field(default_factory=list, description="Specific failing engineering conditions")
    missing_evidence: list[str] = Field(default_factory=list, description="Missing required engineering evidence items")
    stale_reasons: list[str] = Field(default_factory=list, description="Reasons why evidence was marked STALE")
    
    waived: bool = Field(default=False, description="Whether a waiver was applied")
    waiver_rationale: Optional[str] = Field(default=None, description="Documented human engineer waiver rationale")
    waived_by: Optional[str] = Field(default=None, description="Human engineer who authorized waiver")
    
    evaluated_at: datetime = Field(..., description="Timestamp of gate evaluation")


class ReleaseEvaluationRequest(BaseModel):
    circuit_id: Optional[str] = Field(default=None, description="Target circuit ID to evaluate (or active latest)")
    board_id: Optional[str] = Field(default=None, description="Target board ID to evaluate (or active latest)")
    bom_id: Optional[str] = Field(default=None, description="Target BOM ID to evaluate (or active latest)")
    expected_audit_head_hash: Optional[str] = Field(default=None, description="Expected audit chain head hash for anchor checking")


class ReleaseEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    tenant_id: Optional[str] = None
    evaluator_version: str
    project_revision: int
    overall_readiness: OverallReadinessState
    is_stale: bool
    state_fingerprint: str
    
    gate_results: dict[str, ReleaseGateDetail]
    blocking_findings: list[dict[str, Any]]
    missing_evidence: list[dict[str, Any]]
    stale_evidence: list[dict[str, Any]]
    
    audit_chain_verified: bool
    audit_chain_head_hash: Optional[str] = None
    audit_chain_sequence: Optional[int] = None
    audit_chain_trusted_anchor_checked: bool
    
    evaluated_by_id: str
    evaluated_at: datetime


class ReleaseBaselineCreateRequest(BaseModel):
    evaluation_id: str = Field(..., description="ID of fresh, valid ReleaseEvaluation to freeze")
    release_tag: str = Field(..., min_length=2, max_length=64, description="Release identifier e.g. REL-2026.1-A")
    release_rationale: str = Field(..., min_length=5, description="Human engineer sign-off justification")
    exceptions_approved: list[dict[str, Any]] = Field(default_factory=list, description="Explicit human-approved exceptions")


class ReleaseBaselineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    release_tag: str
    project_id: str
    tenant_id: Optional[str] = None
    evaluation_id: str
    project_revision: int
    
    circuit_id: Optional[str] = None
    circuit_version: Optional[int] = None
    circuit_digest: Optional[str] = None
    
    board_id: Optional[str] = None
    board_version: Optional[int] = None
    board_digest: Optional[str] = None
    
    bom_id: Optional[str] = None
    bom_version: Optional[int] = None
    bom_digest: Optional[str] = None
    
    audit_chain_head_hash: str
    audit_chain_sequence: int
    audit_chain_trusted_anchor_checked: bool
    
    evaluation_snapshot: dict[str, Any]
    canonical_snapshot_digest: str
    
    authorized_by_id: str
    authorized_by_role: str
    authorized_at: datetime
    release_rationale: str
    exceptions_approved: list[dict[str, Any]]
    created_at: datetime
