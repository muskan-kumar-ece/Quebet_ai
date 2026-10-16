from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.decision import (
    EngineeringDecisionRecord,
    EngineeringDecisionAlternative,
    EngineeringDesignReviewSession,
    DecisionStatus,
    AlternativeStatus,
    ReviewStatus,
)
from app.repositories.decision_repo import DecisionRepository
from app.repositories.system_repo import SystemRepository
from app.services.ai.decision.design_review_readiness_service import DesignReviewReadinessService
from app.services.ai.decision.decision_comparison_service import DecisionComparisonService
from app.services.ai.decision.ai_decision_brief_service import AIDecisionBriefService
from app.services.ai.decision.design_review_report_service import DesignReviewReportService


class DecisionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DecisionRepository(db)
        self.system_repo = SystemRepository(db)

    async def select_alternative(
        self,
        decision_id: str,
        alternative_id: str,
        actor: str,
        rationale: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> EngineeringDecisionRecord:
        decision = await self.repo.get_decision(decision_id, tenant_id=tenant_id)
        if not decision:
            raise HTTPException(status_code=404, detail="Decision record not found")

        # 1. Stale Protection check
        system = await self.system_repo.get_system(decision.system_id, tenant_id=tenant_id)
        if not system:
            raise HTTPException(status_code=404, detail="System not found")

        if decision.system_revision != system.revision:
            decision.status = DecisionStatus.STALE.value
            await self.db.commit()
            raise HTTPException(
                status_code=409,
                detail=f"DECISION_STALE: Decision revision {decision.system_revision} does not match current system revision {system.revision}",
            )

        # 2. Check alternative exists
        alternatives = await self.repo.get_alternatives(decision_id)
        selected_alt = next((a for a in alternatives if a.id == alternative_id), None)
        if not selected_alt:
            raise HTTPException(status_code=404, detail="Alternative not found for this decision")

        # 3. Update alternative statuses
        for alt in alternatives:
            if alt.id == alternative_id:
                alt.status = AlternativeStatus.SELECTED_BY_ENGINEER.value
            elif alt.status != AlternativeStatus.ELIMINATED.value:
                alt.status = AlternativeStatus.NOT_SELECTED.value

        # 4. Record human decision
        decision.selected_alternative_id = alternative_id
        decision.decided_by = actor
        decision.decided_at = datetime.now(timezone.utc)
        decision.status = DecisionStatus.DECIDED.value
        decision.rationale = {
            "selected_alternative_id": alternative_id,
            "decision_rationale": rationale.get("decision_rationale", ""),
            "key_requirements": rationale.get("key_requirements", []),
            "key_tradeoffs": rationale.get("key_tradeoffs", []),
            "accepted_unknowns": rationale.get("accepted_unknowns", []),
            "rejected_alternatives": rationale.get("rejected_alternatives", []),
            "verification_plan": rationale.get("verification_plan", ""),
            "freeform_explanation": rationale.get("freeform_explanation", ""),
            "decided_by": actor,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        }

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(self.db)
        await audit_service.record_event(
            project_id=decision.project_id,
            actor_id=actor,
            actor_role="ENGINEER",
            event_type=AuditEventType.DECISION_RECORDED,
            entity_type="DECISION",
            entity_id=decision.id,
            entity_revision=decision.system_revision,
            payload={
                "decision_id": decision.id,
                "system_id": decision.system_id,
                "project_id": decision.project_id,
                "selected_alternative_id": alternative_id,
                "selected_alternative_name": getattr(selected_alt, "name", ""),
                "decision_key": decision.decision_key,
                "decision_type": decision.decision_type,
                "status": decision.status,
                "system_revision": decision.system_revision,
            },
            tenant_id=tenant_id or decision.tenant_id,
            commit=False,
        )

        await self.db.commit()
        await self.db.refresh(decision)
        return decision

    async def close_design_review(
        self,
        review_id: str,
        actor: str,
        tenant_id: Optional[str] = None,
    ) -> EngineeringDesignReviewSession:
        review = await self.repo.get_design_review(review_id, tenant_id=tenant_id)
        if not review:
            raise HTTPException(status_code=404, detail="Design review session not found")

        decision = None
        if review.decision_id:
            decision = await self.repo.get_decision(review.decision_id, tenant_id=tenant_id)

        questions = []
        if review.decision_id:
            questions = await self.repo.get_questions(review.decision_id)

        readiness = DesignReviewReadinessService.evaluate_readiness(
            review=review,
            decision=decision,
            checkpoints=review.checkpoints or [],
            findings=review.findings or [],
            questions=questions,
        )

        if not readiness["can_close_review"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "REVIEW_CLOSURE_BLOCKED",
                    "message": "Cannot close review session due to outstanding blockers",
                    "blockers": readiness["blockers"],
                    "dimensions": readiness["dimensions"],
                },
            )

        review.status = ReviewStatus.CLOSED.value
        review.closed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(review)
        return review

    async def generate_ai_brief(
        self,
        decision_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        decision = await self.repo.get_decision(decision_id, tenant_id=tenant_id)
        if not decision:
            raise HTTPException(status_code=404, detail="Decision record not found")

        requirements = await self.repo.get_requirements_by_system(decision.system_id, tenant_id=tenant_id)
        assumptions = await self.repo.get_assumptions_by_system(decision.system_id, tenant_id=tenant_id)
        alternatives = await self.repo.get_alternatives(decision_id)
        questions = await self.repo.get_questions(decision_id)

        return AIDecisionBriefService.generate_brief(
            decision=decision,
            requirements=requirements,
            assumptions=assumptions,
            alternatives=alternatives,
            findings=[],
            questions=questions,
        )

    async def generate_review_report(
        self,
        review_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        review = await self.repo.get_design_review(review_id, tenant_id=tenant_id)
        if not review:
            raise HTTPException(status_code=404, detail="Design review session not found")

        decision = None
        alternatives = []
        questions = []
        tradeoffs = []
        if review.decision_id:
            decision = await self.repo.get_decision(review.decision_id, tenant_id=tenant_id)
            alternatives = await self.repo.get_alternatives(review.decision_id)
            questions = await self.repo.get_questions(review.decision_id)
            tradeoffs = await self.repo.get_tradeoffs(review.decision_id)

        requirements = await self.repo.get_requirements_by_system(review.system_id, tenant_id=tenant_id)

        return DesignReviewReportService.compile_report(
            review=review,
            decision=decision,
            requirements=requirements,
            checkpoints=review.checkpoints or [],
            findings=review.findings or [],
            actions=review.actions or [],
            questions=questions,
            alternatives=alternatives,
            tradeoffs=tradeoffs,
        )
