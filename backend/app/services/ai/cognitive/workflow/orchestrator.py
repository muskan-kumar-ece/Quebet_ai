from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.cognitive import (
    CognitiveWorkflowStatus,
    EngineeringCognitiveWorkflow,
    EngineeringIntentPacket,
    EngineeringTaskPlan,
    EngineeringCognitiveExecution,
    EngineeringReflection,
    EngineeringDecisionBrief,
    EngineeringContextSnapshot,
    PlanStatus,
    HumanDecisionType,
)
from app.models.db.project import Project
from app.models.db.circuit import Circuit
from app.models.db.system import EngineeringSystem
from app.models.schemas.cognitive import (
    WorkflowStartRequest,
    WorkflowContinueRequest,
    IntentResolveRequest,
    TaskPlanCreateRequest,
    DecisionBriefCreateRequest,
    HumanDecisionRecordRequest,
    ContextSynthesisRequest,
)
from app.services.cognitive_service import CognitiveService
from app.services.ai.cognitive.plan_validator import EngineeringPlanValidator
from app.services.ai.cognitive.plan_executor import EngineeringPlanExecutor
from app.services.ai.cognitive.reflection.reflection_service import EngineeringReflectionService
from app.services.ai.cognitive.reflection.replanner import ReflectionReplanner
from app.services.ai.cognitive.decision.decision_brief_service import EngineeringDecisionBriefService
from app.services.ai.cognitive.synthesis.synthesis_service import EngineeringContextSynthesisService
from app.repositories.circuit_repo import CircuitRepository
from app.repositories.system_repo import SystemRepository
from app.repositories.project_repo import ProjectRepository


