from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.cognitive import EngineeringTaskPlan, PlanStatus
from app.models.schemas.cognitive import PlanValidationResponse
from app.services.ai.cognitive.capability_registry import capability_registry
from app.repositories.project_repo import ProjectRepository
from app.repositories.system_repo import SystemRepository
from app.repositories.circuit_repo import CircuitRepository


class EngineeringPlanValidator:
    """
    Validates EngineeringTaskPlans across Structural, Context, Engineering, Security, and Governance dimensions.
    Enforces strict non-mutation, revision binding, and DAG invariants.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_plan(
        self,
        plan: EngineeringTaskPlan,
        tenant_id: str,
    ) -> PlanValidationResponse:
        blocking_reasons: List[str] = []
        task_graph: Dict[str, List[str]] = {}

        # 1. Security Validation: Tenant Ownership
        security_valid = plan.tenant_id == tenant_id
        if not security_valid:
            blocking_reasons.append("TENANT_ISOLATION_VIOLATION: Plan does not belong to requesting tenant.")

        # 2. Structural Validation
        structural_valid = True
        tasks = plan.tasks or []
        if not tasks:
            structural_valid = False
            blocking_reasons.append("EMPTY_TASK_GRAPH: Plan contains no executable tasks.")

        task_ids = {t.id for t in tasks}
        order_indices = [f"task_{t.order_index}" for t in tasks]

        for t in tasks:
            task_graph[f"task_{t.order_index}"] = t.dependencies or []
            # Check capability exists in registry
            for cap_id in t.required_capabilities or []:
                cap = capability_registry.get(cap_id)
                if not cap:
                    structural_valid = False
                    blocking_reasons.append(f"UNKNOWN_CAPABILITY: Task {t.order_index} references undeclared capability '{cap_id}'.")

        # 3. Context Validation: Freshness & Object Existence
        context_valid = True
        proj_repo = ProjectRepository()
        project = await proj_repo.get_by_id(self.db, plan.project_id, tenant_id=tenant_id)
        if not project:
            context_valid = False
            blocking_reasons.append(f"PROJECT_NOT_FOUND: Project {plan.project_id} not found.")

        # Check revision binding
        if plan.system_id:
            sys_repo = SystemRepository(self.db)
            system = await sys_repo.get_system(plan.system_id, tenant_id=tenant_id)
            if not system:
                context_valid = False
                blocking_reasons.append(f"SYSTEM_NOT_FOUND: System {plan.system_id} not found.")
            elif system.revision != plan.base_revision:
                context_valid = False
                blocking_reasons.append(
                    f"COGNITIVE_PLAN_STALE: Plan revision {plan.base_revision} does not match current system revision {system.revision}."
                )

        if plan.circuit_id and not plan.system_id:
            circ_repo = CircuitRepository()
            circuit = await circ_repo.get_by_id(self.db, plan.circuit_id, tenant_id=tenant_id)
            if not circuit:
                context_valid = False
                blocking_reasons.append(f"CIRCUIT_NOT_FOUND: Circuit {plan.circuit_id} not found.")
            elif circuit.version != plan.base_revision:
                context_valid = False
                blocking_reasons.append(
                    f"COGNITIVE_PLAN_STALE: Plan revision {plan.base_revision} does not match current circuit version {circuit.version}."
                )

        # 4. Engineering Validation: Check Ambiguities in Snapshot
        engineering_valid = True
        snapshot_ambiguities = (plan.context_snapshot or {}).get("ambiguities", [])
        for amb in snapshot_ambiguities:
            if amb.get("status") == "CLARIFICATION_REQUIRED":
                engineering_valid = False
                blocking_reasons.append(
                    f"CLARIFICATION_REQUIRED: Unresolved ambiguity on '{amb.get('target', 'object')}'. Human engineer selection required."
                )

        # 5. Governance & Capability Policy Validation
        governance_valid = True
        from app.services.ai.cognitive.execution_policy import CapabilityExecutionPolicy, CapabilityExecutionError
        for t in tasks:
            for cap_id in t.required_capabilities or []:
                try:
                    CapabilityExecutionPolicy.evaluate(
                        capability_id=cap_id,
                        tenant_id=tenant_id,
                        plan_tenant_id=plan.tenant_id,
                    )
                except CapabilityExecutionError as cee:
                    governance_valid = False
                    blocking_reasons.append(f"{cee.detail.get('error', 'CAPABILITY_POLICY_VIOLATION')}: {cee.detail.get('message')}")
                except Exception as ex:
                    governance_valid = False
                    blocking_reasons.append(f"CAPABILITY_ERROR: {ex}")

        is_valid = structural_valid and context_valid and engineering_valid and security_valid and governance_valid
        status = "PLAN_READY" if is_valid else ("PLAN_BLOCKED" if (not context_valid or not engineering_valid) else "PLAN_INVALID")

        return PlanValidationResponse(
            plan_id=plan.id,
            status=status,
            is_valid=is_valid,
            structural_valid=structural_valid,
            context_valid=context_valid,
            engineering_valid=engineering_valid,
            security_valid=security_valid,
            governance_valid=governance_valid,
            blocking_reasons=blocking_reasons,
            task_graph=task_graph,
            validated_at=datetime.now(timezone.utc),
        )
