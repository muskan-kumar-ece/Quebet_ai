from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.decision import (
    EngineeringRequirementCreate,
    EngineeringRequirementUpdate,
    EngineeringRequirementResponse,
    EngineeringRequirementBaselineCreate,
    EngineeringRequirementBaselineResponse,
    EngineeringAssumptionCreate,
    EngineeringAssumptionUpdate,
    EngineeringAssumptionResponse,
)
from app.repositories.decision_repo import DecisionRepository
from app.repositories.system_repo import SystemRepository
from app.services.requirement_service import RequirementService

router = APIRouter(tags=["Requirements & Assumptions"])


@router.post("/systems/{system_id}/requirements", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_requirement(
    system_id: str,
    payload: EngineeringRequirementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    sys_repo = SystemRepository(db)
    system = await sys_repo.get_system(system_id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=404, detail="System not found")

    repo = DecisionRepository(db)
    req = await repo.create_requirement(
        project_id=system.project_id,
        system_id=system_id,
        requirement_key=payload.requirement_key,
        title=payload.title,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        source_type=payload.source_type,
        source_reference=payload.source_reference,
        parent_requirement_id=payload.parent_requirement_id,
        expression=payload.expression,
        created_by=current_user.id,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"status": "success", "data": EngineeringRequirementResponse.model_validate(req)}


@router.get("/systems/{system_id}/requirements", response_model=Dict[str, Any])
async def list_requirements(
    system_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    reqs = await repo.get_requirements_by_system(system_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": [EngineeringRequirementResponse.model_validate(r) for r in reqs]}


@router.get("/requirements/{requirement_id}", response_model=Dict[str, Any])
async def get_requirement(
    requirement_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    req = await repo.get_requirement(requirement_id, tenant_id=current_user.tenant_id)
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return {"status": "success", "data": EngineeringRequirementResponse.model_validate(req)}


@router.patch("/requirements/{requirement_id}", response_model=Dict[str, Any])
async def update_requirement(
    requirement_id: str,
    payload: EngineeringRequirementUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    req = await repo.update_requirement(
        requirement_id,
        updates=payload.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
        actor_id=current_user.id,
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return {"status": "success", "data": EngineeringRequirementResponse.model_validate(req)}


# Baselines
@router.post("/systems/{system_id}/requirement-baselines", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_requirement_baseline(
    system_id: str,
    payload: EngineeringRequirementBaselineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    sys_repo = SystemRepository(db)
    system = await sys_repo.get_system(system_id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=404, detail="System not found")

    repo = DecisionRepository(db)
    reqs = await repo.get_requirements_by_system(system_id, tenant_id=current_user.tenant_id)
    if not reqs:
        raise HTTPException(status_code=400, detail="Cannot baseline empty requirements set")

    baseline = await repo.create_baseline(
        system_id=system_id,
        system_revision=system.revision,
        name=payload.name,
        requirement_ids=[r.id for r in reqs],
        requirement_revisions={r.id: r.revision for r in reqs},
        created_by=current_user.id,
        knowledge_snapshot_id=payload.knowledge_snapshot_id,
        tenant_id=current_user.tenant_id,
    )
    return {"status": "success", "data": EngineeringRequirementBaselineResponse.model_validate(baseline)}


@router.get("/systems/{system_id}/requirement-baselines", response_model=Dict[str, Any])
async def list_requirement_baselines(
    system_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    baselines = await repo.get_baselines_by_system(system_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": [EngineeringRequirementBaselineResponse.model_validate(b) for b in baselines]}


# Assumptions
@router.post("/systems/{system_id}/assumptions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_assumption(
    system_id: str,
    payload: EngineeringAssumptionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    sys_repo = SystemRepository(db)
    system = await sys_repo.get_system(system_id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=404, detail="System not found")

    repo = DecisionRepository(db)
    assump = await repo.create_assumption(
        system_id=system_id,
        description=payload.description,
        basis=payload.basis,
        value=payload.value,
        unit=payload.unit,
        requirement_id=payload.requirement_id,
        source_id=payload.source_id,
        status=payload.status,
        impact=payload.impact,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"status": "success", "data": EngineeringAssumptionResponse.model_validate(assump)}


@router.get("/systems/{system_id}/assumptions", response_model=Dict[str, Any])
async def list_assumptions(
    system_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    assumps = await repo.get_assumptions_by_system(system_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": [EngineeringAssumptionResponse.model_validate(a) for a in assumps]}


@router.get("/assumptions/{assumption_id}", response_model=Dict[str, Any])
async def get_assumption(
    assumption_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    assump = await repo.get_assumption(assumption_id, tenant_id=current_user.tenant_id)
    if not assump:
        raise HTTPException(status_code=404, detail="Assumption not found")
    return {"status": "success", "data": EngineeringAssumptionResponse.model_validate(assump)}


@router.patch("/assumptions/{assumption_id}", response_model=Dict[str, Any])
async def update_assumption(
    assumption_id: str,
    payload: EngineeringAssumptionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    assump = await repo.update_assumption(
        assumption_id,
        updates=payload.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
    )
    if not assump:
        raise HTTPException(status_code=404, detail="Assumption not found")
    return {"status": "success", "data": EngineeringAssumptionResponse.model_validate(assump)}


# Coverage & Impact
@router.get("/systems/{system_id}/requirement-coverage", response_model=Dict[str, Any])
async def get_requirement_coverage(
    system_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = RequirementService(db)
    coverage = await service.get_system_requirement_coverage(system_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": coverage}


@router.get("/requirements/{requirement_id}/impact", response_model=Dict[str, Any])
async def get_requirement_impact(
    requirement_id: str,
    system_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = RequirementService(db)
    impact = await service.calculate_requirement_impact(requirement_id, system_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": impact}


@router.get("/assumptions/{assumption_id}/impact", response_model=Dict[str, Any])
async def get_assumption_impact(
    assumption_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = RequirementService(db)
    impact = await service.calculate_assumption_impact(assumption_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": impact}
