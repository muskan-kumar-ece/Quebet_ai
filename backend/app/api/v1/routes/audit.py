"""
API endpoints for Phase 3 Wave 10A: Engineering Audit Ledger Foundation.

Provides project-scoped, tenant-isolated read APIs for:
1. Listing chronological engineering audit ledger events.
2. Verifying the complete mathematical and sequence integrity of the project's hash chain.

STRICT INVARIANTS:
- All endpoints strictly enforce server-side project membership and tenant isolation.
- No client-supplied tenant identity accepted as an authorization authority.
- Verification is read-only.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.audit_ledger import (
    AuditChainVerificationResponse,
    AuditLedgerListResponse,
    EngineeringAuditEventResponse,
)
from app.models.schemas.audit_anchor import (
    AuditAnchorListResponse,
    AuditAnchorRequest,
    AuditAnchorResponse,
    AuditAnchorVerificationResponse,
)
from app.models.schemas.common import ApiResponse
from app.services.audit_ledger_service import AuditLedgerService
from app.services.audit_anchor_service import AuditAnchorService
from app.services.project_service import project_service

router = APIRouter(prefix="/projects/{project_id}/audit", tags=["Engineering Audit Ledger"])


@router.get("/events", response_model=ApiResponse[AuditLedgerListResponse])
async def list_audit_events(
    project_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves chronological engineering audit events for a project with strict tenant boundary checks.
    """
    # Verify project exists and belongs to current user / tenant
    project = await project_service.get_project(db=db, project_id=project_id, current_user=current_user)

    service = AuditLedgerService(db)
    events = await service.list_events(project_id=project.id, limit=limit, offset=offset)

    response_data = AuditLedgerListResponse(
        project_id=project.id,
        total_events=len(events),
        events=[EngineeringAuditEventResponse.model_validate(e) for e in events],
    )
    return ApiResponse(success=True, data=response_data)


@router.get("/verify-chain", response_model=ApiResponse[AuditChainVerificationResponse])
async def verify_audit_chain(
    project_id: str,
    expected_head_hash: Optional[str] = Query(default=None),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verifies mathematical and cryptographic continuity of the project's audit hash chain:
    - Genesis correctness
    - Monotonic sequence continuity with zero gaps
    - Predecessor hash linkage
    - Canonical payload digest matching
    - Canonical event header digest matching
    - Truncation detection if expected_head_hash is supplied
    """
    # Verify project exists and belongs to current user / tenant
    project = await project_service.get_project(db=db, project_id=project_id, current_user=current_user)

    service = AuditLedgerService(db)
    verification_result = await service.verify_chain(
        project_id=project.id,
        expected_head_hash=expected_head_hash,
    )

    response_data = AuditChainVerificationResponse(**verification_result)
    return ApiResponse(success=True, data=response_data)


# ==============================================================================
# Phase 4D: External Audit Anchoring & Ledger Notarization Endpoints
# ==============================================================================

@router.post("/anchor", response_model=ApiResponse[AuditAnchorResponse])
async def request_audit_anchor(
    project_id: str,
    payload: Optional[AuditAnchorRequest] = None,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiates an immutable checkpoint and requests external RFC 3161 timestamp notarization.
    Strictly restricted to authorized human engineering roles (AI ENGINEERING AUTHORITY = NONE).
    """
    service = AuditAnchorService(db)
    anchor = await service.request_anchor(
        project_id=project_id,
        current_user=current_user,
        tsa_url=payload.tsa_url if payload else None,
        ca_cert_path=payload.ca_cert_path if payload else None,
        force_retry=payload.force_retry if payload else False,
    )
    return ApiResponse(success=True, data=AuditAnchorResponse.model_validate(anchor))


@router.get("/anchors", response_model=ApiResponse[AuditAnchorListResponse])
async def list_audit_anchors(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves chronological RFC 3161 audit anchors for a project with strict tenant boundary checks.
    """
    service = AuditAnchorService(db)
    anchors = await service.list_anchors(
        project_id=project_id,
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        success=True,
        data=AuditAnchorListResponse(
            project_id=project_id,
            total_anchors=len(anchors),
            anchors=[AuditAnchorResponse.model_validate(a) for a in anchors],
        ),
    )


@router.get("/anchors/{anchor_id}", response_model=ApiResponse[AuditAnchorResponse])
async def get_audit_anchor(
    project_id: str,
    anchor_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieves a specific RFC 3161 audit anchor record by ID.
    """
    service = AuditAnchorService(db)
    anchor = await service.get_anchor_by_id(
        project_id=project_id,
        anchor_id=anchor_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=AuditAnchorResponse.model_validate(anchor))


@router.post("/anchors/{anchor_id}/verify", response_model=ApiResponse[AuditAnchorVerificationResponse])
async def verify_audit_anchor(
    project_id: str,
    anchor_id: str,
    ca_cert_path: Optional[str] = Query(default=None),
    check_events: bool = Query(default=True),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Executes full cryptographic and ledger re-verification of a stored audit anchor:
    - Manifest canonicalization and digest matching
    - 10-stage CMS signature, EKU, and CA chain validation
    - Underlying audit ledger continuity check over the covered sequence range
    """
    service = AuditAnchorService(db)
    verification = await service.verify_anchor(
        project_id=project_id,
        anchor_id=anchor_id,
        current_user=current_user,
        ca_cert_path=ca_cert_path,
        check_underlying_events=check_events,
    )
    return ApiResponse(success=True, data=AuditAnchorVerificationResponse(**verification))
