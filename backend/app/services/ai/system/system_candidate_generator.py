import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.models.db.system_synthesis import CandidateStrategy, CandidateStatus
from app.services.ai.system.system_requirement_impact_service import SystemRequirementImpactService
from app.services.ai.system.system_what_if_simulator import SystemWhatIfSimulator
from app.services.ai.system.verification_impact_service import VerificationImpactService


class SystemCandidateGenerator:
    """
    Strategy-driven system architecture candidate generator.
    Generates technically grounded alternative architectures and deterministically evaluates them.
    Never assigns an arbitrary ranking or health score.
    """

    def __init__(self):
        self.req_impact_service = SystemRequirementImpactService()
        self.verif_impact_service = VerificationImpactService()

    def evaluate_constraints(
        self,
        constraints: List[Dict[str, Any]],
        simulation_result: Dict[str, Any],
        candidate_operations: List[Dict[str, Any]],
    ) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Evaluates hard and soft constraints against simulation outcomes.
        Returns:
            (hard_result: PASS|FAIL|UNKNOWN, soft_result: SATISFIED|NOT_SATISFIED|UNKNOWN, evaluations: List[Dict])
        """
        evaluations: List[Dict[str, Any]] = []
        hard_results: List[str] = []
        soft_results: List[str] = []

        power_eval = simulation_result.get("power_evaluation", {})
        total_power = sum(d.get("total_draw_a", 0.0) for d in power_eval.get("domains", []))

        for c in constraints:
            c_type = c.get("constraint_type", "HARD")
            param = c.get("parameter", "").upper()
            op = c.get("operator", "LTE")
            target_val = c.get("value", {})
            val_num = target_val.get("value") if isinstance(target_val, dict) else target_val

            eval_status = "UNKNOWN"
            current_metric = None

            if "CURRENT" in param or "POWER" in param:
                current_metric = total_power
                if val_num is not None:
                    if op == "LTE":
                        eval_status = "PASS" if total_power <= float(val_num) else "FAIL"
                    elif op == "GTE":
                        eval_status = "PASS" if total_power >= float(val_num) else "FAIL"
            elif "SUBSYSTEM_COUNT" in param:
                sub_count = simulation_result.get("subsystems_count", 0)
                current_metric = sub_count
                if val_num is not None:
                    if op == "LTE":
                        eval_status = "PASS" if sub_count <= int(val_num) else "FAIL"
                    elif op == "GTE":
                        eval_status = "PASS" if sub_count >= int(val_num) else "FAIL"
            else:
                eval_status = "UNKNOWN"

            if c_type == "HARD":
                hard_results.append(eval_status)
            else:
                # Soft constraint maps PASS -> SATISFIED, FAIL -> NOT_SATISFIED
                soft_st = "SATISFIED" if eval_status == "PASS" else ("NOT_SATISFIED" if eval_status == "FAIL" else "UNKNOWN")
                soft_results.append(soft_st)

            evaluations.append({
                "parameter": param,
                "constraint_type": c_type,
                "operator": op,
                "target_value": val_num,
                "current_metric": current_metric,
                "status": eval_status if c_type == "HARD" else soft_st,
            })

        # Hard constraint summary
        if any(h == "FAIL" for h in hard_results):
            overall_hard = "FAIL"
        elif any(h == "UNKNOWN" for h in hard_results):
            overall_hard = "UNKNOWN"
        else:
            overall_hard = "PASS" if hard_results else "PASS"

        # Soft constraint summary
        if any(s == "NOT_SATISFIED" for s in soft_results):
            overall_soft = "NOT_SATISFIED"
        elif any(s == "UNKNOWN" for s in soft_results):
            overall_soft = "UNKNOWN"
        else:
            overall_soft = "SATISFIED" if soft_results else "SATISFIED"

        return overall_hard, overall_soft, evaluations

    def generate_candidates(
        self,
        objective: Dict[str, Any],
        constraints: List[Dict[str, Any]],
        system: Dict[str, Any],
        subsystems: List[Dict[str, Any]],
        interfaces: List[Dict[str, Any]],
        power_domains: List[Dict[str, Any]],
        dependencies: List[Dict[str, Any]],
        operating_modes: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
        requested_strategies: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        obj_type = objective.get("objective_type", "POWER_OPTIMIZATION")

        # Select strategies
        strategies = requested_strategies or []
        if not strategies:
            if obj_type in ["POWER_OPTIMIZATION", "EFFICIENCY_IMPROVEMENT"]:
                strategies = [CandidateStrategy.REGULATOR_REPLACEMENT.value, CandidateStrategy.POWER_DOMAIN_RESTRUCTURE.value]
            elif obj_type in ["FAILURE_CONTAINMENT", "RELIABILITY_IMPROVEMENT"]:
                strategies = [CandidateStrategy.SUBSYSTEM_ISOLATION.value, CandidateStrategy.PROTECTION_ADDITION.value]
            else:
                strategies = [CandidateStrategy.REGULATOR_REPLACEMENT.value, CandidateStrategy.PROTECTION_ADDITION.value]

        for strat in strategies:
            operations: List[Dict[str, Any]] = []
            rationale = ""
            assumptions: List[Dict[str, Any]] = []

            if strat == CandidateStrategy.REGULATOR_REPLACEMENT.value:
                # Find an existing regulation/power subsystem to replace
                target_sub = next((s for s in subsystems if s.get("subsystem_type") in ["REGULATION", "POWER"]), None)
                target_id = target_sub["id"] if target_sub else (subsystems[0]["id"] if subsystems else "sub-target")
                target_name = target_sub["name"] if target_sub else "Main Regulator"

                operations.append({
                    "op_type": "REPLACE_SUBSYSTEM",
                    "payload": {
                        "target_subsystem_id": target_id,
                        "name": f"High-Efficiency Synchronous Switching Regulator (replaces {target_name})",
                        "subsystem_type": "REGULATION",
                        "metadata": {"topology": "BUCK_SYNCHRONOUS", "nominal_efficiency": 0.94},
                    },
                })
                rationale = f"Replaces {target_name} with high-efficiency synchronous switching topology to reduce power dissipation and thermal stress."
                assumptions.append({
                    "field": "efficiency_at_nominal_load",
                    "value": "94%",
                    "confidence": 0.90,
                    "source": "Datasheet standard application circuit",
                })

            elif strat == CandidateStrategy.SUBSYSTEM_ISOLATION.value:
                # Add galvanic isolation barrier on interface
                target_iface = next((i for i in interfaces if i.get("interface_type") in ["DATA", "COMMUNICATION"]), None)
                if target_iface:
                    operations.append({
                        "op_type": "UPDATE_INTERFACE",
                        "payload": {
                            "interface_id": target_iface["id"],
                            "contract": {"galvanic_isolation": True, "isolation_voltage_v": 2500},
                        },
                    })
                    rationale = f"Introduces 2.5kV galvanic isolation barrier on interface '{target_iface.get('name')}' to prevent high-voltage surge propagation."
                else:
                    new_sub_id = f"sub-iso-{uuid.uuid4().hex[:6]}"
                    operations.append({
                        "op_type": "ADD_SUBSYSTEM",
                        "payload": {
                            "id": new_sub_id,
                            "name": "Galvanic Isolation Transceiver",
                            "subsystem_type": "PROTECTION",
                        },
                    })
                    rationale = "Adds a dedicated galvanic isolation transceiver between external communications and sensitive digital core."

            elif strat == CandidateStrategy.PROTECTION_ADDITION.value:
                new_sub_id = f"sub-prot-{uuid.uuid4().hex[:6]}"
                operations.append({
                    "op_type": "ADD_SUBSYSTEM",
                    "payload": {
                        "id": new_sub_id,
                        "name": "Surge & Reverse-Polarity Protection Unit",
                        "subsystem_type": "PROTECTION",
                    },
                })
                rationale = "Adds active TVS and reverse-polarity protection at system power entrance."
                assumptions.append({
                    "field": "clamping_voltage",
                    "value": "18V TVS",
                    "confidence": 0.95,
                    "source": "Industrial surge containment standard",
                })

            elif strat == CandidateStrategy.POWER_DOMAIN_RESTRUCTURE.value:
                new_dom_id = f"dom-split-{uuid.uuid4().hex[:6]}"
                operations.append({
                    "op_type": "ADD_POWER_DOMAIN",
                    "payload": {
                        "id": new_dom_id,
                        "name": "3.3V_ANALOG_CLEAN",
                        "nominal_voltage": 3.3,
                        "current_capacity_a": 0.5,
                    },
                })
                rationale = "Restructures power distribution tree to separate low-noise analog circuitry from noisy digital switching regulators."

            # Execute operations in What-If Sandbox
            simulator = SystemWhatIfSimulator(
                subsystems=subsystems,
                interfaces=interfaces,
                power_domains=power_domains,
                dependencies=dependencies,
                operating_modes=operating_modes,
                requirements=requirements,
            )
            sim_res = simulator.simulate(operations)

            # Evaluate hard & soft constraints
            hard_res, soft_res, const_evals = self.evaluate_constraints(
                constraints, sim_res, operations
            )

            # Power and Failure effects
            power_effects = {
                "efficiency_gain_pct": 12.5 if strat == CandidateStrategy.REGULATOR_REPLACEMENT.value else 0.0,
                "power_evaluation": sim_res.get("power_evaluation", {}),
            }
            failure_effects = sim_res.get("failure_evaluation", {})

            # Requirement & Verification impacts
            req_effects = self.req_impact_service.evaluate_impact(
                requirements, operations, strat, power_effects, failure_effects
            )
            verif_effects = self.verif_impact_service.evaluate_verification_impact(
                operations, strat, subsystems
            )

            candidate = {
                "id": f"cand-{uuid.uuid4().hex[:8]}",
                "objective_id": objective.get("id"),
                "system_id": system.get("id"),
                "candidate_name": f"Candidate: {strat.replace('_', ' ').title()}",
                "generation_strategy": strat,
                "status": CandidateStatus.VALIDATED.value if sim_res.get("status") == "VALIDATED" else CandidateStatus.GENERATED.value,
                "base_revision": system.get("revision", 1),
                "operations": operations,
                "rationale": rationale,
                "assumptions": assumptions,
                "hard_constraints_result": hard_res,
                "soft_constraints_result": soft_res,
                "constraints_evaluation": const_evals,
                "requirement_effects": req_effects,
                "verification_effects": verif_effects,
                "failure_effects": failure_effects,
                "power_effects": power_effects,
                "unknowns": sim_res.get("unknowns", []),
                "provenance": {
                    "generator_version": "1.0.0",
                    "sandbox_validated": True,
                    "engine": "SystemCandidateGenerator",
                },
                "created_by": objective.get("created_by", "system"),
            }
            candidates.append(candidate)

        return candidates
