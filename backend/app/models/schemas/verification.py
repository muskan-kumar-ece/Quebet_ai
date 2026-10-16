from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.models.db.verification import (
    DesignReviewStatus,
    EvidenceStatus,
    EvidenceType,
    FailureModeCategory,
    OperatingCondition,
    VerificationMethod,
    VerificationStatus,
)


class EvidenceCreate(BaseModel):
    evidence_type: EvidenceType = Field(..., description="Type of evidence being submitted")
    source: str = Field(..., min_length=1, max_length=128, description="Source or tool, e.g. Bench DMM, Datasheet Section 6.2")
    description: str = Field(..., min_length=3, description="Detailed engineering description of the evidence")
    value: str | None = Field(None, max_length=255, description="Observed or measured value, e.g. 3.32")
    unit: str | None = Field(None, max_length=32, description="Physical unit, e.g. V, mA, degC")
    reference: str | None = Field(None, max_length=255, description="Document, datasheet, or bench log reference")
    confidence: str = Field("HIGH", description="Confidence level: HIGH, MEDIUM, LOW")
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    verification_requirement_id: str
    review_id: str
    tenant_id: str | None = None
    evidence_type: str
    source: str
    description: str
    value: str | None = None
    unit: str | None = None
    reference: str | None = None
    status: str
    confidence: str
    provided_by: str
    provided_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")


class RequirementStatusUpdate(BaseModel):
    status: VerificationStatus = Field(..., description="New verification status")
    not_applicable_reason: str | None = Field(None, description="Mandatory rationale if marking NOT_APPLICABLE")
    reason: str | None = Field(None, description="Human engineering rationale for manual state change")


class VerificationRequirementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    tenant_id: str | None = None
    code: str
    title: str
    reason: str
    trigger: str | None = None
    method: str
    operating_condition: str
    required_evidence: list[str] = Field(default_factory=list)
    status: str
    is_mandatory: bool
    not_applicable_reason: str | None = None
    affected_components: list[str] = Field(default_factory=list)
    affected_nets: list[str] = Field(default_factory=list)
    related_rule_id: str | None = None
    related_finding_id: str | None = None
    unknowns: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    evidence_items: list[EvidenceResponse] = Field(default_factory=list)


class FailureModeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    tenant_id: str | None = None
    category: str
    trigger: str
    mechanism: str
    consequence: str
    likelihood: str
    severity: str
    affected_components: list[str] = Field(default_factory=list)
    affected_nets: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    related_findings: list[str] = Field(default_factory=list)
    related_rules: list[str] = Field(default_factory=list)
    verification_requirement_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class TestPointCreate(BaseModel):
    code: str = Field(..., max_length=32, description="Test point identifier, e.g. TP-001")
    measurement: str = Field(..., max_length=255, description="Measurement parameter, e.g. 3.3V Rail Voltage")
    expected_basis: str = Field(..., description="Engineering basis for expected value, e.g. Datasheet V_OUT +/- 2%")
    instrumentation: str = Field(..., max_length=128, description="Recommended laboratory instrument, e.g. Oscilloscope 100MHz")
    operating_condition: OperatingCondition = Field(OperatingCondition.NOMINAL, description="Operating condition")
    target_net: str | None = Field(None, max_length=128)
    target_component: str | None = Field(None, max_length=128)
    related_requirement_id: str | None = None


class TestPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    tenant_id: str | None = None
    code: str
    target_net: str | None = None
    target_component: str | None = None
    measurement: str
    expected_basis: str
    instrumentation: str
    operating_condition: str
    related_requirement_id: str | None = None
    created_at: datetime


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    review_id: str
    tenant_id: str | None = None
    actor_id: str
    event_type: str
    object_id: str
    previous_state: str | None = None
    new_state: str | None = None
    reason: str | None = None
    created_at: datetime


class VerificationMatrixRow(BaseModel):
    requirement_id: str
    requirement_code: str
    title: str
    reason: str
    method: str
    operating_condition: str
    evidence_count: int
    latest_evidence_summary: str | None = None
    status: str
    is_mandatory: bool
    unknowns: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    affected_nets: list[str] = Field(default_factory=list)


class VerificationMatrixResponse(BaseModel):
    review_id: str
    circuit_id: str
    circuit_revision: int
    status: str
    total_requirements: int
    satisfied_count: int
    in_progress_count: int
    unknown_count: int
    blocked_count: int
    failed_count: int
    not_applicable_count: int
    is_stale: bool
    matrix: list[VerificationMatrixRow]


class DesignReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None = None
    project_id: str
    circuit_id: str
    circuit_revision: int
    analysis_id: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    failure_modes: list[FailureModeResponse] = Field(default_factory=list)
    verification_requirements: list[VerificationRequirementResponse] = Field(default_factory=list)
    test_points: list[TestPointResponse] = Field(default_factory=list)
    evidence_summary: dict[str, int] = Field(default_factory=dict)
    unresolved_findings_count: int = 0
    unknowns: list[str] = Field(default_factory=list)
    is_stale: bool = False
