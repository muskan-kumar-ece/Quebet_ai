from typing import Any, Dict, List, Optional
from app.models.db.decision import (
    EngineeringDesignReviewSession,
    EngineeringDecisionRecord,
    EngineeringDecisionAlternative,
    EngineeringRequirement,
    EngineeringReviewCheckpoint,
    EngineeringReviewFinding,
    EngineeringReviewAction,
    EngineeringDecisionQuestion,
    EngineeringTradeoff,
)


class DesignReviewReportService:
    """
    Generates a structured, auditable Design Review Report synthesizing
    system revision, baseline, requirements, assumptions, findings,
    alternatives, trade-offs, questions, actions, and the human decision record.
    """

    @classmethod
    def compile_report(
        cls,
        review: EngineeringDesignReviewSession,
        decision: Optional[EngineeringDecisionRecord],
        requirements: List[EngineeringRequirement],
        checkpoints: List[EngineeringReviewCheckpoint],
        findings: List[EngineeringReviewFinding],
        actions: List[EngineeringReviewAction],
        questions: List[EngineeringDecisionQuestion],
        alternatives: Optional[List[EngineeringDecisionAlternative]] = None,
        tradeoffs: Optional[List[EngineeringTradeoff]] = None,
    ) -> Dict[str, Any]:
        alternatives = alternatives or []
        tradeoffs = tradeoffs or []

        return {
            "review_id": review.id,
            "title": review.title,
            "status": review.status,
            "system_id": review.system_id,
            "system_revision": review.system_revision,
            "requirement_baseline_id": review.requirement_baseline_id,
            "chairperson": review.chairperson,
            "opened_at": review.opened_at.isoformat() if review.opened_at else None,
            "closed_at": review.closed_at.isoformat() if review.closed_at else None,
            "decision": {
                "decision_id": decision.id if decision else None,
                "title": decision.title if decision else None,
                "status": decision.status if decision else None,
                "selected_alternative_id": decision.selected_alternative_id if decision else None,
                "decided_by": decision.decided_by if decision else None,
                "decided_at": decision.decided_at.isoformat() if (decision and decision.decided_at) else None,
                "rationale": decision.rationale if decision else {},
            },
            "requirements_count": len(requirements),
            "checkpoints_summary": [
                {"name": c.checkpoint_name, "status": c.status, "notes": c.notes}
                for c in checkpoints
            ],
            "findings_summary": {
                "total": len(findings),
                "open": sum(1 for f in findings if f.status == "OPEN"),
                "waived": sum(1 for f in findings if f.status == "WAIVED"),
                "resolved": sum(1 for f in findings if f.status == "RESOLVED"),
                "critical": sum(1 for f in findings if f.severity in ["CRITICAL", "BLOCKER"]),
            },
            "findings": [
                {"severity": f.severity, "description": f.description, "status": f.status}
                for f in findings
            ],
            "actions_summary": [
                {"owner": a.owner, "description": a.description, "status": a.status, "priority": a.priority}
                for a in actions
            ],
            "questions_summary": [
                {"question": q.question, "status": q.status, "blocking": q.blocking, "answer": q.answer}
                for q in questions
            ],
            "alternatives_count": len(alternatives),
            "tradeoffs_count": len(tradeoffs),
        }
