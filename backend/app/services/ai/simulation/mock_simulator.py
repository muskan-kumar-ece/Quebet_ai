import re
import time
from typing import Any
import numpy as np
from app.models.db.simulation import ConvergenceStatus, SimulatorType
from app.services.ai.simulation.simulator_base import (
    SimulationExecutionResult,
    SimulatorBase,
)


class MockSimulator(SimulatorBase):
    """
    Deterministic circuit simulator utilizing Modified Nodal Analysis (MNA).
    Used in automated test environments or offline verification when ngspice binary
    is not installed on the system.
    Strictly flags execution mode as TEST_MOCK.
    """

    @property
    def simulator_name(self) -> str:
        return SimulatorType.MOCK_SPICE.value

    @property
    def simulator_version(self) -> str:
        return "1.0-mock"

    def is_available(self) -> bool:
        return True

    @staticmethod
    def parse_spice_value(val_str: str) -> float:
        """Parses SPICE numerical formats with metric suffixes (e.g., 10k, 1u, 100m, 1meg)."""
        clean = val_str.strip().lower()
        # Remove trailing unit characters like 'v', 'a', 'ohm', 'f', 'h'
        clean = re.sub(r"(v|a|ohm|f|h|s)$", "", clean)
        multipliers = {
            "t": 1e12,
            "g": 1e9,
            "meg": 1e6,
            "k": 1e3,
            "m": 1e-3,
            "u": 1e-6,
            "n": 1e-9,
            "p": 1e-12,
            "f": 1e-15,
        }
        for suffix, mult in multipliers.items():
            if clean.endswith(suffix):
                try:
                    num_part = clean[:-len(suffix)]
                    return float(num_part) * mult
                except ValueError:
                    pass
        try:
            return float(clean)
        except ValueError:
            return 0.0

    def validate_netlist(self, netlist: str) -> tuple[bool, str | None]:
        if not netlist or not netlist.strip():
            return False, "Netlist cannot be empty"

        lines = [line.strip() for line in netlist.strip().splitlines() if line.strip()]
        if len(lines) < 2:
            return False, "Netlist must contain at least a title and components"

        has_end = any(line.lower().startswith(".end") for line in lines)
        if not has_end:
            return False, "Netlist must terminate with a .end directive"

        return True, None

    def execute(
        self,
        netlist: str,
        config: dict[str, Any] | None = None,
        timeout_seconds: int = 30,
    ) -> SimulationExecutionResult:
        start_time = time.perf_counter()
        config = config or {}

        # Allow forced test failure states
        if config.get("force_convergence_status"):
            status = config["force_convergence_status"]
            return SimulationExecutionResult(
                success=(status == ConvergenceStatus.CONVERGED.value),
                convergence_status=status,
                raw_stdout="Forced convergence state",
                execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                error_message=config.get("force_error_message", "Simulated failure"),
            )

        is_valid, err = self.validate_netlist(netlist)
        if not is_valid:
            return SimulationExecutionResult(
                success=False,
                convergence_status=ConvergenceStatus.NOT_RUN.value,
                error_message=err,
                execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        # Parse netlist lines
        resistors: list[tuple[str, str, str, float]] = []  # name, n1, n2, R
        capacitors: list[tuple[str, str, str, float]] = []  # name, n1, n2, C
        inductors: list[tuple[str, str, str, float]] = []  # name, n1, n2, L
        v_sources: list[tuple[str, str, str, float]] = []  # name, n+, n-, V
        i_sources: list[tuple[str, str, str, float]] = []  # name, n+, n-, I

        all_nodes: set[str] = set()

        for line in netlist.splitlines():
            line = line.strip()
            if not line or line.startswith("*") or line.startswith("."):
                continue

            tokens = line.split()
            if len(tokens) < 4:
                continue

            elem = tokens[0].upper()
            n1 = tokens[1]
            n2 = tokens[2]
            all_nodes.add(n1)
            all_nodes.add(n2)

            # Determine value token (may skip DC/AC tags)
            val_token = tokens[3]
            if val_token.upper() in ("DC", "AC") and len(tokens) > 4:
                val_token = tokens[4]

            val = self.parse_spice_value(val_token)

            if elem.startswith("R"):
                resistors.append((elem, n1, n2, max(val, 1e-9)))
            elif elem.startswith("C"):
                capacitors.append((elem, n1, n2, max(val, 1e-15)))
            elif elem.startswith("L"):
                inductors.append((elem, n1, n2, max(val, 1e-12)))
            elif elem.startswith("V"):
                v_sources.append((elem, n1, n2, val))
            elif elem.startswith("I"):
                i_sources.append((elem, n1, n2, val))

        # Check for reference node "0" (or GND)
        ground_node = None
        for n in all_nodes:
            if n in ("0", "GND", "0V", "GROUND"):
                ground_node = n
                break

        if ground_node is None:
            return SimulationExecutionResult(
                success=False,
                convergence_status=ConvergenceStatus.SINGULAR_MATRIX.value,
                error_message="Simulation failed: Circuit has no ground reference node (node 0 / GND)",
                execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        # Map non-ground nodes to matrix indices 0..(N-1)
        non_ground_nodes = sorted([n for n in all_nodes if n != ground_node])
        num_nodes = len(non_ground_nodes)
        node_to_idx = {n: idx for idx, n in enumerate(non_ground_nodes)}

        num_v = len(v_sources)
        total_dim = num_nodes + num_v

        if total_dim == 0:
            return SimulationExecutionResult(
                success=True,
                convergence_status=ConvergenceStatus.CONVERGED.value,
                execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        A = np.zeros((total_dim, total_dim), dtype=float)
        z = np.zeros(total_dim, dtype=float)

        # Fill Conductance matrix G
        for _, n1, n2, r_val in resistors:
            g = 1.0 / r_val
            idx1 = node_to_idx.get(n1)
            idx2 = node_to_idx.get(n2)

            if idx1 is not None:
                A[idx1, idx1] += g
            if idx2 is not None:
                A[idx2, idx2] += g
            if idx1 is not None and idx2 is not None:
                A[idx1, idx2] -= g
                A[idx2, idx1] -= g

        # Fill Voltage Sources B and C, and RHS
        for v_idx, (v_name, np_node, nn_node, v_val) in enumerate(v_sources):
            row = num_nodes + v_idx
            idx_p = node_to_idx.get(np_node)
            idx_n = node_to_idx.get(nn_node)

            if idx_p is not None:
                A[idx_p, row] += 1.0
                A[row, idx_p] += 1.0
            if idx_n is not None:
                A[idx_n, row] -= 1.0
                A[row, idx_n] -= 1.0

            z[row] = v_val

        # Fill Current Sources in RHS
        for _, np_node, nn_node, i_val in i_sources:
            idx_p = node_to_idx.get(np_node)
            idx_n = node_to_idx.get(nn_node)
            if idx_p is not None:
                z[idx_p] -= i_val  # current leaving positive node
            if idx_n is not None:
                z[idx_n] += i_val  # current entering negative node

        # Solve linear system A * x = z
        try:
            cond = np.linalg.cond(A)
            if np.isinf(cond) or cond > 1e15:
                return SimulationExecutionResult(
                    success=False,
                    convergence_status=ConvergenceStatus.SINGULAR_MATRIX.value,
                    error_message="Matrix is singular or ill-conditioned (floating nodes or ideal loops)",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                )
            x = np.linalg.solve(A, z)
        except np.linalg.LinAlgError as e:
            return SimulationExecutionResult(
                success=False,
                convergence_status=ConvergenceStatus.SINGULAR_MATRIX.value,
                error_message=f"Singular matrix solver error: {str(e)}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        # Extract node voltages
        node_voltages: dict[str, float] = {ground_node: 0.0, "0": 0.0}
        for n, idx in node_to_idx.items():
            node_voltages[n] = float(x[idx])

        # Extract branch currents
        branch_currents: dict[str, float] = {}
        for v_idx, (v_name, _, _, _) in enumerate(v_sources):
            branch_currents[v_name.lower()] = float(x[num_nodes + v_idx])

        # Compute resistor currents and element powers
        total_power_w = 0.0
        for r_name, n1, n2, r_val in resistors:
            v1 = node_voltages.get(n1, 0.0)
            v2 = node_voltages.get(n2, 0.0)
            v_drop = v1 - v2
            i_r = v_drop / r_val
            branch_currents[r_name.lower()] = float(i_r)
            total_power_w += float(abs(v_drop * i_r))

        metrics: dict[str, Any] = {
            "max_node_voltage_v": max(node_voltages.values()) if node_voltages else 0.0,
            "min_node_voltage_v": min(node_voltages.values()) if node_voltages else 0.0,
            "total_power_dissipation_w": total_power_w,
            "matrix_dimension": total_dim,
        }

        # Handle transient or AC vector simulation requests
        vectors: dict[str, list[float]] = {}
        sim_type = config.get("simulation_type", "DC_OPERATING_POINT")
        if sim_type == "TRANSIENT":
            tstop = config.get("tstop", 0.01)
            tstep = config.get("tstep", tstop / 50.0)
            time_pts = list(np.arange(0.0, tstop + tstep, tstep))
            vectors["time"] = [float(t) for t in time_pts]
            for n, v in node_voltages.items():
                if n not in ("0", ground_node):
                    vectors[f"v({n})"] = [float(v) for _ in time_pts]
        elif sim_type == "AC_SMALL_SIGNAL":
            fstart = config.get("start_freq", 10.0)
            fstop = config.get("stop_freq", 100000.0)
            freq_pts = list(np.logspace(np.log10(fstart), np.log10(fstop), 20))
            vectors["frequency"] = [float(f) for f in freq_pts]
            for n, v in node_voltages.items():
                if n not in ("0", ground_node):
                    vectors[f"v({n})"] = [float(v) for _ in freq_pts]

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        raw_out = (
            f"MOCK_SPICE 1.0-mock run completed in {elapsed_ms:.2f}ms\n"
            f"Convergence: CONVERGED\n"
            f"Nodes solved: {num_nodes}, Sources: {num_v}\n"
        )

        return SimulationExecutionResult(
            success=True,
            convergence_status=ConvergenceStatus.CONVERGED.value,
            raw_stdout=raw_out,
            node_voltages=node_voltages,
            branch_currents=branch_currents,
            parsed_vectors=vectors,
            metrics=metrics,
            execution_time_ms=elapsed_ms,
        )
