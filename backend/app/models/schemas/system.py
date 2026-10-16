from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SystemBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SystemCreate(SystemBase):
    project_id: str


class SystemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SystemResponse(SystemBase):
    id: str
    project_id: str
    tenant_id: Optional[str] = None
    revision: int
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class SubsystemBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    subsystem_type: str = "OTHER"
    parent_subsystem_id: Optional[str] = None
    circuit_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SubsystemCreate(SubsystemBase):
    pass


class SubsystemUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subsystem_type: Optional[str] = None
    parent_subsystem_id: Optional[str] = None
    circuit_id: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SubsystemResponse(SubsystemBase):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    revision: int
    status: str
    created_at: datetime
    updated_at: datetime


class InterfaceBase(BaseModel):
    name: str = Field(..., max_length=255)
    interface_type: str = "OTHER"
    source_subsystem_id: str
    destination_subsystem_id: str
    description: Optional[str] = None
    contract: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class InterfaceCreate(InterfaceBase):
    pass


class InterfaceUpdate(BaseModel):
    name: Optional[str] = None
    interface_type: Optional[str] = None
    source_subsystem_id: Optional[str] = None
    destination_subsystem_id: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    contract: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class InterfaceResponse(InterfaceBase):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class PowerDomainBase(BaseModel):
    name: str = Field(..., max_length=255)
    nominal_voltage: float
    min_voltage: Optional[float] = None
    max_voltage: Optional[float] = None
    source_subsystem_id: str
    regulator_subsystem_id: Optional[str] = None
    current_capacity_a: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class PowerDomainCreate(PowerDomainBase):
    pass


class PowerDomainResponse(PowerDomainBase):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class DependencyBase(BaseModel):
    source_subsystem_id: str
    target_subsystem_id: str
    dependency_type: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class DependencyCreate(DependencyBase):
    pass


class DependencyResponse(DependencyBase):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class OperatingModeBase(BaseModel):
    name: str = Field(..., max_length=64)
    description: Optional[str] = None
    active_subsystem_ids: List[str] = Field(default_factory=list)
    inactive_subsystem_ids: List[str] = Field(default_factory=list)
    expected_power_domain_ids: List[str] = Field(default_factory=list)
    relevant_interface_ids: List[str] = Field(default_factory=list)
    operating_conditions: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class OperatingModeCreate(OperatingModeBase):
    pass


class OperatingModeResponse(OperatingModeBase):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class ModeTransitionBase(BaseModel):
    source_mode_id: str
    destination_mode_id: str
    trigger: str = Field(..., max_length=255)
    conditions: Dict[str, Any] = Field(default_factory=dict)
    required_subsystems: List[str] = Field(default_factory=list)
    forbidden_conditions: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ModeTransitionCreate(ModeTransitionBase):
    pass


class ModeTransitionResponse(ModeTransitionBase):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class SystemRequirementBase(BaseModel):
    code: str = Field(..., max_length=64)
    title: str = Field(..., max_length=255)
    description: str
    requirement_type: str = "FUNCTIONAL"
    source: Optional[str] = None
    status: str = "UNKNOWN"
    constraints: Dict[str, Any] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SystemRequirementCreate(SystemRequirementBase):
    pass


class SystemRequirementResponse(SystemRequirementBase):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SystemFindingResponse(BaseModel):
    id: str
    analysis_id: str
    system_id: str
    rule_id: str
    category: str
    severity: str
    title: str
    description: str
    affected_subsystems: List[str] = Field(default_factory=list)
    affected_interfaces: List[str] = Field(default_factory=list)
    affected_power_domains: List[str] = Field(default_factory=list)
    inputs: Dict[str, Any] = Field(default_factory=dict)
    calculation: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    unknowns: List[str] = Field(default_factory=list)
    status: str
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SystemAnalysisResponse(BaseModel):
    id: str
    system_id: str
    tenant_id: Optional[str] = None
    system_revision: int
    subsystem_revisions: Dict[str, int] = Field(default_factory=dict)
    circuit_revisions: Dict[str, int] = Field(default_factory=dict)
    engine_versions: Dict[str, str] = Field(default_factory=dict)
    rule_set_version: str
    knowledge_snapshot_id: Optional[str] = None
    inputs_digest: str
    status: str
    is_stale: bool
    findings: List[SystemFindingResponse] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="metadata_")
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class FailurePropagationRequest(BaseModel):
    failed_subsystem_id: Optional[str] = None
    failed_interface_id: Optional[str] = None
    failure_type: str = "TOTAL_LOSS_OF_FUNCTION"

    model_config = ConfigDict(populate_by_name=True)


class FailurePropagationResult(BaseModel):
    root_cause: Dict[str, Any]
    upstream_affected_subsystems: List[str] = Field(default_factory=list)
    downstream_affected_subsystems: List[str] = Field(default_factory=list)
    affected_interfaces: List[str] = Field(default_factory=list)
    affected_power_domains: List[str] = Field(default_factory=list)
    containment_barriers: List[Dict[str, Any]] = Field(default_factory=list)
    loss_of_functions: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class ChangeImpactRequest(BaseModel):
    target_type: str  # SUBSYSTEM, INTERFACE, POWER_DOMAIN, DEPENDENCY
    target_id: str
    proposed_change: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class ChangeImpactResult(BaseModel):
    target_id: str
    target_type: str
    affected_subsystems: List[str] = Field(default_factory=list)
    affected_interfaces: List[str] = Field(default_factory=list)
    affected_power_domains: List[str] = Field(default_factory=list)
    affected_analyses: List[str] = Field(default_factory=list)
    affected_verification_requirements: List[str] = Field(default_factory=list)
    stale_analyses_count: int
    blast_radius_summary: str

    model_config = ConfigDict(populate_by_name=True)


class SystemSnapshotResponse(BaseModel):
    id: str
    system_id: str
    system_revision: int
    snapshot_hash: str
    content: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class SystemDetailResponse(SystemResponse):
    subsystems: List[SubsystemResponse] = Field(default_factory=list)
    interfaces: List[InterfaceResponse] = Field(default_factory=list)
    power_domains: List[PowerDomainResponse] = Field(default_factory=list)
    dependencies: List[DependencyResponse] = Field(default_factory=list)
    operating_modes: List[OperatingModeResponse] = Field(default_factory=list)
    mode_transitions: List[ModeTransitionResponse] = Field(default_factory=list)
    requirements: List[SystemRequirementResponse] = Field(default_factory=list)
    latest_analysis: Optional[SystemAnalysisResponse] = None
