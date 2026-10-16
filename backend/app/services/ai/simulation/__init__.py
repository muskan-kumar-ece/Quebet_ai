"""QUEBET AI - Phase 3 Wave 4: SPICE & Simulation Integration.

Provides deterministic model-based circuit simulation, SPICE netlist generation,
model registry management, result parsing, and analytical discrepancy comparison.
"""

from app.services.ai.simulation.simulator_base import (
    SimulatorBase,
    SimulationExecutionResult,
)
from app.services.ai.simulation.ngspice_simulator import NgSpiceSimulator
from app.services.ai.simulation.mock_simulator import MockSimulator
from app.services.ai.simulation.netlist_generator import NetlistGenerator, NetlistValidationResult
from app.services.ai.simulation.model_registry import SpiceModelRegistry
from app.services.ai.simulation.result_parser import SpiceResultParser
from app.services.ai.simulation.interpretation_service import SimulationInterpretationService

__all__ = [
    "SimulatorBase",
    "SimulationExecutionResult",
    "NgSpiceSimulator",
    "MockSimulator",
    "NetlistGenerator",
    "NetlistValidationResult",
    "SpiceModelRegistry",
    "SpiceResultParser",
    "SimulationInterpretationService",
]
