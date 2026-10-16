from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.db.simulation import (
    SimulationType,
    SimulationStatus,
    ConvergenceStatus,
    SimulatorType,
    ExecutionMode,
)


class SimulationRunRequest(BaseModel):
    """Request payload to initiate a deterministic circuit simulation."""
    simulation_type: SimulationType = Field(
        default=SimulationType.DC_OPERATING_POINT,
        description="Type of simulation to execute: DC_OPERATING_POINT, DC_SWEEP, AC_SMALL_SIGNAL, TRANSIENT"
    )
    operating_mode: str | None = Field(
        default=None,
        description="Optional operating mode context (e.g. NORMAL, LOW_POWER, FAULT)"
    )
    simulator: SimulatorType = Field(
        default=SimulatorType.NGSPICE,
        description="Target simulation engine: NGSPICE, MOCK_SPICE"
    )
    execution_mode: ExecutionMode | None = Field(
        default=None,
        description="Execution mode: LOCAL_SUBPROCESS, TEST_MOCK. Defaults automatically."
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Simulation-specific parameters (e.g., tstop, tstep, start_freq, stop_freq, points_per_decade)"
    )


class SimulationDiscrepancy(BaseModel):
    """Comparison between deterministic analytical calculation (Wave 3) and SPICE simulation."""
    element_or_node: str
    parameter: str
    analytical_value: float
    simulation_value: float
    unit: str
    relative_delta: float
    flag: str = Field(description="MATCH | ANALYSIS_SIMULATION_DISCREPANCY")
    description: str


class SimulationConstraintEvaluation(BaseModel):
    """Evaluation of simulation results against operating limits or engineering requirements."""
    constraint_id: str
    component_id: str | None = None
    parameter: str
    simulated_value: float
    limit_value: float
    unit: str
    limit_type: str = Field(description="MAX | MIN | TYPICAL")
    status: str = Field(description="SATISFIED | VIOLATED | UNKNOWN")
    margin: float | None = None
    note: str | None = None


class SimulationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    simulation_job_id: str
    circuit_id: str
    circuit_version: int
    tenant_id: str | None = None
    convergence_status: ConvergenceStatus
    node_voltages: dict[str, float] = Field(default_factory=dict)
    branch_currents: dict[str, float] = Field(default_factory=dict)
    waveforms: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    raw_output: str | None = None
    classification: str = "CALCULATED_RESULT"
    verification_status: str = "NOT_VERIFIED"
    discrepancies: list[SimulationDiscrepancy] = Field(default_factory=list)
    constraint_evaluations: list[SimulationConstraintEvaluation] = Field(default_factory=list)
    created_at: datetime


class SimulationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None = None
    project_id: str
    circuit_id: str
    circuit_version: int
    created_by: str
    simulation_type: SimulationType
    status: SimulationStatus
    operating_mode: str | None = None
    simulator: str
    simulator_version: str | None = None
    execution_mode: str
    netlist_digest: str | None = None
    model_digest: str | None = None
    netlist_content: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    error_detail: str | None = None
    execution_time_ms: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    result: SimulationResultResponse | None = None


class SimulationProvenanceResponse(BaseModel):
    simulation_job_id: str
    circuit_id: str
    circuit_version: int
    netlist_digest: str | None = None
    model_digest: str | None = None
    simulator: str
    simulator_version: str | None = None
    execution_mode: str
    classification: str = "CALCULATED_RESULT"
    verification_status: str = "NOT_VERIFIED"
    epistemic_warning: str = (
        "SIMULATION_RESULT != PHYSICAL_VERIFICATION. "
        "A simulation is a model-based numerical calculation and does NOT constitute physical hardware verification."
    )
