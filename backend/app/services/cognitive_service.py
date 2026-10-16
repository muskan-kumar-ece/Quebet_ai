from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.db.cognitive import (
    EngineeringIntentPacket,
    EngineeringTaskPlan,
    EngineeringCognitiveExecution,
    EngineeringCognitiveProvenance,
    EngineeringCognitiveContextSnapshot,
    PlanStatus,
)
from app.models.schemas.cognitive import (
    IntentResolveRequest,
    IntentPacketCreate,
    TaskPlanCreateRequest,
    PlanValidationResponse,
)
from app.repositories.cognitive_repo import CognitiveRepository
from app.services.ai.cognitive.intent_resolver import IntentResolver
from app.services.ai.cognitive.context_resolver import EngineeringContextResolver
from app.services.ai.cognitive.task_decomposer import TaskDecomposer
from app.services.ai.cognitive.plan_validator import EngineeringPlanValidator
from app.services.ai.cognitive.plan_executor import EngineeringPlanExecutor
from app.services.ai.cognitive.explanation_service import EngineeringExplanationService
from app.services.ai.cognitive.context_snapshot_service import ContextSnapshotService


class CognitiveService:
    """
    Central orchestration service for Phase 2 Wave 1 Cognitive Engineering Layer.
    Coordinates Intent Resolution, Context Resolution, Context Snapshotting,
    Task Decomposition, Validation, and Deterministic Plan Execution.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CognitiveRepository(db)

    async def resolve_and_create_intent(
        self,
        payload: IntentResolveRequest,
        tenant_id: str,
    ) -> EngineeringIntentPacket:
        # 1. Resolve raw natural language into structured packet definition
        intent_create = IntentResolver.resolve_intent(
            raw_request=payload.raw_request,
            project_id=payload.project_id,
            system_id=payload.system_id,
            circuit_id=payload.circuit_id,
            scope=payload.scope,
            urgency=payload.urgency,
        )

        # 2. Persist intent packet
        intent = await self.repo.create_intent_packet(intent_create, tenant_id=tenant_id)

        # 3. Resolve context and update ambiguities against actual circuit/system records
        context_resolver = EngineeringContextResolver(self.db)
        context = await context_resolver.resolve_context(intent, tenant_id=tenant_id)

        if not context.get("is_valid", False):
            intent.status = "PLANNING_BLOCKED"
        elif any(a.get("status") == "CLARIFICATION_REQUIRED" for a in context.get("ambiguities", [])):
            intent.status = "CLARIFICATION_REQUIRED"

        intent.ambiguities = list(context.get("ambiguities", intent.ambiguities or []))
        flag_modified(intent, "ambiguities")
        await self.db.commit()
        await self.db.refresh(intent)
        return intent

    async def create_plan(
        self,
        payload: TaskPlanCreateRequest,
        tenant_id: str,
    ) -> EngineeringTaskPlan:
        # 1. Retrieve intent packet
        intent = await self.repo.get_intent_packet(payload.intent_packet_id, tenant_id=tenant_id)
        if not intent:
            raise HTTPException(status_code=404, detail="Intent packet not found or access denied.")

        # 2. Deterministically resolve context
        context_resolver = EngineeringContextResolver(self.db)
        context = await context_resolver.resolve_context(intent, tenant_id=tenant_id)
        if not context.get("is_valid", False):
            raise HTTPException(status_code=400, detail=context.get("message", "Invalid engineering context."))

        # 3. Create canonical context snapshot
        snapshot_svc = ContextSnapshotService(self.db)
        snapshot = await snapshot_svc.create_snapshot(intent=intent, tenant_id=tenant_id)

        # 4. Decompose into directed acyclic task graph
        tasks = TaskDecomposer.decompose(intent, context)

        # 5. Persist plan with context_snapshot_id binding
        plan = await self.repo.create_task_plan(
            intent=intent,
            tasks=tasks,
            context_snapshot=context,
            execution_policy=payload.execution_policy,
            tenant_id=tenant_id,
            context_snapshot_id=snapshot.id,
        )
        return plan

    async def validate_plan(
        self,
        plan_id: str,
        tenant_id: str,
    ) -> PlanValidationResponse:
        plan = await self.repo.get_task_plan(plan_id, tenant_id=tenant_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Task plan not found or access denied.")

        validator = EngineeringPlanValidator(self.db)
        val_res = await validator.validate_plan(plan, tenant_id=tenant_id)

        mapped_status = PlanStatus.READY.value if val_res.is_valid else (
            PlanStatus.BLOCKED.value if (not val_res.context_valid or not val_res.engineering_valid) else PlanStatus.VALIDATION_FAILED.value
        )

        # Validate state machine transition
        self.repo.validate_transition(plan.status, mapped_status)

        plan.status = mapped_status
        plan.blocking_reasons = val_res.blocking_reasons
        plan.validated_at = val_res.validated_at
        await self.db.commit()

        return val_res

    async def execute_plan(
        self,
        plan_id: str,
        tenant_id: str,
        actor: str,
        actor_permissions: Optional[List[str]] = None,
    ) -> EngineeringCognitiveExecution:
        plan = await self.repo.get_task_plan(plan_id, tenant_id=tenant_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Task plan not found or access denied.")

        executor = EngineeringPlanExecutor(self.db)
        return await executor.execute_plan(
            plan=plan,
            tenant_id=tenant_id,
            actor=actor,
            actor_permissions=actor_permissions,
        )

    async def get_context_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> EngineeringCognitiveContextSnapshot:
        snapshot = await self.repo.get_context_snapshot(snapshot_id, tenant_id=tenant_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Context snapshot not found or access denied.")
        return snapshot

    async def list_context_snapshots(
        self,
        project_id: str,
        tenant_id: str,
    ) -> List[EngineeringCognitiveContextSnapshot]:
        return await self.repo.list_context_snapshots_by_project(project_id, tenant_id=tenant_id)

    async def get_execution_with_provenance(
        self,
        execution_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        execution = await self.repo.get_execution(execution_id, tenant_id=tenant_id)
        if not execution:
            raise HTTPException(status_code=404, detail="Cognitive execution not found or access denied.")

        provenance = await self.repo.get_provenance_by_execution(execution_id, tenant_id=tenant_id)
        return {
            "execution": execution,
            "provenance": provenance,
        }

    # ========================================================================
    # 5. COGNITIVE REFLECTION & ENGINEERING REASONING
    # ========================================================================

    async def reflect_on_execution(
        self,
        execution_id: str,
        tenant_id: str,
        user_focus: Optional[str] = None,
        force_reevaluation: bool = False,
    ) -> Dict[str, Any]:
        from app.services.ai.cognitive.reflection.reflection_service import EngineeringReflectionService
        reflector = EngineeringReflectionService(self.db)
        reflection = await reflector.reflect_on_execution(
            execution_id=execution_id,
            tenant_id=tenant_id,
            user_focus=user_focus,
            force_reevaluation=force_reevaluation,
        )
        provenance = await reflector.get_reflection_provenance(reflection.id, tenant_id=tenant_id)
        return {
            "reflection": reflection,
            "provenance": provenance,
        }

    async def get_reflection_with_provenance(
        self,
        reflection_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        from app.services.ai.cognitive.reflection.reflection_service import EngineeringReflectionService
        reflector = EngineeringReflectionService(self.db)
        reflection = await reflector.get_reflection(reflection_id, tenant_id=tenant_id)
        if not reflection:
            raise HTTPException(status_code=404, detail="Reflection record not found or access denied.")
        provenance = await reflector.get_reflection_provenance(reflection_id, tenant_id=tenant_id)
        return {
            "reflection": reflection,
            "provenance": provenance,
        }

    async def list_reflections_for_execution(
        self,
        execution_id: str,
        tenant_id: str,
    ) -> List[Any]:
        from app.services.ai.cognitive.reflection.reflection_service import EngineeringReflectionService
        reflector = EngineeringReflectionService(self.db)
        return await reflector.list_reflections_for_execution(execution_id, tenant_id=tenant_id)

    async def replan_from_reflection(
        self,
        reflection_id: str,
        tenant_id: str,
        actor: str,
        selected_finding_ids: Optional[List[str]] = None,
        execution_policy: Optional[Dict[str, Any]] = None,
    ) -> EngineeringTaskPlan:
        from app.services.ai.cognitive.reflection.reflection_service import EngineeringReflectionService
        reflector = EngineeringReflectionService(self.db)
        return await reflector.replan_from_reflection(
            reflection_id=reflection_id,
            tenant_id=tenant_id,
            actor=actor,
            selected_finding_ids=selected_finding_ids,
            execution_policy=execution_policy,
        )

    # ========================================================================
    # 6. CONTROLLED ENGINEERING DECISION PREPARATION
    # ========================================================================

    async def create_decision_brief(
        self,
        payload: Any,
        tenant_id: str,
        actor: str,
    ) -> Dict[str, Any]:
        from app.services.ai.cognitive.decision.decision_brief_service import EngineeringDecisionBriefService
        service = EngineeringDecisionBriefService(self.db)
        brief = await service.create_decision_brief(payload, tenant_id=tenant_id, actor=actor)
        provenance = await service.get_decision_brief_provenance(brief.id, tenant_id=tenant_id)
        return {
            "brief": brief,
            "provenance": provenance,
        }

    async def get_decision_brief_with_provenance(
        self,
        brief_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        from app.services.ai.cognitive.decision.decision_brief_service import EngineeringDecisionBriefService
        service = EngineeringDecisionBriefService(self.db)
        brief = await service.get_decision_brief(brief_id, tenant_id=tenant_id)
        if not brief:
            raise HTTPException(status_code=404, detail="Decision brief not found or access denied.")
        provenance = await service.get_decision_brief_provenance(brief.id, tenant_id=tenant_id)
        return {
            "brief": brief,
            "provenance": provenance,
        }

    async def list_decision_briefs_by_project(
        self,
        project_id: str,
        tenant_id: str,
    ) -> List[Any]:
        from app.services.ai.cognitive.decision.decision_brief_service import EngineeringDecisionBriefService
        service = EngineeringDecisionBriefService(self.db)
        return await service.list_decision_briefs_by_project(project_id, tenant_id=tenant_id)

    async def record_human_decision(
        self,
        brief_id: str,
        payload: Any,
        tenant_id: str,
        actor: str,
    ) -> Dict[str, Any]:
        from app.services.ai.cognitive.decision.decision_brief_service import EngineeringDecisionBriefService
        service = EngineeringDecisionBriefService(self.db)
        return await service.record_human_decision(
            brief_id=brief_id,
            payload=payload,
            tenant_id=tenant_id,
            actor=actor,
        )
