"""
Manufacturing / DFM & Assembly Intelligence API routes for Phase 3 Wave 7.
"""
from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.common import ApiResponse
from app.models.schemas.dfm import (
    DFMSnapshotResponse,
    ManufacturingAnalysisCreate,
    ManufacturingAnalysisResponse,
    ManufacturingProposalCreate,
    ManufacturingProposalResponse,
    ManufacturingRuleSetCreate,
    ManufacturingRuleSetResponse,
)
from app.services.dfm_service import dfm_service

router = APIRouter(tags=["Manufacturing / DFM & Assembly Intelligence"])


@router.post("/dfm/rulesets", response_model=ApiResponse[ManufacturingRuleSetResponse])
async def create_ruleset(
    request: ManufacturingRuleSetCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new manufacturing ruleset."""
    ruleset = await dfm_service.create_ruleset(db=db, current_user=current_user, request=request)
    return ApiResponse(success=True, data=ManufacturingRuleSetResponse.model_validate(ruleset))


@router.get("/dfm/rulesets", response_model=ApiResponse[List[ManufacturingRuleSetResponse]])
async def list_rulesets(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List available manufacturing rulesets."""
    rulesets = await dfm_service.list_rulesets(db=db, current_user=current_user)
    return ApiResponse(
        success=True,
        data=[ManufacturingRuleSetResponse.model_validate(rs) for rs in rulesets],
    )


@router.get("/dfm/rulesets/{ruleset_id}", response_model=ApiResponse[ManufacturingRuleSetResponse])
async def get_ruleset(
    ruleset_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific manufacturing ruleset."""
    ruleset = await dfm_service.get_ruleset(db=db, ruleset_id=ruleset_id, current_user=current_user)
    return ApiResponse(success=True, data=ManufacturingRuleSetResponse.model_validate(ruleset))


@router.post("/dfm/analyses", response_model=ApiResponse[ManufacturingAnalysisResponse])
async def run_dfm_analysis(
    request: ManufacturingAnalysisCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Run deterministic DFM & DFA rules against an engineering board."""
    record = await dfm_service.run_analysis(db=db, current_user=current_user, request=request)
    return ApiResponse(success=True, data=ManufacturingAnalysisResponse.model_validate(record))


@router.get("/dfm/analyses/{analysis_id}", response_model=ApiResponse[ManufacturingAnalysisResponse])
async def get_dfm_analysis(
    analysis_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an existing DFM analysis record."""
    record = await dfm_service.get_analysis(db=db, analysis_id=analysis_id, current_user=current_user)
    return ApiResponse(success=True, data=ManufacturingAnalysisResponse.model_validate(record))


@router.get("/dfm/analyses/{analysis_id}/proposals", response_model=ApiResponse[List[ManufacturingProposalResponse]])
async def list_proposals(
    analysis_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List resolution proposals for a DFM analysis."""
    proposals = await dfm_service.list_proposals(db=db, analysis_id=analysis_id, current_user=current_user)
    return ApiResponse(
        success=True,
        data=[ManufacturingProposalResponse.model_validate(p) for p in proposals],
    )


@router.post("/dfm/proposals/{proposal_id}/approve", response_model=ApiResponse[ManufacturingProposalResponse])
async def approve_proposal(
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Human engineer approval for a DFM proposal (AI actors rejected)."""
    proposal = await dfm_service.approve_proposal(db=db, proposal_id=proposal_id, current_user=current_user)
    return ApiResponse(success=True, data=ManufacturingProposalResponse.model_validate(proposal))


@router.post("/dfm/proposals/{proposal_id}/apply", response_model=ApiResponse[ManufacturingProposalResponse])
async def apply_proposal(
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply approved DFM proposal mutations to the board (human gate and stale revision checks enforced)."""
    proposal = await dfm_service.apply_proposal(db=db, proposal_id=proposal_id, current_user=current_user)
    return ApiResponse(success=True, data=ManufacturingProposalResponse.model_validate(proposal))


@router.get("/dfm/analyses/{analysis_id}/snapshot", response_model=ApiResponse[DFMSnapshotResponse])
async def get_dfm_snapshot(
    analysis_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate canonical DFM snapshot with SHA-256 provenance digest."""
    snapshot = await dfm_service.get_snapshot(db=db, analysis_id=analysis_id, current_user=current_user)
    return ApiResponse(success=True, data=snapshot)
