from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.models.db.decision import (
    EngineeringDecisionRecord,
    EngineeringDecisionAlternative,
    EngineeringRequirement,
    EngineeringAssumption,
    EngineeringReviewFinding,
    EngineeringDecisionQuestion,
)


class AIDecisionBriefService:
    """
    Generates a structured, informational AI Decision Brief summarizing requirements,
    alternatives, trade-offs, critical findings, and verification gaps.

    STRICT GOVERNANCE BOUNDARY:
    1. Origin is explicitly labeled origin = "AI_GENERATED".
    2. Prohibited from declaring a "WINNER", "BEST CHOICE", or "RECOMMENDED DECISION".
    3. The brief is informational for the review session; only the human engineer
       possesses the authority to select an alternative or close a review.
    """

    @classmethod
    def generate_brief(
        cls,
        decision: EngineeringDecisionRecord,
        requirements: List[EngineeringRequirement],
        assumptions: List[EngineeringAssumption],
        alternatives: List[EngineeringDecisionAlternative],
        findings: List[EngineeringReviewFinding],
        questions: List[EngineeringDecisionQuestion],
        evidence_records: Optional[List[Any]] = None,
        model_name: str = "quebet-decision-intelligence-v1",
    ) -> Dict[str, Any]:
        evidence_records = evidence_records or []

        # Summarize requirements
        req_summary = [
            {
                "key": r.requirement_key,
                "title": r.title,
                "category": r.category,
                "priority": r.priority,
                "status": r.status,
            }
            for r in requirements
        ]

        # Summarize alternatives
        alt_summary = [
            {
                "id": a.id,
                "name": a.name,
                "status": a.status,
                "elimination_reason": a.elimination_reason,
                "key_effects": a.engineering_effects,
                "unknowns_count": len(a.unknowns),
            }
            for a in alternatives
        ]

        # Critical findings
        crit_findings = [
            {
                "id": f.id,
                "severity": f.severity,
                "source": f.source_analysis,
                "description": f.description,
                "status": f.status,
            }
            for f in findings if f.severity == "CRITICAL"
        ]

        # Open questions
        blocking_questions = [
            {
                "id": q.id,
                "question": q.question,
                "reason": q.reason,
                "blocking": q.blocking,
            }
            for q in questions if q.status == "OPEN"
        ]

        return {
            "origin": "AI_GENERATED",
            "informational_only": True,
            "provenance": {
                "origin": "AI_GENERATED",
                "model_identifier": model_name,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "prompt_version": "1.0.0",
                "authority": "INFORMATIONAL_ONLY_HUMAN_DECISION_REQUIRED",
            },
            "decision_key": decision.decision_key,
            "title": decision.title,
            "executive_summary": (
                f"Engineering Decision Context for '{decision.title}'. "
                f"Evaluating {len(alternatives)} alternatives against {len(requirements)} requirements "
                f"under system revision {decision.system_revision}."
            ),
            "requirements_summary": req_summary,
            "assumptions_summary": [
                {"description": a.description, "impact": a.impact, "status": a.status}
                for a in assumptions
            ],
            "alternatives_summary": alt_summary,
            "critical_findings": crit_findings,
            "blocking_questions": blocking_questions,
            "evidence_count": len(evidence_records),
            "disclaimer": "This document is AI-generated for engineering review. AI cannot select alternatives or close reviews.",
        }
