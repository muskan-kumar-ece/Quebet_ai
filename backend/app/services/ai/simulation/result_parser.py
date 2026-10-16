import re
from typing import Any
from app.models.db.simulation import ConvergenceStatus


class SpiceResultParser:
    """
    Deterministic parser for SPICE stdout, stderr, and raw file outputs.
    Extracts node voltages, branch currents, vector traces, and convergence statuses.
    """

    @staticmethod
    def detect_convergence(output: str) -> str:
        """Determines the convergence status from SPICE console logs."""
        output_lower = output.lower()

        if "singular matrix" in output_lower:
            return ConvergenceStatus.SINGULAR_MATRIX.value
        if "timestep too small" in output_lower:
            return ConvergenceStatus.TIMESTEP_TOO_SMALL.value
        if "iteration limit reached" in output_lower or "too many iterations" in output_lower:
            return ConvergenceStatus.MAX_ITERATIONS_EXCEEDED.value
        if "no convergence" in output_lower or "simulation failed" in output_lower:
            return ConvergenceStatus.NON_CONVERGENT.value
        if "fatal error" in output_lower or "error:" in output_lower:
            return ConvergenceStatus.NON_CONVERGENT.value

        return ConvergenceStatus.CONVERGED.value

    @staticmethod
    def parse_dc_operating_point(output: str) -> tuple[dict[str, float], dict[str, float]]:
        """
        Parses node voltages and branch currents from DC operating point printout.
        Handles lines like:
          v(n1) = 5.000000e+00
          v1#branch = -2.500000e-03
          i(v1) = 2.500000e-03
          node1 : 5.000000e+00
        """
        node_voltages: dict[str, float] = {}
        branch_currents: dict[str, float] = {}

        # Pattern 1: v(node) = value or i(branch) = value
        pattern1 = re.compile(
            r"(?:v\((?P<vnode>[a-zA-Z0-9_\-\.]+)\)|i\((?P<ibranch>[a-zA-Z0-9_\-\.]+)\)|(?P<bname>[a-zA-Z0-9_\-\.]+)#branch)\s*[:=]\s*(?P<val>[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)",
            re.IGNORECASE,
        )

        for match in pattern1.finditer(output):
            val = float(match.group("val"))
            if match.group("vnode"):
                node = match.group("vnode").strip()
                node_voltages[node] = val
            elif match.group("ibranch"):
                branch = match.group("ibranch").strip()
                branch_currents[branch] = val
            elif match.group("bname"):
                branch = match.group("bname").strip()
                branch_currents[branch] = val

        # Pattern 2: Tabular Node Voltage pairs commonly found in SPICE OP tables
        # Example: Node Voltage Node Voltage
        #          1 5.000000e+00 2 2.500000e+00
        table_pattern = re.compile(
            r"^\s*([a-zA-Z0-9_\-\.]+)\s+([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*$",
            re.MULTILINE,
        )
        for match in table_pattern.finditer(output):
            key = match.group(1).strip()
            val = float(match.group(2))
            if key.lower().startswith("v(") and key.endswith(")"):
                node_voltages[key[2:-1]] = val
            elif key.lower().startswith("i(") and key.endswith(")"):
                branch_currents[key[2:-1]] = val
            elif key.lower().endswith("#branch"):
                branch_currents[key[:-7]] = val
            elif key not in node_voltages and not key.isdigit():
                # Potential node name
                node_voltages[key] = val

        return node_voltages, branch_currents

    @staticmethod
    def parse_transient_or_ac(output: str) -> dict[str, list[float]]:
        """
        Parses time or frequency vectors along with node responses from tabular text output.
        """
        vectors: dict[str, list[float]] = {}
        lines = [line.strip() for line in output.splitlines() if line.strip()]

        header_found = False
        headers: list[str] = []

        for line in lines:
            if not header_found:
                if line.lower().startswith("index") or line.lower().startswith("time") or line.lower().startswith("freq"):
                    headers = [h.strip() for h in re.split(r"\s+", line) if h.strip()]
                    for h in headers:
                        vectors[h] = []
                    header_found = True
                continue

            # Data lines
            parts = re.split(r"\s+", line)
            if len(parts) == len(headers):
                try:
                    for idx, h in enumerate(headers):
                        vectors[h].append(float(parts[idx]))
                except ValueError:
                    continue

        return vectors

    @staticmethod
    def compute_summary_metrics(
        node_voltages: dict[str, float],
        branch_currents: dict[str, float],
    ) -> dict[str, Any]:
        """Calculates deterministic derived metrics from SPICE operating point."""
        metrics: dict[str, Any] = {}

        if node_voltages:
            voltages = list(node_voltages.values())
            metrics["max_node_voltage_v"] = max(voltages)
            metrics["min_node_voltage_v"] = min(voltages)

        # Estimate source power dissipation: sum(|V * I|) for detected branch currents
        total_power_w = 0.0
        for branch, current in branch_currents.items():
            # If current is through a voltage source (e.g., v1), branch power is |V_src * I|
            v_src_val = node_voltages.get(branch, None)
            if v_src_val is not None:
                power = abs(v_src_val * current)
                total_power_w += power

        metrics["total_power_dissipation_w"] = total_power_w
        return metrics
