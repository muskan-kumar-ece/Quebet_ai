from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.db.provenance import (
    CalibrationStatus,
    KnowledgeApplicability,
    KnowledgeClassification,
    KnowledgeStatus,
    SourceStatus,
    SourceTrustLevel,
    SourceType,
)


class SourceCreate(BaseModel):
    source_type: SourceType | str
    title: str
    publisher: str
    document_identifier: str
    revision: str = "Rev A"
    version: str = "1.0"
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    uri: Optional[str] = None
    document_hash: Optional[str] = None
    trust_level: SourceTrustLevel | str = SourceTrustLevel.UNVERIFIED.value
    status: SourceStatus | str = SourceStatus.CURRENT.value
    metadata: Optional[dict[str, Any]] = None


class SourceResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    source_type: str
    title: str
    publisher: str
    document_identifier: str
    revision: str
    version: str
    publication_date: Optional[str] = None
    effective_date: Optional[str] = None
    uri: Optional[str] = None
    document_hash: Optional[str] = None
    trust_level: str
    status: str
    supersedes_source_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class SourceSupersedeRequest(BaseModel):
    new_source: SourceCreate
    reason: str


class KnowledgeRecordCreate(BaseModel):
    source_id: Optional[str] = None
    domain: str = "SEMICONDUCTOR"
    subject_type: str = "COMPONENT"
    subject_identifier: str
    parameter: str
    value: str
    unit: Optional[str] = None
    classification: KnowledgeClassification | str = KnowledgeClassification.AUTHORITATIVE_SOURCE.value
    parameter_category: Optional[str] = None
    raw_value: Optional[str] = None
    normalized_value: Optional[float] = None
    source_location: dict[str, Any] = Field(default_factory=dict)
    is_conflicting: bool = False
    conflict_details: dict[str, Any] = Field(default_factory=dict)
    conditions: dict[str, Any] = Field(default_factory=dict)
    valid_range: Optional[dict[str, Any]] = None
    status: KnowledgeStatus | str = KnowledgeStatus.VERIFIED.value
    provenance: dict[str, Any] = Field(default_factory=dict)


class KnowledgeRecordResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    source_id: Optional[str] = None
    domain: str
    subject_type: str
    subject_identifier: str
    parameter: str
    value: str
    unit: Optional[str] = None
    classification: str = KnowledgeClassification.AUTHORITATIVE_SOURCE.value
    parameter_category: Optional[str] = None
    raw_value: Optional[str] = None
    normalized_value: Optional[float] = None
    source_location: dict[str, Any] = Field(default_factory=dict)
    is_conflicting: bool = False
    conflict_details: dict[str, Any] = Field(default_factory=dict)
    conditions: dict[str, Any] = Field(default_factory=dict)
    valid_range: Optional[dict[str, Any]] = None
    status: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    supersedes_knowledge_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    source: Optional[SourceResponse] = None

    model_config = ConfigDict(from_attributes=True)


class KnowledgeSupersedeRequest(BaseModel):
    new_record: KnowledgeRecordCreate
    reason: str


class KnowledgeApplicabilityRequest(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)


class KnowledgeApplicabilityResponse(BaseModel):
    knowledge_id: str
    applicability: KnowledgeApplicability | str
    reasons: list[str] = Field(default_factory=list)
    evaluated_conditions: dict[str, Any] = Field(default_factory=dict)
    missing_conditions: list[str] = Field(default_factory=list)


class AnalysisTraceabilityResponse(BaseModel):
    analysis_id: str
    circuit_id: str
    circuit_revision: int
    engine_versions: dict[str, str] = Field(default_factory=dict)
    rule_set_version: str
    knowledge_snapshot_id: Optional[str] = None
    input_values: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    calculation_methods: list[str] = Field(default_factory=list)
    knowledge_records: list[KnowledgeRecordResponse] = Field(default_factory=list)
    sources: list[SourceResponse] = Field(default_factory=list)
    created_at: datetime


class FindingTraceabilityResponse(BaseModel):
    finding_id: str
    rule_id: str
    analysis_id: str
    affected_components: list[str] = Field(default_factory=list)
    affected_nets: list[str] = Field(default_factory=list)
    knowledge_records: list[KnowledgeRecordResponse] = Field(default_factory=list)
    sources: list[SourceResponse] = Field(default_factory=list)
    input_values: dict[str, Any] = Field(default_factory=dict)
    calculation_result: dict[str, Any] = Field(default_factory=dict)


class RequirementTraceabilityResponse(BaseModel):
    requirement_id: str
    requirement_code: str
    related_finding_id: Optional[str] = None
    related_rule_id: Optional[str] = None
    knowledge_records: list[KnowledgeRecordResponse] = Field(default_factory=list)
    sources: list[SourceResponse] = Field(default_factory=list)
    evidence_count: int = 0


class EvidenceTraceabilityResponse(BaseModel):
    evidence_id: str
    requirement_id: str
    evidence_type: str
    source: str
    source_id: Optional[str] = None
    source_document: Optional[SourceResponse] = None
    instrument: Optional[str] = None
    instrument_model: Optional[str] = None
    instrument_serial: Optional[str] = None
    calibration_reference: Optional[str] = None
    calibration_status: str
    circuit_id: Optional[str] = None
    circuit_revision: Optional[int] = None
    is_stale: bool
    status: str


class KnowledgeImpactResponse(BaseModel):
    knowledge_id: str
    parameter: str
    subject_identifier: str
    status: str
    affected_components: list[str] = Field(default_factory=list)
    affected_analyses: list[str] = Field(default_factory=list)
    affected_findings: list[str] = Field(default_factory=list)
    affected_verification_requirements: list[str] = Field(default_factory=list)
    affected_design_reviews: list[str] = Field(default_factory=list)
    affected_proposals: list[str] = Field(default_factory=list)
    recommendation: str


class ExtractedParameterItem(BaseModel):
    parameter: str
    raw_value: str
    unit: Optional[str] = None
    classification: KnowledgeClassification | str = KnowledgeClassification.AUTHORITATIVE_SOURCE.value
    parameter_category: Optional[str] = None
    domain: str = "SEMICONDUCTOR"
    subject_type: str = "COMPONENT"
    subject_identifier: str
    conditions: dict[str, Any] = Field(default_factory=dict)
    valid_range: Optional[dict[str, Any]] = None
    source_location: dict[str, Any] = Field(default_factory=dict)


class KnowledgeIngestRequest(BaseModel):
    source: SourceCreate
    parameters: list[ExtractedParameterItem] = Field(default_factory=list)


class KnowledgeIngestResponse(BaseModel):
    source: SourceResponse
    knowledge_records: list[KnowledgeRecordResponse] = Field(default_factory=list)
    superseded_source_id: Optional[str] = None


class KnowledgeSearchItemResponse(BaseModel):
    record: KnowledgeRecordResponse
    source: Optional[SourceResponse] = None
    provenance_chain: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchResponse(BaseModel):
    total: int
    items: list[KnowledgeSearchItemResponse] = Field(default_factory=list)
