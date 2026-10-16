from typing import Any, Dict, List, Optional
from app.models.db.decision import (
    EngineeringDecisionAlternative,
    EngineeringDecisionRecord,
    EliminationReason,
)


class DecisionComparisonService:
    """
    Evaluates and compares candidate alternatives along independent engineering dimensions.

    STRICT PRINCIPLE: Zero synthetic scoring.
    No overall_score, decision_score, risk_score, health_score, or winner badges.
    The service provides facts and consequences; the human engineer makes the decision.
    """

    @classmethod
    def compare_alternatives(
        cls,
        decision: EngineeringDecisionRecord,
        alternatives: List[EngineeringDecisionAlternative],
        baseline_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        baseline_metrics = baseline_metrics or {}
        comparison_matrix: List[Dict[str, Any]] = []

        for alt in alternatives:
            eng_eff = alt.engineering_effects or {}
            req_eff = alt.requirement_effects or {}
            ver_eff = alt.verification_effects or {}
            fail_eff = alt.failure_effects or {}
            unknowns = alt.unknowns or []

            # Extract objective engineering dimensions
            matrix_entry = {
                "alternative_id": alt.id,
                "candidate_id": alt.candidate_id,
                "name": alt.name,
                "status": alt.status,
                "elimination_reason": alt.elimination_reason,
                # 1. Requirement Compliance
                "requirements_satisfied_count": req_eff.get("satisfied_count", 0),
                "requirements_violated_count": req_eff.get("violated_count", 0),
                "requirements_unknown_count": req_eff.get("unknown_count", 0),
                # 2. Constraints
                "hard_constraints_violated": eng_eff.get("hard_constraints_violated", 0),
                "soft_constraints_satisfied": eng_eff.get("soft_constraints_satisfied", 0),
                # 3. Power & Thermal
                "power_dissipation_w": eng_eff.get("power_dissipation_w"),
                "power_margin_w": eng_eff.get("power_margin_w"),
                "estimated_efficiency_pct": eng_eff.get("efficiency_pct"),
                # 4. Interface Contracts
                "interface_violations": eng_eff.get("interface_violations", 0),
                "interface_unknowns": eng_eff.get("interface_unknowns", 0),
                # 5. Failure Propagation & Blast Radius
                "failure_blast_radius_subsystems": fail_eff.get("blast_radius_count", 0),
                "containment_barriers_active": fail_eff.get("containment_barriers_active", 0),
                # 6. Verification Burden
                "new_verifications_required": len(ver_eff.get("new_verifications", [])),
                "invalidated_verifications": len(ver_eff.get("invalidated_verifications", [])),
                # 7. Unresolved Unknowns
                "unresolved_unknowns_count": len(unknowns),
                "unresolved_unknowns": unknowns,
            }

            # Check if any hard constraint violation eliminates the candidate
            if matrix_entry["hard_constraints_violated"] > 0 and alt.status != "ELIMINATED":
                matrix_entry["recommended_elimination"] = EliminationReason.HARD_CONSTRAINT_VIOLATION.value
            elif matrix_entry["requirements_violated_count"] > 0 and alt.status != "ELIMINATED":
                matrix_entry["recommended_elimination"] = EliminationReason.REQUIREMENT_VIOLATION.value
            elif matrix_entry["interface_violations"] > 0 and alt.status != "ELIMINATED":
                matrix_entry["recommended_elimination"] = EliminationReason.INTERFACE_INCOMPATIBILITY.value

            comparison_matrix.append(matrix_entry)

        return {
            "decision_id": decision.id,
            "decision_key": decision.decision_key,
            "system_revision": decision.system_revision,
            "baseline_metrics": baseline_metrics,
            "comparison_matrix": comparison_matrix,
            # Note: Explicit omission of composite_score, rank, or winner
        }
