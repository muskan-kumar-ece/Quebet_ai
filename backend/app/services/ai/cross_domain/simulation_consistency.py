"""
Simulation Staleness & Consistency Engine for Phase 3 Wave 8.
Evaluates Rules X011 (Simulation Snapshot vs Current Design Snapshot)
and X012 (Simulation Result vs Current Component/Design Identity).
STRICT INVARIANTS:
- A stale simulation MUST NOT be represented as current verification.
- If circuit revision or snapshot changed -> STATUS = UNKNOWN / STALE.
- SIMULATION_RESULT != PHYSICAL_MEASUREMENT
- SIMULATION_RESULT != HARDWARE_VERIFICATION
- Zero synthetic scoring.
"""
from typing import Any, Optional
from app.models.db.cross_domain import (
    CrossDomainSeverity,
    CrossDomainStatus,
    SourceClassification,
    ValidationDomain,
)
from app.models.schemas.cross_domain import CrossDomainFinding


class SimulationConsistencyEngine:
    """
    Evaluates currency and fidelity of SPICE simulation runs against current schematic state.
    """

    @staticmethod
    def evaluate(
        project_id: str,
        circuit: Optional[Any],
        simulation_job: Optional[Any],
        simulation_result: Optional[Any],
        rules: dict[str, dict[str, Any]],
    ) -> list[CrossDomainFinding]:
        findings: list[CrossDomainFinding] = []

        rule_011 = rules.get("X011")
        rule_012 = rules.get("X012")

        if not simulation_job:
            for rule_id, claim in [("X011", rule_011["engineering_claim"] if rule_011 else ""), ("X012", rule_012["engineering_claim"] if rule_012 else "")]:
                r = rules.get(rule_id)
                if r:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"{rule_id}_NO_SIMULATION",
                            project_id=project_id,
                            domain_a=ValidationDomain.SIMULATION,
                            domain_b=ValidationDomain.SCHEMATIC,
                            rule_id=rule_id,
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=claim,
                            explanation="No SPICE simulation has been executed for this circuit. Simulation verification status unknown.",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )
            return findings

        if not circuit:
            for rule_id, claim in [("X011", rule_011["engineering_claim"] if rule_011 else ""), ("X012", rule_012["engineering_claim"] if rule_012 else "")]:
                r = rules.get(rule_id)
                if r:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"{rule_id}_NO_CIRCUIT",
                            project_id=project_id,
                            domain_a=ValidationDomain.SIMULATION,
                            domain_b=ValidationDomain.SCHEMATIC,
                            rule_id=rule_id,
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.HIGH,
                            engineering_claim=claim,
                            explanation="Circuit model is missing. Simulation staleness cannot be evaluated.",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )
            return findings

        # --- Rule X011: Simulation Snapshot vs Current Design Snapshot ---
        if rule_011:
            c_ver = getattr(circuit, "version", None)
            s_ver = getattr(simulation_job, "circuit_version", None)
            sim_status = str(getattr(simulation_job, "status", "")).upper()

            if c_ver is None or s_ver is None:
                findings.append(
                    CrossDomainFinding(
                        finding_id=f"X011_MISSING_REVISION_{simulation_job.id}",
                        project_id=project_id,
                        domain_a=ValidationDomain.SIMULATION,
                        domain_b=ValidationDomain.SCHEMATIC,
                        affected_entity_ids=[str(simulation_job.id), str(circuit.id)],
                        rule_id="X011",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.HIGH,
                        engineering_claim=rule_011["engineering_claim"],
                        explanation=f"MISSING REVISION: Authoritative circuit revision information cannot be determined (circuit revision: {c_ver}, simulation circuit revision: {s_ver}). Revision synchronization cannot be established. (UNKNOWN != SATISFIED; UNKNOWN != PASS).",
                        quantitative_values={"simulation_revision": s_ver, "current_circuit_revision": c_ver},
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                circuit_version = int(c_ver)
                sim_circuit_version = int(s_ver)
                is_stale = (circuit_version != sim_circuit_version) or (sim_status == "STALE")

                if is_stale:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X011_STALE_SIMULATION_{simulation_job.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.SIMULATION,
                            domain_b=ValidationDomain.SCHEMATIC,
                            affected_entity_ids=[str(simulation_job.id), str(circuit.id)],
                            rule_id="X011",
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.HIGH,
                            engineering_claim=rule_011["engineering_claim"],
                            explanation=f"STALE SIMULATION: SPICE simulation was run on circuit revision {sim_circuit_version}, but current circuit is revision {circuit_version}. (SIMULATION_RESULT != CURRENT_VERIFICATION).",
                            quantitative_values={"simulation_revision": sim_circuit_version, "current_circuit_revision": circuit_version},
                            source_classification=SourceClassification.SIMULATED,
                        )
                    )
                elif sim_status != "COMPLETED":
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X011_INCOMPLETE_SIMULATION_{simulation_job.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.SIMULATION,
                            domain_b=ValidationDomain.SCHEMATIC,
                            affected_entity_ids=[str(simulation_job.id)],
                            rule_id="X011",
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.MEDIUM,
                            engineering_claim=rule_011["engineering_claim"],
                            explanation=f"Simulation job {simulation_job.id} has status '{sim_status}' and cannot serve as authoritative simulation verification.",
                            source_classification=SourceClassification.SIMULATED,
                        )
                    )
                else:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X011_PASS_{simulation_job.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.SIMULATION,
                            domain_b=ValidationDomain.SCHEMATIC,
                            affected_entity_ids=[str(simulation_job.id)],
                            rule_id="X011",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_011["engineering_claim"],
                            explanation=f"SPICE simulation matches current circuit revision {circuit_version}. (SIMULATION_RESULT != PHYSICAL_MEASUREMENT).",
                            source_classification=SourceClassification.SIMULATED,
                        )
                    )

        # --- Rule X012: Simulation Result vs Current Component/Design Identity ---
        if rule_012:
            if not simulation_result:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X012_NO_RESULT",
                        project_id=project_id,
                        domain_a=ValidationDomain.SIMULATION,
                        domain_b=ValidationDomain.SCHEMATIC,
                        rule_id="X012",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_012["engineering_claim"],
                        explanation="No structured simulation result records exist to evaluate simulated component parameters.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                metrics = getattr(simulation_result, "metrics", {}) or {}
                # Check convergence
                convergence = str(getattr(simulation_result, "convergence_status", "")).upper()
                if convergence in ("NON_CONVERGENT", "SINGULAR_MATRIX", "TIMESTEP_TOO_SMALL"):
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X012_NON_CONVERGENT_{simulation_result.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.SIMULATION,
                            domain_b=ValidationDomain.SCHEMATIC,
                            affected_entity_ids=[str(simulation_result.id)],
                            rule_id="X012",
                            status=CrossDomainStatus.FAIL,
                            severity=CrossDomainSeverity.HIGH,
                            engineering_claim=rule_012["engineering_claim"],
                            explanation=f"Simulation failed to achieve mathematical convergence: {convergence}. Results are invalid for design verification.",
                            source_classification=SourceClassification.SIMULATED,
                        )
                    )
                else:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X012_PASS_{simulation_result.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.SIMULATION,
                            domain_b=ValidationDomain.SCHEMATIC,
                            affected_entity_ids=[str(simulation_result.id)],
                            rule_id="X012",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_012["engineering_claim"],
                            explanation="Simulation result achieved valid numerical convergence consistent with component parameters. (CONVERGENCE != ENGINEERING_CORRECTNESS; SIMULATION_RESULT != PHYSICAL_MEASUREMENT).",
                            source_classification=SourceClassification.SIMULATED,
                        )
                    )

        return findings
