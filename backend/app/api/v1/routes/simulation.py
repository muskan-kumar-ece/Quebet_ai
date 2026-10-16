from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.common import ApiResponse
from app.models.schemas.simulation import (
    SimulationJobResponse,
    SimulationProvenanceResponse,
    SimulationResultResponse,
    SimulationRunRequest,
)
from app.services.simulation_service import simulation_service

router = APIRouter(prefix="/circuits", tags=["Circuit Simulation & SPICE"])


@router.post("/{circuit_id}/simulations", response_model=ApiResponse[SimulationJobResponse])
async def run_simulation(
    circuit_id: str,
    request: SimulationRunRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run deterministic SPICE simulation (DC operating point, DC sweep, AC, transient).
    Simulation results are strictly CALCULATED_RESULT and do not constitute physical verification.
    """
    job = await simulation_service.run_simulation(
        db=db,
        circuit_id=circuit_id,
        current_user=current_user,
        request=request,
    )
    return ApiResponse(success=True, data=SimulationJobResponse.model_validate(job))


@router.get("/{circuit_id}/simulations", response_model=ApiResponse[list[SimulationJobResponse]])
async def list_simulations(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List simulation jobs executed for this circuit."""
    jobs = await simulation_service.list_simulations(
        db=db,
        circuit_id=circuit_id,
        current_user=current_user,
    )
    return ApiResponse(
        success=True,
        data=[SimulationJobResponse.model_validate(j) for j in jobs],
    )


@router.get("/{circuit_id}/simulations/{simulation_id}", response_model=ApiResponse[SimulationJobResponse])
async def get_simulation(
    circuit_id: str,
    simulation_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Get details and results of a specific simulation job."""
    job = await simulation_service.get_simulation_job(
        db=db,
        simulation_id=simulation_id,
        current_user=current_user,
    )
    if job.circuit_id != circuit_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation job does not belong to circuit")
    return ApiResponse(success=True, data=SimulationJobResponse.model_validate(job))


@router.post("/{circuit_id}/simulations/{simulation_id}/cancel", response_model=ApiResponse[SimulationJobResponse])
async def cancel_simulation(
    circuit_id: str,
    simulation_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an ongoing simulation job."""
    job = await simulation_service.get_simulation_job(
        db=db,
        simulation_id=simulation_id,
        current_user=current_user,
    )
    if job.circuit_id != circuit_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation job does not belong to circuit")
    job = await simulation_service.cancel_simulation(
        db=db,
        simulation_id=simulation_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=SimulationJobResponse.model_validate(job))


@router.get("/{circuit_id}/simulations/{simulation_id}/results", response_model=ApiResponse[SimulationResultResponse])
async def get_simulation_results(
    circuit_id: str,
    simulation_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Get calculated outputs, waveforms, and discrepancy findings for a completed simulation."""
    job = await simulation_service.get_simulation_job(
        db=db,
        simulation_id=simulation_id,
        current_user=current_user,
    )
    if job.circuit_id != circuit_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation job does not belong to circuit")
    if not job.result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation results not available yet")
    return ApiResponse(success=True, data=SimulationResultResponse.model_validate(job.result))


@router.get("/{circuit_id}/simulations/{simulation_id}/provenance", response_model=ApiResponse[SimulationProvenanceResponse])
async def get_simulation_provenance(
    circuit_id: str,
    simulation_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Get provenance metadata, netlist digest, and model digest for a simulation job."""
    job = await simulation_service.get_simulation_job(
        db=db,
        simulation_id=simulation_id,
        current_user=current_user,
    )
    if job.circuit_id != circuit_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation job does not belong to circuit")
    prov = await simulation_service.get_provenance(
        db=db,
        simulation_id=simulation_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=prov)
