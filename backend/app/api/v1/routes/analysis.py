from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.analysis import (
    CircuitAnalysisResponse,
    ExplainRequest,
    ExplainResponse,
)
from app.models.schemas.common import ApiResponse
from app.services.analysis_service import analysis_service

router = APIRouter(prefix="/circuits", tags=["Circuit Analysis & Intelligence"])


@router.post("/{circuit_id}/analyze", response_model=ApiResponse[CircuitAnalysisResponse])
async def analyze_circuit(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run deterministic engineering analysis on circuit revision.
    Calculates Ohm's law, power dissipation, voltage dividers, RC constants,
    regulator margins, and evaluates rules R001 through R008.
    """
    analysis = await analysis_service.run_analysis(
        db=db,
        circuit_id=circuit_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=analysis)


@router.get("/{circuit_id}/analysis/latest", response_model=ApiResponse[CircuitAnalysisResponse])
async def get_latest_analysis(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the latest verified engineering analysis for this circuit."""
    analysis = await analysis_service.get_latest_analysis(
        db=db,
        circuit_id=circuit_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=analysis)


@router.get("/{circuit_id}/analysis/{analysis_id}", response_model=ApiResponse[CircuitAnalysisResponse])
async def get_analysis_by_id(
    circuit_id: str,
    analysis_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific analysis snapshot by ID."""
    analysis = await analysis_service.get_analysis_by_id(
        db=db,
        circuit_id=circuit_id,
        analysis_id=analysis_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=analysis)


@router.post("/{circuit_id}/explain", response_model=ApiResponse[ExplainResponse])
async def explain_circuit_analysis(
    circuit_id: str,
    explain_in: ExplainRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    AI Engineering Explanation Boundary:
    Synthesizes deterministic findings, explains physical mechanisms and tradeoffs,
    and recommends concrete fixes without recalculating or modifying physical numbers.
    """
    explanation = await analysis_service.explain_analysis(
        db=db,
        circuit_id=circuit_id,
        explain_in=explain_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=explanation)
