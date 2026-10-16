from datetime import datetime, timezone
from typing import Any
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AuthenticatedUser
from app.models.db.analysis import CircuitAnalysis
from app.models.db.simulation import (
    ConvergenceStatus,
    ExecutionMode,
    SimulationJob,
    SimulationResultRecord,
    SimulationStatus,
    SimulatorType,
)
from app.models.schemas.simulation import (
    SimulationJobResponse,
    SimulationProvenanceResponse,
    SimulationResultResponse,
    SimulationRunRequest,
)
from app.repositories.circuit_repo import circuit_repo
from app.services.ai.simulation.interpretation_service import SimulationInterpretationService
from app.services.ai.simulation.mock_simulator import MockSimulator
from app.services.ai.simulation.model_registry import SpiceModelRegistry
from app.services.ai.simulation.netlist_generator import NetlistGenerator
from app.services.ai.simulation.ngspice_simulator import NgSpiceSimulator


class SimulationService:
    """
    Orchestration service for SPICE simulation workflows.
    Manages netlist generation, model resolution, simulator dispatch,
    analytical cross-comparison, constraint checks, and database persistence.
    """

    def __init__(self) -> None:
        self.ngspice_sim = NgSpiceSimulator()
        self.mock_sim = MockSimulator()

    async def run_simulation(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
        request: SimulationRunRequest,
    ) -> SimulationJob:
        # 1. Fetch circuit with eager-loaded relations
        circuit = await circuit_repo.get_by_id(
            db=db,
            circuit_id=circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not circuit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit {circuit_id} not found or tenant access denied",
            )

        # 2. Generate and validate SPICE Netlist
        netlist_res = NetlistGenerator.generate(
            circuit=circuit,
            simulation_type=request.simulation_type.value,
            config=request.config,
        )

        if not netlist_res.is_valid:
            error_msg = "; ".join(netlist_res.errors)
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY if "RESOURCE_LIMIT" in error_msg else status.HTTP_400_BAD_REQUEST
            raise HTTPException(
                status_code=status_code,
                detail=f"Netlist validation failed: {error_msg}",
            )

        model_digest = SpiceModelRegistry.compute_model_digest(netlist_res.models_included)

        # 3. Select Simulator backend
        if request.simulator == SimulatorType.NGSPICE and self.ngspice_sim.is_available():
            active_simulator = self.ngspice_sim
            exec_mode = ExecutionMode.LOCAL_SUBPROCESS.value
        else:
            # Fall back safely to deterministic MNA mock simulator
            active_simulator = self.mock_sim
            exec_mode = ExecutionMode.TEST_MOCK.value

        if request.execution_mode:
            exec_mode = request.execution_mode.value

        # 4. Instantiate SimulationJob record
        job = SimulationJob(
            id=str(uuid.uuid4()),
            tenant_id=current_user.tenant_id,
            project_id=circuit.project_id,
            circuit_id=circuit.id,
            circuit_version=circuit.version,
            created_by=current_user.id,
            simulation_type=request.simulation_type.value,
            status=SimulationStatus.RUNNING.value,
            operating_mode=request.operating_mode,
            simulator=active_simulator.simulator_name,
            simulator_version=active_simulator.simulator_version,
            execution_mode=exec_mode,
            netlist_digest=netlist_res.netlist_digest,
            model_digest=model_digest,
            netlist_content=netlist_res.netlist,
            config=request.config,
            started_at=datetime.now(timezone.utc),
        )

        db.add(job)
        await db.flush()

        # 5. Execute Simulation
        exec_config = {
            **request.config,
            "simulation_type": request.simulation_type.value,
        }
        exec_res = active_simulator.execute(
            netlist=netlist_res.netlist,
            config=exec_config,
            timeout_seconds=request.config.get("timeout_seconds", 30),
        )

        job.completed_at = datetime.now(timezone.utc)
        job.execution_time_ms = exec_res.execution_time_ms

        if not exec_res.success:
            job.status = SimulationStatus.FAILED.value
            job.error_detail = exec_res.error_message or "Simulation failed"
        else:
            job.status = SimulationStatus.COMPLETED.value

        # 6. Fetch latest Wave 3 analytical analysis for cross-comparison
        stmt = (
            select(CircuitAnalysis)
            .where(
                CircuitAnalysis.circuit_id == circuit.id,
                CircuitAnalysis.circuit_version == circuit.version,
            )
            .order_by(CircuitAnalysis.created_at.desc())
            .limit(1)
        )
        if current_user.tenant_id:
            stmt = stmt.where(CircuitAnalysis.tenant_id == current_user.tenant_id)
        analysis_res = await db.execute(stmt)
        latest_analysis = analysis_res.scalar_one_or_none()

        discrepancies = SimulationInterpretationService.compare_with_analytical_analysis(
            analysis=latest_analysis,
            node_voltages=exec_res.node_voltages,
            branch_currents=exec_res.branch_currents,
        )

        constraint_evals = SimulationInterpretationService.evaluate_constraints(
            circuit=circuit,
            node_voltages=exec_res.node_voltages,
            branch_currents=exec_res.branch_currents,
        )

        # 7. Persist SimulationResultRecord
        result_record = SimulationResultRecord(
            id=str(uuid.uuid4()),
            simulation_job_id=job.id,
            circuit_id=circuit.id,
            circuit_version=circuit.version,
            tenant_id=current_user.tenant_id,
            convergence_status=exec_res.convergence_status,
            node_voltages=exec_res.node_voltages,
            branch_currents=exec_res.branch_currents,
            waveforms=exec_res.parsed_vectors,
            metrics=exec_res.metrics,
            raw_output=exec_res.raw_stdout or exec_res.raw_stderr,
            classification="CALCULATED_RESULT",
            verification_status="NOT_VERIFIED",
            discrepancies=[d.model_dump() for d in discrepancies],
            constraint_evaluations=[c.model_dump() for c in constraint_evals],
        )

        db.add(result_record)
        await db.commit()

        # Re-query with loaded relationship
        return await self.get_simulation_job(
            db=db,
            simulation_id=job.id,
            current_user=current_user,
        )

    async def get_simulation_job(
        self,
        db: AsyncSession,
        simulation_id: str,
        current_user: AuthenticatedUser,
    ) -> SimulationJob:
        stmt = (
            select(SimulationJob)
            .where(SimulationJob.id == simulation_id)
            .options(selectinload(SimulationJob.result))
        )
        if current_user.tenant_id:
            stmt = stmt.where(SimulationJob.tenant_id == current_user.tenant_id)
        else:
            stmt = stmt.where(SimulationJob.tenant_id.is_(None), SimulationJob.created_by == current_user.id)

        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Simulation job {simulation_id} not found",
            )
        return job

    async def list_simulations(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> list[SimulationJob]:
        circuit = await circuit_repo.get_by_id(
            db=db,
            circuit_id=circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not circuit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit {circuit_id} not found",
            )

        stmt = (
            select(SimulationJob)
            .where(SimulationJob.circuit_id == circuit_id)
            .options(selectinload(SimulationJob.result))
            .order_by(SimulationJob.created_at.desc())
        )
        if current_user.tenant_id:
            stmt = stmt.where(SimulationJob.tenant_id == current_user.tenant_id)
        else:
            stmt = stmt.where(SimulationJob.tenant_id.is_(None), SimulationJob.created_by == current_user.id)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def cancel_simulation(
        self,
        db: AsyncSession,
        simulation_id: str,
        current_user: AuthenticatedUser,
    ) -> SimulationJob:
        job = await self.get_simulation_job(db, simulation_id, current_user)
        if job.status in (SimulationStatus.RUNNING.value, SimulationStatus.QUEUED.value):
            job.status = SimulationStatus.CANCELLED.value
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(job)
        return job

    async def get_provenance(
        self,
        db: AsyncSession,
        simulation_id: str,
        current_user: AuthenticatedUser,
    ) -> SimulationProvenanceResponse:
        job = await self.get_simulation_job(db, simulation_id, current_user)
        return SimulationProvenanceResponse(
            simulation_job_id=job.id,
            circuit_id=job.circuit_id,
            circuit_version=job.circuit_version,
            netlist_digest=job.netlist_digest,
            model_digest=job.model_digest,
            simulator=job.simulator,
            simulator_version=job.simulator_version,
            execution_mode=job.execution_mode,
            classification="CALCULATED_RESULT",
            verification_status="NOT_VERIFIED",
        )


simulation_service = SimulationService()
