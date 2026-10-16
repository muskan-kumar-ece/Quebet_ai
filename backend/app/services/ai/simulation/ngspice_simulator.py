import os
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any
from app.models.db.simulation import ConvergenceStatus, SimulatorType
from app.services.ai.simulation.result_parser import SpiceResultParser
from app.services.ai.simulation.simulator_base import (
    MAX_OUTPUT_BYTES,
    SimulationExecutionResult,
    SimulatorBase,
)


class NgSpiceSimulator(SimulatorBase):
    """
    Subprocess-based integration for the ngspice circuit simulator.
    Strictly isolated with no shell execution (shell=False) and sandboxed files.
    """

    def __init__(self, executable_path: str | None = None) -> None:
        self._executable = executable_path or shutil.which("ngspice") or shutil.which("ngspice.exe")
        self._cached_version: str | None = None

    @property
    def simulator_name(self) -> str:
        return SimulatorType.NGSPICE.value

    @property
    def simulator_version(self) -> str:
        if self._cached_version:
            return self._cached_version

        if not self.is_available():
            return "ngspice-unavailable"

        try:
            res = subprocess.run(
                [self._executable, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            version_match = re.search(r"ngspice-?(\d+)", res.stdout, re.IGNORECASE)
            if version_match:
                self._cached_version = f"ngspice-{version_match.group(1)}"
            else:
                self._cached_version = res.stdout.splitlines()[0][:32] if res.stdout else "ngspice-generic"
        except Exception:
            self._cached_version = "ngspice-unknown"

        return self._cached_version

    def is_available(self) -> bool:
        return bool(self._executable and os.path.isfile(self._executable))

    def validate_netlist(self, netlist: str) -> tuple[bool, str | None]:
        """Ensures safety invariants and basic structure before passing to subprocess."""
        if not netlist or not netlist.strip():
            return False, "Netlist cannot be empty"

        # Security check: disallow arbitrary shell execution directives, command chaining, path traversal or injection characters
        forbidden_patterns = [r"\.sys", r"\bshell\b", r"`", r"\|", r";", r"&&", r"\$\(", r"\.\./", r"\.\.\\"]
        for pattern in forbidden_patterns:
            if re.search(pattern, netlist, re.IGNORECASE):
                return False, f"Netlist contains forbidden or unsafe directive: {pattern}"

        # Disallow dangerous .include and .lib directives to prevent path traversal or arbitrary file inclusion
        if re.search(r"^\s*(\.include|\.lib)\b", netlist, re.IGNORECASE | re.MULTILINE):
            return False, ".include and .lib directives are not permitted in sandboxed netlists"

        lines = [line.strip() for line in netlist.strip().splitlines() if line.strip()]
        if len(lines) < 2:
            return False, "Netlist must contain at least a title and circuit elements"

        # Check for .end directive
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
        """Executes ngspice in batch mode within a sandboxed temporary directory."""
        start_time = time.perf_counter()

        # Validate netlist
        is_valid, error_msg = self.validate_netlist(netlist)
        if not is_valid:
            return SimulationExecutionResult(
                success=False,
                convergence_status=ConvergenceStatus.NOT_RUN.value,
                error_message=error_msg,
                execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        if not self.is_available():
            return SimulationExecutionResult(
                success=False,
                convergence_status=ConvergenceStatus.NOT_RUN.value,
                error_message="ngspice executable is not available on this host system",
                execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        # Execute in sandboxed temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            netlist_path = os.path.join(temp_dir, "circuit.cir")
            with open(netlist_path, "w", encoding="utf-8") as f:
                f.write(netlist)

            try:
                proc = subprocess.run(
                    [self._executable, "-b", netlist_path],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    shell=False,
                )
                stdout = proc.stdout or ""
                stderr = proc.stderr or ""
                if len(stdout) > MAX_OUTPUT_BYTES:
                    stdout = stdout[:MAX_OUTPUT_BYTES] + "\n... [TRUNCATED: OUTPUT EXCEEDED MAX_OUTPUT_BYTES]"
                if len(stderr) > 100_000:
                    stderr = stderr[:100_000] + "\n... [TRUNCATED]"
                combined_output = f"{stdout}\n{stderr}"
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                convergence = SpiceResultParser.detect_convergence(combined_output)
                if proc.returncode != 0 or convergence != ConvergenceStatus.CONVERGED.value:
                    return SimulationExecutionResult(
                        success=False,
                        convergence_status=convergence,
                        raw_stdout=stdout,
                        raw_stderr=stderr,
                        execution_time_ms=elapsed_ms,
                        error_message=stderr.strip() or f"Process exited with code {proc.returncode}",
                    )

                node_v, branch_i = SpiceResultParser.parse_dc_operating_point(combined_output)
                vectors = SpiceResultParser.parse_transient_or_ac(combined_output)
                metrics = SpiceResultParser.compute_summary_metrics(node_v, branch_i)

                return SimulationExecutionResult(
                    success=True,
                    convergence_status=ConvergenceStatus.CONVERGED.value,
                    raw_stdout=stdout,
                    raw_stderr=stderr,
                    parsed_vectors=vectors,
                    node_voltages=node_v,
                    branch_currents=branch_i,
                    metrics=metrics,
                    execution_time_ms=elapsed_ms,
                )

            except subprocess.TimeoutExpired:
                return SimulationExecutionResult(
                    success=False,
                    convergence_status=ConvergenceStatus.NON_CONVERGENT.value,
                    error_message=f"Simulation timed out after {timeout_seconds} seconds",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                )
            except Exception as e:
                return SimulationExecutionResult(
                    success=False,
                    convergence_status=ConvergenceStatus.NON_CONVERGENT.value,
                    error_message=f"Simulation execution error: {str(e)}",
                    execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
                )
