from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.common import ApiResponse
from app.models.schemas.verification import (
    DesignReviewResponse,
    EvidenceCreate,
    EvidenceResponse,
    FailureModeResponse,
    RequirementStatusUpdate,
    TestPointCreate,
    TestPointResponse,
    VerificationMatrixResponse,
    VerificationRequirementResponse,
)
from app.services.verification_service import verification_service

router = APIRouter(tags=["Engineering Verification & Design Review"])


@router.post("/circuits/{circuit_id}/design-review", response_model=ApiResponse[DesignReviewResponse], status_code=status.HTTP_201_CREATED)
async def create_or_generate_design_review(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate or retrieve the latest revision-bound Design Review for a circuit.
    Derives deterministic failure modes, verification requirements, and suggested test points.
    """
    review = await verification_service.create_or_generate_review(
        db=db,
        circuit_id=circuit_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=review)


@router.get("/design-reviews/{review_id}", response_model=ApiResponse[DesignReviewResponse])
async def get_design_review(
    review_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve full details of a Design Review, including failure modes, requirements, and test points.
    Evaluates stale status against the current circuit revision.
    """
    review = await verification_service.get_review(
        db=db,
        review_id=review_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=review)


@router.get("/design-reviews/{review_id}/failure-modes", response_model=ApiResponse[list[FailureModeResponse]])
async def get_failure_modes(
    review_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all deterministic failure modes identified for this design review.
    """
    review = await verification_service.get_review(
        db=db,
        review_id=review_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=review.failure_modes)


@router.get("/design-reviews/{review_id}/verification-requirements", response_model=ApiResponse[list[VerificationRequirementResponse]])
async def get_verification_requirements(
    review_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all verification requirements in the VR001+ namespace for this design review.
    """
    review = await verification_service.get_review(
        db=db,
        review_id=review_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=review.verification_requirements)


@router.get("/design-reviews/{review_id}/verification-matrix", response_model=ApiResponse[VerificationMatrixResponse])
async def get_verification_matrix(
    review_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the inspectable verification matrix aggregating requirements, methods, evidence, and states.
    """
    matrix = await verification_service.get_verification_matrix(
        db=db,
        review_id=review_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=matrix)


@router.post("/verification-requirements/{requirement_id}/evidence", response_model=ApiResponse[EvidenceResponse], status_code=status.HTTP_201_CREATED)
async def add_verification_evidence(
    requirement_id: str,
    evidence_in: EvidenceCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Attach traceable engineering evidence (measurement, datasheet citation, calculation) to a requirement.
    Advances requirement status and recomputes overall review status.
    """
    evidence = await verification_service.add_evidence(
        db=db,
        requirement_id=requirement_id,
        evidence_in=evidence_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=evidence)


@router.patch("/verification-requirements/{requirement_id}/status", response_model=ApiResponse[VerificationRequirementResponse])
async def update_requirement_status(
    requirement_id: str,
    status_in: RequirementStatusUpdate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update verification requirement status with mandatory engineering justification.
    Enforces that UNKNOWN cannot be marked SATISFIED without verifiable evidence.
    """
    updated = await verification_service.update_requirement_status(
        db=db,
        requirement_id=requirement_id,
        status_in=status_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=updated)


@router.get("/design-reviews/{review_id}/test-points", response_model=ApiResponse[list[TestPointResponse]])
async def get_test_points(
    review_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve suggested physical and electrical test points for laboratory measurement.
    """
    review = await verification_service.get_review(
        db=db,
        review_id=review_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=review.test_points)


@router.post("/design-reviews/{review_id}/test-points", response_model=ApiResponse[TestPointResponse], status_code=status.HTTP_201_CREATED)
async def add_test_point(
    review_id: str,
    test_point_in: TestPointCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add a custom laboratory test point to an active design review.
    """
    test_point = await verification_service.add_test_point(
        db=db,
        review_id=review_id,
        test_point_in=test_point_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=test_point)


@router.post("/design-reviews/{review_id}/refresh", response_model=ApiResponse[DesignReviewResponse])
async def refresh_design_review(
    review_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Re-evaluate design review against the latest circuit revision and analysis.
    """
    review = await verification_service.get_review(
        db=db,
        review_id=review_id,
        current_user=current_user,
    )
    # Generate new review for latest circuit revision
    fresh = await verification_service.create_or_generate_review(
        db=db,
        circuit_id=review.circuit_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=fresh)
