from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.system import (
    ChangeImpactRequest,
    ChangeImpactResult,
    DependencyCreate,
    DependencyResponse,
    FailurePropagationRequest,
    FailurePropagationResult,
    InterfaceCreate,
    InterfaceResponse,
    InterfaceUpdate,
    ModeTransitionCreate,
    ModeTransitionResponse,
    OperatingModeCreate,
    OperatingModeResponse,
    PowerDomainCreate,
    PowerDomainResponse,
    SubsystemCreate,
    SubsystemResponse,
    SubsystemUpdate,
    SystemAnalysisResponse,
    SystemCreate,
    SystemDetailResponse,
    SystemFindingResponse,
    SystemRequirementCreate,
    SystemRequirementResponse,
    SystemResponse,
    SystemSnapshotResponse,
    SystemUpdate,
)
from app.services.system_service import SystemService

router = APIRouter(tags=["Engineering Systems & Subsystem Architecture"])


# ============================================================================
# 1. SYSTEMS
# ============================================================================

@router.post("/systems", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_system(
    payload: SystemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    system = await svc.create_system(
        project_id=payload.project_id,
        name=payload.name,
        created_by=current_user.id,
        description=payload.description,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"data": SystemResponse.model_validate(system)}


@router.get("/systems", response_model=dict[str, Any])
async def list_systems(
    project_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    systems = await svc.get_systems_for_project(project_id, tenant_id=current_user.tenant_id)
    return {"data": [SystemResponse.model_validate(s) for s in systems]}


@router.get("/systems/{id}", response_model=dict[str, Any])
async def get_system_detail(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    system = await svc.get_system(id, tenant_id=current_user.tenant_id, load_relations=True)
    if not system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")

    subsystems = await svc.get_subsystems(id, tenant_id=current_user.tenant_id)
    interfaces = await svc.get_interfaces(id, tenant_id=current_user.tenant_id)
    power_domains = await svc.get_power_domains(id, tenant_id=current_user.tenant_id)
    dependencies = await svc.get_dependencies(id, tenant_id=current_user.tenant_id)
    operating_modes = await svc.get_operating_modes(id, tenant_id=current_user.tenant_id)
    mode_transitions = await svc.get_mode_transitions(id, tenant_id=current_user.tenant_id)
    requirements = await svc.get_requirements(id, tenant_id=current_user.tenant_id)
    latest_analysis = await svc.get_latest_analysis(id, tenant_id=current_user.tenant_id)

    detail = SystemDetailResponse(
        id=system.id,
        project_id=system.project_id,
        tenant_id=system.tenant_id,
        name=system.name,
        description=system.description,
        revision=system.revision,
        status=system.status,
        created_by=system.created_by,
        metadata=system.metadata_,
        created_at=system.created_at,
        updated_at=system.updated_at,
        subsystems=[SubsystemResponse.model_validate(s) for s in subsystems],
        interfaces=[InterfaceResponse.model_validate(i) for i in interfaces],
        power_domains=[PowerDomainResponse.model_validate(d) for d in power_domains],
        dependencies=[DependencyResponse.model_validate(dep) for dep in dependencies],
        operating_modes=[OperatingModeResponse.model_validate(m) for m in operating_modes],
        mode_transitions=[ModeTransitionResponse.model_validate(t) for t in mode_transitions],
        requirements=[SystemRequirementResponse.model_validate(r) for r in requirements],
        latest_analysis=SystemAnalysisResponse.model_validate(latest_analysis) if latest_analysis else None,
    )
    return {"data": detail}


@router.patch("/systems/{id}", response_model=dict[str, Any])
async def update_system(
    id: str,
    payload: SystemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    updated = await svc.update_system(
        id,
        payload.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")
    return {"data": SystemResponse.model_validate(updated)}


# ============================================================================
# 2. SUBSYSTEMS
# ============================================================================

@router.post("/systems/{id}/subsystems", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_subsystem(
    id: str,
    payload: SubsystemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    system = await svc.get_system(id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")

    try:
        subsystem = await svc.create_subsystem(
            system_id=id,
            name=payload.name,
            subsystem_type=payload.subsystem_type,
            parent_subsystem_id=payload.parent_subsystem_id,
            circuit_id=payload.circuit_id,
            description=payload.description,
            tenant_id=current_user.tenant_id,
            metadata_=payload.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return {"data": SubsystemResponse.model_validate(subsystem)}


@router.get("/systems/{id}/subsystems", response_model=dict[str, Any])
async def list_subsystems(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    subsystems = await svc.get_subsystems(id, tenant_id=current_user.tenant_id)
    return {"data": [SubsystemResponse.model_validate(s) for s in subsystems]}


@router.patch("/subsystems/{id}", response_model=dict[str, Any])
async def update_subsystem(
    id: str,
    payload: SubsystemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    try:
        updated = await svc.update_subsystem(
            id,
            payload.model_dump(exclude_unset=True),
            tenant_id=current_user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subsystem not found")
    return {"data": SubsystemResponse.model_validate(updated)}


@router.delete("/subsystems/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subsystem(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> None:
    svc = SystemService(db)
    try:
        deleted = await svc.delete_subsystem(id, tenant_id=current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subsystem not found")


# ============================================================================
# 3. INTERFACES
# ============================================================================

@router.post("/systems/{id}/interfaces", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_interface(
    id: str,
    payload: InterfaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    system = await svc.get_system(id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")

    interface = await svc.create_interface(
        system_id=id,
        name=payload.name,
        source_subsystem_id=payload.source_subsystem_id,
        destination_subsystem_id=payload.destination_subsystem_id,
        interface_type=payload.interface_type,
        contract=payload.contract,
        description=payload.description,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"data": InterfaceResponse.model_validate(interface)}


@router.get("/systems/{id}/interfaces", response_model=dict[str, Any])
async def list_interfaces(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    interfaces = await svc.get_interfaces(id, tenant_id=current_user.tenant_id)
    return {"data": [InterfaceResponse.model_validate(i) for i in interfaces]}


@router.patch("/interfaces/{id}", response_model=dict[str, Any])
async def update_interface(
    id: str,
    payload: InterfaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    updated = await svc.update_interface(
        id,
        payload.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interface not found")
    return {"data": InterfaceResponse.model_validate(updated)}


@router.delete("/interfaces/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interface(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> None:
    svc = SystemService(db)
    deleted = await svc.delete_interface(id, tenant_id=current_user.tenant_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interface not found")


# ============================================================================
# 4. POWER DOMAINS
# ============================================================================

@router.post("/systems/{id}/power-domains", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_power_domain(
    id: str,
    payload: PowerDomainCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    system = await svc.get_system(id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")

    domain = await svc.create_power_domain(
        system_id=id,
        name=payload.name,
        nominal_voltage=payload.nominal_voltage,
        source_subsystem_id=payload.source_subsystem_id,
        min_voltage=payload.min_voltage,
        max_voltage=payload.max_voltage,
        regulator_subsystem_id=payload.regulator_subsystem_id,
        current_capacity_a=payload.current_capacity_a,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"data": PowerDomainResponse.model_validate(domain)}


@router.get("/systems/{id}/power-domains", response_model=dict[str, Any])
async def list_power_domains(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    domains = await svc.get_power_domains(id, tenant_id=current_user.tenant_id)
    return {"data": [PowerDomainResponse.model_validate(d) for d in domains]}


# ============================================================================
# 5. DEPENDENCIES
# ============================================================================

@router.post("/systems/{id}/dependencies", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_dependency(
    id: str,
    payload: DependencyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    system = await svc.get_system(id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")

    dep = await svc.create_dependency(
        system_id=id,
        source_subsystem_id=payload.source_subsystem_id,
        target_subsystem_id=payload.target_subsystem_id,
        dependency_type=payload.dependency_type,
        description=payload.description,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"data": DependencyResponse.model_validate(dep)}


@router.get("/systems/{id}/dependencies", response_model=dict[str, Any])
async def list_dependencies(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    dependencies = await svc.get_dependencies(id, tenant_id=current_user.tenant_id)
    return {"data": [DependencyResponse.model_validate(d) for d in dependencies]}


# ============================================================================
# 6. OPERATING MODES & TRANSITIONS
# ============================================================================

@router.post("/systems/{id}/modes", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_operating_mode(
    id: str,
    payload: OperatingModeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    system = await svc.get_system(id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")

    mode = await svc.create_operating_mode(
        system_id=id,
        name=payload.name,
        description=payload.description,
        active_subsystem_ids=payload.active_subsystem_ids,
        inactive_subsystem_ids=payload.inactive_subsystem_ids,
        expected_power_domain_ids=payload.expected_power_domain_ids,
        relevant_interface_ids=payload.relevant_interface_ids,
        operating_conditions=payload.operating_conditions,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"data": OperatingModeResponse.model_validate(mode)}


@router.get("/systems/{id}/modes", response_model=dict[str, Any])
async def list_operating_modes(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    modes = await svc.get_operating_modes(id, tenant_id=current_user.tenant_id)
    return {"data": [OperatingModeResponse.model_validate(m) for m in modes]}


# ============================================================================
# 7. REQUIREMENTS
# ============================================================================

@router.post("/systems/{id}/requirements", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_requirement(
    id: str,
    payload: SystemRequirementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    system = await svc.get_system(id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System not found")

    req = await svc.create_requirement(
        system_id=id,
        code=payload.code,
        title=payload.title,
        description=payload.description,
        requirement_type=payload.requirement_type,
        source=payload.source,
        status=payload.status,
        constraints=payload.constraints,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"data": SystemRequirementResponse.model_validate(req)}


@router.get("/systems/{id}/requirements", response_model=dict[str, Any])
async def list_requirements(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    requirements = await svc.get_requirements(id, tenant_id=current_user.tenant_id)
    return {"data": [SystemRequirementResponse.model_validate(r) for r in requirements]}


# ============================================================================
# 8. MASTER SYSTEM ANALYSIS & FINDINGS
# ============================================================================

@router.post("/systems/{id}/analyze", response_model=dict[str, Any])
async def run_system_analysis(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    try:
        analysis = await svc.run_system_analysis(id, tenant_id=current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return {"data": SystemAnalysisResponse.model_validate(analysis)}


@router.get("/systems/{id}/analysis/latest", response_model=dict[str, Any])
async def get_latest_system_analysis(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    analysis = await svc.get_latest_analysis(id, tenant_id=current_user.tenant_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No system analysis exists")
    return {"data": SystemAnalysisResponse.model_validate(analysis)}


@router.get("/systems/{id}/findings", response_model=dict[str, Any])
async def list_system_findings(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    findings = await svc.get_findings(id, tenant_id=current_user.tenant_id)
    return {"data": [SystemFindingResponse.model_validate(f) for f in findings]}


# ============================================================================
# 9. FAILURE SIMULATION & CHANGE IMPACT
# ============================================================================

@router.post("/systems/{id}/failure-analysis", response_model=dict[str, Any])
async def simulate_failure(
    id: str,
    payload: FailurePropagationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    try:
        result = await svc.simulate_failure(
            system_id=id,
            failed_subsystem_id=payload.failed_subsystem_id,
            failed_interface_id=payload.failed_interface_id,
            failure_type=payload.failure_type,
            tenant_id=current_user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return {"data": result}


@router.post("/systems/{id}/change-impact", response_model=dict[str, Any])
async def calculate_change_impact(
    id: str,
    payload: ChangeImpactRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    try:
        result = await svc.calculate_change_impact(
            system_id=id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            proposed_change=payload.proposed_change,
            tenant_id=current_user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return {"data": result}


# ============================================================================
# 10. TRACEABILITY & SNAPSHOTS
# ============================================================================

@router.get("/systems/{id}/traceability", response_model=dict[str, Any])
async def get_system_traceability(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    try:
        trace = await svc.get_system_traceability(id, tenant_id=current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"data": trace}


@router.post("/systems/{id}/snapshots", response_model=dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_snapshot(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, Any]:
    svc = SystemService(db)
    try:
        snapshot = await svc.create_snapshot(id, tenant_id=current_user.tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"data": SystemSnapshotResponse.model_validate(snapshot)}
