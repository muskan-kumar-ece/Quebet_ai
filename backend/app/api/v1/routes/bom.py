"""
BOM & Supply-Chain Intelligence API routes.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.common import ApiResponse
from app.models.schemas.bom import (
    EngineeringBOMCreate,
    EngineeringBOMResponse,
    EngineeringBOMLineResponse,
    ComponentPartCandidateCreate,
    ComponentPartCandidateResponse,
    BOMSubstitutionProposalCreate,
    BOMSubstitutionProposalResponse,
    BOMSnapshotResponse,
)
from app.services.bom_service import bom_service

router = APIRouter(tags=["BOM & Supply-Chain Intelligence"])


@router.post("/boms", response_model=ApiResponse[EngineeringBOMResponse])
async def create_bom(
    request: EngineeringBOMCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate an EngineeringBOM for a given circuit."""
    bom = await bom_service.create_bom(db=db, current_user=current_user, request=request)
    return ApiResponse(success=True, data=EngineeringBOMResponse.model_validate(bom))


@router.get("/boms/{bom_id}", response_model=ApiResponse[EngineeringBOMResponse])
async def get_bom(
    bom_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an EngineeringBOM with lines and part candidates."""
    bom = await bom_service.get_bom(db=db, bom_id=bom_id, current_user=current_user)
    return ApiResponse(success=True, data=EngineeringBOMResponse.model_validate(bom))


@router.get("/circuits/{circuit_id}/bom", response_model=ApiResponse[EngineeringBOMResponse])
async def get_bom_by_circuit(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the latest EngineeringBOM for a circuit."""
    bom = await bom_service.get_bom_by_circuit(db=db, circuit_id=circuit_id, current_user=current_user)
    return ApiResponse(success=True, data=EngineeringBOMResponse.model_validate(bom))


@router.get("/boms/{bom_id}/lines", response_model=ApiResponse[List[EngineeringBOMLineResponse]])
async def list_bom_lines(
    bom_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List all lines in an EngineeringBOM."""
    lines = await bom_service.list_lines(db=db, bom_id=bom_id, current_user=current_user)
    return ApiResponse(success=True, data=[EngineeringBOMLineResponse.model_validate(l) for l in lines])


@router.post("/boms/lines/{line_id}/candidates", response_model=ApiResponse[ComponentPartCandidateResponse])
async def add_candidate(
    line_id: str,
    request: ComponentPartCandidateCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a manufacturer part candidate to a BOM line and evaluate compatibility."""
    candidate = await bom_service.add_candidate(
        db=db,
        line_id=line_id,
        candidate_in=request,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=ComponentPartCandidateResponse.model_validate(candidate))


@router.post("/boms/{bom_id}/evaluate", response_model=ApiResponse[EngineeringBOMResponse])
async def evaluate_bom(
    bom_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-evaluate compatibility and supply sources for all candidates in the BOM."""
    bom = await bom_service.evaluate_bom(db=db, bom_id=bom_id, current_user=current_user)
    return ApiResponse(success=True, data=EngineeringBOMResponse.model_validate(bom))


@router.post("/boms/{bom_id}/substitutions", response_model=ApiResponse[BOMSubstitutionProposalResponse])
async def create_substitution_proposal(
    bom_id: str,
    request: BOMSubstitutionProposalCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a human-reviewable substitution proposal with deterministic diff."""
    if request.bom_id != bom_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mismatched bom_id in path and body",
        )
    proposal = await bom_service.create_substitution_proposal(
        db=db,
        proposal_in=request,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=BOMSubstitutionProposalResponse.model_validate(proposal))


@router.post("/boms/substitutions/{proposal_id}/approve", response_model=ApiResponse[BOMSubstitutionProposalResponse])
async def approve_substitution_proposal(
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve and apply a candidate substitution.
    Enforces human approval boundary (HTTP 403 AI_UNAUTHORIZED_SUBSTITUTION for AI agents).
    """
    proposal = await bom_service.approve_substitution_proposal(
        db=db,
        proposal_id=proposal_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=BOMSubstitutionProposalResponse.model_validate(proposal))


@router.get("/boms/{bom_id}/snapshot", response_model=ApiResponse[BOMSnapshotResponse])
async def get_bom_snapshot(
    bom_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate canonical snapshot and SHA-256 integrity digest for the BOM."""
    snapshot = await bom_service.get_snapshot(db=db, bom_id=bom_id, current_user=current_user)
    return ApiResponse(success=True, data=BOMSnapshotResponse.model_validate(snapshot))
