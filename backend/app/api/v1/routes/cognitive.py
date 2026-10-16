from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.cognitive import (
    IntentResolveRequest,
    IntentPacketCreate,
    IntentPacketResponse,
    TaskPlanCreateRequest,
    EngineeringTaskPlanResponse,
    PlanValidationResponse,
    CognitivePlanExecuteRequest,
    CognitiveExecutionResponse,
    CognitiveProvenanceResponse,
    CognitiveExplanationRequest,
    CognitiveExplanationResponse,
    CapabilityDeclaration,
    ContextSnapshotResponse,
    EngineeringReflectionResponse,
    EngineeringReasoningFindingResponse,
    EngineeringReflectionProvenanceResponse,
    ReflectionTriggerRequest,
    ReflectionReplanRequest,
    ReflectionReplanResponse,
    DecisionBriefCreateRequest,
    HumanDecisionRecordRequest,
    EngineeringDecisionBriefResponse,
    EngineeringDecisionBriefProvenanceResponse,
    MemoryRecordCreateRequest,
    MemoryFeedbackRequest,
    MemoryRetrievalRequest,
    EngineeringMemoryFeedbackResponse,
    EngineeringMemoryRecordResponse,
    SurfacedMemoryItemResponse,
    MemoryRetrievalResponse,
    ContextSynthesisRequest,
    ContextExplainRequest,
    EngineeringContextSnapshotResponse,
    ContextExplanationResponse,
    WorkflowStartRequest,
    WorkflowContinueRequest,
    EngineeringCognitiveWorkflowResponse,
    EngineeringExplanationRequest,
    EngineeringExplanationResponse,
    EvidenceRegisterRequest,
    VerificationCloseRequest,
    VerificationWorkspaceObligation,
    VerificationWorkspaceResponse,
    EngineeringActionItem,
    EngineeringActionCenterResponse,
    EngineeringActionCenterSummary,
)
from app.services.cognitive_service import CognitiveService
from app.services.ai.cognitive.capability_registry import capability_registry
from app.services.ai.cognitive.memory.memory_service import EngineeringMemoryService
from app.services.ai.cognitive.memory.retrieval_service import EngineeringMemoryRetrievalService
from app.services.ai.cognitive.synthesis.synthesis_service import EngineeringContextSynthesisService
from app.services.ai.cognitive.synthesis.explanation_service import EngineeringContextExplanationService
from app.services.ai.cognitive.explain.explanation_service import EngineeringCognitiveExplanationService
from app.services.ai.cognitive.workflow.orchestrator import EngineeringWorkflowOrchestrator
from app.services.ai.cognitive.verification.workspace_service import EngineeringVerificationWorkspaceService
from app.services.ai.cognitive.action_center.action_center_service import EngineeringActionCenterService
from app.repositories.cognitive_repo import CognitiveRepository



router = APIRouter(prefix="/cognitive", tags=["Cognitive Engineering"])


# ============================================================================
# 1. INTENT RESOLUTION & MANAGEMENT
# ============================================================================

