from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from app.models.db.simulation import ConvergenceStatus

# Deterministic Simulation Resource Limits
MAX_NETLIST_CHARS: int = 100_000  # 100 KB
MAX_ELEMENT_COUNT: int = 500
MAX_NODE_COUNT: int = 500
MAX_OUTPUT_BYTES: int = 5_000_000  # 5 MB
DEFAULT_TIMEOUT_SECONDS: int = 30
MAX_TIMEOUT_SECONDS: int = 60


@dataclass
class SimulationExecutionResult:
    """Execution output from a circuit simulator."""
    success: bool
    convergence_status: str = ConvergenceStatus.CONVERGED.value
    raw_stdout: str = ""
    raw_stderr: str = ""
    parsed_vectors: dict[str, list[float]] = field(default_factory=dict)
    node_voltages: dict[str, float] = field(default_factory=dict)
    branch_currents: dict[str, float] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    error_message: str | None = None


class SimulatorBase(ABC):
    """Abstract base class for all circuit simulation backends."""

    @property
    @abstractmethod
    def simulator_name(self) -> str:
        """Name of the simulator (e.g., NGSPICE, MOCK_SPICE)."""
        pass

    @property
    @abstractmethod
    def simulator_version(self) -> str:
        """Version string of the simulator backend."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the simulator executable and runtime are available."""
        pass

    @abstractmethod
    def validate_netlist(self, netlist: str) -> tuple[bool, str | None]:
        """Validates that the netlist adheres to the simulator's syntax and safety invariants."""
        pass

    @abstractmethod
    def execute(
        self,
        netlist: str,
        config: dict[str, Any] | None = None,
        timeout_seconds: int = 30,
    ) -> SimulationExecutionResult:
        """Executes a simulation run deterministically and safely."""
        pass
