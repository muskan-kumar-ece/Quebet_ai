from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.common import ApiResponse
from app.models.schemas.pcb import (
    EngineeringBoardCreate,
    EngineeringBoardResponse,
    EngineeringBoardUpdate,
    PCBAnalysisResponse,
    PCBProposalCreate,
    PCBProposalResponse,
    PCBSnapshotResponse,
)
from app.services.pcb_service import pcb_service

router = APIRouter(tags=["PCB & Schematic Intelligence"])


@router.post("/boards", response_model=ApiResponse[EngineeringBoardResponse])
async def create_board(
    request: EngineeringBoardCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an EngineeringBoard bound to a schematic circuit."""
    board = await pcb_service.create_board(db=db, current_user=current_user, request=request)
    return ApiResponse(success=True, data=EngineeringBoardResponse.model_validate(board))


@router.get("/boards/{board_id}", response_model=ApiResponse[EngineeringBoardResponse])
async def get_board(
    board_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve an EngineeringBoard with its stackup, footprints, pads, traces, and vias."""
    board = await pcb_service.get_board(db=db, board_id=board_id, current_user=current_user)
    return ApiResponse(success=True, data=EngineeringBoardResponse.model_validate(board))


@router.patch("/boards/{board_id}", response_model=ApiResponse[EngineeringBoardResponse])
async def update_board(
    board_id: str,
    request: EngineeringBoardUpdate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Update board properties (dimensions, units, outline)."""
    board = await pcb_service.update_board(db=db, board_id=board_id, update_req=request, current_user=current_user)
    return ApiResponse(success=True, data=EngineeringBoardResponse.model_validate(board))


@router.get("/circuits/{circuit_id}/boards", response_model=ApiResponse[list[EngineeringBoardResponse]])
async def list_circuit_boards(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List all boards bound to a specific circuit."""
    boards = await pcb_service.list_boards(db=db, circuit_id=circuit_id, current_user=current_user)
    return ApiResponse(success=True, data=[EngineeringBoardResponse.model_validate(b) for b in boards])


@router.post("/boards/{board_id}/drc", response_model=ApiResponse[PCBAnalysisResponse])
async def run_drc_analysis(
    board_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run deterministic Design Rule Check (DRC) and constraint validation.
    DRC results are strictly PCB_ANALYSIS and NOT_VERIFIED.
    """
    record = await pcb_service.run_drc(db=db, board_id=board_id, current_user=current_user)
    resp = await pcb_service.get_analysis(db=db, board_id=board_id, analysis_id=record.id, current_user=current_user)
    return ApiResponse(success=True, data=resp)


@router.get("/boards/{board_id}/analyses/{analysis_id}", response_model=ApiResponse[PCBAnalysisResponse])
async def get_drc_analysis(
    board_id: str,
    analysis_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical DRC findings and check revision staleness."""
    resp = await pcb_service.get_analysis(db=db, board_id=board_id, analysis_id=analysis_id, current_user=current_user)
    return ApiResponse(success=True, data=resp)


@router.post("/boards/{board_id}/proposals", response_model=ApiResponse[PCBProposalResponse])
async def create_layout_proposal(
    board_id: str,
    request: PCBProposalCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a human-gated layout proposal."""
    proposal = await pcb_service.create_proposal(db=db, board_id=board_id, req=request, current_user=current_user)
    return ApiResponse(success=True, data=PCBProposalResponse.model_validate(proposal))


@router.post("/boards/{board_id}/proposals/{proposal_id}/approve", response_model=ApiResponse[PCBProposalResponse])
async def approve_layout_proposal(
    board_id: str,
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Human approval gate for a layout proposal."""
    proposal = await pcb_service.approve_proposal(db=db, board_id=board_id, proposal_id=proposal_id, current_user=current_user)
    return ApiResponse(success=True, data=PCBProposalResponse.model_validate(proposal))


@router.post("/boards/{board_id}/proposals/{proposal_id}/apply", response_model=ApiResponse[EngineeringBoardResponse])
async def apply_layout_proposal(
    board_id: str,
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Atomically apply an approved layout proposal. Fails if not approved or if board revision is stale."""
    board = await pcb_service.apply_proposal(db=db, board_id=board_id, proposal_id=proposal_id, current_user=current_user)
    return ApiResponse(success=True, data=EngineeringBoardResponse.model_validate(board))


@router.get("/boards/{board_id}/snapshot", response_model=ApiResponse[PCBSnapshotResponse])
async def get_board_snapshot(
    board_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve canonical snapshot and PROVENANCE_AND_INTEGRITY_DIGEST for a board."""
    snap = await pcb_service.get_snapshot(db=db, board_id=board_id, current_user=current_user)
    return ApiResponse(success=True, data=snap)


# --- /pcb namespace aliases for frontend and cognitive client compatibility ---

@router.get("/pcb/boards/by-circuit/{circuit_id}", response_model=ApiResponse[EngineeringBoardResponse | None])
async def get_pcb_board_by_circuit(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    boards = await pcb_service.list_boards(db=db, circuit_id=circuit_id, current_user=current_user)
    first_board = boards[0] if boards else None
    return ApiResponse(
        success=True,
        data=EngineeringBoardResponse.model_validate(first_board) if first_board else None,
    )


@router.post("/pcb/boards/{board_id}/analyze", response_model=ApiResponse[PCBAnalysisResponse])
async def run_pcb_analysis_alias(
    board_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    record = await pcb_service.run_drc(db=db, board_id=board_id, current_user=current_user)
    resp = await pcb_service.get_analysis(db=db, board_id=board_id, analysis_id=record.id, current_user=current_user)
    return ApiResponse(success=True, data=resp)


@router.get("/pcb/boards/{board_id}/proposals", response_model=ApiResponse[list[PCBProposalResponse]])
async def list_pcb_proposals_alias(
    board_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    proposals = await pcb_service.list_proposals(db=db, board_id=board_id, current_user=current_user)
    return ApiResponse(success=True, data=[PCBProposalResponse.model_validate(p) for p in proposals])


@router.post("/pcb/boards/{board_id}/proposals/{proposal_id}/approve", response_model=ApiResponse[PCBProposalResponse])
async def approve_pcb_proposal_alias(
    board_id: str,
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    proposal = await pcb_service.approve_proposal(db=db, board_id=board_id, proposal_id=proposal_id, current_user=current_user)
    return ApiResponse(success=True, data=PCBProposalResponse.model_validate(proposal))


@router.post("/pcb/proposals/{proposal_id}/approve", response_model=ApiResponse[PCBProposalResponse])
async def approve_pcb_proposal_by_id(
    proposal_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.db.pcb import PCBProposalRecord
    stmt = select(PCBProposalRecord).where(PCBProposalRecord.id == proposal_id)
    if current_user.tenant_id:
        stmt = stmt.where(PCBProposalRecord.tenant_id == current_user.tenant_id)
    res = await db.execute(stmt)
    prop = res.scalar_one_or_none()
    if not prop:
        raise HTTPException(status_code=404, detail="Proposal not found")
    proposal = await pcb_service.approve_proposal(db=db, board_id=prop.board_id, proposal_id=proposal_id, current_user=current_user)
    return ApiResponse(success=True, data=PCBProposalResponse.model_validate(proposal))

