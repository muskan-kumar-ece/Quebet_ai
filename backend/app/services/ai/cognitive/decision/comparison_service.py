from enum import Enum
from typing import Any, Dict, List, Optional
from app.services.ai.cognitive.reflection.contradiction_engine import UnitNormalizer


class CategoricalState(str, Enum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    UNKNOWN = "UNKNOWN"
    NOT_EVALUATED = "NOT_EVALUATED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EngineeringDecisionComparisonService:
    """
    Compares candidate design alternatives using authoritative deterministic engineering facts.
    Strictly uses categorical evaluation states:
    SATISFIED, NOT_SATISFIED, UNKNOWN, NOT_EVALUATED, NOT_APPLICABLE.

    CRITICAL INVARIANTS:
    - Zero synthetic scoring: No overall_score, readiness_score, decision_score, or confidence percentages.
    - Zero automated ranking: No winner badge, recommended alternative, or best choice.
    - Preserves UNKNOWN != SATISFIED.
    """

    CATEGORICAL_STATES = {
        "SATISFIED": CategoricalState.SATISFIED.value,
        "NOT_SATISFIED": CategoricalState.NOT_SATISFIED.value,
        "UNKNOWN": CategoricalState.UNKNOWN.value,
        "NOT_EVALUATED": CategoricalState.NOT_EVALUATED.value,
        "NOT_APPLICABLE": CategoricalState.NOT_APPLICABLE.value,
    }

    @classmethod
    def compare_alternatives(
        cls,
        alternatives: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
        constraints: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        constraints = constraints or []
        comparison_matrix: List[Dict[str, Any]] = []

        for alt in alternatives:
            alt_id = alt.get("id") or alt.get("alternative_id") or "ALT"
            name = alt.get("name") or str(alt_id)
            description = alt.get("description", "")

            # Deterministic effects & parameters
            eng_eff = {**alt.get("parameters", {}), **alt.get("engineering_effects", {})}
            req_evals = alt.get("requirement_evaluations", {})
            constraint_evals = alt.get("constraint_evaluations", {})
            findings = alt.get("engineering_findings", [])
            unknowns = list(alt.get("unknowns", []))
            evidence_gaps = list(alt.get("evidence_gaps", []))
            verification_gaps = list(alt.get("verification_gaps", []))

            # Categorical requirement evaluations
            req_matrix: Dict[str, Dict[str, Any]] = {}
            for req in requirements:
                req_id = str(req.get("id") or req.get("name") or req.get("key"))
                req_name = req.get("name") or req.get("title") or req_id
                target_prop = str(req.get("target_property") or req.get("property") or "").lower()
                limit_val = req.get("max_value") or req.get("limit") or req.get("value")
                min_val = req.get("min_value")

                # Check if explicitly evaluated in alternative
                if req_id in req_evals:
                    raw_eval = req_evals[req_id]
                    if isinstance(raw_eval, dict):
                        eval_state = str(raw_eval.get("state", "UNKNOWN")).upper()
                    else:
                        eval_state = str(raw_eval).upper()
                    state = cls.CATEGORICAL_STATES.get(eval_state, "UNKNOWN")
                elif target_prop and target_prop in eng_eff and eng_eff[target_prop] is not None:
                    prop_str = str(eng_eff[target_prop]).strip()
                    if not prop_str:
                        state = "UNKNOWN"
                        unknowns.append(f"Property '{target_prop}' is uncharacterized for {name}")
                        verification_gaps.append(f"Verification required for '{target_prop}'")
                    else:
                        parsed_val = UnitNormalizer.parse_value_unit(prop_str)
                        if min_val is not None:
                            parsed_min = UnitNormalizer.parse_value_unit(min_val)
                            if parsed_min and parsed_val and parsed_min[1] == parsed_val[1]:
                                state = "SATISFIED" if parsed_val[0] >= parsed_min[0] else "NOT_SATISFIED"
                            else:
                                state = "UNKNOWN"
                        elif limit_val is not None:
                            parsed_limit = UnitNormalizer.parse_value_unit(limit_val)
                            if parsed_limit and parsed_val and parsed_limit[1] == parsed_val[1]:
                                state = "SATISFIED" if parsed_val[0] <= parsed_limit[0] else "NOT_SATISFIED"
                            else:
                                state = "UNKNOWN"
                        else:
                            state = "SATISFIED"
                elif target_prop and target_prop not in eng_eff:
                    state = "UNKNOWN"
                    unknowns.append(f"Property '{target_prop}' is missing/uncharacterized for {name}")
                    verification_gaps.append(f"Verification required for '{target_prop}' on {name}")
                elif req.get("status") in ("UNKNOWN", "VERIFICATION_REQUIRED"):
                    state = "UNKNOWN"
                else:
                    state = "NOT_EVALUATED"

                req_matrix[req_id] = {
                    "requirement_id": req_id,
                    "requirement_name": req_name,
                    "state": state,
                    "target_property": target_prop,
                }

            # Categorical constraint evaluations
            constraint_matrix: Dict[str, Dict[str, Any]] = {}
            for c in constraints:
                c_id = str(c.get("id") or c.get("name") or c.get("key"))
                c_name = c.get("name") or c_id
                c_type = str(c.get("type", "HARD")).upper()

                if c_id in constraint_evals:
                    state = str(constraint_evals[c_id].get("state", constraint_evals[c_id])).upper()
                else:
                    state = "SATISFIED" if not any(c_id in str(f) for f in findings) else "NOT_SATISFIED"

                constraint_matrix[c_id] = {
                    "constraint_id": c_id,
                    "constraint_name": c_name,
                    "type": c_type,
                    "state": state,
                }

            # Tally categorical counts (discrete factual counts only)
            satisfied_reqs = sum(1 for r in req_matrix.values() if r["state"] == "SATISFIED")
            violated_reqs = sum(1 for r in req_matrix.values() if r["state"] == "NOT_SATISFIED")
            unknown_reqs = sum(1 for r in req_matrix.values() if r["state"] == "UNKNOWN")
            not_eval_reqs = sum(1 for r in req_matrix.values() if r["state"] == "NOT_EVALUATED")

            entry = {
                "alternative_id": alt_id,
                "name": name,
                "description": description,
                "requirement_evaluations": req_matrix,
                "constraint_evaluations": constraint_matrix,
                "categorical_counts": {
                    "requirements_satisfied": satisfied_reqs,
                    "requirements_not_satisfied": violated_reqs,
                    "requirements_unknown": unknown_reqs,
                    "requirements_not_evaluated": not_eval_reqs,
                    "unknowns_count": len(unknowns),
                    "evidence_gaps_count": len(evidence_gaps),
                    "verification_gaps_count": len(verification_gaps),
                    "findings_count": len(findings),
                },
                "affected_components": alt.get("affected_components", []),
                "affected_subsystems": alt.get("affected_subsystems", []),
                "affected_interfaces": alt.get("affected_interfaces", []),
                "unknowns": unknowns,
                "evidence_gaps": evidence_gaps,
                "verification_gaps": verification_gaps,
            }
            comparison_matrix.append(entry)

        return {
            "comparison_matrix": comparison_matrix,
            "evaluated_requirements_count": len(requirements),
            "evaluated_constraints_count": len(constraints),
        }
