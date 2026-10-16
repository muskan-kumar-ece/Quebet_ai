from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.db.proposal import ProposalStatus


class ProposalOperation(BaseModel):
    op_type: str = Field(
        ...,
        description="add_component | remove_component | update_component | add_net | remove_net | add_connection | remove_connection | update_component_value | update_component_rating | replace_component",
    )
    payload: dict[str, Any] = Field(..., description="Operation-specific data payload")
    description: str | None = None


class ProposalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    source: str = Field(default="AI", description="AI | USER | HEURISTIC")
    base_revision: int = Field(default=1, description="Circuit version baseline for stale detection")
    analysis_id: str | None = None
    objective_id: str | None = None
    operations: list[ProposalOperation] = Field(..., min_length=1)
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    findings_resolved: list[str] = Field(default_factory=list)
    findings_introduced: list[str] = Field(default_factory=list)
    constraints_evaluated: list[dict[str, Any]] = Field(default_factory=list)
    engineering_effects: list[str] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)
    confidence: str = "HIGH"


class ProposalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    circuit_id: str
    tenant_id: str | None = None
    created_by: str
    source: str
    title: str
    description: str | None = None
    status: ProposalStatus
    base_revision: int = 1
    analysis_id: str | None = None
    objective_id: str | None = None
    operations: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[dict[str, Any]] = Field(default_factory=list)
    validation_result: dict[str, Any] | None = None
    findings_resolved: list[str] = Field(default_factory=list)
    findings_introduced: list[str] = Field(default_factory=list)
    constraints_evaluated: list[dict[str, Any]] = Field(default_factory=list)
    engineering_effects: list[str] = Field(default_factory=list)
    unknowns: list[dict[str, Any]] = Field(default_factory=list)
    confidence: str = "HIGH"
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
