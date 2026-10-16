import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.models.db.system_synthesis import (
    EngineeringScenario,
    EngineeringScenarioCondition,
    EngineeringScenarioResult,
    EngineeringScenarioSnapshot,
    ScenarioResultStatus,
)
from app.services.ai.system.failure_propagation_engine import SystemFailurePropagationEngine
from app.services.ai.system.interface_compatibility_engine import SystemInterfaceCompatibilityEngine
from app.services.ai.system.system_what_if_simulator import SimObj, SystemWhatIfSimulator


class ScenarioExecutionService:
    """
    Deterministic execution of operating and failure scenarios against system architecture.
    Enforces strict precondition validation and immutable snapshot digests.
    """

    def validate_preconditions(
        self,
        conditions: List[Dict[str, Any]],
        subsystems: List[Dict[str, Any]],
        power_domains: List[Dict[str, Any]],
    ) -> Tuple[str, List[str]]:
        """
        Evaluates precondition conditions.
        Returns:
            (status: "SATISFIED" | "NOT_SATISFIED" | "UNKNOWN", reasons: List[str])
        """
        reasons: List[str] = []
        has_unknown = False

        sub_ids = {s["id"] for s in subsystems}
        sub_names = {s["name"].lower(): s["id"] for s in subsystems}
        domain_names = {p["name"].lower(): p for p in power_domains}

        preconditions = [c for c in conditions if c.get("condition_type") == "PRECONDITION"]
        if not preconditions:
            return "SATISFIED", []

        for cond in preconditions:
            param = cond.get("parameter", "").lower()
            val = cond.get("value", {})
            mandatory = cond.get("mandatory", True)
            target_id = cond.get("target_id")

            # Check subsystem active precondition
            if "subsystem" in param or cond.get("target_type") == "SUBSYSTEM":
                if target_id and target_id not in sub_ids:
                    msg = f"Precondition failed: required subsystem {target_id} not present in system"
                    reasons.append(msg)
                    if mandatory:
                        return "NOT_SATISFIED", reasons

            # Check power domain precondition
            elif "power_domain" in param or "rail" in param or cond.get("target_type") == "POWER_DOMAIN":
                domain_name = val.get("name", "").lower() if isinstance(val, dict) else str(val).lower()
                if domain_name and domain_name not in domain_names:
                    msg = f"Precondition failed: required power rail '{domain_name}' not defined"
                    reasons.append(msg)
                    if mandatory:
                        return "NOT_SATISFIED", reasons

            # Check environmental / external context
            elif param in ["ambient_temperature", "input_voltage", "battery_soc"]:
                if not val:
                    reasons.append(f"Precondition unknown: parameter '{param}' has no specified value")
                    has_unknown = True
            else:
                # Unmodeled parameter evaluates to UNKNOWN
                reasons.append(f"Precondition unknown: uncharacterized parameter '{param}'")
                has_unknown = True

        if reasons and any("failed" in r for r in reasons):
            return "NOT_SATISFIED", reasons
        if has_unknown:
            return "UNKNOWN", reasons
        return "SATISFIED", []

    def execute_scenario(
        self,
        scenario: Dict[str, Any],
        conditions: List[Dict[str, Any]],
        system: Dict[str, Any],
        subsystems: List[Dict[str, Any]],
        interfaces: List[Dict[str, Any]],
        power_domains: List[Dict[str, Any]],
        dependencies: List[Dict[str, Any]],
        operating_modes: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Runs the scenario in a sandboxed cloned system graph.
        Never mutates the persistent database.
        """
        # 1. Precondition Validation
        precond_status, precond_reasons = self.validate_preconditions(
            conditions, subsystems, power_domains
        )

        if precond_status == "NOT_SATISFIED":
            return {
                "status": ScenarioResultStatus.BLOCKED.value,
                "precondition_status": "NOT_SATISFIED",
                "findings": [
                    {
                        "severity": "CRITICAL",
                        "title": "Scenario Precondition Violation",
                        "description": "; ".join(precond_reasons),
                        "unknowns": [],
                    }
                ],
                "requirement_results": [],
                "power_results": {},
                "interface_results": {},
                "failure_results": {},
                "unknowns": precond_reasons,
                "inputs_digest": "none",
            }

        # 2. Setup Sandboxed Simulation
        simulator = SystemWhatIfSimulator(
            subsystems=subsystems,
            interfaces=interfaces,
            power_domains=power_domains,
            dependencies=dependencies,
            operating_modes=operating_modes,
            requirements=requirements,
        )

        # 3. Apply Operating Conditions and Fault Injections
        unknowns: List[str] = list(precond_reasons) if precond_status == "UNKNOWN" else []
        failed_sub_ids: List[str] = []

        for cond in conditions:
            cond_type = cond.get("condition_type")
            target_type = cond.get("target_type")
            target_id = cond.get("target_id")
            param = cond.get("parameter", "")
            val = cond.get("value", {})

            if cond_type == "FAULT_INJECTION":
                if target_type == "SUBSYSTEM" and target_id:
                    failed_sub_ids.append(target_id)
                    simulator.apply_operation(
                        "UPDATE_SUBSYSTEM",
                        {"subsystem_id": target_id, "status": "FAULT_FAILED"},
                    )
                elif target_type == "INTERFACE" and target_id:
                    simulator.apply_operation(
                        "UPDATE_INTERFACE",
                        {"interface_id": target_id, "status": "FAULT_DISCONNECTED"},
                    )
                elif target_type == "POWER_DOMAIN" and target_id:
                    simulator.apply_operation(
                        "UPDATE_POWER_DOMAIN",
                        {"domain_id": target_id, "status": "FAULT_COLLAPSED"},
                    )

            elif cond_type == "OPERATING_CONDITION":
                if target_type == "POWER_DOMAIN" and target_id:
                    current_draw = val.get("load_current_a") if isinstance(val, dict) else None
                    if current_draw is not None:
                        simulator.apply_operation(
                            "UPDATE_POWER_DOMAIN",
                            {"domain_id": target_id, "metadata": {"scenario_load_a": current_draw}},
                        )

        # 4. Deterministic Analyses on Cloned Graph
        sim_result = simulator.simulate([])

        # 5. Failure Propagation for Injected Faults
        failure_results = {}
        if failed_sub_ids:
            sub_objs = [SimObj(**s) for s in simulator.subsystems]
            iface_objs = [SimObj(**i) for i in simulator.interfaces]
            dom_objs = [SimObj(**p) for p in simulator.power_domains]
            dep_objs = [SimObj(**d) for d in simulator.dependencies]
            for f_id in failed_sub_ids:
                f_sim = SystemFailurePropagationEngine.simulate_failure(
                    sub_objs, iface_objs, dom_objs, dep_objs, failed_subsystem_id=f_id, failure_type="INJECTED_FAULT"
                )
                failure_results[f_id] = f_sim

        # 6. Inputs Digest (SHA-256 for reproducibility)
        digest_payload = {
            "system_id": system.get("id"),
            "system_revision": system.get("revision", 1),
            "scenario_id": scenario.get("id"),
            "conditions": conditions,
            "subsystems_count": len(subsystems),
            "interfaces_count": len(interfaces),
        }
        inputs_digest = hashlib.sha256(
            json.dumps(digest_payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()

        # 7. Collect Scenario Findings
        findings: List[Dict[str, Any]] = []
        if sim_result.get("status") == "BLOCKED":
            findings.append({
                "severity": "CRITICAL",
                "title": "Scenario Revealed Incompatible Interfaces",
                "description": f"Interface contract violations detected under scenario '{scenario.get('name')}'.",
                "unknowns": sim_result.get("unknowns", []),
            })

        for err in sim_result.get("errors", []):
            findings.append({
                "severity": "WARNING",
                "title": "Simulation Anomaly",
                "description": err,
                "unknowns": [],
            })

        final_status = ScenarioResultStatus.COMPLETE.value
        if precond_status == "UNKNOWN":
            final_status = ScenarioResultStatus.PARTIAL.value

        return {
            "status": final_status,
            "precondition_status": precond_status,
            "findings": findings,
            "requirement_results": [
                {
                    "requirement_id": r.get("id"),
                    "code": r.get("code"),
                    "scenario_status": "SUPPORTED" if sim_result.get("status") == "VALIDATED" else "VERIFICATION_REQUIRED",
                }
                for r in requirements
            ],
            "power_results": sim_result.get("power_evaluation", {}),
            "interface_results": {"evaluations": sim_result.get("interface_evaluations", [])},
            "failure_results": failure_results,
            "unknowns": list(set(unknowns + sim_result.get("unknowns", []))),
            "inputs_digest": inputs_digest,
            "provenance": {
                "engine_versions": {"ScenarioExecutionService": "1.0.0", "SystemWhatIfSimulator": "1.0.0"},
                "rule_set_version": "QUEBET-SYSTEM-SCENARIO-001 v1.0",
                "timestamp": datetime.utcnow().isoformat(),
            },
        }
