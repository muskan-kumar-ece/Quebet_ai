from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.decision import (
    EngineeringDesignReviewCreate,
    EngineeringDesignReviewResponse,
    EngineeringReviewParticipantCreate,
    EngineeringReviewParticipantResponse,
    EngineeringReviewCheckpointCreate,
    EngineeringReviewCheckpointUpdate,
    EngineeringReviewCheckpointResponse,
    EngineeringReviewFindingCreate,
    EngineeringReviewFindingResponse,
    EngineeringReviewActionCreate,
    EngineeringReviewActionUpdate,
    EngineeringReviewActionResponse,
)
from app.repositories.decision_repo import DecisionRepository
from app.repositories.system_repo import SystemRepository
from app.services.decision_service import DecisionService
from app.services.ai.decision.design_review_readiness_service import DesignReviewReadinessService

router = APIRouter(tags=["Engineering Design Reviews"])


class FindingWaiverRequest(BaseModel):
    waiver_rationale: str


@router.post("/systems/{system_id}/design-reviews", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_design_review(
    system_id: str,
    payload: EngineeringDesignReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    sys_repo = SystemRepository(db)
    system = await sys_repo.get_system(system_id, tenant_id=current_user.tenant_id)
    if not system:
        raise HTTPException(status_code=404, detail="System not found")

    repo = DecisionRepository(db)
    rev = await repo.create_design_review(
        system_id=system_id,
        system_revision=system.revision,
        title=payload.title,
        chairperson=current_user.id,
        decision_id=payload.decision_id,
        requirement_baseline_id=payload.requirement_baseline_id,
        tenant_id=current_user.tenant_id,
        metadata_=payload.metadata,
    )
    return {"status": "success", "data": EngineeringDesignReviewResponse.model_validate(rev)}


@router.get("/systems/{system_id}/design-reviews", response_model=Dict[str, Any])
async def list_design_reviews(
    system_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    revs = await repo.get_design_reviews_by_system(system_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": [EngineeringDesignReviewResponse.model_validate(r) for r in revs]}


@router.get("/design-reviews/{review_id}", response_model=Dict[str, Any])
async def get_design_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    rev = await repo.get_design_review(review_id, tenant_id=current_user.tenant_id)
    if rev:
        return {"status": "success", "success": True, "data": EngineeringDesignReviewResponse.model_validate(rev)}

    # Fallback to circuit-level review (Wave 5)
    from app.services.verification_service import verification_service
    try:
        circ_review = await verification_service.get_review(
            db=db,
            review_id=review_id,
            current_user=current_user,
        )
        return {"status": "success", "success": True, "data": circ_review}
    except Exception:
        raise HTTPException(status_code=404, detail="Design review session not found")


# Participants
@router.post("/design-reviews/{review_id}/participants", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def add_participant(
    review_id: str,
    payload: EngineeringReviewParticipantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    rev = await repo.get_design_review(review_id, tenant_id=current_user.tenant_id)
    if not rev:
        raise HTTPException(status_code=404, detail="Design review session not found")

    part = await repo.add_participant(
        review_id=review_id,
        user_id=payload.user_id,
        name=payload.name,
        role=payload.role,
    )
    return {"status": "success", "data": EngineeringReviewParticipantResponse.model_validate(part)}


# Checkpoints
@router.post("/design-reviews/{review_id}/checkpoints", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def add_checkpoint(
    review_id: str,
    payload: EngineeringReviewCheckpointCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    rev = await repo.get_design_review(review_id, tenant_id=current_user.tenant_id)
    if not rev:
        raise HTTPException(status_code=404, detail="Design review session not found")

    chk = await repo.add_checkpoint(
        review_id=review_id,
        checkpoint_name=payload.checkpoint_name,
        description=payload.description,
        status=payload.status,
        notes=payload.notes,
    )
    return {"status": "success", "data": EngineeringReviewCheckpointResponse.model_validate(chk)}


@router.patch("/design-reviews/checkpoints/{checkpoint_id}", response_model=Dict[str, Any])
@router.patch("/review-checkpoints/{checkpoint_id}", response_model=Dict[str, Any])
async def update_checkpoint(
    checkpoint_id: str,
    payload: EngineeringReviewCheckpointUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    chk = await repo.update_checkpoint(
        checkpoint_id=checkpoint_id,
        status=payload.status,
        verified_by=current_user.id,
        notes=payload.notes,
    )
    if not chk:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return {"status": "success", "data": EngineeringReviewCheckpointResponse.model_validate(chk)}


# Findings
@router.post("/design-reviews/{review_id}/findings", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def add_finding(
    review_id: str,
    payload: EngineeringReviewFindingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    rev = await repo.get_design_review(review_id, tenant_id=current_user.tenant_id)
    if not rev:
        raise HTTPException(status_code=404, detail="Design review session not found")

    f = await repo.add_finding(
        review_id=review_id,
        source_analysis=payload.source_analysis,
        severity=payload.severity,
        description=payload.description,
        finding_id=payload.finding_id,
        affected_requirement_id=payload.affected_requirement_id,
        affected_subsystem_id=payload.affected_subsystem_id,
    )
    return {"status": "success", "data": EngineeringReviewFindingResponse.model_validate(f)}


@router.post("/design-reviews/findings/{finding_id}/waive", response_model=Dict[str, Any])
@router.post("/review-findings/{finding_id}/waive", response_model=Dict[str, Any])
async def waive_finding(
    finding_id: str,
    payload: FindingWaiverRequest,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    f = await repo.waive_finding(
        finding_id=finding_id,
        waived_by=current_user.id,
        waiver_rationale=payload.waiver_rationale,
    )
    if not f:
        raise HTTPException(status_code=404, detail="Finding not found")
    return {"status": "success", "data": EngineeringReviewFindingResponse.model_validate(f)}


# Actions
@router.post("/design-reviews/{review_id}/actions", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def add_action(
    review_id: str,
    payload: EngineeringReviewActionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    rev = await repo.get_design_review(review_id, tenant_id=current_user.tenant_id)
    if not rev:
        raise HTTPException(status_code=404, detail="Design review session not found")

    act = await repo.add_action(
        review_id=review_id,
        description=payload.description,
        owner=payload.owner,
        priority=payload.priority,
        due_at=payload.due_at,
        linked_requirement_id=payload.linked_requirement_id,
        linked_finding_id=payload.linked_finding_id,
        linked_verification_requirement_id=payload.linked_verification_requirement_id,
    )
    return {"status": "success", "data": EngineeringReviewActionResponse.model_validate(act)}


@router.patch("/design-reviews/actions/{action_id}", response_model=Dict[str, Any])
@router.patch("/review-actions/{action_id}", response_model=Dict[str, Any])
async def update_action(
    action_id: str,
    payload: EngineeringReviewActionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    act = await repo.update_action(
        action_id=action_id,
        updates=payload.model_dump(exclude_unset=True),
    )
    if not act:
        raise HTTPException(status_code=404, detail="Action item not found")
    return {"status": "success", "data": EngineeringReviewActionResponse.model_validate(act)}


# Readiness & Closure
@router.get("/design-reviews/{review_id}/readiness", response_model=Dict[str, Any])
async def get_review_readiness(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    repo = DecisionRepository(db)
    rev = await repo.get_design_review(review_id, tenant_id=current_user.tenant_id)
    if not rev:
        raise HTTPException(status_code=404, detail="Design review session not found")

    decision = None
    questions = []
    if rev.decision_id:
        decision = await repo.get_decision(rev.decision_id, tenant_id=current_user.tenant_id)
        questions = await repo.get_questions(rev.decision_id)

    readiness = DesignReviewReadinessService.evaluate_readiness(
        review=rev,
        decision=decision,
        checkpoints=rev.checkpoints or [],
        findings=rev.findings or [],
        questions=questions,
    )
    return {"status": "success", "data": readiness}


@router.post("/design-reviews/{review_id}/close", response_model=Dict[str, Any])
async def close_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = DecisionService(db)
    rev = await service.close_design_review(review_id, actor=current_user.id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": EngineeringDesignReviewResponse.model_validate(rev)}


# Full Report
@router.get("/design-reviews/{review_id}/report", response_model=Dict[str, Any])
async def get_review_report(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    service = DecisionService(db)
    report = await service.generate_review_report(review_id, tenant_id=current_user.tenant_id)
    return {"status": "success", "data": report}
