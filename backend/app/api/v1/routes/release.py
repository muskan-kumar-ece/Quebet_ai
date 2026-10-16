import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.release import (
    ReleaseBaselineCreateRequest,
    ReleaseBaselineResponse,
    ReleaseEvaluationRequest,
    ReleaseEvaluationResponse,
)
from app.services.project_service import project_service
from app.services.release_service import ReleaseService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/release", tags=["release"])


@router.post(
    "/evaluate",
    response_model=ReleaseEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate deterministic release readiness",
)
async def evaluate_release_readiness(
    project_id: UUID,
    request: Optional[ReleaseEvaluationRequest] = None,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deterministically evaluate Release Gates RG-01 through RG-09 for the specified project.
    Verifies audit ledger chain integrity and computes immutable state fingerprint.
    """
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found or access denied.",
        )

    waivers = request.waivers if request else None
    actor_id = current_user.id
    actor_role = getattr(current_user, "role", "ENGINEER")
    if hasattr(actor_role, "value"):
        actor_role = actor_role.value

    service = ReleaseService(db)
    evaluation = await service.evaluate_release_readiness(
        project_id=str(project_id),
        user=current_user,
        request=request,
    )
    return evaluation


@router.get(
    "/evaluations/latest",
    response_model=ReleaseEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest release evaluation",
)
async def get_latest_release_evaluation(
    project_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the most recent release readiness evaluation for the project.
    """
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found or access denied.",
        )

    service = ReleaseService(db)
    return await service.get_latest_evaluation(str(project_id), current_user)


@router.get(
    "/evaluations/{evaluation_id}",
    response_model=ReleaseEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get release evaluation by ID",
)
async def get_release_evaluation(
    project_id: UUID,
    evaluation_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a specific release readiness evaluation by ID.
    """
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found or access denied.",
        )

    service = ReleaseService(db)
    return await service.get_evaluation(str(evaluation_id), current_user)


@router.post(
    "/baselines",
    response_model=ReleaseBaselineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Authorize and create frozen engineering release baseline",
)
async def create_release_baseline(
    project_id: UUID,
    request: ReleaseBaselineCreateRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Authorize and create an immutable, frozen engineering release baseline.
    Requires human engineer role and fresh READY_FOR_RELEASE evaluation.
    Atomically records a RELEASE_BASELINE_CREATED audit event in the ledger.
    """
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found or access denied.",
        )

    service = ReleaseService(db)
    return await service.authorize_release_baseline(
        project_id=str(project_id),
        request=request,
        user=current_user,
    )


@router.get(
    "/baselines",
    response_model=List[ReleaseBaselineResponse],
    status_code=status.HTTP_200_OK,
    summary="List release baselines for project",
)
async def list_release_baselines(
    project_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List frozen engineering release baselines for the project.
    """
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found or access denied.",
        )

    service = ReleaseService(db)
    return await service.list_baselines(str(project_id), current_user)


@router.get(
    "/baselines/{baseline_id}",
    response_model=ReleaseBaselineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get release baseline by ID",
)
async def get_release_baseline(
    project_id: UUID,
    baseline_id: UUID,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a specific frozen engineering release baseline by ID.
    """
    project = await project_service.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found or access denied.",
        )

    service = ReleaseService(db)
    return await service.get_baseline(str(baseline_id), current_user)