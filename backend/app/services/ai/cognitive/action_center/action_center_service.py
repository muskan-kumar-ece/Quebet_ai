import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.project import Project
from app.models.db.circuit import Circuit
from app.models.db.system import EngineeringSystem
from app.models.db.assumption import Assumption
from app.models.db.verification import (
    EngineeringDesignReview,
    EngineeringVerificationRequirement,
    EngineeringEvidence,
    VerificationStatus,
    EvidenceStatus,
    DesignReviewStatus,
)
from app.models.db.decision import (
    EngineeringRequirement,
    RequirementStatus,
    EngineeringAssumption,
    AssumptionStatus,
    AssumptionImpact,
    EngineeringDecisionRecord,
    DecisionStatus,
    EngineeringDecisionQuestion,
    QuestionStatus,
    EngineeringUnknownDisposition,
    UnknownDispositionStatus,
    EngineeringDesignReviewSession,
    ReviewStatus,
    EngineeringReviewFinding,
    EngineeringReviewAction,
    ReviewActionStatus,
)
from app.models.db.cognitive import (
    EngineeringCognitiveWorkflow,
    CognitiveWorkflowStatus,
    EngineeringDecisionBrief,
    DecisionBriefStatus,
)
from app.models.schemas.cognitive import (
    EngineeringActionItem,
    EngineeringActionCenterSummary,
    EngineeringActionCenterResponse,
    ActionCenterCategory,
    EngineeringExplanationRequest,
    EngineeringExplanationResponse,
    EvidenceChainNode,
    HumanActionItem,
)


