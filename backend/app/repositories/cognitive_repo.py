from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.cognitive import (
    EngineeringIntentPacket,
    EngineeringTaskPlan,
    EngineeringTask,
    EngineeringTaskDependency,
    EngineeringCognitiveExecution,
    EngineeringCognitiveProvenance,
    EngineeringCognitiveContextSnapshot,
    EngineeringReflection,
    EngineeringReasoningFinding,
    EngineeringReflectionProvenance,
    PlanStatus,
)
from app.models.schemas.cognitive import IntentPacketCreate, EngineeringTaskCreate

VALID_PLAN_TRANSITIONS: Dict[str, List[str]] = {
    PlanStatus.DRAFT.value: [
        PlanStatus.RESOLUTION_REQUIRED.value,
        PlanStatus.READY_FOR_VALIDATION.value,
        PlanStatus.READY.value,
        PlanStatus.VALIDATION_FAILED.value,
        PlanStatus.BLOCKED.value,
        PlanStatus.STALE.value,
    ],
    PlanStatus.RESOLUTION_REQUIRED.value: [
        PlanStatus.READY_FOR_VALIDATION.value,
        PlanStatus.STALE.value,
    ],
    PlanStatus.READY_FOR_VALIDATION.value: [
        PlanStatus.READY.value,
        PlanStatus.VALIDATION_FAILED.value,
        PlanStatus.BLOCKED.value,
        PlanStatus.STALE.value,
    ],
    PlanStatus.VALIDATION_FAILED.value: [
        PlanStatus.READY_FOR_VALIDATION.value,
        PlanStatus.READY.value,
        PlanStatus.STALE.value,
    ],
    PlanStatus.READY.value: [
        PlanStatus.EXECUTING.value,
        PlanStatus.STALE.value,
        PlanStatus.BLOCKED.value,
    ],
    PlanStatus.EXECUTING.value: [
        PlanStatus.COMPLETED.value,
        PlanStatus.PARTIAL.value,
        PlanStatus.FAILED.value,
        PlanStatus.STALE.value,
        PlanStatus.BLOCKED.value,
    ],
    PlanStatus.PARTIAL.value: [
        PlanStatus.EXECUTING.value,
        PlanStatus.STALE.value,
    ],
    PlanStatus.FAILED.value: [
        PlanStatus.EXECUTING.value,
        PlanStatus.STALE.value,
    ],
    PlanStatus.BLOCKED.value: [
        PlanStatus.READY_FOR_VALIDATION.value,
        PlanStatus.STALE.value,
    ],
    PlanStatus.COMPLETED.value: [],
    PlanStatus.STALE.value: [],
}