@router.post("/intents/resolve", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def resolve_intent(
    payload: IntentResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    intent = await service.resolve_and_create_intent(payload, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": IntentPacketResponse.model_validate(intent)}


@router.post("/intents", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_intent(
    payload: IntentPacketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = CognitiveRepository(db)
    intent = await repo.create_intent_packet(payload, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": IntentPacketResponse.model_validate(intent)}


@router.get("/intents/{intent_id}", response_model=Dict[str, Any])
async def get_intent(
    intent_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = CognitiveRepository(db)
    intent = await repo.get_intent_packet(intent_id, tenant_id=current_user.tenant_id)
    if not intent:
        raise HTTPException(status_code=404, detail="Intent packet not found or access denied.")
    return {"status": "success", "data": IntentPacketResponse.model_validate(intent)}


# ============================================================================
# 2. TASK PLANNING & VALIDATION
# ============================================================================

@router.post("/plans", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: TaskPlanCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    plan = await service.create_plan(payload, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": EngineeringTaskPlanResponse.model_validate(plan)}


@router.get("/plans/{plan_id}", response_model=Dict[str, Any])
async def get_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = CognitiveRepository(db)
    plan = await repo.get_task_plan(plan_id, tenant_id=current_user.tenant_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Task plan not found or access denied.")
    return {"status": "success", "data": EngineeringTaskPlanResponse.model_validate(plan)}


@router.post("/plans/{plan_id}/validate", response_model=Dict[str, Any])
async def validate_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    val_res = await service.validate_plan(plan_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": val_res}


# ============================================================================
# 3. CONTEXT SNAPSHOTS
# ============================================================================

@router.get("/snapshots/{snapshot_id}", response_model=Dict[str, Any])
async def get_context_snapshot(
    snapshot_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    snapshot = await service.get_context_snapshot(snapshot_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": ContextSnapshotResponse.model_validate(snapshot)}


@router.get("/projects/{project_id}/snapshots", response_model=Dict[str, Any])
async def list_context_snapshots(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    snapshots = await service.list_context_snapshots(project_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": [ContextSnapshotResponse.model_validate(s) for s in snapshots]}


# ============================================================================
# 4. DETERMINISTIC EXECUTION & PROVENANCE
# ============================================================================

@router.post("/plans/{plan_id}/execute", response_model=Dict[str, Any])
async def execute_plan(
    plan_id: str,
    payload: Optional[CognitivePlanExecuteRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    execution = await service.execute_plan(plan_id, tenant_id=current_user.tenant_id, actor=current_user.id)
    details = await service.get_execution_with_provenance(execution.id, tenant_id=current_user.tenant_id)

    response_data = CognitiveExecutionResponse.model_validate(execution).model_dump()
    if details.get("provenance"):
        response_data["provenance"] = CognitiveProvenanceResponse.model_validate(details["provenance"]).model_dump()

    return {"status": "success", "data": response_data}


@router.get("/executions/{execution_id}", response_model=Dict[str, Any])
async def get_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    details = await service.get_execution_with_provenance(execution_id, tenant_id=current_user.tenant_id)

    response_data = CognitiveExecutionResponse.model_validate(details["execution"]).model_dump()
    if details.get("provenance"):
        response_data["provenance"] = CognitiveProvenanceResponse.model_validate(details["provenance"]).model_dump()

    return {"status": "success", "data": response_data}


# ============================================================================
# 5. CAPABILITY REGISTRY & EXPLANATIONS
# ============================================================================

@router.get("/capabilities", response_model=Dict[str, Any])
async def list_capabilities(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    caps = capability_registry.list_all()
    return {"status": "success", "data": [c.model_dump() for c in caps]}


@router.post("/explanations", response_model=Dict[str, Any])
async def get_explanation(
    payload: CognitiveExplanationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    details = await service.get_execution_with_provenance(payload.execution_id, tenant_id=current_user.tenant_id)
    execution = details["execution"]
    provenance = details.get("provenance")

    return {
        "status": "success",
        "data": CognitiveExplanationResponse(
            execution_id=execution.id,
            explanation=execution.explanation or "No explanation generated for this execution.",
            origin="AI_GENERATED",
            authority="INFORMATIONAL_ONLY",
            provenance_trace={
                "model": provenance.model_identifier if provenance else "unknown",
                "prompt_version": provenance.prompt_version if provenance else "v1.0.0",
                "base_revision": provenance.base_revision if provenance else 1,
                "input_digest": provenance.input_digest if provenance else "",
            },
        ),
    }


# ============================================================================
# 6. COGNITIVE REFLECTION & ENGINEERING REASONING
# ============================================================================

@router.post("/executions/{execution_id}/reflect", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def trigger_reflection(
    execution_id: str,
    payload: Optional[ReflectionTriggerRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    user_focus = payload.user_focus if payload else None
    force_reeval = payload.force_reevaluation if payload else False

    details = await service.reflect_on_execution(
        execution_id=execution_id,
        tenant_id=current_user.tenant_id,
        user_focus=user_focus,
        force_reevaluation=force_reeval,
    )

    reflection = details["reflection"]
    provenance = details["provenance"]

    resp_data = EngineeringReflectionResponse.model_validate(reflection).model_dump()
    if provenance:
        resp_data["provenance"] = EngineeringReflectionProvenanceResponse.model_validate(provenance).model_dump()

    return {"status": "success", "data": resp_data}


@router.get("/reflections/{reflection_id}", response_model=Dict[str, Any])
async def get_reflection(
    reflection_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    details = await service.get_reflection_with_provenance(reflection_id, tenant_id=current_user.tenant_id)
    reflection = details["reflection"]
    provenance = details["provenance"]

    resp_data = EngineeringReflectionResponse.model_validate(reflection).model_dump()
    if provenance:
        resp_data["provenance"] = EngineeringReflectionProvenanceResponse.model_validate(provenance).model_dump()

    return {"status": "success", "data": resp_data}


@router.get("/executions/{execution_id}/reflections", response_model=Dict[str, Any])
async def list_reflections_for_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    reflections = await service.list_reflections_for_execution(execution_id, tenant_id=current_user.tenant_id)
    return {
        "status": "success",
        "data": [EngineeringReflectionResponse.model_validate(r).model_dump() for r in reflections],
    }


@router.post("/reflections/{reflection_id}/replan", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def replan_from_reflection(
    reflection_id: str,
    payload: Optional[ReflectionReplanRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    selected_finding_ids = payload.selected_finding_ids if payload else None
    policy = payload.execution_policy if payload else {}

    plan = await service.replan_from_reflection(
        reflection_id=reflection_id,
        tenant_id=current_user.tenant_id,
        actor=current_user.id,
        selected_finding_ids=selected_finding_ids,
        execution_policy=policy,
    )

    return {
        "status": "success",
        "data": ReflectionReplanResponse(
            reflection_id=reflection_id,
            follow_up_plan_id=plan.id,
            reflection_cycle=plan.execution_policy.get("reflection_cycle", 2),
            status=plan.status,
            tasks_count=len(plan.tasks),
            created_at=plan.created_at,
        ),
    }


# ============================================================================
# 6. DECISION BRIEF PREPARATION & HUMAN DECISION GATE
# ============================================================================

@router.post("/decision-briefs", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_decision_brief(
    payload: DecisionBriefCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    res = await service.create_decision_brief(payload, tenant_id=current_user.tenant_id, actor=current_user.id)
    brief = res["brief"]
    provenance = res["provenance"]
    resp_data = EngineeringDecisionBriefResponse.model_validate(brief).model_dump()
    if provenance:
        resp_data["provenance"] = EngineeringDecisionBriefProvenanceResponse.model_validate(provenance).model_dump()
    return {"status": "success", "data": resp_data}


@router.get("/decision-briefs/{brief_id}", response_model=Dict[str, Any])
async def get_decision_brief(
    brief_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    details = await service.get_decision_brief_with_provenance(brief_id, tenant_id=current_user.tenant_id)
    brief = details["brief"]
    provenance = details["provenance"]

    resp_data = EngineeringDecisionBriefResponse.model_validate(brief).model_dump()
    if provenance:
        resp_data["provenance"] = EngineeringDecisionBriefProvenanceResponse.model_validate(provenance).model_dump()

    return {"status": "success", "data": resp_data}


@router.get("/projects/{project_id}/decision-briefs", response_model=Dict[str, Any])
async def list_decision_briefs_by_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    briefs = await service.list_decision_briefs_by_project(project_id, tenant_id=current_user.tenant_id)
    return {
        "status": "success",
        "data": [EngineeringDecisionBriefResponse.model_validate(b).model_dump() for b in briefs],
    }


@router.post("/decision-briefs/{brief_id}/decision", response_model=Dict[str, Any])
async def record_human_decision(
    brief_id: str,
    payload: HumanDecisionRecordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = CognitiveService(db)
    actor = payload.actor or current_user.id
    result = await service.record_human_decision(
        brief_id=brief_id,
        payload=payload,
        tenant_id=current_user.tenant_id,
        actor=actor,
    )
    brief = result["brief"]
    decision = result["decision"]
    resp_data = EngineeringDecisionBriefResponse.model_validate(brief).model_dump()
    resp_data["decision_record"] = {
        "id": decision.id,
        "title": decision.title,
        "status": decision.status,
        "decision_type": decision.decision_type,
        "decided_by": decision.decided_by,
        "decided_at": decision.decided_at.isoformat() if decision.decided_at else None,
        "selected_alternative_id": decision.selected_alternative_id,
        "rationale": decision.rationale,
    }
    return {"status": "success", "data": resp_data}


# ============================================================================
# 8. ENGINEERING MEMORY & CONTEXTUAL LEARNING
# ============================================================================

@router.post("/memories", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_memory_record(
    payload: MemoryRecordCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringMemoryService(db)
    record = await service.create_memory_record(
        tenant_id=current_user.tenant_id,
        request=payload,
    )
    return {
        "status": "success",
        "data": EngineeringMemoryRecordResponse.model_validate(record).model_dump(),
    }


@router.get("/memories/{memory_id}", response_model=Dict[str, Any])
async def get_memory_record(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringMemoryService(db)
    record = await service.get_memory_record(
        tenant_id=current_user.tenant_id,
        memory_id=memory_id,
    )
    feedbacks = await service.get_feedback_for_memory(
        tenant_id=current_user.tenant_id,
        memory_id=memory_id,
    )
    resp = EngineeringMemoryRecordResponse.model_validate(record).model_dump()
    resp["feedback"] = [EngineeringMemoryFeedbackResponse.model_validate(f).model_dump() for f in feedbacks]
    return {"status": "success", "data": resp}


@router.get("/projects/{project_id}/memories", response_model=Dict[str, Any])
async def list_project_memories(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringMemoryService(db)
    records = await service.list_project_memories(
        tenant_id=current_user.tenant_id,
        project_id=project_id,
    )
    return {
        "status": "success",
        "data": [EngineeringMemoryRecordResponse.model_validate(r).model_dump() for r in records],
    }


@router.post("/projects/{project_id}/memories/retrieve", response_model=Dict[str, Any])
async def retrieve_contextual_memories(
    project_id: str,
    payload: MemoryRetrievalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    # Ensure payload.project_id is set to path project_id
    payload.project_id = project_id
    service = EngineeringMemoryRetrievalService(db)
    result = await service.retrieve_contextual_memories(
        tenant_id=current_user.tenant_id,
        request=payload,
    )
    return {
        "status": "success",
        "data": result.model_dump(),
    }


@router.post("/memories/{memory_id}/feedback", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def record_memory_feedback(
    memory_id: str,
    payload: MemoryFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringMemoryService(db)
    if not payload.engineer_identity:
        payload.engineer_identity = current_user.email or current_user.id
    feedback = await service.record_feedback(
        tenant_id=current_user.tenant_id,
        memory_id=memory_id,
        request=payload,
    )
    return {
        "status": "success",
        "data": EngineeringMemoryFeedbackResponse.model_validate(feedback).model_dump(),
    }


# ============================================================================
# 9. ENGINEERING CONTEXT SYNTHESIS & COGNITIVE STATE
# ============================================================================

@router.post("/context/synthesize", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def synthesize_context(
    payload: ContextSynthesisRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringContextSynthesisService(db)
    snapshot = await service.synthesize_context(
        tenant_id=current_user.tenant_id,
        request=payload,
    )
    return {
        "status": "success",
        "data": EngineeringContextSnapshotResponse.model_validate(snapshot).model_dump(),
    }


@router.get("/context/{context_id}", response_model=Dict[str, Any])
async def get_context_snapshot(
    context_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringContextSynthesisService(db)
    snapshot = await service.get_context_snapshot(
        tenant_id=current_user.tenant_id,
        context_id=context_id,
    )
    return {
        "status": "success",
        "data": EngineeringContextSnapshotResponse.model_validate(snapshot).model_dump(),
    }


@router.get("/projects/{project_id}/context", response_model=Dict[str, Any])
async def list_project_context_snapshots(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringContextSynthesisService(db)
    snapshots = await service.list_project_snapshots(
        tenant_id=current_user.tenant_id,
        project_id=project_id,
    )
    return {
        "status": "success",
        "data": [EngineeringContextSnapshotResponse.model_validate(s).model_dump() for s in snapshots],
    }


@router.post("/context/{context_id}/explain", response_model=Dict[str, Any])
async def explain_context(
    context_id: str,
    payload: EngineeringExplanationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringCognitiveExplanationService(db)
    explanation = await service.explain_context(
        context_id=context_id,
        tenant_id=current_user.tenant_id,
        request=payload,
    )
    return {
        "status": "success",
        "data": explanation.model_dump(),
    }


# ============================================================================
# 10. WORKFLOW ORCHESTRATION (Phase 2 Wave 6)
# ============================================================================

@router.post("/workflows", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def start_workflow(
    payload: WorkflowStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    orchestrator = EngineeringWorkflowOrchestrator(db)
    workflow = await orchestrator.start_workflow(
        request=payload,
        tenant_id=current_user.tenant_id,
        actor=current_user.email,
    )
    return {
        "status": "success",
        "data": EngineeringCognitiveWorkflowResponse.model_validate(workflow).model_dump(),
    }


@router.get("/workflows/{workflow_id}", response_model=Dict[str, Any])
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    orchestrator = EngineeringWorkflowOrchestrator(db)
    workflow = await orchestrator.get_workflow(
        workflow_id=workflow_id,
        tenant_id=current_user.tenant_id,
    )
    return {
        "status": "success",
        "data": EngineeringCognitiveWorkflowResponse.model_validate(workflow).model_dump(),
    }


@router.post("/workflows/{workflow_id}/continue", response_model=Dict[str, Any])
async def continue_workflow(
    workflow_id: str,
    payload: WorkflowContinueRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    orchestrator = EngineeringWorkflowOrchestrator(db)
    workflow = await orchestrator.continue_workflow(
        workflow_id=workflow_id,
        request=payload,
        tenant_id=current_user.tenant_id,
        actor=current_user.email,
    )
    return {
        "status": "success",
        "data": EngineeringCognitiveWorkflowResponse.model_validate(workflow).model_dump(),
    }


# ============================================================================
# 11. WORKFLOW INTERACTION & EXPLAINABILITY (Phase 2 Wave 7)
# ============================================================================

@router.post("/workflows/{workflow_id}/explain", response_model=Dict[str, Any])
async def explain_workflow(
    workflow_id: str,
    payload: EngineeringExplanationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringCognitiveExplanationService(db)
    explanation = await service.explain_workflow(
        workflow_id=workflow_id,
        tenant_id=current_user.tenant_id,
        request=payload,
    )
    return {
        "status": "success",
        "data": explanation.model_dump(),
    }


# ============================================================================
# 12. EVIDENCE & VERIFICATION WORKSPACE (Phase 2 Wave 8)
# ============================================================================

@router.get("/workflows/{workflow_id}/verification", response_model=Dict[str, Any])
async def get_workflow_verification_workspace(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringVerificationWorkspaceService(db)
    workspace = await service.get_workflow_verification_workspace(
        workflow_id=workflow_id,
        tenant_id=current_user.tenant_id,
    )
    return {
        "status": "success",
        "data": workspace.model_dump(),
    }


@router.get("/verification/{verification_id}", response_model=Dict[str, Any])
async def get_verification_obligation(
    verification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringVerificationWorkspaceService(db)
    obligation = await service.get_verification_obligation(
        verification_id=verification_id,
        tenant_id=current_user.tenant_id,
    )
    return {
        "status": "success",
        "data": obligation.model_dump(),
    }


@router.post("/verification/{verification_id}/evidence", response_model=Dict[str, Any])
async def attach_evidence_to_verification(
    verification_id: str,
    payload: EvidenceRegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringVerificationWorkspaceService(db)
    result = await service.attach_evidence(
        verification_id=verification_id,
        request=payload,
        tenant_id=current_user.tenant_id,
        actor=current_user.email,
    )
    return {
        "status": "success",
        "data": result,
    }


@router.post("/verification/{verification_id}/review", response_model=Dict[str, Any])
async def review_verification_obligation(
    verification_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringVerificationWorkspaceService(db)
    result = await service.review_verification(
        verification_id=verification_id,
        tenant_id=current_user.tenant_id,
        actor=current_user.email,
    )
    return {
        "status": "success",
        "data": result,
    }


@router.post("/verification/{verification_id}/close", response_model=Dict[str, Any])
async def close_verification_obligation(
    verification_id: str,
    payload: VerificationCloseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringVerificationWorkspaceService(db)
    result = await service.close_verification(
        verification_id=verification_id,
        request=payload,
        tenant_id=current_user.tenant_id,
        actor=current_user.email,
    )
    return {
        "status": "success",
        "data": result,
    }


# ============================================================================
# 13. COGNITIVE ENGINEERING ACTION & CLOSURE CENTER (Phase 2 Wave 9)
# ============================================================================

@router.get("/projects/{project_id}/actions", response_model=Dict[str, Any])
async def get_project_actions(
    project_id: str,
    category: Optional[str] = None,
    system_id: Optional[str] = None,
    circuit_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringActionCenterService(db)
    response = await service.get_project_actions(
        project_id=project_id,
        tenant_id=current_user.tenant_id,
        category=category,
        system_id=system_id,
        circuit_id=circuit_id,
    )
    return {
        "status": "success",
        "data": response.model_dump(),
    }


@router.get("/actions/{source_entity_type}/{source_entity_id}", response_model=Dict[str, Any])
async def get_action_item_detail(
    source_entity_type: str,
    source_entity_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringActionCenterService(db)
    action = await service.get_action_item(
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        tenant_id=current_user.tenant_id,
    )
    return {
        "status": "success",
        "data": action.model_dump(),
    }


@router.post("/actions/{source_entity_type}/{source_entity_id}/explain", response_model=Dict[str, Any])
async def explain_action_item(
    source_entity_type: str,
    source_entity_id: str,
    payload: Optional[EngineeringExplanationRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = EngineeringActionCenterService(db)
    explanation = await service.explain_action(
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
        tenant_id=current_user.tenant_id,
        request=payload,
    )
    return {
        "status": "success",
        "data": explanation.model_dump(),
    }