class EngineeringActionCenterService:
    """
    Phase 2 Wave 9: Cognitive Engineering Action & Closure Center.
    Unified aggregation of outstanding engineering obligations across requirements,
    decisions, evidence, verification, and reviews.

    Core Invariant:
    ACTION CENTER != ENGINEERING SOURCE OF TRUTH
    Existing domain models remain the sole authoritative owners.
    ZERO SYNTHETIC SCORING: Strictly no priority_score, confidence_score, or AI rankings.
    AUTONOMOUS CLOSURE DISABLED: All actions require explicit human engineering authority.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_project_actions(
        self,
        project_id: str,
        tenant_id: str,
        category: Optional[str] = None,
        system_id: Optional[str] = None,
        circuit_id: Optional[str] = None,
    ) -> EngineeringActionCenterResponse:
        """
        Aggregates open engineering obligations across project domains into a unified action center.
        """
        # 1. Tenant Authorization check
        proj_query = select(Project).where(Project.id == project_id, Project.tenant_id == tenant_id)
        proj_res = await self.db.execute(proj_query)
        project = proj_res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Determine current base revision
        base_revision = 1
        if circuit_id:
            c_query = select(Circuit.version).where(Circuit.id == circuit_id, Circuit.tenant_id == tenant_id)
            c_rev = (await self.db.execute(c_query)).scalar_one_or_none()
            if c_rev is not None:
                base_revision = c_rev
        elif system_id:
            s_query = select(EngineeringSystem.revision).where(EngineeringSystem.id == system_id, EngineeringSystem.tenant_id == tenant_id)
            s_rev = (await self.db.execute(s_query)).scalar_one_or_none()
            if s_rev is not None:
                base_revision = s_rev
        else:
            # Check highest circuit version in project
            c_max_query = select(Circuit.version).where(Circuit.project_id == project_id, Circuit.tenant_id == tenant_id).order_by(Circuit.version.desc()).limit(1)
            c_max = (await self.db.execute(c_max_query)).scalar_one_or_none()
            if c_max is not None:
                base_revision = c_max

        actions: List[EngineeringActionItem] = []

        # 2. Aggregate Workflows
        wf_actions = await self._aggregate_workflow_actions(project_id, tenant_id, circuit_id, system_id)
        actions.extend(wf_actions)

        # 3. Aggregate Verification Obligations & Evidence Gaps
        ver_actions = await self._aggregate_verification_actions(project_id, tenant_id, circuit_id, system_id)
        actions.extend(ver_actions)

        # 4. Aggregate System Engineering Requirements
        req_actions = await self._aggregate_requirement_actions(project_id, tenant_id, system_id)
        actions.extend(req_actions)

        # 5. Aggregate Engineering Assumptions (System & Circuit level)
        assump_actions = await self._aggregate_assumption_actions(project_id, tenant_id, system_id, circuit_id)
        actions.extend(assump_actions)

        # 6. Aggregate Decisions, Briefs, & Questions
        dec_actions = await self._aggregate_decision_actions(project_id, tenant_id, system_id)
        actions.extend(dec_actions)

        # 7. Aggregate Design Reviews, Findings, & Review Actions
        rev_actions = await self._aggregate_review_actions(project_id, tenant_id, system_id)
        actions.extend(rev_actions)

        # 8. Compute Summary (Strictly Zero Synthetic Scoring)
        total_actions = len(actions)
        blocked_count = sum(1 for a in actions if a.category == ActionCenterCategory.BLOCKED.value)
        decisions_count = sum(1 for a in actions if a.category == ActionCenterCategory.DECISIONS.value)
        evidence_count = sum(1 for a in actions if a.category == ActionCenterCategory.EVIDENCE.value)
        verification_count = sum(1 for a in actions if a.category == ActionCenterCategory.VERIFICATION.value)
        reviews_count = sum(1 for a in actions if a.category == ActionCenterCategory.REVIEWS.value)
        unknowns_count = sum(1 for a in actions if a.category == ActionCenterCategory.UNKNOWN.value)
        stale_count = sum(1 for a in actions if a.category == ActionCenterCategory.STALE.value)

        categories_present = list({a.category for a in actions})

        summary = EngineeringActionCenterSummary(
            total_actions=total_actions,
            blocked_count=blocked_count,
            decisions_count=decisions_count,
            evidence_count=evidence_count,
            verification_count=verification_count,
            reviews_count=reviews_count,
            unknowns_count=unknowns_count,
            stale_count=stale_count,
            outstanding_categories=categories_present,
        )

        # 9. Compute Canonical Integrity Digest
        digest_content = f"{project_id}:{total_actions}:{blocked_count}:{decisions_count}:{evidence_count}:{verification_count}:{stale_count}"
        integrity_digest = hashlib.sha256(digest_content.encode("utf-8")).hexdigest()

        # 10. Filter by category if requested
        filtered_actions = actions
        if category and category.upper() != ActionCenterCategory.ALL.value:
            cat_upper = category.upper()
            filtered_actions = [a for a in actions if a.category.upper() == cat_upper]

        return EngineeringActionCenterResponse(
            project_id=project_id,
            circuit_id=circuit_id,
            system_id=system_id,
            base_revision=base_revision,
            actions=filtered_actions,
            summary=summary,
            provenance_integrity_digest=integrity_digest,
            created_at=datetime.now(timezone.utc),
        )

    async def get_action_item(
        self,
        source_entity_type: str,
        source_entity_id: str,
        tenant_id: str,
    ) -> EngineeringActionItem:
        """
        Retrieves action item detail for a specific authoritative entity with tenant verification.
        """
        normalized_type = source_entity_type.lower()

        if normalized_type in ["verificationrequirement", "engineeringverificationrequirement", "engineering_verification_requirement", "verification"]:
            vr_query = select(EngineeringVerificationRequirement).where(
                EngineeringVerificationRequirement.id == source_entity_id,
                EngineeringVerificationRequirement.tenant_id == tenant_id,
            )
            vr = (await self.db.execute(vr_query)).scalar_one_or_none()
            if not vr:
                raise HTTPException(status_code=404, detail="Verification requirement not found")

            evi_query = select(EngineeringEvidence).where(
                EngineeringEvidence.verification_requirement_id == vr.id
            )
            evidences = list((await self.db.execute(evi_query)).scalars().all())

            rev_query = select(EngineeringDesignReview).where(EngineeringDesignReview.id == vr.review_id)
            review = (await self.db.execute(rev_query)).scalar_one_or_none()
            circuit_revision = review.circuit_revision if review else 1
            circuit_id = review.circuit_id if review else None
            project_id = review.project_id if review else ""

            return self._build_verification_action(vr, evidences, circuit_revision, circuit_id, project_id)

        elif normalized_type in ["requirement", "engineeringrequirement", "engineering_requirement"]:
            req_query = select(EngineeringRequirement).where(
                EngineeringRequirement.id == source_entity_id,
                EngineeringRequirement.tenant_id == tenant_id,
            )
            req = (await self.db.execute(req_query)).scalar_one_or_none()
            if not req:
                raise HTTPException(status_code=404, detail="Requirement not found")
            return self._build_requirement_action(req)

        elif normalized_type in ["workflow", "engineeringcognitiveworkflow", "engineering_cognitive_workflow", "cognitiveworkflow"]:
            wf_query = select(EngineeringCognitiveWorkflow).where(
                EngineeringCognitiveWorkflow.id == source_entity_id,
                EngineeringCognitiveWorkflow.tenant_id == tenant_id,
            )
            wf = (await self.db.execute(wf_query)).scalar_one_or_none()
            if not wf:
                raise HTTPException(status_code=404, detail="Cognitive workflow not found")
            return self._build_workflow_action(wf)

        elif normalized_type in ["decision", "engineeringdecisionrecord", "engineering_decision_record", "decisionrecord"]:
            dec_query = select(EngineeringDecisionRecord).where(
                EngineeringDecisionRecord.id == source_entity_id,
                EngineeringDecisionRecord.tenant_id == tenant_id,
            )
            dec = (await self.db.execute(dec_query)).scalar_one_or_none()
            if not dec:
                raise HTTPException(status_code=404, detail="Decision record not found")
            return self._build_decision_action(dec, dec.project_id)

        elif normalized_type in ["assumption", "engineeringassumption", "engineering_assumption"]:
            assump_query = select(EngineeringAssumption).where(
                EngineeringAssumption.id == source_entity_id,
                EngineeringAssumption.tenant_id == tenant_id,
            )
            assump = (await self.db.execute(assump_query)).scalar_one_or_none()
            if assump:
                sys_query = select(EngineeringSystem.project_id).where(EngineeringSystem.id == assump.system_id)
                proj_id = (await self.db.execute(sys_query)).scalar_one_or_none() or ""
                return self._build_system_assumption_action(assump, proj_id)

            # Check circuit assumption
            c_asm_query = select(Assumption).where(Assumption.id == source_entity_id)
            c_asm = (await self.db.execute(c_asm_query)).scalar_one_or_none()
            if c_asm:
                circ_query = select(Circuit).where(Circuit.id == c_asm.circuit_id, Circuit.tenant_id == tenant_id)
                circ = (await self.db.execute(circ_query)).scalar_one_or_none()
                if not circ:
                    raise HTTPException(status_code=404, detail="Assumption not found")
                return self._build_circuit_assumption_action(c_asm, circ.project_id)

            raise HTTPException(status_code=404, detail="Assumption not found")

        elif normalized_type in ["finding", "engineeringreviewfinding", "engineering_review_finding", "reviewfinding"]:
            f_query = select(EngineeringReviewFinding).where(
                EngineeringReviewFinding.id == source_entity_id,
            )
            finding = (await self.db.execute(f_query)).scalar_one_or_none()
            if not finding:
                raise HTTPException(status_code=404, detail="Review finding not found")

            # Validate tenant via review session
            sess_query = select(EngineeringDesignReviewSession).where(
                EngineeringDesignReviewSession.id == finding.review_id,
                EngineeringDesignReviewSession.tenant_id == tenant_id,
            )
            sess = (await self.db.execute(sess_query)).scalar_one_or_none()
            if not sess:
                raise HTTPException(status_code=404, detail="Review finding not found")

            sys_query = select(EngineeringSystem.project_id).where(EngineeringSystem.id == sess.system_id)
            proj_id = (await self.db.execute(sys_query)).scalar_one_or_none() or ""
            return self._build_finding_action(finding, proj_id, sess.system_id)

        else:
            raise HTTPException(
                status_code=404,
                detail=f"Unsupported or unknown source entity type: {source_entity_type}",
            )

    async def explain_action(
        self,
        source_entity_type: str,
        source_entity_id: str,
        tenant_id: str,
        request: Optional[EngineeringExplanationRequest] = None,
    ) -> EngineeringExplanationResponse:
        """
        Integrates Wave 7 explanation service to ground why an action exists,
        what caused it, what evidence supports it, and what happens if it remains unresolved.
        """
        # 1. Fetch action item to verify authorization and get context
        action = await self.get_action_item(source_entity_type, source_entity_id, tenant_id)

        # 2. Build structured grounded explanation
        explanation_text = (
            f"Action '{action.title}' is open under category {action.category}. "
            f"Current state: {action.current_status}. "
            f"Required human action: {action.required_human_action}."
        )
        if action.blocking_reason:
            explanation_text += f" Blocking factor: {action.blocking_reason}."

        statement_text = f"Action {action.action_type} on {action.source_entity_type}:{action.source_entity_id}"

        # 3. Build grounded evidence chain
        chain_nodes: List[EvidenceChainNode] = [
            EvidenceChainNode(
                step="1",
                entity_type=action.source_entity_type,
                entity_id=action.source_entity_id,
                description=f"Authoritative source: {action.title}",
                is_physical=False,
                is_calculation=False,
            )
        ]

        human_actions: List[HumanActionItem] = [
            HumanActionItem(
                action_type=action.action_type,
                title=action.title,
                description=action.required_human_action,
                target_entity_type=action.source_entity_type,
                target_entity_id=action.source_entity_id,
                urgency="HIGH" if action.category == "BLOCKED" else "MEDIUM",
            )
        ]

        return EngineeringExplanationResponse(
            category=request.category if request else "WHY",
            statement=statement_text,
            explanation=explanation_text,
            summary=f"Action item {action.action_id} requiring human action: {action.required_human_action}",
            root_cause=action.blocking_reason or "Unresolved engineering obligation requiring validation or decision.",
            authority="INFORMATIONAL_ONLY",
            source_entity_type=action.source_entity_type,
            source_entity_id=action.source_entity_id,
            base_revision=action.revision,
            is_stale=action.is_stale,
            stale_factors=action.stale_factors,
            evidence_refs=[],
            evidence_chain=chain_nodes,
            human_actions=human_actions,
            affected_requirements=[action.source_entity_id] if "requirement" in action.source_entity_type.lower() else [],
            finding_refs=[action.source_entity_id] if "finding" in action.source_entity_type.lower() else [],
            assumption_refs=[action.source_entity_id] if "assumption" in action.source_entity_type.lower() else [],
            decision_refs=[action.source_entity_id] if "decision" in action.source_entity_type.lower() else [],
            downstream_impacts=[f"Blocks progression on {action.source_entity_type}"] if action.category == "BLOCKED" else [],
            generated_at=datetime.now(timezone.utc),
        )

    # -------------------------------------------------------------------------
    # Aggregation Helpers
    # -------------------------------------------------------------------------

    async def _aggregate_workflow_actions(
        self,
        project_id: str,
        tenant_id: str,
        circuit_id: Optional[str],
        system_id: Optional[str],
    ) -> List[EngineeringActionItem]:
        query = select(EngineeringCognitiveWorkflow).where(
            EngineeringCognitiveWorkflow.project_id == project_id,
            EngineeringCognitiveWorkflow.tenant_id == tenant_id,
        )
        if circuit_id:
            query = query.where(EngineeringCognitiveWorkflow.circuit_id == circuit_id)
        if system_id:
            query = query.where(EngineeringCognitiveWorkflow.system_id == system_id)

        workflows = list((await self.db.execute(query)).scalars().all())
        items: List[EngineeringActionItem] = []

        for wf in workflows:
            wf_is_stale = wf.status == CognitiveWorkflowStatus.STALE.value
            if wf.status == CognitiveWorkflowStatus.BLOCKED.value:
                items.append(self._build_workflow_action(wf))
            elif wf.status == CognitiveWorkflowStatus.AWAITING_HUMAN.value:
                items.append(self._build_workflow_action(wf))
            elif wf_is_stale:
                items.append(self._build_workflow_action(wf))

        return items

    def _build_workflow_action(self, wf: EngineeringCognitiveWorkflow) -> EngineeringActionItem:
        wf_is_stale = wf.status == CognitiveWorkflowStatus.STALE.value
        category = ActionCenterCategory.BLOCKED.value if wf.status == CognitiveWorkflowStatus.BLOCKED.value else ActionCenterCategory.DECISIONS.value
        if wf_is_stale:
            category = ActionCenterCategory.STALE.value

        action_type = "BLOCKED_WORKFLOW" if wf.status == CognitiveWorkflowStatus.BLOCKED.value else "DECISION_REQUIRED"
        if wf_is_stale:
            action_type = "STALE_CONTEXT"

        req_action = "Review workflow blockers and resolve design constraints."
        if wf.status == CognitiveWorkflowStatus.AWAITING_HUMAN.value:
            req_action = "Conduct human review and ratify decision or continue workflow."
        elif wf_is_stale:
            req_action = "Refresh workflow baseline against latest circuit revision."

        stale_reasons = []
        if wf_is_stale:
            stale_reasons = ["Baseline superseded by revision increment"]

        return EngineeringActionItem(
            action_id=f"act-wf-{wf.id[:8]}",
            action_type=action_type,
            category=category,
            title=f"Workflow Action: {wf.user_request[:60]}",
            description=f"Cognitive workflow in status '{wf.status}'. Base revision: {wf.base_revision}.",
            source_entity_type="ENGINEERING_COGNITIVE_WORKFLOW",
            source_entity_id=wf.id,
            project_id=wf.project_id,
            circuit_id=wf.circuit_id,
            system_id=wf.system_id,
            revision=wf.base_revision,
            current_status=wf.status,
            required_human_action=req_action,
            blocking_reason="Workflow execution blocked by unresolved dependencies" if wf.status == CognitiveWorkflowStatus.BLOCKED.value else None,
            related_entity_refs=[{"type": "CognitiveWorkflow", "id": wf.id}],
            blocked_by=[],
            depends_on=[],
            is_stale=wf_is_stale,
            stale_factors=stale_reasons,
            route_target=f"/api/v1/cognitive/workflows/{wf.id}",
            created_at=wf.created_at,
        )

    async def _aggregate_verification_actions(
        self,
        project_id: str,
        tenant_id: str,
        circuit_id: Optional[str],
        system_id: Optional[str],
    ) -> List[EngineeringActionItem]:
        rev_query = select(EngineeringDesignReview).where(
            EngineeringDesignReview.project_id == project_id,
            EngineeringDesignReview.tenant_id == tenant_id,
        )
        if circuit_id:
            rev_query = rev_query.where(EngineeringDesignReview.circuit_id == circuit_id)

        reviews = list((await self.db.execute(rev_query)).scalars().all())
        items: List[EngineeringActionItem] = []

        for rev in reviews:
            vr_query = select(EngineeringVerificationRequirement).where(
                EngineeringVerificationRequirement.review_id == rev.id,
                EngineeringVerificationRequirement.tenant_id == tenant_id,
            )
            vrs = list((await self.db.execute(vr_query)).scalars().all())

            for vr in vrs:
                evi_query = select(EngineeringEvidence).where(
                    EngineeringEvidence.verification_requirement_id == vr.id
                )
                evidences = list((await self.db.execute(evi_query)).scalars().all())

                is_open = vr.status not in [VerificationStatus.SATISFIED.value, VerificationStatus.NOT_APPLICABLE.value]
                if is_open:
                    item = self._build_verification_action(vr, evidences, rev.circuit_revision, rev.circuit_id, project_id)
                    items.append(item)

        return items

    def _build_verification_action(
        self,
        vr: EngineeringVerificationRequirement,
        evidences: Optional[List[EngineeringEvidence]] = None,
        circuit_revision: int = 1,
        circuit_id: Optional[str] = None,
        project_id: str = "",
    ) -> EngineeringActionItem:
        evis = evidences or []
        has_evidence = len(evis) > 0
        is_physical_req = vr.method in ["BENCH_TEST", "MEASUREMENT", "LAB_OBSERVATION"] or "thermal" in vr.title.lower()
        has_physical = any(
            e.evidence_type in ["MEASUREMENT", "LAB_OBSERVATION", "TEST_REPORT"]
            or (e.metadata_ or {}).get("is_physical") is True
            for e in evis
        )

        category = ActionCenterCategory.VERIFICATION.value
        action_type = "VERIFICATION_REQUIRED"
        req_action = f"Complete verification method '{vr.method}' under {vr.operating_condition}."

        if vr.status == VerificationStatus.BLOCKED.value:
            category = ActionCenterCategory.BLOCKED.value
            action_type = "VERIFICATION_BLOCKED"
            req_action = "Resolve blocking dependencies before executing verification."
        elif not has_evidence:
            category = ActionCenterCategory.EVIDENCE.value
            action_type = "EVIDENCE_REQUIRED"
            req_action = "Upload and bind supporting engineering evidence."
        elif is_physical_req and not has_physical:
            category = ActionCenterCategory.VERIFICATION.value
            action_type = "VERIFICATION_PHYSICAL_REQUIRED"
            req_action = "Execute physical laboratory bench test (simulation alone is insufficient)."
        elif has_evidence and (has_physical or not is_physical_req):
            category = ActionCenterCategory.VERIFICATION.value
            action_type = "VERIFICATION_CLOSURE"
            req_action = "Review attached evidence and execute formal human verification closure."

        return EngineeringActionItem(
            action_id=f"act-vr-{vr.id[:8]}",
            action_type=action_type,
            category=category,
            title=f"Verification Obligation: {vr.code} - {vr.title}",
            description=f"{vr.reason}. Method: {vr.method}.",
            source_entity_type="ENGINEERING_VERIFICATION_REQUIREMENT",
            source_entity_id=vr.id,
            project_id=project_id,
            circuit_id=circuit_id,
            revision=circuit_revision,
            current_status=vr.status,
            required_human_action=req_action,
            blocking_reason=vr.reason if vr.status == VerificationStatus.BLOCKED.value else None,
            related_entity_refs=[{"type": "EngineeringVerificationRequirement", "id": vr.id}],
            blocked_by=[],
            depends_on=[],
            is_stale=False,
            stale_factors=[],
            route_target=f"/api/v1/cognitive/verification/{vr.id}",
            created_at=vr.created_at,
        )

    async def _aggregate_requirement_actions(
        self,
        project_id: str,
        tenant_id: str,
        system_id: Optional[str],
    ) -> List[EngineeringActionItem]:
        query = select(EngineeringRequirement).where(
            EngineeringRequirement.project_id == project_id,
            EngineeringRequirement.tenant_id == tenant_id,
        )
        if system_id:
            query = query.where(EngineeringRequirement.system_id == system_id)

        reqs = list((await self.db.execute(query)).scalars().all())
        items: List[EngineeringActionItem] = []

        for req in reqs:
            if req.status in [RequirementStatus.VIOLATED.value, RequirementStatus.VERIFICATION_REQUIRED.value, RequirementStatus.ACTIVE.value]:
                items.append(self._build_requirement_action(req))

        return items

    def _build_requirement_action(self, req: EngineeringRequirement) -> EngineeringActionItem:
        is_violated = req.status == RequirementStatus.VIOLATED.value
        category = ActionCenterCategory.BLOCKED.value if is_violated else ActionCenterCategory.VERIFICATION.value
        action_type = "REQUIREMENT_VIOLATION" if is_violated else "REQUIREMENT_VERIFICATION_REQUIRED"
        req_action = "Perform engineering redesign or parameter tuning to satisfy requirement." if is_violated else "Verify requirement with supporting evidence."

        return EngineeringActionItem(
            action_id=f"act-req-{req.id[:8]}",
            action_type=action_type,
            category=category,
            title=f"Requirement: {req.requirement_key} - {req.title}",
            description=req.description,
            source_entity_type="ENGINEERING_REQUIREMENT",
            source_entity_id=req.id,
            project_id=req.project_id,
            system_id=req.system_id,
            revision=req.revision,
            current_status=req.status,
            required_human_action=req_action,
            blocking_reason="Requirement violated by design calculation or physical measurement" if is_violated else None,
            related_entity_refs=[{"type": "EngineeringRequirement", "id": req.id}],
            blocked_by=[],
            depends_on=[],
            is_stale=False,
            stale_factors=[],
            route_target=f"/api/v1/projects/{req.project_id}/requirements",
            created_at=req.created_at,
        )

    async def _aggregate_assumption_actions(
        self,
        project_id: str,
        tenant_id: str,
        system_id: Optional[str],
        circuit_id: Optional[str],
    ) -> List[EngineeringActionItem]:
        items: List[EngineeringActionItem] = []

        # 1. System Assumptions
        sys_query = select(EngineeringSystem.id).where(EngineeringSystem.project_id == project_id, EngineeringSystem.tenant_id == tenant_id)
        if system_id:
            sys_query = sys_query.where(EngineeringSystem.id == system_id)
        sys_ids = list((await self.db.execute(sys_query)).scalars().all())

        if sys_ids:
            assump_query = select(EngineeringAssumption).where(
                EngineeringAssumption.system_id.in_(sys_ids),
                EngineeringAssumption.tenant_id == tenant_id,
            )
            assumptions = list((await self.db.execute(assump_query)).scalars().all())
            for a in assumptions:
                if a.status in [AssumptionStatus.INVALIDATED.value, AssumptionStatus.UNKNOWN.value] or a.impact in [AssumptionImpact.BLOCKING.value, AssumptionImpact.REVIEW_REQUIRED.value]:
                    items.append(self._build_system_assumption_action(a, project_id))

        # 2. Circuit Assumptions
        circ_query = select(Circuit.id).where(Circuit.project_id == project_id, Circuit.tenant_id == tenant_id)
        if circuit_id:
            circ_query = circ_query.where(Circuit.id == circuit_id)
        circ_ids = list((await self.db.execute(circ_query)).scalars().all())

        if circ_ids:
            asm_query = select(Assumption).where(Assumption.circuit_id.in_(circ_ids))
            circuit_assumptions = list((await self.db.execute(asm_query)).scalars().all())
            for ca in circuit_assumptions:
                if not ca.user_confirmed:
                    items.append(self._build_circuit_assumption_action(ca, project_id))

        return items

    def _build_system_assumption_action(self, a: EngineeringAssumption, project_id: str = "") -> EngineeringActionItem:
        is_blocking = a.status == AssumptionStatus.INVALIDATED.value or a.impact == AssumptionImpact.BLOCKING.value
        is_unknown = a.status == AssumptionStatus.UNKNOWN.value
        if is_blocking:
            category = ActionCenterCategory.BLOCKED.value
        elif is_unknown:
            category = ActionCenterCategory.UNKNOWN.value
        else:
            category = ActionCenterCategory.REVIEWS.value

        action_type = "ASSUMPTION_VALIDATION_REQUIRED"

        return EngineeringActionItem(
            action_id=f"act-asm-{a.id[:8]}",
            action_type=action_type,
            category=category,
            title=f"System Assumption: {a.description[:60]}",
            description=a.description,
            source_entity_type="ENGINEERING_ASSUMPTION",
            source_entity_id=a.id,
            project_id=project_id,
            system_id=a.system_id,
            revision=1,
            current_status=a.status,
            required_human_action=f"Validate assumption basis: {a.basis}",
            blocking_reason="Assumption marked as blocking or invalidated" if is_blocking else None,
            related_entity_refs=[{"type": "EngineeringAssumption", "id": a.id}],
            blocked_by=[],
            depends_on=[],
            is_stale=False,
            stale_factors=[],
            route_target=f"/api/v1/systems/{a.system_id}/assumptions",
            created_at=a.created_at,
        )

    def _build_circuit_assumption_action(self, ca: Assumption, project_id: str = "") -> EngineeringActionItem:
        return EngineeringActionItem(
            action_id=f"act-casm-{ca.id[:8]}",
            action_type="ASSUMPTION_UNVALIDATED",
            category=ActionCenterCategory.UNKNOWN.value,
            title=f"Unvalidated Assumption: {ca.field} = {ca.value} {ca.unit or ''}",
            description=f"Assumption source: {ca.source}. Confidence: {ca.confidence}. Rationale: {ca.rationale or 'N/A'}",
            source_entity_type="ENGINEERING_ASSUMPTION",
            source_entity_id=ca.id,
            project_id=project_id,
            circuit_id=ca.circuit_id,
            revision=1,
            current_status="UNVALIDATED",
            required_human_action=f"Validate engineering assumption for parameter '{ca.field}' with measurement or datasheet reference.",
            blocking_reason=None,
            related_entity_refs=[{"type": "Assumption", "id": ca.id}],
            blocked_by=[],
            depends_on=[],
            is_stale=False,
            stale_factors=[],
            route_target=f"/api/v1/circuits/{ca.circuit_id}",
            created_at=ca.created_at,
        )

    async def _aggregate_decision_actions(
        self,
        project_id: str,
        tenant_id: str,
        system_id: Optional[str],
    ) -> List[EngineeringActionItem]:
        # Decisions
        dec_query = select(EngineeringDecisionRecord).where(
            EngineeringDecisionRecord.project_id == project_id,
            EngineeringDecisionRecord.tenant_id == tenant_id,
        )
        if system_id:
            dec_query = dec_query.where(EngineeringDecisionRecord.system_id == system_id)

        decisions = list((await self.db.execute(dec_query)).scalars().all())
        items: List[EngineeringActionItem] = []

        for d in decisions:
            if d.status in [
                DecisionStatus.DRAFT.value,
                DecisionStatus.UNDER_REVIEW.value,
                DecisionStatus.PENDING_DECISION.value,
                DecisionStatus.BLOCKED.value,
                "PENDING",
            ]:
                items.append(self._build_decision_action(d, project_id))

        # Open Decision Questions
        dec_ids = [d.id for d in decisions]
        if dec_ids:
            q_query = select(EngineeringDecisionQuestion).where(
                EngineeringDecisionQuestion.decision_id.in_(dec_ids),
                EngineeringDecisionQuestion.status == QuestionStatus.OPEN.value,
            )
            questions = list((await self.db.execute(q_query)).scalars().all())
            for q in questions:
                if q.blocking:
                    items.append(
                        EngineeringActionItem(
                            action_id=f"act-q-{q.id[:8]}",
                            action_type="DECISION_BLOCKER",
                            category=ActionCenterCategory.BLOCKED.value,
                            title=f"Blocking Question: {q.question[:60]}",
                            description=f"Reason: {q.reason}",
                            source_entity_type="DECISION_QUESTION",
                            source_entity_id=q.id,
                            project_id=project_id,
                            system_id=system_id,
                            revision=1,
                            current_status="OPEN",
                            required_human_action="Answer blocking question to unlock decision ratification.",
                            blocking_reason="Decision question is marked as blocking",
                            related_entity_refs=[{"type": "EngineeringDecisionQuestion", "id": q.id}],
                            blocked_by=[],
                            depends_on=[q.decision_id],
                            is_stale=False,
                            stale_factors=[],
                            route_target=f"/api/v1/cognitive/decision-records/{q.decision_id}",
                            created_at=q.created_at,
                        )
                    )

        return items

    def _build_decision_action(self, d: EngineeringDecisionRecord, project_id: str = "") -> EngineeringActionItem:
        category = ActionCenterCategory.BLOCKED.value if d.status == DecisionStatus.BLOCKED.value else ActionCenterCategory.DECISIONS.value
        action_type = "DECISION_PENDING"

        return EngineeringActionItem(
            action_id=f"act-dec-{d.id[:8]}",
            action_type=action_type,
            category=category,
            title=f"Decision: {d.title}",
            description=d.description,
            source_entity_type="ENGINEERING_DECISION_RECORD",
            source_entity_id=d.id,
            project_id=d.project_id or project_id,
            system_id=d.system_id,
            revision=d.system_revision,
            current_status=d.status,
            required_human_action="Review decision brief, evaluate tradeoffs, and record authoritative human decision.",
            blocking_reason="Decision is in BLOCKED status pending prerequisite resolution" if d.status == DecisionStatus.BLOCKED.value else None,
            related_entity_refs=[{"type": "EngineeringDecisionRecord", "id": d.id}],
            blocked_by=[],
            depends_on=[],
            is_stale=False,
            stale_factors=[],
            route_target=f"/api/v1/cognitive/decision-records/{d.id}",
            created_at=d.created_at,
        )

    async def _aggregate_review_actions(
        self,
        project_id: str,
        tenant_id: str,
        system_id: Optional[str],
    ) -> List[EngineeringActionItem]:
        # Scope systems belonging to this project
        sys_query = select(EngineeringSystem.id).where(
            EngineeringSystem.project_id == project_id,
            EngineeringSystem.tenant_id == tenant_id,
        )
        if system_id:
            sys_query = sys_query.where(EngineeringSystem.id == system_id)
        sys_ids = list((await self.db.execute(sys_query)).scalars().all())
        if not sys_ids:
            return []

        # Check Design Review Sessions for these systems
        rev_query = select(EngineeringDesignReviewSession).where(
            EngineeringDesignReviewSession.system_id.in_(sys_ids),
            EngineeringDesignReviewSession.tenant_id == tenant_id,
        )

        sessions = list((await self.db.execute(rev_query)).scalars().all())
        session_ids = [s.id for s in sessions]
        session_map = {s.id: s.system_id for s in sessions}
        if not session_ids:
            return []

        items: List[EngineeringActionItem] = []

        # Findings
        f_query = select(EngineeringReviewFinding).where(
            EngineeringReviewFinding.review_id.in_(session_ids),
        )
        findings = list((await self.db.execute(f_query)).scalars().all())
        for f in findings:
            if f.severity in ["BLOCKER", "CRITICAL"] and f.status not in ["WAIVED", "RESOLVED"]:
                items.append(self._build_finding_action(f, project_id, session_map.get(f.review_id)))

        # Review Actions
        act_query = select(EngineeringReviewAction).where(
            EngineeringReviewAction.review_id.in_(session_ids),
        )
        actions = list((await self.db.execute(act_query)).scalars().all())
        for act in actions:
            if act.status in [ReviewActionStatus.OPEN.value, ReviewActionStatus.BLOCKED.value]:
                items.append(
                    EngineeringActionItem(
                        action_id=f"act-ra-{act.id[:8]}",
                        action_type="REVIEW_ACTION_REQUIRED",
                        category=ActionCenterCategory.BLOCKED.value if act.status == ReviewActionStatus.BLOCKED.value else ActionCenterCategory.REVIEWS.value,
                        title=f"Review Action: {act.description[:60]}",
                        description=act.description,
                        source_entity_type="REVIEW_ACTION",
                        source_entity_id=act.id,
                        project_id=project_id,
                        system_id=session_map.get(act.review_id),
                        revision=1,
                        current_status=act.status,
                        required_human_action="Execute and resolve design review action item.",
                        blocking_reason="Action item is blocking review session completion" if act.status == ReviewActionStatus.BLOCKED.value else None,
                        related_entity_refs=[{"type": "ReviewAction", "id": act.id}],
                        blocked_by=[],
                        depends_on=[act.review_id],
                        is_stale=False,
                        stale_factors=[],
                        route_target=f"/api/v1/reviews/{act.review_id}/actions",
                        created_at=act.created_at,
                    )
                )

        return items

    def _build_finding_action(self, f: EngineeringReviewFinding, project_id: str = "", system_id: Optional[str] = None) -> EngineeringActionItem:
        return EngineeringActionItem(
            action_id=f"act-fnd-{f.id[:8]}",
            action_type="FINDING_BLOCKER",
            category=ActionCenterCategory.BLOCKED.value,
            title=f"Review Finding: [{f.severity}] {f.description[:60]}",
            description=f.description,
            source_entity_type="ENGINEERING_REVIEW_FINDING",
            source_entity_id=f.id,
            project_id=project_id,
            system_id=system_id,
            revision=1,
            current_status=f.status,
            required_human_action="Waive finding with mandatory rationale or resolve root cause.",
            blocking_reason=f"Finding severity '{f.severity}' blocks design review gating",
            related_entity_refs=[{"type": "EngineeringReviewFinding", "id": f.id}],
            blocked_by=[],
            depends_on=[f.review_id],
            is_stale=False,
            stale_factors=[],
            route_target=f"/api/v1/reviews/{f.review_id}/findings",
            created_at=f.created_at,
        )
