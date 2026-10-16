from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.db.project import ProjectStatus, ProjectType


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    project_type: ProjectType = ProjectType.CIRCUIT
    status: ProjectStatus = ProjectStatus.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    project_type: ProjectType | None = None
    status: ProjectStatus | None = None
    metadata: dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    tenant_id: str | None
    owner_id: str
    name: str
    description: str | None
    project_type: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    created_at: datetime
    updated_at: datetime


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int
    page: int = 1
    page_size: int = 50
