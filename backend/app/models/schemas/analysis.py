from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AnalysisStatus(str, Enum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    INVALID = "INVALID"


class AnalysisConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class CalculationItem(BaseModel):
    id: str
    name: str
    category: str
    component_ids: list[str] = Field(default_factory=list)
    net_ids: list[str] = Field(default_factory=list)
    formula: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    unit: str
    confidence: str = AnalysisConfidence.HIGH.value
    notes: str | None = None


class FindingItem(BaseModel):
    id: str
    rule_id: str
    title: str
    description: str
    severity: str = FindingSeverity.WARNING.value
    component_ids: list[str] = Field(default_factory=list)
    net_ids: list[str] = Field(default_factory=list)
    pin_ids: list[str] = Field(default_factory=list)
    recommended_action: str | None = None
    provenance: str = "DETERMINISTIC_RULE"


class EngineeringUnknown(BaseModel):
    id: str
    component_id: str | None = None
    net_id: str | None = None
    field: str
    reason: str
    impact: str


class GraphSummary(BaseModel):
    total_components: int = 0
    total_nets: int = 0
    total_connections: int = 0
    floating_pins: list[dict[str, Any]] = Field(default_factory=list)
    power_nets: list[str] = Field(default_factory=list)
    ground_nets: list[str] = Field(default_factory=list)
    isolated_subgraphs: int = 1


class CircuitAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    circuit_id: str
    circuit_version: int
    tenant_id: str | None = None
    created_by: str
    status: str
    confidence: str
    graph_summary: dict[str, Any] = Field(default_factory=dict)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    execution_time_ms: float
    created_at: datetime


class ExplainRequest(BaseModel):
    finding_ids: list[str] | None = None
    component_ids: list[str] | None = None
    user_query: str | None = None


class ExplainResponse(BaseModel):
    circuit_id: str
    explanation: str
    identified_mechanisms: list[str] = Field(default_factory=list)
    engineering_tradeoffs: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    verified_calculations_used: list[str] = Field(default_factory=list)
