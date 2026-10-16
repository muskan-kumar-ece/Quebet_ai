from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.system_synthesis import (
    ScenarioComparisonRequest,
    ScenarioComparisonResponse,
    ScenarioCreate,
    ScenarioResponse,
    ScenarioResultResponse,
    SystemArchitectureCompareRequest,
    SystemArchitectureCompareResponse,
    SystemCandidateGenerateRequest,
    SystemCandidateResponse,
    SystemDesignObjectiveCreate,
    SystemDesignObjectiveResponse,
    SystemProposalCreate,
    SystemProposalResponse,
    SystemWhatIfRequest,
    SystemWhatIfResponse,
)
from app.services.system_proposal_service import SystemProposalService
from app.services.system_synthesis_service import SystemSynthesisService

router = APIRouter(tags=["System Design Synthesis & Scenario Intelligence"])


# -------------------------------------------------------------
# Objectives & Constraints
# -------------------------------------------------------------

@router.post(
    "/systems/{system_id}/design-objectives",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a system design objective with optional constraints",
)
async def create_system_objective(
    system_id: str,
    payload: SystemDesignObjectiveCreate,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    obj = await service.create_objective(
        system_id=system_id,
        user_id=user.id,
        payload=payload,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": SystemDesignObjectiveResponse.model_validate(obj)}


@router.get(
    "/systems/{system_id}/design-objectives",
    response_model=dict,
    summary="List all design objectives for a system",
)
async def list_system_objectives(
    system_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    objectives = await service.get_objectives_for_system(system_id, tenant_id=user.tenant_id)
    return {
        "success": True,
        "data": [SystemDesignObjectiveResponse.model_validate(o) for o in objectives],
    }


@router.get(
    "/design-objectives/{objective_id}",
    response_model=dict,
    summary="Get details of a system design objective",
)
async def get_system_objective(
    objective_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    obj = await service.get_objective(objective_id, tenant_id=user.tenant_id)
    return {"success": True, "data": SystemDesignObjectiveResponse.model_validate(obj)}


# -------------------------------------------------------------
# Scenarios
# -------------------------------------------------------------

@router.post(
    "/systems/{system_id}/scenarios",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create an engineering operating or failure scenario",
)
async def create_scenario(
    system_id: str,
    payload: ScenarioCreate,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    scenario = await service.create_scenario(
        system_id=system_id,
        user_id=user.id,
        payload=payload,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": ScenarioResponse.model_validate(scenario)}


@router.get(
    "/systems/{system_id}/scenarios",
    response_model=dict,
    summary="List all scenarios for a system",
)
async def list_system_scenarios(
    system_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    scenarios = await service.get_scenarios_for_system(system_id, tenant_id=user.tenant_id)
    return {
        "success": True,
        "data": [ScenarioResponse.model_validate(s) for s in scenarios],
    }


@router.get(
    "/scenarios/{scenario_id}",
    response_model=dict,
    summary="Get scenario details",
)
async def get_scenario_detail(
    scenario_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    scen = await service.get_scenario(scenario_id, tenant_id=user.tenant_id)
    return {"success": True, "data": ScenarioResponse.model_validate(scen)}


@router.post(
    "/scenarios/{scenario_id}/execute",
    response_model=dict,
    summary="Execute scenario with precondition validation and immutable snapshotting",
)
async def execute_scenario(
    scenario_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    result = await service.execute_scenario(
        scenario_id=scenario_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": ScenarioResultResponse.model_validate(result)}


@router.post(
    "/scenarios/comparison",
    response_model=dict,
    summary="Compare baseline and alternative scenario results without composite score",
)
async def compare_scenarios(
    payload: ScenarioComparisonRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    delta = await service.compare_scenarios(
        baseline_id=payload.baseline_scenario_id,
        alternative_id=payload.alternative_scenario_id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": delta}


# -------------------------------------------------------------
# Candidates & Comparison
# -------------------------------------------------------------

@router.post(
    "/systems/{system_id}/design/candidates",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Generate system architecture candidates using deterministic strategies",
)
async def generate_system_candidates(
    system_id: str,
    payload: SystemCandidateGenerateRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    candidates = await service.generate_candidates(
        objective_id=payload.objective_id,
        user_id=user.id,
        strategies=payload.strategies,
        tenant_id=user.tenant_id,
    )
    return {
        "success": True,
        "data": [SystemCandidateResponse.model_validate(c) for c in candidates],
    }


@router.get(
    "/systems/{system_id}/design/candidates",
    response_model=dict,
    summary="List all generated candidates for a system",
)
async def list_system_candidates(
    system_id: str,
    objective_id: Optional[str] = None,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    if objective_id:
        candidates = await service.get_candidates_for_objective(objective_id, tenant_id=user.tenant_id)
    else:
        candidates = await service.synthesis_repo.get_candidates_for_system(system_id, tenant_id=user.tenant_id)
    return {
        "success": True,
        "data": [SystemCandidateResponse.model_validate(c) for c in candidates],
    }


@router.post(
    "/systems/{system_id}/design/compare",
    response_model=dict,
    summary="Build multidimensional transparent architecture comparison matrix",
)
async def compare_system_architectures(
    system_id: str,
    payload: SystemArchitectureCompareRequest,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    service = SystemSynthesisService(db)
    matrix = await service.compare_architectures(
        candidate_ids=payload.candidate_ids,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": matrix}


# -------------------------------------------------------------
# System Proposals
# -------------------------------------------------------------

@router.post(
    "/systems/{system_id}/design/proposals",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Create a revision-bound system change proposal",
)
async def create_system_proposal(
    system_id: str,
    payload: SystemProposalCreate,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    proposal_service = SystemProposalService(db)
    proposal = await proposal_service.create_proposal(
        system_id=system_id,
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        base_revision=payload.base_revision,
        operations=payload.operations,
        generation_strategy=payload.generation_strategy,
        rationale=payload.rationale,
        candidate_id=payload.candidate_id,
        objective_id=payload.objective_id,
        scenario_ids=payload.scenario_ids,
        engineering_effects=payload.engineering_effects,
        requirement_effects=payload.requirement_effects,
        verification_effects=payload.verification_effects,
        failure_effects=payload.failure_effects,
        unknowns=payload.unknowns,
        provenance=payload.provenance,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": SystemProposalResponse.model_validate(proposal)}


@router.get(
    "/systems/{system_id}/design/proposals",
    response_model=dict,
    summary="List all proposals for a system",
)
async def list_system_proposals(
    system_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    proposal_service = SystemProposalService(db)
    proposals = await proposal_service.synthesis_repo.get_proposals_for_system(system_id, tenant_id=user.tenant_id)
    return {
        "success": True,
        "data": [SystemProposalResponse.model_validate(p) for p in proposals],
    }


@router.get(
    "/system-proposals/{proposal_id}",
    response_model=dict,
    summary="Get details of a system proposal",
)
async def get_system_proposal(
    proposal_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    proposal_service = SystemProposalService(db)
    proposal = await proposal_service.synthesis_repo.get_proposal(proposal_id, tenant_id=user.tenant_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="System proposal not found")
    return {"success": True, "data": SystemProposalResponse.model_validate(proposal)}


@router.post(
    "/system-proposals/{proposal_id}/approve",
    response_model=dict,
    summary="Explicitly approve a system architecture proposal",
)
async def approve_system_proposal(
    proposal_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    proposal_service = SystemProposalService(db)
    proposal = await proposal_service.approve_proposal(
        proposal_id=proposal_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": SystemProposalResponse.model_validate(proposal)}


@router.post(
    "/system-proposals/{proposal_id}/apply",
    response_model=dict,
    summary="Atomically apply approved proposal with revision bump and stale invalidation",
)
async def apply_system_proposal(
    proposal_id: str,
    user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    proposal_service = SystemProposalService(db)
    res = await proposal_service.apply_proposal(
        proposal_id=proposal_id,
        user_id=user.id,
        tenant_id=user.tenant_id,
    )
    return {"success": True, "data": res}