class EngineeringWorkflowOrchestrator:
    """
    Central orchestration service for Phase 2 Wave 6 Cognitive Engineering Workflows.
    Coordinates existing cognitive subsystems into one unified, revision-bound lifecycle:
    Intent -> Context -> Plan -> Execute -> Reflect -> Replan -> Decision Prep -> Context Synthesis -> Human.

    INVARIANTS:
    - AI ENGINEERING AUTHORITY = NONE
    - AI DECISION AUTHORITY = NONE
    - AUTONOMOUS MUTATION = DISABLED
    - AUTONOMOUS APPROVAL = DISABLED
    - AUTONOMOUS VERIFICATION = DISABLED
    - UNKNOWN != SATISFIED
    - CALCULATED != PHYSICALLY VERIFIED
    - REVISION-BOUND & STALE-PROTECTED
    - CANONICAL SHA-256 INTEGRITY DIGEST
    - ZERO SYNTHETIC SCORING
    """

    MAX_REFLECTION_CYCLES = 3

    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_workflow(
        self,
        request: WorkflowStartRequest,
        tenant_id: str,
        actor: str,
    ) -> EngineeringCognitiveWorkflow:
        # 1. Resolve project and determine base revision
        p_query = select(Project).where(Project.id == request.project_id, Project.tenant_id == tenant_id)
        p_res = await self.db.execute(p_query)
        project = p_res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or access denied.")

        base_revision = 1
        circuit: Optional[Circuit] = None
        system: Optional[EngineeringSystem] = None

        if request.circuit_id:
            c_query = select(Circuit).where(Circuit.id == request.circuit_id, Circuit.tenant_id == tenant_id)
            c_res = await self.db.execute(c_query)
            circuit = c_res.scalar_one_or_none()
            if not circuit:
                raise HTTPException(status_code=404, detail="Circuit not found or access denied.")
            base_revision = circuit.version
        elif request.system_id:
            s_query = select(EngineeringSystem).where(EngineeringSystem.id == request.system_id, EngineeringSystem.tenant_id == tenant_id)
            s_res = await self.db.execute(s_query)
            system = s_res.scalar_one_or_none()
            if not system:
                raise HTTPException(status_code=404, detail="System not found or access denied.")
            base_revision = system.revision

        # 2. Initialize workflow record
        workflow = EngineeringCognitiveWorkflow(
            tenant_id=tenant_id,
            project_id=request.project_id,
            system_id=request.system_id,
            circuit_id=request.circuit_id,
            base_revision=base_revision,
            status=CognitiveWorkflowStatus.RECEIVED.value,
            current_step="INTENT_RESOLUTION",
            user_request=request.user_request,
            blocking_reasons=[],
            timeline=[
                {
                    "step": "WORKFLOW_START",
                    "status": "INITIALIZED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": {"base_revision": base_revision, "actor": actor},
                }
            ],
        )
        self.db.add(workflow)
        await self.db.flush()

        # Step 1: Intent Resolution
        cog_svc = CognitiveService(self.db)
        intent = await cog_svc.resolve_and_create_intent(
            payload=IntentResolveRequest(
                project_id=request.project_id,
                system_id=request.system_id,
                circuit_id=request.circuit_id,
                raw_request=request.user_request,
                scope=request.scope or "CIRCUIT",
                urgency=request.urgency or "NORMAL",
            ),
            tenant_id=tenant_id,
        )
        workflow.intent_packet_id = intent.id
        self._add_timeline_step(workflow, "INTENT_RESOLUTION", "COMPLETED", {"intent_type": intent.intent_type, "status": intent.status})

        # Clarification check
        if intent.status in ["CLARIFICATION_REQUIRED", "PLANNING_BLOCKED"]:
            workflow.status = CognitiveWorkflowStatus.AWAITING_HUMAN.value
            workflow.current_step = "CLARIFICATION_REQUIRED"
            workflow.blocking_reasons = [
                f"Clarification required: {a.get('question', a.get('target', 'Ambiguity detected'))}"
                for a in (intent.ambiguities or [])
            ] or ["Ambiguities detected in user engineering request. Human clarification required."]
            self._update_digest(workflow)
            await self.db.commit()
            await self.db.refresh(workflow)
            return workflow

        workflow.status = CognitiveWorkflowStatus.INTENT_RESOLVED.value

        # Step 2: Context Snapshot Freshness
        await self._check_revision_freshness(workflow, tenant_id)
        if workflow.status == CognitiveWorkflowStatus.STALE.value:
            self._update_digest(workflow)
            await self.db.commit()
            await self.db.refresh(workflow)
            return workflow

        workflow.status = CognitiveWorkflowStatus.CONTEXT_RESOLVED.value
        self._add_timeline_step(workflow, "CONTEXT_RESOLUTION", "COMPLETED", {"base_revision": workflow.base_revision})

        # Step 3: Task Planning & Validation
        plan = await cog_svc.create_plan(
            payload=TaskPlanCreateRequest(intent_packet_id=intent.id),
            tenant_id=tenant_id,
        )
        workflow.plan_id = plan.id

        validator = EngineeringPlanValidator(self.db)
        val_res = await validator.validate_plan(plan, tenant_id=tenant_id)
        if not val_res.is_valid:
            workflow.status = CognitiveWorkflowStatus.BLOCKED.value
            workflow.current_step = "PLANNING_BLOCKED"
            workflow.blocking_reasons = val_res.blocking_reasons
            self._add_timeline_step(workflow, "PLAN_VALIDATION", "FAILED", {"reasons": val_res.blocking_reasons})
            self._update_digest(workflow)
            await self.db.commit()
            await self.db.refresh(workflow)
            return workflow

        workflow.status = CognitiveWorkflowStatus.PLAN_READY.value
        self._add_timeline_step(workflow, "TASK_PLANNING", "COMPLETED", {"plan_id": plan.id, "tasks_count": len(plan.tasks)})

        # Step 4: Deterministic Plan Execution
        await self._check_revision_freshness(workflow, tenant_id)
        if workflow.status == CognitiveWorkflowStatus.STALE.value:
            self._update_digest(workflow)
            await self.db.commit()
            await self.db.refresh(workflow)
            return workflow

        executor = EngineeringPlanExecutor(self.db)
        execution = await executor.execute_plan(
            plan=plan,
            tenant_id=tenant_id,
            actor=actor,
        )
        workflow.execution_id = execution.id
        workflow.status = CognitiveWorkflowStatus.EXECUTING.value
        self._add_timeline_step(
            workflow,
            "PLAN_EXECUTION",
            execution.execution_status,
            {"execution_id": execution.id, "results_count": len(execution.results)},
        )

        # Step 5: Cognitive Reflection & Reasoning
        ref_svc = EngineeringReflectionService(self.db)
        reflection = await ref_svc.reflect_on_execution(
            execution_id=execution.id,
            tenant_id=tenant_id,
        )
        workflow.reflection_id = reflection.id
        workflow.reflection_cycles = 1
        workflow.status = CognitiveWorkflowStatus.REFLECTING.value

        reflection_details = {
            "reflection_id": reflection.id,
            "has_contradictions": reflection.has_contradictions,
            "has_unresolved_unknowns": reflection.has_unresolved_unknowns,
            "has_evidence_gaps": reflection.has_evidence_gaps,
            "has_requirement_gaps": reflection.has_requirement_gaps,
            "has_verification_gaps": reflection.has_verification_gaps,
            "additional_work_required": reflection.additional_work_required,
        }
        self._add_timeline_step(workflow, "COGNITIVE_REFLECTION", "COMPLETED", reflection_details)

        # Step 6: Bounded Re-Planning if Additional Work Required
        if reflection.additional_work_required and workflow.reflection_cycles < self.MAX_REFLECTION_CYCLES:
            replanner = ReflectionReplanner(self.db)
            follow_up = await replanner.replan_after_reflection(
                reflection_id=reflection.id,
                tenant_id=tenant_id,
                actor=actor,
            )
            if follow_up.get("follow_up_plan_id"):
                workflow.reflection_cycles += 1
                self._add_timeline_step(
                    workflow,
                    "ADDITIONAL_WORK_REPLAN",
                    "REPLANNED",
                    {"follow_up_plan_id": follow_up.get("follow_up_plan_id"), "cycle": workflow.reflection_cycles},
                )
            elif follow_up.get("human_action_required"):
                workflow.blocking_reasons.append(
                    follow_up.get("human_action_required") or "Reflection identified additional work requiring human action."
                )

        # Step 7: Decision Preparation (if requested or findings warrant brief)
        decision_warranted = (
            intent.intent_type in ["COMPARE_ALTERNATIVES", "REVIEW_DESIGN", "EXPLORE_DESIGN_ALTERNATIVES", "INVESTIGATE_FAILURE"]
            or reflection.has_contradictions
            or reflection.has_unresolved_unknowns
            or reflection.has_requirement_gaps
        )
        if decision_warranted:
            brief_svc = EngineeringDecisionBriefService(self.db)
            brief_payload = DecisionBriefCreateRequest(
                project_id=request.project_id,
                circuit_id=request.circuit_id,
                system_id=request.system_id,
                reflection_id=reflection.id,
                question=f"Decision Brief: {intent.goal or request.user_request}",
                base_revision=workflow.base_revision,
            )
            brief = await brief_svc.create_decision_brief(brief_payload, tenant_id=tenant_id, actor=actor)
            workflow.decision_brief_id = brief.id
            workflow.status = CognitiveWorkflowStatus.DECISION_PREPARATION.value
            self._add_timeline_step(workflow, "DECISION_PREPARATION", "PREPARED", {"brief_id": brief.id, "alternatives_count": len(brief.alternatives_data)})

        # Step 8: Unified Context Synthesis
        synth_svc = EngineeringContextSynthesisService(self.db)
        synth_req = ContextSynthesisRequest(
            project_id=request.project_id,
            circuit_id=request.circuit_id,
            system_id=request.system_id,
            include_historical_memory=True,
        )
        context_snap = await synth_svc.synthesize_context(tenant_id=tenant_id, request=synth_req)
        workflow.synthesized_context_id = context_snap.id
        workflow.status = CognitiveWorkflowStatus.CONTEXT_SYNTHESIS.value
        self._add_timeline_step(workflow, "CONTEXT_SYNTHESIS", "COMPLETED", {"context_id": context_snap.id, "canonical_digest": context_snap.canonical_digest})

        # Step 9: Final Workflow State Evaluation
        if workflow.blocking_reasons:
            workflow.status = CognitiveWorkflowStatus.BLOCKED.value
            workflow.current_step = "BLOCKED"
        elif workflow.decision_brief_id:
            workflow.status = CognitiveWorkflowStatus.AWAITING_HUMAN.value
            workflow.current_step = "HUMAN_DECISION_REQUIRED"
        elif reflection.has_verification_gaps:
            workflow.status = CognitiveWorkflowStatus.AWAITING_HUMAN.value
            workflow.current_step = "HUMAN_VERIFICATION_REQUIRED"
        else:
            workflow.status = CognitiveWorkflowStatus.COMPLETED.value
            workflow.current_step = "COMPLETED"

        self._add_timeline_step(workflow, "WORKFLOW_STATE", workflow.status, {"current_step": workflow.current_step})
        self._update_digest(workflow)
        await self.db.commit()
        await self.db.refresh(workflow)
        return workflow

    async def get_workflow(
        self,
        workflow_id: str,
        tenant_id: str,
    ) -> EngineeringCognitiveWorkflow:
        query = select(EngineeringCognitiveWorkflow).where(
            EngineeringCognitiveWorkflow.id == workflow_id,
            EngineeringCognitiveWorkflow.tenant_id == tenant_id,
        )
        res = await self.db.execute(query)
        wf = res.scalar_one_or_none()
        if not wf:
            raise HTTPException(status_code=404, detail="Workflow not found or access denied.")

        # Live staleness check
        await self._check_revision_freshness(wf, tenant_id)
        if wf.status == CognitiveWorkflowStatus.STALE.value:
            await self.db.commit()
            await self.db.refresh(wf)

        return wf

    async def continue_workflow(
        self,
        workflow_id: str,
        request: WorkflowContinueRequest,
        tenant_id: str,
        actor: str,
    ) -> EngineeringCognitiveWorkflow:
        wf = await self.get_workflow(workflow_id, tenant_id)

        if wf.status == CognitiveWorkflowStatus.STALE.value:
            raise HTTPException(
                status_code=409,
                detail="Workflow is STALE because engineering revision advanced. Start a new workflow.",
            )

        # Handle Human Decision Ratification
        if request.selected_alternative_id and wf.decision_brief_id:
            brief_svc = EngineeringDecisionBriefService(self.db)
            dec_payload = HumanDecisionRecordRequest(
                decision_type=HumanDecisionType.ADOPT_ALTERNATIVE.value,
                selected_alternative_id=request.selected_alternative_id,
                rationale=request.decision_notes or "Human engineer recorded decision.",
                actor=actor,
            )
            await brief_svc.record_human_decision(wf.decision_brief_id, dec_payload, tenant_id=tenant_id, actor=actor)

            # Re-synthesize context snapshot after human decision
            synth_svc = EngineeringContextSynthesisService(self.db)
            synth_req = ContextSynthesisRequest(
                project_id=wf.project_id,
                circuit_id=wf.circuit_id,
                system_id=wf.system_id,
                include_historical_memory=True,
            )
            context_snap = await synth_svc.synthesize_context(tenant_id=tenant_id, request=synth_req)
            wf.synthesized_context_id = context_snap.id

            wf.status = CognitiveWorkflowStatus.COMPLETED.value
            wf.current_step = "COMPLETED"
            self._add_timeline_step(
                wf,
                "HUMAN_DECISION",
                "RATIFIED",
                {"selected_alternative_id": request.selected_alternative_id, "actor": actor},
            )
            self._update_digest(wf)
            await self.db.commit()
            await self.db.refresh(wf)
            return wf

        # Handle Clarification Input
        if request.clarifications and wf.current_step == "CLARIFICATION_REQUIRED":
            # Resume workflow from context resolution
            wf.blocking_reasons = []
            wf.current_step = "CONTEXT_RESOLUTION"
            wf.status = CognitiveWorkflowStatus.CONTEXT_RESOLVED.value
            self._add_timeline_step(wf, "HUMAN_CLARIFICATION", "SUBMITTED", request.clarifications)
            self._update_digest(wf)
            await self.db.commit()
            await self.db.refresh(wf)
            return wf

        return wf

    async def _check_revision_freshness(self, workflow: EngineeringCognitiveWorkflow, tenant_id: str) -> None:
        if workflow.circuit_id:
            c_query = select(Circuit).where(Circuit.id == workflow.circuit_id, Circuit.tenant_id == tenant_id)
            c_res = await self.db.execute(c_query)
            c = c_res.scalar_one_or_none()
            if c and c.version != workflow.base_revision:
                workflow.status = CognitiveWorkflowStatus.STALE.value
                workflow.current_step = "STALE_REVISION"
                workflow.blocking_reasons.append(
                    f"STALE_REVISION: Workflow base revision {workflow.base_revision} does not match current circuit version {c.version}."
                )
                self._add_timeline_step(workflow, "STALE_DETECTION", "STALE", {"current_circuit_version": c.version})
        elif workflow.system_id:
            s_query = select(EngineeringSystem).where(EngineeringSystem.id == workflow.system_id, EngineeringSystem.tenant_id == tenant_id)
            s_res = await self.db.execute(s_query)
            s = s_res.scalar_one_or_none()
            if s and s.revision != workflow.base_revision:
                workflow.status = CognitiveWorkflowStatus.STALE.value
                workflow.current_step = "STALE_REVISION"
                workflow.blocking_reasons.append(
                    f"STALE_REVISION: Workflow base revision {workflow.base_revision} does not match current system revision {s.revision}."
                )
                self._add_timeline_step(workflow, "STALE_DETECTION", "STALE", {"current_system_revision": s.revision})

    def _add_timeline_step(self, workflow: EngineeringCognitiveWorkflow, step: str, status_val: str, details: Optional[Dict[str, Any]] = None) -> None:
        timeline = list(workflow.timeline or [])
        timeline.append({
            "step": step,
            "status": status_val,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        workflow.timeline = timeline

    def _update_digest(self, workflow: EngineeringCognitiveWorkflow) -> None:
        content = (
            f"{workflow.id}:{workflow.base_revision}:{workflow.status}:"
            f"{workflow.intent_packet_id}:{workflow.plan_id}:{workflow.execution_id}:"
            f"{workflow.reflection_id}:{workflow.decision_brief_id}:{workflow.synthesized_context_id}"
        )
        workflow.integrity_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
