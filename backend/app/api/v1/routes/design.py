from typing import Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.common import ApiResponse
from app.models.schemas.design import (
    DesignComparisonResponse,
    EngineeringConstraint,
    EngineeringDesignAlternative,
    EngineeringDesignObjectiveCreate,
    EngineeringDesignObjectiveResponse,
)
from app.models.schemas.proposal import ProposalResponse
from app.services.ai.design.design_intelligence_service import design_intelligence_service

router = APIRouter(prefix="/circuits", tags=["Engineering Design Intelligence"])


class GenerateAlternativesRequest(BaseModel):
    objective_id: str | None = None
    objective_type: str = "FIX_RULE_VIOLATION"
    target: dict[str, Any] = Field(default_factory=dict)
    constraints: list[EngineeringConstraint] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)


class CompareAlternativesRequest(BaseModel):
    alternatives: list[dict[str, Any]] = Field(..., min_length=1)


class ProposeAlternativeRequest(BaseModel):
    alternative: dict[str, Any] = Field(...)


@router.post("/{circuit_id}/design/objectives", response_model=ApiResponse[EngineeringDesignObjectiveResponse])
async def create_design_objective(
    circuit_id: str,
    objective_in: EngineeringDesignObjectiveCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Establish a normalized engineering design objective with explicit constraints.
    Does not mutate circuit state.
    """
    objective = await design_intelligence_service.create_objective(
        db=db,
        circuit_id=circuit_id,
        objective_in=objective_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=objective)


@router.post("/{circuit_id}/design/alternatives", response_model=ApiResponse[list[EngineeringDesignAlternative]])
async def generate_design_alternatives(
    circuit_id: str,
    req: GenerateAlternativesRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate technically grounded candidate design alternatives.
    Simulates candidates in non-persistent in-memory sandbox and re-analyzes physics deterministically.
    """
    alternatives = await design_intelligence_service.generate_alternatives_for_circuit(
        db=db,
        circuit_id=circuit_id,
        objective_id=req.objective_id,
        objective_type=req.objective_type,
        target=req.target,
        constraints=[c.model_dump() for c in req.constraints],
        current_user=current_user,
        affected_components=req.affected_components,
    )
    return ApiResponse(success=True, data=alternatives)


@router.post("/{circuit_id}/design/compare", response_model=ApiResponse[DesignComparisonResponse])
async def compare_design_alternatives(
    circuit_id: str,
    req: CompareAlternativesRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deterministically compare candidate alternatives against current baseline circuit metrics.
    Compares critical findings, power dissipation, margins, component count, and constraint compliance.
    """
    comparison = await design_intelligence_service.compare_design_alternatives(
        db=db,
        circuit_id=circuit_id,
        alternatives=req.alternatives,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=comparison)


@router.post("/{circuit_id}/design/propose", response_model=ApiResponse[ProposalResponse])
async def create_proposal_from_alternative(
    circuit_id: str,
    req: ProposeAlternativeRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Promote a verified design alternative into a staged EngineeringProposal.
    Tied to the current circuit revision for stale proposal protection.
    Requires explicit human approval before atomic application.
    """
    proposal = await design_intelligence_service.create_proposal_from_alternative(
        db=db,
        circuit_id=circuit_id,
        alternative_data=req.alternative,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=proposal)
