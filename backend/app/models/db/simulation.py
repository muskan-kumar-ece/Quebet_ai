from datetime import datetime
from enum import Enum
from typing import Any
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.db.base import Base, TimestampMixin, UUIDMixin


class SimulationType(str, Enum):
    DC_OPERATING_POINT = "DC_OPERATING_POINT"
    DC_SWEEP = "DC_SWEEP"
    AC_SMALL_SIGNAL = "AC_SMALL_SIGNAL"
    TRANSIENT = "TRANSIENT"


class SimulationStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    INVALID = "INVALID"
    STALE = "STALE"


class ConvergenceStatus(str, Enum):
    CONVERGED = "CONVERGED"
    NON_CONVERGENT = "NON_CONVERGENT"
    SINGULAR_MATRIX = "SINGULAR_MATRIX"
    TIMESTEP_TOO_SMALL = "TIMESTEP_TOO_SMALL"
    MAX_ITERATIONS_EXCEEDED = "MAX_ITERATIONS_EXCEEDED"
    NOT_RUN = "NOT_RUN"


class SimulatorType(str, Enum):
    NGSPICE = "NGSPICE"
    MOCK_SPICE = "MOCK_SPICE"
    XSPICE = "XSPICE"


class ExecutionMode(str, Enum):
    LOCAL_SUBPROCESS = "LOCAL_SUBPROCESS"
    REAL_SIMULATOR = "REAL_SIMULATOR"
    TEST_MOCK = "TEST_MOCK"


class SimulationJob(Base, UUIDMixin, TimestampMixin):
    """
    Simulation job managing the end-to-end execution of a deterministic SPICE simulation
    for a specific circuit revision.
    """
    __tablename__ = "simulation_jobs"

    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)

    simulation_type: Mapped[str] = mapped_column(
        String(32),
        default=SimulationType.DC_OPERATING_POINT.value,
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=SimulationStatus.CREATED.value,
        index=True,
        nullable=False,
    )
    operating_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)

    simulator: Mapped[str] = mapped_column(String(64), default=SimulatorType.NGSPICE.value, nullable=False)
    simulator_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_mode: Mapped[str] = mapped_column(
        String(32),
        default=ExecutionMode.LOCAL_SUBPROCESS.value,
        nullable=False,
    )

    netlist_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    netlist_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    circuit = relationship("Circuit", back_populates="simulations")
    result = relationship(
        "SimulationResultRecord",
        back_populates="simulation_job",
        uselist=False,
        cascade="all, delete-orphan",
    )


class SimulationResultRecord(Base, UUIDMixin, TimestampMixin):
    """
    Structured outcome of a SPICE simulation run.
    Explicit epistemic invariant: simulation results are CALCULATED_RESULT and NOT_VERIFIED.
    """
    __tablename__ = "simulation_results"

    simulation_job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("simulation_jobs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    circuit_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("circuits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    circuit_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)

    convergence_status: Mapped[str] = mapped_column(
        String(32),
        default=ConvergenceStatus.CONVERGED.value,
        nullable=False,
    )

    node_voltages: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    branch_currents: Mapped[dict[str, float]] = mapped_column(JSON, default=dict, nullable=False)
    waveforms: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Epistemic Invariants
    classification: Mapped[str] = mapped_column(String(32), default="CALCULATED_RESULT", nullable=False)
    verification_status: Mapped[str] = mapped_column(String(32), default="NOT_VERIFIED", nullable=False)

    # Wave 3 cross-comparison & requirements
    discrepancies: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    constraint_evaluations: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)

    # Relationships
    simulation_job = relationship("SimulationJob", back_populates="result")
    circuit = relationship("Circuit", back_populates="simulation_results")
