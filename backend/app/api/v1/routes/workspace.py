"""
API routes for Phase 3 Wave 9: Unified Engineering Project Workspace,
Revision Navigation & State Synthesis.

Provides endpoints for querying multi-domain workspace state, revision lineage,
and chronological activity timeline. Enforces tenant isolation and authenticated project access.

STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- UNKNOWN != PASS
- UNKNOWN != CONFIGURED
- MISSING != CONFIGURED
- ZERO SYNTHETIC SCORING
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.common import ApiResponse
from app.models.schemas.workspace import (
    ProjectActivityTimelineResponse,
    ProjectRevisionLineageResponse,
    ProjectWorkspaceStateResponse,
)
from app.services.project_service import project_service
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/projects/{project_id}/workspace", tags=["Project Workspace"])


@router.get("/state", response_model=ApiResponse[ProjectWorkspaceStateResponse])
async def get_project_workspace_state(
    project_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the unified engineering workspace state for a project,
    aggregating domain inventory, posture states, and cross-domain validation staleness.
    """
    project = await project_service.get_project(db=db, project_id=project_id, current_user=current_user)
    service = WorkspaceService(db)
    state = await service.get_workspace_state(project=project)
    return ApiResponse(success=True, data=state)


@router.get("/revisions", response_model=ApiResponse[ProjectRevisionLineageResponse])
async def get_project_revision_lineage(
    project_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves multi-domain revision lineage grouping PCB boards, BOMs, simulations,
    DFM analyses, and design reviews by schematic circuit version.
    """
    project = await project_service.get_project(db=db, project_id=project_id, current_user=current_user)
    service = WorkspaceService(db)
    lineage = await service.get_revision_lineage(project=project)
    return ApiResponse(success=True, data=lineage)


@router.get("/activity", response_model=ApiResponse[ProjectActivityTimelineResponse])
async def get_project_activity_timeline(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of activity events to return"),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves a reconstructed chronological activity timeline across all persisted
    engineering records for the project, sorted deterministically by timestamp descending.
    """
    project = await project_service.get_project(db=db, project_id=project_id, current_user=current_user)
    service = WorkspaceService(db)
    timeline = await service.get_activity_timeline(project=project, limit=limit)
    return ApiResponse(success=True, data=timeline)
