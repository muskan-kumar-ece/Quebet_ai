from typing import Any, Dict, List, Optional


class SystemArchitectureComparisonService:
    """
    Transparent multidimensional comparison across system architecture candidates.
    Does NOT calculate an overall winner, score, or composite health rating.
    """

    DIMENSIONS = [
        "Hard Constraints",
        "Soft Constraints",
        "Power & Efficiency",
        "Subsystem Count",
        "Failure Containment",
        "Requirement Impact",
        "Verification Burden",
        "Unknowns",
    ]

    def build_comparison_matrix(
        self,
        candidates: List[Dict[str, Any]],
        baseline_revision: int,
    ) -> Dict[str, Any]:
        matrix: Dict[str, Any] = {}

        for cand in candidates:
            c_id = cand.get("id") or cand.get("candidate_name")

            # 1. Hard & Soft constraints
            hard_res = cand.get("hard_constraints_result", "UNKNOWN")
            soft_res = cand.get("soft_constraints_result", "UNKNOWN")

            # 2. Power & Efficiency
            p_effects = cand.get("power_effects", {})
            eff_gain = p_effects.get("efficiency_gain_pct", 0.0)
            power_summary = f"+{eff_gain}% efficiency" if eff_gain > 0 else "Unchanged"

            # 3. Subsystem count change
            ops = cand.get("operations", [])
            add_count = sum(1 for op in ops if "ADD_SUBSYSTEM" in op.get("op_type", ""))
            rem_count = sum(1 for op in ops if "REMOVE_SUBSYSTEM" in op.get("op_type", ""))
            sub_count_delta = f"+{add_count}" if add_count > 0 else (f"-{rem_count}" if rem_count > 0 else "0")

            # 4. Failure Containment
            f_effects = cand.get("failure_effects", {})
            barriers = f_effects.get("containment_barriers", [])
            failure_summary = f"{len(barriers)} barriers active" if barriers else "Baseline paths"

            # 5. Requirement impact count
            req_effects = cand.get("requirement_effects", [])
            improved_reqs = sum(1 for r in req_effects if r.get("transition") == "IMPROVED")
            degraded_reqs = sum(1 for r in req_effects if r.get("transition") == "DEGRADED")
            req_summary = f"{improved_reqs} improved, {degraded_reqs} degraded"

            # 6. Verification burden
            v_effects = cand.get("verification_effects", [])
            new_v = sum(1 for v in v_effects if v.get("impact") == "NEW_VERIFICATION_REQUIRED")
            inval_v = sum(1 for v in v_effects if v.get("impact") == "VERIFICATION_INVALIDATED")
            v_summary = f"{new_v} new tests, {inval_v} invalidated"

            # 7. Unknowns
            unknowns = cand.get("unknowns", [])

            matrix[c_id] = {
                "candidate_name": cand.get("candidate_name"),
                "generation_strategy": cand.get("generation_strategy"),
                "hard_constraints": hard_res,
                "soft_constraints": soft_res,
                "power_efficiency": power_summary,
                "subsystem_count_delta": sub_count_delta,
                "failure_containment": failure_summary,
                "requirement_impact": req_summary,
                "verification_burden": v_summary,
                "unknowns_count": len(unknowns),
                "unknowns": unknowns,
                "status": cand.get("status", "GENERATED"),
            }

        return {
            "baseline_revision": baseline_revision,
            "candidates_count": len(candidates),
            "dimensions": self.DIMENSIONS,
            "matrix": matrix,
        }
