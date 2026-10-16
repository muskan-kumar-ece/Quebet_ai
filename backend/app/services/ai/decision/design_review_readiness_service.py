from typing import Any, Dict, List, Optional
from app.models.db.decision import (
    EngineeringDesignReviewSession,
    EngineeringDecisionRecord,
    EngineeringReviewCheckpoint,
    EngineeringReviewFinding,
    EngineeringDecisionQuestion,
)


class DesignReviewReadinessService:
    """
    Evaluates design review readiness across independent engineering dimensions.

    STRICT PRINCIPLE: Zero composite readiness scores.
    Returns structured categorical states (READY, NOT_READY, BLOCKED, UNKNOWN)
    so the engineering team sees exactly what prevents closure.
    """

    @classmethod
    def evaluate_readiness(
        cls,
        review: EngineeringDesignReviewSession,
        decision: Optional[EngineeringDecisionRecord],
        checkpoints: List[EngineeringReviewCheckpoint],
        findings: List[EngineeringReviewFinding],
        questions: List[EngineeringDecisionQuestion],
        evidence_records: Optional[List[Any]] = None,
        verification_requirements: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        evidence_records = evidence_records or []
        verification_requirements = verification_requirements or []

        readiness_dimensions: Dict[str, str] = {}
        blockers: List[str] = []

        # 1. Checkpoints completeness
        if not checkpoints:
            readiness_dimensions["checkpoints"] = "NOT_READY"
        else:
            failed_ck = [c for c in checkpoints if c.status == "FAIL"]
            unknown_ck = [c for c in checkpoints if c.status == "UNKNOWN"]
            if failed_ck:
                readiness_dimensions["checkpoints"] = "BLOCKED"
                blockers.append(f"{len(failed_ck)} review checkpoints are failing")
            elif unknown_ck:
                readiness_dimensions["checkpoints"] = "UNKNOWN"
            else:
                readiness_dimensions["checkpoints"] = "READY"

        # 2. Critical Findings & Waivers
        unresolved_critical = [
            f for f in findings
            if f.severity in ["CRITICAL", "BLOCKER"] and f.status in ["OPEN", "ACTION_REQUIRED"]
        ]
        if unresolved_critical:
            readiness_dimensions["findings"] = "BLOCKED"
            blockers.append(f"{len(unresolved_critical)} critical/blocker engineering findings remain open without waiver")
        elif any(f.status in ["OPEN", "ACTION_REQUIRED"] for f in findings):
            readiness_dimensions["findings"] = "NOT_READY"
        else:
            readiness_dimensions["findings"] = "READY"

        # 3. Open Blocking Questions
        unanswered_blocking_q = [
            q for q in questions
            if q.blocking and q.status == "OPEN"
        ]
        if unanswered_blocking_q:
            readiness_dimensions["questions"] = "BLOCKED"
            blockers.append(f"{len(unanswered_blocking_q)} blocking engineering questions remain unanswered")
        elif any(q.status == "OPEN" for q in questions):
            readiness_dimensions["questions"] = "NOT_READY"
        else:
            readiness_dimensions["questions"] = "READY"

        # 4. Evidence Sufficiency
        unverified_ev = [e for e in evidence_records if getattr(e, "status", "") != "VERIFIED"]
        if not evidence_records and verification_requirements:
            readiness_dimensions["evidence"] = "NOT_READY"
        elif unverified_ev:
            readiness_dimensions["evidence"] = "PARTIAL"
        else:
            readiness_dimensions["evidence"] = "READY"

        # 5. Verification Requirements
        unsatisfied_vr = [
            vr for vr in verification_requirements
            if getattr(vr, "status", "") != "SATISFIED"
        ]
        if unsatisfied_vr:
            readiness_dimensions["verification"] = "NOT_READY"
        else:
            readiness_dimensions["verification"] = "READY"

        # 6. Decision Status
        if not decision:
            readiness_dimensions["decision"] = "NOT_READY"
        elif decision.status in ["STALE", "BLOCKED"]:
            readiness_dimensions["decision"] = "BLOCKED"
            blockers.append(f"Decision is {decision.status}")
        elif decision.status in ["DECIDED", "IMPLEMENTED", "CLOSED"]:
            readiness_dimensions["decision"] = "READY"
        else:
            readiness_dimensions["decision"] = "NOT_READY"

        # Overall Status
        if blockers or any(v == "BLOCKED" for v in readiness_dimensions.values()):
            overall_status = "BLOCKED"
        elif any(v in ["NOT_READY", "PARTIAL", "UNKNOWN"] for v in readiness_dimensions.values()):
            overall_status = "NOT_READY"
        else:
            overall_status = "READY"

        return {
            "review_id": review.id,
            "overall_status": overall_status,
            "can_close_review": overall_status != "BLOCKED" and len(blockers) == 0,
            "blockers": blockers,
            "dimensions": readiness_dimensions,
        }
