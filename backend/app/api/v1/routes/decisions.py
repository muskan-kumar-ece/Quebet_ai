from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.decision import (
    EngineeringDecisionCreate,
    EngineeringDecisionUpdate,
    EngineeringDecisionResponse,
    EngineeringDecisionAlternativeCreate,
    EngineeringDecisionAlternativeResponse,
    EngineeringTradeoffCreate,
    EngineeringTradeoffResponse,
    EngineeringDecisionQuestionCreate,
    EngineeringDecisionQuestionAnswer,
    EngineeringDecisionQuestionResponse,
    EngineeringUnknownDispositionCreate,
    EngineeringUnknownDispositionResponse,
    AlternativeSelectionRequest,
)
from app.repositories.decision_repo import DecisionRepository
from app.repositories.system_repo import SystemRepository
from app.services.decision_service import DecisionService
from app.services.ai.decision.decision_comparison_service import DecisionComparisonService

router = APIRouter(tags=["Engineering Decisions"])


@router.post("/systems/{system_id}/decisions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_decision(
    system_id: str,
    payload: EngineeringDecisionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    sys_repo = SystemRepository(db)
    system = await sys_repo.get_system(system_id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=404, detail="System not found")

    repo = DecisionRepository(db)
    dec = await repo.create_decision(
        system_id=system_id,
        project_id=system.project_id,
        title=payload.title,
        decision_key=payload.decision_key,
        description=payload.description,
        system_revision=system.revision,
        decision_type=payload.decision_type,
        requirement_baseline_id=payload.requirement_baseline_id,
        analysis_id=payload.analysis_id,
        decision_context=payload.decision_context,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"status": "success", "data": EngineeringDecisionResponse.model_validate(dec)}


@router.get("/systems/{system_id}/decisions", response_model=Dict[str, Any])
async def list_decisions(
    system_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    decs = await repo.get_decisions_by_system(system_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": [EngineeringDecisionResponse.model_validate(d) for d in decs]}


@router.get("/decisions/{decision_id}", response_model=Dict[str, Any])
async def get_decision(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")
    return {"status": "success", "data": EngineeringDecisionResponse.model_validate(dec)}


@router.patch("/decisions/{decision_id}", response_model=Dict[str, Any])
async def update_decision(
    decision_id: str,
    payload: EngineeringDecisionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.update_decision(
        decision_id,
        updates=payload.model_dump(exclude_unset=True),
        tenant_id=current_user.tenant_id,
    )
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")
    return {"status": "success", "data": EngineeringDecisionResponse.model_validate(dec)}


# Alternatives
@router.post("/decisions/{decision_id}/alternatives", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_alternative(
    decision_id: str,
    payload: EngineeringDecisionAlternativeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")

    alt = await repo.create_alternative(
        decision_id=decision_id,
        name=payload.name,
        description=payload.description,
        candidate_id=payload.candidate_id,
        status=payload.status,
        elimination_reason=payload.elimination_reason,
        engineering_effects=payload.engineering_effects,
        requirement_effects=payload.requirement_effects,
        verification_effects=payload.verification_effects,
        failure_effects=payload.failure_effects,
        tradeoffs=payload.tradeoffs,
        unknowns=payload.unknowns,
        evidence_refs=payload.evidence_refs,
    )
    return {"status": "success", "data": EngineeringDecisionAlternativeResponse.model_validate(alt)}


@router.get("/decisions/{decision_id}/alternatives", response_model=Dict[str, Any])
async def list_alternatives(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")
    alts = await repo.get_alternatives(decision_id)
    return {"status": "success", "data": [EngineeringDecisionAlternativeResponse.model_validate(a) for a in alts]}


# Comparison Matrix (Zero Synthetic Scoring)
@router.get("/decisions/{decision_id}/compare", response_model=Dict[str, Any])
@router.post("/decisions/{decision_id}/compare", response_model=Dict[str, Any])
async def compare_alternatives(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")

    alts = await repo.get_alternatives(decision_id)
    comparison = DecisionComparisonService.compare_alternatives(decision=dec, alternatives=alts)
    return {"status": "success", "data": comparison}


# Trade-offs
@router.post("/decisions/{decision_id}/tradeoffs", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_tradeoff(
    decision_id: str,
    payload: EngineeringTradeoffCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")

    troff = await repo.create_tradeoff(
        decision_id=decision_id,
        dimension=payload.dimension,
        alternative_a_id=payload.alternative_a_id,
        alternative_b_id=payload.alternative_b_id,
        advantage_a=payload.advantage_a,
        disadvantage_a=payload.disadvantage_a,
        advantage_b=payload.advantage_b,
        disadvantage_b=payload.disadvantage_b,
        evidence=payload.evidence,
        unknowns=payload.unknowns,
    )
    return {"status": "success", "data": EngineeringTradeoffResponse.model_validate(troff)}


@router.get("/decisions/{decision_id}/tradeoffs", response_model=Dict[str, Any])
async def list_tradeoffs(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")
    troffs = await repo.get_tradeoffs(decision_id)
    return {"status": "success", "data": [EngineeringTradeoffResponse.model_validate(t) for t in troffs]}


# Questions
@router.post("/decisions/{decision_id}/questions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_question(
    decision_id: str,
    payload: EngineeringDecisionQuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")

    q = await repo.create_question(
        decision_id=decision_id,
        question=payload.question,
        reason=payload.reason,
        blocking=payload.blocking,
        review_id=payload.review_id,
        affected_object=payload.affected_object,
        affected_requirement_id=payload.affected_requirement_id,
        affected_analysis_id=payload.affected_analysis_id,
    )
    return {"status": "success", "data": EngineeringDecisionQuestionResponse.model_validate(q)}


@router.get("/decisions/{decision_id}/questions", response_model=Dict[str, Any])
async def list_questions(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")
    qs = await repo.get_questions(decision_id)
    return {"status": "success", "data": [EngineeringDecisionQuestionResponse.model_validate(q) for q in qs]}


@router.post("/decisions/questions/{question_id}/answer", response_model=Dict[str, Any])
@router.post("/decision-questions/{question_id}/answer", response_model=Dict[str, Any])
async def answer_question(
    question_id: str,
    payload: EngineeringDecisionQuestionAnswer,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    q = await repo.answer_question(
        question_id=question_id,
        answer=payload.answer,
        answered_by=current_user.id,
        evidence_id=payload.evidence_id,
    )
    if not q:
        raise HTTPException(status_code=404, detail="Decision question not found")
    return {"status": "success", "data": EngineeringDecisionQuestionResponse.model_validate(q)}


# Dispositions
@router.post("/decisions/{decision_id}/unknowns", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
@router.post("/decisions/{decision_id}/dispositions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_unknown_disposition(
    decision_id: str,
    payload: EngineeringUnknownDispositionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")

    disp = await repo.create_unknown_disposition(
        decision_id=decision_id,
        unknown_key=payload.unknown_key,
        actor=current_user.id,
        reason=payload.reason,
        affected_requirement_id=payload.affected_requirement_id,
        status=payload.status,
    )
    return {"status": "success", "data": EngineeringUnknownDispositionResponse.model_validate(disp)}


@router.get("/decisions/{decision_id}/unknowns", response_model=Dict[str, Any])
@router.get("/decisions/{decision_id}/dispositions", response_model=Dict[str, Any])
async def list_unknown_dispositions(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    dec = await repo.get_decision(decision_id, tenant_id=current_user.tenant_id)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision record not found")
    disps = await repo.get_unknown_dispositions(decision_id)
    return {"status": "success", "data": [EngineeringUnknownDispositionResponse.model_validate(d) for d in disps]}


# Human Alternative Selection
@router.post("/decisions/{decision_id}/select", response_model=Dict[str, Any])
@router.post("/decisions/{decision_id}/select-alternative", response_model=Dict[str, Any])
async def select_alternative(
    decision_id: str,
    payload: AlternativeSelectionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = DecisionService(db)
    dec = await service.select_alternative(
        decision_id=decision_id,
        alternative_id=payload.alternative_id,
        actor=current_user.id,
        rationale=payload.model_dump(),
        tenant_id=current_user.tenant_id,
    )
    return {"status": "success", "data": EngineeringDecisionResponse.model_validate(dec)}


# Informational AI Decision Brief
@router.get("/decisions/{decision_id}/brief", response_model=Dict[str, Any])
@router.get("/decisions/{decision_id}/ai-brief", response_model=Dict[str, Any])
async def get_ai_decision_brief(
    decision_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = DecisionService(db)
    brief = await service.generate_ai_brief(decision_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": brief}
