import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db.decision import (
    EngineeringRequirement,
    EngineeringRequirementBaseline,
    EngineeringAssumption,
    EngineeringDecisionRecord,
    EngineeringDecisionAlternative,
    EngineeringTradeoff,
    EngineeringDesignReviewSession,
    EngineeringReviewParticipant,
    EngineeringReviewCheckpoint,
    EngineeringReviewFinding,
    EngineeringReviewAction,
    EngineeringDecisionQuestion,
    EngineeringUnknownDisposition,
    RequirementStatus,
    DecisionStatus,
    AlternativeStatus,
    ReviewStatus,
    QuestionStatus,
    UnknownDispositionStatus,
)


class DecisionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # 1. Requirements
    async def create_requirement(
        self,
        project_id: str,
        system_id: str,
        requirement_key: str,
        title: str,
        description: str,
        category: str = "FUNCTIONAL",
        priority: str = "MEDIUM",
        source_type: str = "INTERNAL_SPEC",
        source_reference: Optional[str] = None,
        parent_requirement_id: Optional[str] = None,
        expression: Optional[Dict[str, Any]] = None,
        created_by: str = "system",
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringRequirement:
        req = EngineeringRequirement(
            id=str(uuid.uuid4()),
            project_id=project_id,
            system_id=system_id,
            parent_requirement_id=parent_requirement_id,
            tenant_id=tenant_id,
            requirement_key=requirement_key,
            title=title,
            description=description,
            category=category,
            priority=priority,
            source_type=source_type,
            source_reference=source_reference,
            status=RequirementStatus.ACTIVE.value,
            revision=1,
            expression=expression or {},
            created_by=created_by,
            metadata_=metadata_ or {},
        )
        self.db.add(req)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(self.db)
        await audit_service.record_event(
            project_id=project_id,
            actor_id=created_by,
            actor_role="ENGINEER",
            event_type=AuditEventType.REQUIREMENT_CREATED,
            entity_type="REQUIREMENT",
            entity_id=req.id,
            entity_revision=req.revision,
            payload={
                "requirement_id": req.id,
                "system_id": req.system_id,
                "requirement_key": req.requirement_key,
                "title": req.title,
                "category": req.category,
                "priority": req.priority,
            },
            tenant_id=tenant_id,
            commit=False,
        )

        await self.db.commit()
        await self.db.refresh(req)
        return req

    async def get_requirement(
        self,
        requirement_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringRequirement]:
        stmt = select(EngineeringRequirement).where(EngineeringRequirement.id == requirement_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringRequirement.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_requirements_by_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringRequirement]:
        stmt = select(EngineeringRequirement).where(EngineeringRequirement.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringRequirement.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def update_requirement(
        self,
        requirement_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> Optional[EngineeringRequirement]:
        req = await self.get_requirement(requirement_id, tenant_id=tenant_id)
        if not req:
            return None

        # Check if structural definition changes require revision bump
        bump_rev = False
        for k, v in updates.items():
            if v is not None:
                if k in ["title", "description", "category", "expression"]:
                    bump_rev = True
                if k == "metadata":
                    req.metadata_ = v
                else:
                    setattr(req, k, v)

        if bump_rev:
            req.revision += 1

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(self.db)
        await audit_service.record_event(
            project_id=req.project_id,
            actor_id=actor_id or "system",
            actor_role="ENGINEER",
            event_type=AuditEventType.REQUIREMENT_UPDATED,
            entity_type="REQUIREMENT",
            entity_id=req.id,
            entity_revision=req.revision,
            payload={
                "requirement_id": req.id,
                "system_id": req.system_id,
                "requirement_key": req.requirement_key,
                "revision": req.revision,
                "updated_fields": list(updates.keys()),
            },
            tenant_id=req.tenant_id,
            commit=False,
        )

        await self.db.commit()
        await self.db.refresh(req)
        return req

    # 2. Requirement Baselines
    async def create_baseline(
        self,
        system_id: str,
        system_revision: int,
        name: str,
        requirement_ids: List[str],
        requirement_revisions: Dict[str, int],
        created_by: str,
        knowledge_snapshot_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> EngineeringRequirementBaseline:
        # Compute deterministic SHA-256 hash
        digest_input = {
            "system_id": system_id,
            "system_revision": system_revision,
            "requirement_ids": sorted(requirement_ids),
            "requirement_revisions": {k: requirement_revisions[k] for k in sorted(requirement_revisions)},
            "knowledge_snapshot_id": knowledge_snapshot_id,
        }
        baseline_hash = hashlib.sha256(
            json.dumps(digest_input, sort_keys=True).encode("utf-8")
        ).hexdigest()

        baseline = EngineeringRequirementBaseline(
            id=str(uuid.uuid4()),
            system_id=system_id,
            tenant_id=tenant_id,
            system_revision=system_revision,
            name=name,
            baseline_hash=baseline_hash,
            requirement_ids=requirement_ids,
            requirement_revisions=requirement_revisions,
            knowledge_snapshot_id=knowledge_snapshot_id,
            created_by=created_by,
        )
        self.db.add(baseline)

        # Resolve system project_id for audit ledger
        from app.models.db.system import EngineeringSystem
        sys_stmt = select(EngineeringSystem).where(EngineeringSystem.id == system_id)
        sys_res = await self.db.execute(sys_stmt)
        system = sys_res.scalar_one_or_none()
        if system and system.project_id:
            from app.services.audit_ledger_service import AuditLedgerService
            from app.models.db.audit_ledger import AuditEventType

            audit_service = AuditLedgerService(self.db)
            await audit_service.record_event(
                project_id=system.project_id,
                actor_id=created_by,
                actor_role="ENGINEER",
                event_type=AuditEventType.REQUIREMENT_BASELINE_CREATED,
                entity_type="REQUIREMENT_BASELINE",
                entity_id=baseline.id,
                entity_revision=system_revision,
                payload={
                    "baseline_id": baseline.id,
                    "system_id": system_id,
                    "system_revision": system_revision,
                    "name": name,
                    "baseline_hash": baseline_hash,
                    "requirement_count": len(requirement_ids),
                },
                tenant_id=tenant_id,
                commit=False,
            )

        await self.db.commit()
        await self.db.refresh(baseline)
        return baseline

    async def get_baseline(
        self,
        baseline_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringRequirementBaseline]:
        stmt = select(EngineeringRequirementBaseline).where(EngineeringRequirementBaseline.id == baseline_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringRequirementBaseline.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_baselines_by_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringRequirementBaseline]:
        stmt = (
            select(EngineeringRequirementBaseline)
            .where(EngineeringRequirementBaseline.system_id == system_id)
            .order_by(EngineeringRequirementBaseline.created_at.desc())
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringRequirementBaseline.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # 3. Assumptions
    async def create_assumption(
        self,
        system_id: str,
        description: str,
        basis: str,
        value: Optional[str] = None,
        unit: Optional[str] = None,
        requirement_id: Optional[str] = None,
        source_id: Optional[str] = None,
        status: str = "ACTIVE",
        impact: str = "REVIEW_REQUIRED",
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringAssumption:
        assump = EngineeringAssumption(
            id=str(uuid.uuid4()),
            system_id=system_id,
            tenant_id=tenant_id,
            requirement_id=requirement_id,
            description=description,
            value=value,
            unit=unit,
            basis=basis,
            source_id=source_id,
            status=status,
            impact=impact,
            metadata_=metadata_ or {},
        )
        self.db.add(assump)
        await self.db.commit()
        await self.db.refresh(assump)
        return assump

    async def get_assumption(
        self,
        assumption_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringAssumption]:
        stmt = select(EngineeringAssumption).where(EngineeringAssumption.id == assumption_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringAssumption.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_assumptions_by_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringAssumption]:
        stmt = select(EngineeringAssumption).where(EngineeringAssumption.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringAssumption.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def update_assumption(
        self,
        assumption_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringAssumption]:
        assump = await self.get_assumption(assumption_id, tenant_id=tenant_id)
        if not assump:
            return None
        for k, v in updates.items():
            if v is not None:
                if k == "metadata":
                    assump.metadata_ = v
                else:
                    setattr(assump, k, v)
        await self.db.commit()
        await self.db.refresh(assump)
        return assump

    # 4. Decisions
    async def create_decision(
        self,
        system_id: str,
        project_id: str,
        title: str,
        decision_key: str,
        description: str,
        system_revision: int,
        decision_type: str = "ARCHITECTURE",
        requirement_baseline_id: Optional[str] = None,
        analysis_id: Optional[str] = None,
        decision_context: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringDecisionRecord:
        dec = EngineeringDecisionRecord(
            id=str(uuid.uuid4()),
            system_id=system_id,
            project_id=project_id,
            tenant_id=tenant_id,
            title=title,
            decision_key=decision_key,
            description=description,
            decision_type=decision_type,
            status=DecisionStatus.DRAFT.value,
            system_revision=system_revision,
            requirement_baseline_id=requirement_baseline_id,
            analysis_id=analysis_id,
            decision_context=decision_context or {},
            rationale={},
            metadata_=metadata_ or {},
        )
        self.db.add(dec)
        await self.db.commit()
        await self.db.refresh(dec)
        return dec

    async def get_decision(
        self,
        decision_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringDecisionRecord]:
        stmt = (
            select(EngineeringDecisionRecord)
            .options(
                selectinload(EngineeringDecisionRecord.alternatives),
                selectinload(EngineeringDecisionRecord.tradeoffs),
                selectinload(EngineeringDecisionRecord.questions),
            )
            .where(EngineeringDecisionRecord.id == decision_id)
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringDecisionRecord.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_decisions_by_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringDecisionRecord]:
        stmt = (
            select(EngineeringDecisionRecord)
            .options(
                selectinload(EngineeringDecisionRecord.alternatives),
                selectinload(EngineeringDecisionRecord.tradeoffs),
            )
            .where(EngineeringDecisionRecord.system_id == system_id)
            .order_by(EngineeringDecisionRecord.created_at.desc())
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringDecisionRecord.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def update_decision(
        self,
        decision_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringDecisionRecord]:
        dec = await self.get_decision(decision_id, tenant_id=tenant_id)
        if not dec:
            return None
        for k, v in updates.items():
            if v is not None:
                if k == "metadata":
                    dec.metadata_ = v
                else:
                    setattr(dec, k, v)
        await self.db.commit()
        await self.db.refresh(dec)
        return dec

    # 5. Alternatives
    async def create_alternative(
        self,
        decision_id: str,
        name: str,
        description: str,
        candidate_id: Optional[str] = None,
        status: str = "CONSIDERED",
        elimination_reason: Optional[str] = None,
        engineering_effects: Optional[Dict[str, Any]] = None,
        requirement_effects: Optional[Dict[str, Any]] = None,
        verification_effects: Optional[Dict[str, Any]] = None,
        failure_effects: Optional[Dict[str, Any]] = None,
        tradeoffs: Optional[Dict[str, Any]] = None,
        unknowns: Optional[List[str]] = None,
        evidence_refs: Optional[List[str]] = None,
    ) -> EngineeringDecisionAlternative:
        alt = EngineeringDecisionAlternative(
            id=str(uuid.uuid4()),
            decision_id=decision_id,
            candidate_id=candidate_id,
            name=name,
            description=description,
            status=status,
            elimination_reason=elimination_reason,
            engineering_effects=engineering_effects or {},
            requirement_effects=requirement_effects or {},
            verification_effects=verification_effects or {},
            failure_effects=failure_effects or {},
            tradeoffs=tradeoffs or {},
            unknowns=unknowns or [],
            evidence_refs=evidence_refs or [],
        )
        self.db.add(alt)
        await self.db.commit()
        await self.db.refresh(alt)
        return alt

    async def get_alternatives(self, decision_id: str) -> List[EngineeringDecisionAlternative]:
        stmt = select(EngineeringDecisionAlternative).where(EngineeringDecisionAlternative.decision_id == decision_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # 6. Tradeoffs
    async def create_tradeoff(
        self,
        decision_id: str,
        dimension: str,
        alternative_a_id: str,
        alternative_b_id: str,
        advantage_a: str,
        disadvantage_a: str,
        advantage_b: str,
        disadvantage_b: str,
        evidence: Optional[Dict[str, Any]] = None,
        unknowns: Optional[List[str]] = None,
    ) -> EngineeringTradeoff:
        troff = EngineeringTradeoff(
            id=str(uuid.uuid4()),
            decision_id=decision_id,
            dimension=dimension,
            alternative_a_id=alternative_a_id,
            alternative_b_id=alternative_b_id,
            advantage_a=advantage_a,
            disadvantage_a=disadvantage_a,
            advantage_b=advantage_b,
            disadvantage_b=disadvantage_b,
            evidence=evidence or {},
            unknowns=unknowns or [],
        )
        self.db.add(troff)
        await self.db.commit()
        await self.db.refresh(troff)
        return troff

    async def get_tradeoffs(self, decision_id: str) -> List[EngineeringTradeoff]:
        stmt = select(EngineeringTradeoff).where(EngineeringTradeoff.decision_id == decision_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # 7. Questions
    async def create_question(
        self,
        decision_id: str,
        question: str,
        reason: str,
        blocking: bool = True,
        review_id: Optional[str] = None,
        affected_object: Optional[str] = None,
        affected_requirement_id: Optional[str] = None,
        affected_analysis_id: Optional[str] = None,
    ) -> EngineeringDecisionQuestion:
        q = EngineeringDecisionQuestion(
            id=str(uuid.uuid4()),
            decision_id=decision_id,
            review_id=review_id,
            question=question,
            reason=reason,
            blocking=blocking,
            affected_object=affected_object,
            affected_requirement_id=affected_requirement_id,
            affected_analysis_id=affected_analysis_id,
            status=QuestionStatus.OPEN.value,
        )
        self.db.add(q)
        await self.db.commit()
        await self.db.refresh(q)
        return q

    async def get_questions(self, decision_id: str) -> List[EngineeringDecisionQuestion]:
        stmt = select(EngineeringDecisionQuestion).where(EngineeringDecisionQuestion.decision_id == decision_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def answer_question(
        self,
        question_id: str,
        answer: str,
        answered_by: str,
        evidence_id: Optional[str] = None,
    ) -> Optional[EngineeringDecisionQuestion]:
        stmt = select(EngineeringDecisionQuestion).where(EngineeringDecisionQuestion.id == question_id)
        res = await self.db.execute(stmt)
        q = res.scalar_one_or_none()
        if not q:
            return None
        q.answer = answer
        q.answered_by = answered_by
        q.answered_at = datetime.now(timezone.utc)
        q.evidence_id = evidence_id
        q.status = QuestionStatus.ANSWERED.value
        await self.db.commit()
        await self.db.refresh(q)
        return q

    # 8. Unknown Dispositions
    async def create_unknown_disposition(
        self,
        decision_id: str,
        unknown_key: str,
        actor: str,
        reason: str,
        affected_requirement_id: Optional[str] = None,
        status: str = "ACCEPTED",
    ) -> EngineeringUnknownDisposition:
        disp = EngineeringUnknownDisposition(
            id=str(uuid.uuid4()),
            decision_id=decision_id,
            unknown_key=unknown_key,
            actor=actor,
            reason=reason,
            affected_requirement_id=affected_requirement_id,
            status=status,
        )
        self.db.add(disp)

        # Stage UNKNOWN_DISPOSED audit event atomically
        dec = await self.get_decision(decision_id)
        if dec and dec.project_id:
            from app.services.audit_ledger_service import AuditLedgerService
            from app.models.db.audit_ledger import AuditEventType

            audit_service = AuditLedgerService(self.db)
            await audit_service.record_event(
                project_id=dec.project_id,
                actor_id=actor,
                actor_role="ENGINEER",
                event_type=AuditEventType.UNKNOWN_DISPOSED,
                entity_type="UNKNOWN_DISPOSITION",
                entity_id=disp.id,
                entity_revision=dec.system_revision,
                payload={
                    "disposition_id": disp.id,
                    "decision_id": decision_id,
                    "unknown_key": unknown_key,
                    "reason": reason,
                    "affected_requirement_id": affected_requirement_id,
                    "status": status,
                },
                tenant_id=dec.tenant_id,
                commit=False,
            )

        await self.db.commit()
        await self.db.refresh(disp)
        return disp

    async def get_unknown_dispositions(self, decision_id: str) -> List[EngineeringUnknownDisposition]:
        stmt = select(EngineeringUnknownDisposition).where(EngineeringUnknownDisposition.decision_id == decision_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # 9. Design Reviews
    async def create_design_review(
        self,
        system_id: str,
        system_revision: int,
        title: str,
        chairperson: str,
        decision_id: Optional[str] = None,
        requirement_baseline_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringDesignReviewSession:
        rev = EngineeringDesignReviewSession(
            id=str(uuid.uuid4()),
            system_id=system_id,
            decision_id=decision_id,
            tenant_id=tenant_id,
            requirement_baseline_id=requirement_baseline_id,
            system_revision=system_revision,
            title=title,
            status=ReviewStatus.OPEN.value,
            chairperson=chairperson,
            metadata_=metadata_ or {},
        )
        self.db.add(rev)
        await self.db.commit()
        await self.db.refresh(rev)
        return rev

    async def get_design_review(
        self,
        review_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringDesignReviewSession]:
        stmt = (
            select(EngineeringDesignReviewSession)
            .options(
                selectinload(EngineeringDesignReviewSession.participants),
                selectinload(EngineeringDesignReviewSession.checkpoints),
                selectinload(EngineeringDesignReviewSession.findings),
                selectinload(EngineeringDesignReviewSession.actions),
            )
            .where(EngineeringDesignReviewSession.id == review_id)
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringDesignReviewSession.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_design_reviews_by_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringDesignReviewSession]:
        stmt = (
            select(EngineeringDesignReviewSession)
            .options(
                selectinload(EngineeringDesignReviewSession.participants),
                selectinload(EngineeringDesignReviewSession.checkpoints),
                selectinload(EngineeringDesignReviewSession.findings),
                selectinload(EngineeringDesignReviewSession.actions),
            )
            .where(EngineeringDesignReviewSession.system_id == system_id)
            .order_by(EngineeringDesignReviewSession.created_at.desc())
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringDesignReviewSession.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def add_participant(
        self,
        review_id: str,
        user_id: str,
        name: str,
        role: str = "ENGINEER",
    ) -> EngineeringReviewParticipant:
        part = EngineeringReviewParticipant(
            id=str(uuid.uuid4()),
            review_id=review_id,
            user_id=user_id,
            name=name,
            role=role,
        )
        self.db.add(part)
        await self.db.commit()
        await self.db.refresh(part)
        return part

    async def add_checkpoint(
        self,
        review_id: str,
        checkpoint_name: str,
        description: str,
        status: str = "UNKNOWN",
        notes: Optional[str] = None,
    ) -> EngineeringReviewCheckpoint:
        chk = EngineeringReviewCheckpoint(
            id=str(uuid.uuid4()),
            review_id=review_id,
            checkpoint_name=checkpoint_name,
            description=description,
            status=status,
            notes=notes,
        )
        self.db.add(chk)
        await self.db.commit()
        await self.db.refresh(chk)
        return chk

    async def update_checkpoint(
        self,
        checkpoint_id: str,
        status: str,
        verified_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Optional[EngineeringReviewCheckpoint]:
        stmt = select(EngineeringReviewCheckpoint).where(EngineeringReviewCheckpoint.id == checkpoint_id)
        res = await self.db.execute(stmt)
        chk = res.scalar_one_or_none()
        if not chk:
            return None
        chk.status = status
        if verified_by:
            chk.verified_by = verified_by
        if notes:
            chk.notes = notes
        await self.db.commit()
        await self.db.refresh(chk)
        return chk

    async def add_finding(
        self,
        review_id: str,
        source_analysis: str,
        severity: str,
        description: str,
        finding_id: Optional[str] = None,
        affected_requirement_id: Optional[str] = None,
        affected_subsystem_id: Optional[str] = None,
    ) -> EngineeringReviewFinding:
        f = EngineeringReviewFinding(
            id=str(uuid.uuid4()),
            review_id=review_id,
            finding_id=finding_id,
            source_analysis=source_analysis,
            severity=severity,
            description=description,
            affected_requirement_id=affected_requirement_id,
            affected_subsystem_id=affected_subsystem_id,
            status="OPEN",
        )
        self.db.add(f)
        await self.db.commit()
        await self.db.refresh(f)
        return f

    async def waive_finding(
        self,
        finding_id: str,
        waived_by: str,
        waiver_rationale: str,
    ) -> Optional[EngineeringReviewFinding]:
        stmt = select(EngineeringReviewFinding).where(EngineeringReviewFinding.id == finding_id)
        res = await self.db.execute(stmt)
        f = res.scalar_one_or_none()
        if not f:
            return None
        f.status = "WAIVED"
        f.waived_by = waived_by
        f.waiver_rationale = waiver_rationale

        # Resolve system and project for audit emission
        from app.models.db.system import EngineeringSystem
        review = await self.get_design_review(f.review_id)
        if review:
            sys_stmt = select(EngineeringSystem).where(EngineeringSystem.id == review.system_id)
            sys_res = await self.db.execute(sys_stmt)
            system = sys_res.scalar_one_or_none()
            if system and system.project_id:
                from app.services.audit_ledger_service import AuditLedgerService
                from app.models.db.audit_ledger import AuditEventType

                audit_service = AuditLedgerService(self.db)
                await audit_service.record_event(
                    project_id=system.project_id,
                    actor_id=waived_by,
                    actor_role="ENGINEER",
                    event_type=AuditEventType.REVIEW_FINDING_WAIVED,
                    entity_type="REVIEW_FINDING",
                    entity_id=f.id,
                    entity_revision=review.system_revision,
                    payload={
                        "finding_id": f.id,
                        "review_id": f.review_id,
                        "source_analysis": f.source_analysis,
                        "severity": f.severity,
                        "waiver_rationale": waiver_rationale,
                        "waived_by": waived_by,
                    },
                    tenant_id=review.tenant_id,
                    commit=False,
                )

        await self.db.commit()
        await self.db.refresh(f)
        return f

    async def add_action(
        self,
        review_id: str,
        description: str,
        owner: str,
        priority: str = "MEDIUM",
        due_at: Optional[datetime] = None,
        linked_requirement_id: Optional[str] = None,
        linked_finding_id: Optional[str] = None,
        linked_verification_requirement_id: Optional[str] = None,
    ) -> EngineeringReviewAction:
        act = EngineeringReviewAction(
            id=str(uuid.uuid4()),
            review_id=review_id,
            description=description,
            owner=owner,
            priority=priority,
            due_at=due_at,
            status="OPEN",
            linked_requirement_id=linked_requirement_id,
            linked_finding_id=linked_finding_id,
            linked_verification_requirement_id=linked_verification_requirement_id,
        )
        self.db.add(act)
        await self.db.commit()
        await self.db.refresh(act)
        return act

    async def update_action(
        self,
        action_id: str,
        updates: Dict[str, Any],
    ) -> Optional[EngineeringReviewAction]:
        stmt = select(EngineeringReviewAction).where(EngineeringReviewAction.id == action_id)
        res = await self.db.execute(stmt)
        act = res.scalar_one_or_none()
        if not act:
            return None
        for k, v in updates.items():
            if v is not None:
                setattr(act, k, v)
        await self.db.commit()
        await self.db.refresh(act)
        return act
