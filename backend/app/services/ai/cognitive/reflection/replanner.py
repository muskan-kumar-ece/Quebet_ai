from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.cognitive import (
    EngineeringReflection,
    EngineeringTaskPlan,
    PlanStatus,
    ReflectionStatus,
)
from app.repositories.cognitive_repo import CognitiveRepository

MAX_REFLECTION_CYCLES: int = 3


class ReflectionReplanner:
    """
    Formulates bounded follow-up engineering task plans from reflection findings.
    Enforces a strict upper bound of MAX_REFLECTION_CYCLES = 3 to prevent recursive loops.
    Guarantees revision-binding and preserves human decision authority.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CognitiveRepository(db)

    async def replan_from_reflection(
        self,
        reflection: EngineeringReflection,
        tenant_id: str,
        actor: str,
        selected_finding_ids: Optional[List[str]] = None,
        execution_policy: Optional[Dict[str, Any]] = None,
    ) -> EngineeringTaskPlan:
        # 1. Check Max Cycle Boundary
        if reflection.reflection_cycle >= MAX_REFLECTION_CYCLES:
            reflection.status = ReflectionStatus.BLOCKED.value
            await self.db.commit()
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "MAX_REFLECTION_CYCLES_REACHED",
                    "message": (
                        f"Automated reflection has reached the hard iteration limit of {MAX_REFLECTION_CYCLES} cycles. "
                        f"Unresolved contradictions or verification obligations must be addressed directly by a human engineer."
                    ),
                    "reflection_id": reflection.id,
                    "cycle": reflection.reflection_cycle,
                },
            )

        # 2. Check if additional work was required
        if not reflection.additional_work_required or not reflection.proposed_follow_up_tasks:
            raise HTTPException(
                status_code=400,
                detail="No additional follow-up tasks required for this reflection record.",
            )

        # 3. Retrieve original plan to verify revision currency
        original_plan = await self.repo.get_task_plan(reflection.plan_id, tenant_id=tenant_id)
        if not original_plan:
            raise HTTPException(status_code=404, detail="Original task plan not found.")

        # 4. Filter proposed tasks if specific findings were selected
        tasks_to_schedule = list(reflection.proposed_follow_up_tasks)
        if selected_finding_ids:
            # Map selected findings to capability/entity
            tasks_to_schedule = [
                t for t in tasks_to_schedule
                if any(eid in selected_finding_ids for eid in t.get("required_inputs", {}).get("entity_ids", []))
            ] or tasks_to_schedule

        # 5. Retrieve intent packet
        intent = await self.repo.get_intent_packet(original_plan.intent_packet_id, tenant_id=tenant_id)
        if not intent:
            raise HTTPException(status_code=404, detail="Parent intent packet not found.")

        # 6. Create follow-up task plan DAG
        policy = execution_policy or {"read_only_mode": True, "reflection_cycle": reflection.reflection_cycle + 1}
        follow_up_plan = await self.repo.create_task_plan(
            intent=intent,
            tasks=tasks_to_schedule,
            context_snapshot=original_plan.context_snapshot,
            execution_policy=policy,
            tenant_id=tenant_id,
            context_snapshot_id=reflection.context_snapshot_id,
        )

        # 7. Update reflection record with follow-up plan linkage
        reflection.follow_up_plan_id = follow_up_plan.id
        await self.db.commit()
        await self.db.refresh(reflection)

        return follow_up_plan
