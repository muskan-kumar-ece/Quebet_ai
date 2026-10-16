from typing import Any, Dict, List, Optional


class SystemRequirementImpactService:
    """
    Evaluates how a candidate architecture affects system requirements.
    Transitions: UNCHANGED, IMPROVED, DEGRADED, VIOLATED, NEW_REQUIREMENT, UNKNOWN.
    Never collapses UNKNOWN into IMPROVED or SATISFIED.
    """

    def evaluate_impact(
        self,
        requirements: List[Dict[str, Any]],
        candidate_operations: List[Dict[str, Any]],
        candidate_strategy: str,
        power_effects: Dict[str, Any],
        failure_effects: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        # Map target subsystems/rails touched by operations
        touched_subsystems = set()
        touched_rails = set()
        for op in candidate_operations:
            p = op.get("payload", {})
            if "subsystem_id" in p:
                touched_subsystems.add(p["subsystem_id"])
            if "target_subsystem_id" in p:
                touched_subsystems.add(p["target_subsystem_id"])
            if "name" in p and "domain" in op.get("op_type", "").lower():
                touched_rails.add(p["name"])

        for req in requirements:
            req_id = req.get("id")
            code = req.get("code", "REQ")
            title = req.get("title", "")
            req_type = req.get("requirement_type", "FUNCTIONAL")
            constraints = req.get("constraints", {})

            transition = "UNCHANGED"
            rationale = "Requirement is unaffected by candidate architecture changes."

            # Power/efficiency related
            if "power" in title.lower() or "efficiency" in title.lower() or req_type == "ELECTRICAL":
                if candidate_strategy in ["POWER_DOMAIN_RESTRUCTURE", "REGULATOR_REPLACEMENT", "LOAD_REBALANCING"]:
                    # Check if power improved
                    margin_change = power_effects.get("efficiency_gain_pct")
                    if margin_change is not None:
                        if margin_change > 0:
                            transition = "IMPROVED"
                            rationale = f"Strategy '{candidate_strategy}' yields {margin_change}% estimated efficiency gain."
                        else:
                            transition = "DEGRADED"
                            rationale = "Regulator replacement did not improve efficiency margin."
                    else:
                        transition = "UNKNOWN"
                        rationale = "Candidate affects power architecture but exact efficiency delta is uncharacterized."

            # Protection / Isolation / Safety related
            elif "isolation" in title.lower() or "protection" in title.lower() or req_type == "SAFETY":
                if candidate_strategy in ["SUBSYSTEM_ISOLATION", "PROTECTION_ADDITION", "FAILURE_CONTAINMENT"]:
                    transition = "IMPROVED"
                    rationale = f"Strategy '{candidate_strategy}' introduces explicit physical containment."
                elif any("REMOVE" in op.get("op_type", "") for op in candidate_operations):
                    transition = "UNKNOWN"
                    rationale = "Subsystem removal requires re-verifying safety containment."

            # Check for unknown parameters in requirement constraints
            if not constraints and transition == "UNCHANGED":
                pass
            elif constraints and any(v is None or v == "UNKNOWN" for v in constraints.values()):
                transition = "UNKNOWN"
                rationale = "Requirement constraints contain unspecified parameters."

            results.append({
                "requirement_id": req_id,
                "code": code,
                "title": title,
                "requirement_type": req_type,
                "transition": transition,
                "rationale": rationale,
            })

        return results
