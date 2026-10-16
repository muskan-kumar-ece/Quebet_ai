from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import (
    AuthenticatedUser,
    require_authenticated_user,
    require_human_engineer_role,
)
from app.models.schemas.common import ApiResponse
from app.models.schemas.proposal import ProposalResponse
from app.services.proposal_service import proposal_service

router = APIRouter(prefix="/proposals", tags=["Engineering Proposals"])


@router.get("/{proposal_id}", response_model=ApiResponse[ProposalResponse])
async def get_proposal(
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an engineering proposal by ID."""
    proposal = await proposal_service.get_proposal(
        db=db,
        proposal_id=proposal_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=proposal)


@router.post("/{proposal_id}/validate", response_model=ApiResponse[ProposalResponse])
async def validate_proposal(
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run deterministic structural validation on the proposal operations.
    Transitions proposal status to VALIDATED or REJECTED.
    """
    validated = await proposal_service.validate_proposal(
        db=db,
        proposal_id=proposal_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=validated)


@router.post("/{proposal_id}/approve", response_model=ApiResponse[ProposalResponse])
async def approve_proposal(
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_human_engineer_role),
    db: AsyncSession = Depends(get_db),
):
    """
    Explicit user approval of an engineering proposal.
    Transitions proposal status to APPROVED.
    Requires verified human engineering role (SEC-03).
    """
    approved = await proposal_service.approve_proposal(
        db=db,
        proposal_id=proposal_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=approved)


@router.post("/{proposal_id}/apply", response_model=ApiResponse[ProposalResponse])
async def apply_proposal(
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_human_engineer_role),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply an APPROVED proposal to the circuit's authoritative engineering models.
    Increments circuit revision version and commits mutations atomically.
    Requires verified human engineering role (SEC-03).
    """
    applied = await proposal_service.apply_proposal(
        db=db,
        proposal_id=proposal_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=applied)