class CognitiveRepository:
    """
    Tenant-isolated repository for Cognitive Intent, Planning, Context Snapshots,
    Execution, and Provenance records.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # 1. Intent Packets
    async def create_intent_packet(
        self,
        payload: IntentPacketCreate,
        tenant_id: str,
    ) -> EngineeringIntentPacket:
        intent = EngineeringIntentPacket(
            tenant_id=tenant_id,
            project_id=payload.project_id,
            system_id=payload.system_id,
            circuit_id=payload.circuit_id,
            raw_request=payload.raw_request,
            intent_type=payload.intent_type,
            intent_subtype=payload.intent_subtype,
            goal=payload.goal,
            requested_action=payload.requested_action,
            entities=payload.entities,
            requirements=payload.requirements,
            constraints=payload.constraints,
            assumptions=payload.assumptions,
            scenarios=payload.scenarios,
            affected_objects=payload.affected_objects,
            urgency=payload.urgency,
            scope=payload.scope,
            context_confidence=payload.context_confidence,
            ambiguities=payload.ambiguities,
            missing_information=payload.missing_information,
            source=payload.source,
        )
        self.db.add(intent)
        await self.db.commit()
        await self.db.refresh(intent)
        return intent

    async def get_intent_packet(
        self,
        intent_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringIntentPacket]:
        stmt = select(EngineeringIntentPacket).where(EngineeringIntentPacket.id == intent_id)
        if tenant_id:
            stmt = stmt.where(EngineeringIntentPacket.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_intents_by_project(
        self,
        project_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringIntentPacket]:
        stmt = (
            select(EngineeringIntentPacket)
            .where(EngineeringIntentPacket.project_id == project_id)
            .order_by(EngineeringIntentPacket.created_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(EngineeringIntentPacket.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # 2. Task Plans
    async def create_task_plan(
        self,
        intent: EngineeringIntentPacket,
        tasks: List[EngineeringTaskCreate],
        context_snapshot: Dict[str, Any],
        execution_policy: Dict[str, Any],
        tenant_id: str,
        context_snapshot_id: Optional[str] = None,
    ) -> EngineeringTaskPlan:
        plan = EngineeringTaskPlan(
            tenant_id=tenant_id,
            intent_packet_id=intent.id,
            project_id=intent.project_id,
            system_id=intent.system_id,
            circuit_id=intent.circuit_id,
            base_revision=context_snapshot.get("base_revision", 1),
            context_snapshot_id=context_snapshot_id,
            context_snapshot=context_snapshot,
            execution_policy=execution_policy,
        )
        self.db.add(plan)
        await self.db.flush()

        for t in tasks:
            task_db = EngineeringTask(
                plan_id=plan.id,
                intent_packet_id=intent.id,
                task_type=t.task_type,
                description=t.description,
                target_objects=t.target_objects,
                dependencies=t.dependencies,
                required_capabilities=t.required_capabilities,
                required_inputs=t.required_inputs,
                expected_outputs=t.expected_outputs,
                order_index=t.order_index,
            )
            self.db.add(task_db)

        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def get_task_plan(
        self,
        plan_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringTaskPlan]:
        stmt = select(EngineeringTaskPlan).where(EngineeringTaskPlan.id == plan_id)
        if tenant_id:
            stmt = stmt.where(EngineeringTaskPlan.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_task_plans_by_project(
        self,
        project_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringTaskPlan]:
        stmt = (
            select(EngineeringTaskPlan)
            .where(EngineeringTaskPlan.project_id == project_id)
            .order_by(EngineeringTaskPlan.created_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(EngineeringTaskPlan.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    def validate_transition(self, current_status: str, new_status: str) -> None:
        """
        Validates state machine transitions for EngineeringTaskPlan.
        Raises HTTPException 400 if the transition is prohibited.
        """
        if current_status == new_status:
            return
        allowed = VALID_PLAN_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_PLAN_TRANSITION",
                    "message": f"Illegal plan transition from '{current_status}' to '{new_status}'.",
                    "allowed_transitions": allowed,
                },
            )

    # 3. Context Snapshots
    async def get_context_snapshot(
        self,
        snapshot_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringCognitiveContextSnapshot]:
        stmt = select(EngineeringCognitiveContextSnapshot).where(
            EngineeringCognitiveContextSnapshot.id == snapshot_id
        )
        if tenant_id:
            stmt = stmt.where(EngineeringCognitiveContextSnapshot.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_context_snapshots_by_project(
        self,
        project_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringCognitiveContextSnapshot]:
        stmt = (
            select(EngineeringCognitiveContextSnapshot)
            .where(EngineeringCognitiveContextSnapshot.project_id == project_id)
            .order_by(EngineeringCognitiveContextSnapshot.created_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(EngineeringCognitiveContextSnapshot.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # 4. Cognitive Executions & Provenance
    async def get_execution(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringCognitiveExecution]:
        stmt = select(EngineeringCognitiveExecution).where(EngineeringCognitiveExecution.id == execution_id)
        if tenant_id:
            stmt = stmt.where(EngineeringCognitiveExecution.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_provenance_by_execution(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringCognitiveProvenance]:
        stmt = select(EngineeringCognitiveProvenance).where(
            EngineeringCognitiveProvenance.cognitive_execution_id == execution_id
        )
        if tenant_id:
            stmt = stmt.where(EngineeringCognitiveProvenance.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    # 5. Cognitive Reflection & Provenance
    async def get_reflection(
        self,
        reflection_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringReflection]:
        from sqlalchemy.orm import selectinload
        stmt = (
            select(EngineeringReflection)
            .where(
                EngineeringReflection.id == reflection_id,
                EngineeringReflection.deleted_at.is_(None),
            )
            .options(selectinload(EngineeringReflection.findings))
        )
        if tenant_id:
            stmt = stmt.where(EngineeringReflection.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_reflections_by_execution(
        self,
        execution_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringReflection]:
        stmt = (
            select(EngineeringReflection)
            .where(
                EngineeringReflection.execution_id == execution_id,
                EngineeringReflection.deleted_at.is_(None),
            )
            .order_by(EngineeringReflection.reflection_cycle.asc())
        )
        if tenant_id:
            stmt = stmt.where(EngineeringReflection.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_reflection_provenance(
        self,
        reflection_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringReflectionProvenance]:
        stmt = select(EngineeringReflectionProvenance).where(
            EngineeringReflectionProvenance.reflection_id == reflection_id,
            EngineeringReflectionProvenance.deleted_at.is_(None),
        )
        if tenant_id:
            stmt = stmt.where(EngineeringReflectionProvenance.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()
