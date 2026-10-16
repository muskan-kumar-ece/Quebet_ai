from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db.cognitive import (
    EngineeringReflection,
    EngineeringReasoningFinding,
    EngineeringReflectionProvenance,
    EngineeringCognitiveExecution,
    EngineeringTaskPlan,
    EngineeringCognitiveContextSnapshot,
    ReflectionStatus,
)
from app.repositories.cognitive_repo import CognitiveRepository
from app.services.ai.cognitive.reflection.sufficiency_engine import ResultSufficiencyEngine
from app.services.ai.cognitive.reflection.replanner import ReflectionReplanner


class EngineeringReflectionService:
    """
    Central orchestration service for Cognitive Reflection & Engineering Reasoning.
    Evaluates completed deterministic executions for contradictions, unknowns,
    evidence gaps, and requirement/verification compliance.
    Calculates canonical SHA-256 integrity digests and records provenance.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CognitiveRepository(db)

    async def reflect_on_execution(
        self,
        execution_id: str,
        tenant_id: str,
        user_focus: Optional[str] = None,
        force_reevaluation: bool = False,
    ) -> EngineeringReflection:
        # 1. Retrieve execution record
        execution = await self.repo.get_execution(execution_id, tenant_id=tenant_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Execution record not found or access denied.")

        # 2. Retrieve bound task plan
        plan = await self.repo.get_task_plan(execution.plan_id, tenant_id=tenant_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Associated task plan not found.")

        # 3. Retrieve context snapshot if bound
        context_payload: Dict[str, Any] = {}
        if plan.context_snapshot_id:
            snapshot = await self.repo.get_context_snapshot(plan.context_snapshot_id, tenant_id=tenant_id)
            if snapshot:
                context_payload = snapshot.context_payload or {}
        elif plan.context_snapshot:
            context_payload = plan.context_snapshot

        # 4. Extract authoritative inputs for evaluation
        requirements = context_payload.get("requirements", [])
        if not requirements and execution.requirements_affected:
            requirements = execution.requirements_affected

        assumptions = context_payload.get("assumptions", [])
        evidence_items = context_payload.get("evidence", [])
        verification_impacts = execution.verification_impacts or []
        traceability_records = execution.traceability or []

        # Determine existing reflection cycle count
        prior_reflections = await self.list_reflections_for_execution(execution_id, tenant_id=tenant_id)
        cycle_number = len(prior_reflections) + 1

        evaluated_at = datetime.now(timezone.utc)

        # 5. Execute Sufficiency Engine
        eval_result = ResultSufficiencyEngine.evaluate(
            execution_results=execution.results or [],
            execution_findings=execution.findings or [],
            execution_unknowns=execution.unknowns or [],
            requirements=requirements,
            assumptions=assumptions,
            verification_impacts=verification_impacts,
            traceability_records=traceability_records,
            evidence_items=evidence_items,
            context_payload=context_payload,
            base_revision=plan.base_revision,
        )

        completed_at = datetime.now(timezone.utc)

        # 6. Compute Canonical SHA-256 Digests
        # Input digest: canonical JSON over execution state and parameters
        input_data = {
            "execution_id": execution.id,
            "plan_id": plan.id,
            "context_snapshot_id": plan.context_snapshot_id,
            "base_revision": plan.base_revision,
            "cycle_number": cycle_number,
            "user_focus": user_focus or "",
            "results_count": len(execution.results or []),
        }
        input_canonical = json.dumps(input_data, sort_keys=True)
        input_digest = hashlib.sha256(input_canonical.encode("utf-8")).hexdigest()

        # Output digest: canonical JSON over findings and statuses
        output_data = {
            "status": eval_result["status"],
            "has_contradictions": eval_result["has_contradictions"],
            "has_unresolved_unknowns": eval_result["has_unresolved_unknowns"],
            "has_evidence_gaps": eval_result["has_evidence_gaps"],
            "has_requirement_gaps": eval_result["has_requirement_gaps"],
            "has_verification_gaps": eval_result["has_verification_gaps"],
            "additional_work_required": eval_result["additional_work_required"],
            "finding_count": len(eval_result["findings"]),
            "findings_summary": [f"{f['finding_type']}:{f['title']}" for f in eval_result["findings"]],
        }
        output_canonical = json.dumps(output_data, sort_keys=True)
        output_digest = hashlib.sha256(output_canonical.encode("utf-8")).hexdigest()

        # 7. Persist EngineeringReflection
        reflection = EngineeringReflection(
            tenant_id=tenant_id,
            project_id=plan.project_id,
            system_id=plan.system_id,
            circuit_id=plan.circuit_id,
            base_revision=plan.base_revision,
            execution_id=execution.id,
            plan_id=plan.id,
            context_snapshot_id=plan.context_snapshot_id,
            status=eval_result["status"],
            reflection_cycle=cycle_number,
            summary=eval_result["summary"],
            has_contradictions=eval_result["has_contradictions"],
            has_unresolved_unknowns=eval_result["has_unresolved_unknowns"],
            has_evidence_gaps=eval_result["has_evidence_gaps"],
            has_requirement_gaps=eval_result["has_requirement_gaps"],
            has_verification_gaps=eval_result["has_verification_gaps"],
            additional_work_required=eval_result["additional_work_required"],
            proposed_follow_up_tasks=eval_result["proposed_follow_up_tasks"],
            evaluated_at=evaluated_at,
            completed_at=completed_at,
        )
        self.db.add(reflection)
        await self.db.flush()

        # 8. Persist EngineeringReasoningFinding items
        for item in eval_result["findings"]:
            finding_obj = EngineeringReasoningFinding(
                reflection_id=reflection.id,
                finding_type=item["finding_type"],
                severity=item["severity"],
                title=item["title"],
                description=item["description"],
                affected_entity_type=item["affected_entity_type"],
                affected_entity_id=item.get("affected_entity_id"),
                evidence_references=item.get("evidence_references", []),
                deterministic_facts=item.get("deterministic_facts", {}),
                recommended_remedy=item.get("recommended_remedy"),
                follow_up_capability=item.get("follow_up_capability"),
            )
            self.db.add(finding_obj)

        # 9. Persist EngineeringReflectionProvenance
        provenance = EngineeringReflectionProvenance(
            tenant_id=tenant_id,
            reflection_id=reflection.id,
            execution_id=execution.id,
            plan_id=plan.id,
            context_snapshot_id=plan.context_snapshot_id,
            project_id=plan.project_id,
            base_revision=plan.base_revision,
            input_digest=input_digest,
            output_digest=output_digest,
            prompt_id="engineering_reflection",
            prompt_version="v1.0.0",
            rule_set_version="v1.0.0",
            engine_versions={
                "contradiction_engine": "v1.0.0",
                "unknown_service": "v1.0.0",
                "requirement_reflection": "v1.0.0",
                "verification_reflection": "v1.0.0",
                "evidence_sufficiency": "v1.0.0",
                "sufficiency_engine": "v1.0.0",
            },
        )
        self.db.add(provenance)

        await self.db.commit()
        await self.db.refresh(reflection)

        return await self.get_reflection(reflection.id, tenant_id=tenant_id)

    async def get_reflection(self, reflection_id: str, tenant_id: str) -> Optional[EngineeringReflection]:
        stmt = (
            select(EngineeringReflection)
            .where(
                EngineeringReflection.id == reflection_id,
                EngineeringReflection.tenant_id == tenant_id,
                EngineeringReflection.deleted_at.is_(None),
            )
            .options(selectinload(EngineeringReflection.findings))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_reflections_for_execution(
        self,
        execution_id: str,
        tenant_id: str,
    ) -> List[EngineeringReflection]:
        stmt = (
            select(EngineeringReflection)
            .where(
                EngineeringReflection.execution_id == execution_id,
                EngineeringReflection.tenant_id == tenant_id,
                EngineeringReflection.deleted_at.is_(None),
            )
            .order_by(EngineeringReflection.reflection_cycle.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_reflection_provenance(
        self,
        reflection_id: str,
        tenant_id: str,
    ) -> Optional[EngineeringReflectionProvenance]:
        stmt = select(EngineeringReflectionProvenance).where(
            EngineeringReflectionProvenance.reflection_id == reflection_id,
            EngineeringReflectionProvenance.tenant_id == tenant_id,
            EngineeringReflectionProvenance.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def replan_from_reflection(
        self,
        reflection_id: str,
        tenant_id: str,
        actor: str,
        selected_finding_ids: Optional[List[str]] = None,
        execution_policy: Optional[Dict[str, Any]] = None,
    ) -> EngineeringTaskPlan:
        reflection = await self.get_reflection(reflection_id, tenant_id=tenant_id)
        if not reflection:
            raise HTTPException(status_code=404, detail="Reflection record not found or access denied.")

        replanner = ReflectionReplanner(self.db)
        return await replanner.replan_from_reflection(
            reflection=reflection,
            tenant_id=tenant_id,
            actor=actor,
            selected_finding_ids=selected_finding_ids,
            execution_policy=execution_policy,
        )
