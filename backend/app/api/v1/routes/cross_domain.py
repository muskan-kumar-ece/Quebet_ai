"""
API routes for Phase 3 Wave 8: Advanced Engineering Validation, Cross-Domain Consistency & System-Level Verification.
Provides endpoints for executing cross-domain consistency checks, querying validation histories,
and inspecting canonical findings. Enforces tenant isolation and authenticated project access.
STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- UNKNOWN != PASS
- Zero synthetic scoring.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.common import ApiResponse
from app.models.schemas.cross_domain import (
    CrossDomainFinding,
    CrossDomainValidationRequest,
    CrossDomainValidationResponse,
)
from app.services.cross_domain_service import CrossDomainService
from app.services.project_service import project_service

router = APIRouter(prefix="/projects/{project_id}/cross-domain", tags=["Cross-Domain Consistency"])


@router.post("/validate", response_model=ApiResponse[CrossDomainValidationResponse])
async def run_cross_domain_validation(
    project_id: str,
    request: Optional[CrossDomainValidationRequest] = None,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes multi-domain consistency evaluations across Schematic, PCB, BOM, Simulation,
    DFM, Operating Limits, Power, Thermal, Requirements, and Verification.
    """
    # Enforce project access and tenant boundary
    await project_service.get_project(db=db, project_id=project_id, current_user=current_user)

    if getattr(current_user, "role", "") in ("viewer", "guest", "readonly", "read_only"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read-only user roles cannot trigger active cross-domain validation runs.",
        )

    service = CrossDomainService(db)
    record = await service.validate_project(
        project_id=project_id,
        tenant_id=current_user.tenant_id,
        request=request,
    )

    return ApiResponse(
        success=True,
        data=CrossDomainValidationResponse.model_validate(record),
    )


@router.get("/latest", response_model=ApiResponse[CrossDomainValidationResponse])
async def get_latest_cross_domain_validation(
    project_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves the most recent cross-domain validation record for a project.
    """
    await project_service.get_project(db=db, project_id=project_id, current_user=current_user)

    service = CrossDomainService(db)
    record = await service.get_latest_validation(
        project_id=project_id,
        tenant_id=current_user.tenant_id,
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No cross-domain validation records exist for this project.",
        )

    return ApiResponse(
        success=True,
        data=CrossDomainValidationResponse.model_validate(record),
    )


@router.get("/validations", response_model=ApiResponse[List[CrossDomainValidationResponse]])
async def list_cross_domain_validations(
    project_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lists historical cross-domain validation records for a project.
    """
    await project_service.get_project(db=db, project_id=project_id, current_user=current_user)

    service = CrossDomainService(db)
    records = await service.get_validations(
        project_id=project_id,
        tenant_id=current_user.tenant_id,
    )

    return ApiResponse(
        success=True,
        data=[CrossDomainValidationResponse.model_validate(r) for r in records],
    )


@router.get("/validations/{validation_id}", response_model=ApiResponse[CrossDomainValidationResponse])
async def get_cross_domain_validation(
    project_id: str,
    validation_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves a specific cross-domain validation record.
    """
    await project_service.get_project(db=db, project_id=project_id, current_user=current_user)

    service = CrossDomainService(db)
    record = await service.get_validation(
        validation_id=validation_id,
        project_id=project_id,
        tenant_id=current_user.tenant_id,
    )

    return ApiResponse(
        success=True,
        data=CrossDomainValidationResponse.model_validate(record),
    )


@router.get("/validations/{validation_id}/findings", response_model=ApiResponse[List[CrossDomainFinding]])
async def get_validation_findings(
    project_id: str,
    validation_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves canonical findings from a cross-domain validation record.
    """
    await project_service.get_project(db=db, project_id=project_id, current_user=current_user)

    service = CrossDomainService(db)
    record = await service.get_validation(
        validation_id=validation_id,
        project_id=project_id,
        tenant_id=current_user.tenant_id,
    )

    findings = [CrossDomainFinding.model_validate(f) for f in record.findings]

    return ApiResponse(
        success=True,
        data=findings,
    )
