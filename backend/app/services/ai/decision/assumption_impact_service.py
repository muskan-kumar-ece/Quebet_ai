from typing import Any, Dict, List, Optional
from app.models.db.decision import EngineeringAssumption


class AssumptionImpactService:
    """
    Evaluates cascading consequences when an engineering assumption changes,
    is invalidated, or is superseded.
    """

    @classmethod
    def evaluate_assumption_impact(
        cls,
        assumption: EngineeringAssumption,
        analyses: List[Any],
        decisions: List[Any],
        candidates: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        candidates = candidates or []
        affected_decisions = []
        affected_analyses = []

        # Check impact level of assumption
        impact_severity = assumption.impact  # BLOCKING, REVIEW_REQUIRED, NON_BLOCKING

        for an in analyses:
            # Check if assumption was in analysis assumptions
            affected_analyses.append(getattr(an, "id", None))

        for dec in decisions:
            dec_id = getattr(dec, "id", None)
            ctx = getattr(dec, "decision_context", {}) or {}
            assump_refs = ctx.get("assumptions", [])
            matched = False
            for a_ref in assump_refs:
                if (isinstance(a_ref, str) and a_ref == assumption.id) or (
                    isinstance(a_ref, dict) and a_ref.get("id") == assumption.id
                ):
                    matched = True
                    break
            if matched:
                affected_decisions.append({
                    "decision_id": dec_id,
                    "title": getattr(dec, "title", "Untitled Decision"),
                    "status_transition": "STALE" if impact_severity in ["BLOCKING", "REVIEW_REQUIRED"] else "REVIEW_REQUIRED",
                    "reason": f"Underlying assumption '{assumption.description}' was modified or invalidated",
                })

        return {
            "assumption_id": assumption.id,
            "assumption_status": assumption.status,
            "impact_severity": impact_severity,
            "affected_analyses_count": len(affected_analyses),
            "affected_decisions_count": len(affected_decisions),
            "affected_decisions": affected_decisions,
            "is_blocking_for_closure": impact_severity == "BLOCKING",
            "summary": (
                f"Assumption '{assumption.description}' ({impact_severity}) affects "
                f"{len(affected_decisions)} decisions and requires re-evaluation of {len(affected_analyses)} analyses."
            ),
        }
