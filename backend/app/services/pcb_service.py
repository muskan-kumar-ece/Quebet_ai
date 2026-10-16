from datetime import datetime, timezone
from typing import Any
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AuthenticatedUser
from app.models.db.analysis import CircuitAnalysis
from app.models.db.circuit import Circuit
from app.models.db.pcb import (
    BoardFootprint,
    BoardLayer,
    BoardPad,
    BoardStatus,
    BoardTraceSegment,
    BoardVia,
    EngineeringBoard,
    LayerType,
    PCBAnalysisRecord,
    PCBProposalRecord,
)
from app.models.db.proposal import ProposalStatus
from app.models.schemas.pcb import (
    EngineeringBoardCreate,
    EngineeringBoardUpdate,
    PCBAnalysisResponse,
    PCBFinding,
    PCBProposalCreate,
    PCBProposalResponse,
    PCBSnapshotResponse,
)
from app.repositories.circuit_repo import circuit_repo
from app.services.ai.pcb.drc_engine import PCBRuleEngine
from app.services.ai.pcb.proposal_engine import PCBProposalEngine
from app.services.ai.pcb.snapshot import PCBSnapshotService


class PCBService:
    """
    Orchestration service for physical PCB Engineering Intelligence workflows.
    Enforces tenant boundaries, schematic revision binding, deterministic DRC analysis,
    and human-gated layout proposals.
    """

    async def create_board(
        self,
        db: AsyncSession,
        current_user: AuthenticatedUser,
        request: EngineeringBoardCreate,
    ) -> EngineeringBoard:
        # 1. Verify circuit ownership and tenant access
        circuit = await circuit_repo.get_by_id(
            db=db,
            circuit_id=request.circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not circuit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit {request.circuit_id} not found or tenant access denied",
            )

        board_id = str(uuid.uuid4())
        board = EngineeringBoard(
            id=board_id,
            project_id=circuit.project_id,
            circuit_id=circuit.id,
            circuit_version=circuit.version,
            tenant_id=current_user.tenant_id,
            name=request.name,
            version=1,
            status=BoardStatus.DRAFT.value,
            dimensions=request.dimensions,
            units=request.units,
            board_outline=request.board_outline,
            created_by=current_user.id,
            metadata_=request.metadata or {},
        )

        # Initialize standard 2-layer stackup
        l1 = BoardLayer(
            id=str(uuid.uuid4()),
            board_id=board_id,
            name="F.Cu",
            layer_type=LayerType.COPPER.value,
            layer_order=1,
            is_copper=True,
            thickness_um=35.0,  # 1 oz standard
            copper_weight_oz=1.0,
        )
        l2 = BoardLayer(
            id=str(uuid.uuid4()),
            board_id=board_id,
            name="B.Cu",
            layer_type=LayerType.COPPER.value,
            layer_order=2,
            is_copper=True,
            thickness_um=35.0,
            copper_weight_oz=1.0,
        )
        board.layers.extend([l1, l2])

        # Compute initial integrity digest
        snap = PCBSnapshotService.generate_canonical_snapshot(board)
        board.integrity_digest = PCBSnapshotService.compute_integrity_digest(snap)

        db.add(board)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.BOARD_CREATED,
            entity_type="BOARD",
            entity_id=board.id,
            entity_revision=board.version,
            payload={
                "board_id": board.id,
                "circuit_id": board.circuit_id,
                "name": board.name,
                "dimensions": board.dimensions,
                "units": board.units,
                "integrity_digest": board.integrity_digest,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        return await self.get_board(db, board_id, current_user)

    async def get_board(
        self,
        db: AsyncSession,
        board_id: str,
        current_user: AuthenticatedUser,
    ) -> EngineeringBoard:
        stmt = (
            select(EngineeringBoard)
            .where(EngineeringBoard.id == board_id)
            .options(
                selectinload(EngineeringBoard.layers),
                selectinload(EngineeringBoard.footprints).selectinload(BoardFootprint.pads),
                selectinload(EngineeringBoard.traces),
                selectinload(EngineeringBoard.vias),
            )
        )
        if current_user.tenant_id:
            stmt = stmt.where(EngineeringBoard.tenant_id == current_user.tenant_id)
        else:
            stmt = stmt.where(EngineeringBoard.tenant_id.is_(None), EngineeringBoard.created_by == current_user.id)

        res = await db.execute(stmt)
        board = res.scalar_one_or_none()
        if not board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engineering board {board_id} not found or tenant access denied",
            )
        return board

    async def list_boards(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> list[EngineeringBoard]:
        circuit = await circuit_repo.get_by_id(
            db=db,
            circuit_id=circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not circuit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit {circuit_id} not found or tenant access denied",
            )

        stmt = (
            select(EngineeringBoard)
            .where(EngineeringBoard.circuit_id == circuit_id)
            .options(
                selectinload(EngineeringBoard.layers),
                selectinload(EngineeringBoard.footprints).selectinload(BoardFootprint.pads),
                selectinload(EngineeringBoard.traces),
                selectinload(EngineeringBoard.vias),
            )
            .order_by(EngineeringBoard.created_at.desc())
        )
        if current_user.tenant_id:
            stmt = stmt.where(EngineeringBoard.tenant_id == current_user.tenant_id)
        else:
            stmt = stmt.where(EngineeringBoard.tenant_id.is_(None), EngineeringBoard.created_by == current_user.id)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def update_board(
        self,
        db: AsyncSession,
        board_id: str,
        update_req: EngineeringBoardUpdate,
        current_user: AuthenticatedUser,
    ) -> EngineeringBoard:
        board = await self.get_board(db, board_id, current_user)
        if update_req.name is not None:
            board.name = update_req.name
        if update_req.dimensions is not None:
            board.dimensions = update_req.dimensions
        if update_req.units is not None:
            board.units = update_req.units
        if update_req.board_outline is not None:
            board.board_outline = update_req.board_outline
        if update_req.metadata is not None:
            board.metadata_ = update_req.metadata

        board.version += 1
        snap = PCBSnapshotService.generate_canonical_snapshot(board)
        board.integrity_digest = PCBSnapshotService.compute_integrity_digest(snap)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=board.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.BOARD_MUTATED,
            entity_type="BOARD",
            entity_id=board.id,
            entity_revision=board.version,
            payload={
                "board_id": board.id,
                "circuit_id": board.circuit_id,
                "name": board.name,
                "version": board.version,
                "dimensions": board.dimensions,
                "units": board.units,
                "integrity_digest": board.integrity_digest,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        return board

    async def run_drc(
        self,
        db: AsyncSession,
        board_id: str,
        current_user: AuthenticatedUser,
    ) -> PCBAnalysisRecord:
        board = await self.get_board(db, board_id, current_user)

        # Fetch authoritative circuit with components, nets, connections
        circuit = await circuit_repo.get_by_id(
            db=db,
            circuit_id=board.circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not circuit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bound circuit not found for this board",
            )

        # Fetch latest Wave 3 analytical analysis
        stmt = (
            select(CircuitAnalysis)
            .where(CircuitAnalysis.circuit_id == circuit.id)
            .order_by(CircuitAnalysis.created_at.desc())
            .limit(1)
        )
        if current_user.tenant_id:
            stmt = stmt.where(CircuitAnalysis.tenant_id == current_user.tenant_id)
        else:
            stmt = stmt.where(CircuitAnalysis.tenant_id.is_(None), CircuitAnalysis.created_by == current_user.id)
        ana_res = await db.execute(stmt)
        latest_analysis = ana_res.scalar_one_or_none()

        # Compute snapshot and integrity digest
        snap = PCBSnapshotService.generate_canonical_snapshot(board)
        digest = PCBSnapshotService.compute_integrity_digest(snap)
        board.integrity_digest = digest

        # Run deterministic DRC
        findings, evals, metrics = PCBRuleEngine.run_drc(
            circuit=circuit,
            board=board,
            analysis=latest_analysis,
        )

        analysis_rec = PCBAnalysisRecord(
            id=str(uuid.uuid4()),
            board_id=board.id,
            board_version=board.version,
            circuit_id=circuit.id,
            circuit_version=circuit.version,
            tenant_id=current_user.tenant_id,
            status="COMPLETED",
            ruleset_version=PCBRuleEngine.RULESET_VERSION,
            snapshot_digest=digest,
            findings=[f.model_dump() for f in findings],
            metrics=metrics,
            classification="PCB_ANALYSIS",
            verification_status="NOT_VERIFIED",
        )

        db.add(analysis_rec)
        await db.commit()
        await db.refresh(analysis_rec)
        return analysis_rec

    async def get_analysis(
        self,
        db: AsyncSession,
        board_id: str,
        analysis_id: str,
        current_user: AuthenticatedUser,
    ) -> PCBAnalysisResponse:
        board = await self.get_board(db, board_id, current_user)
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=board.circuit_id, tenant_id=current_user.tenant_id, owner_id=current_user.id)

        stmt = select(PCBAnalysisRecord).where(
            PCBAnalysisRecord.id == analysis_id,
            PCBAnalysisRecord.board_id == board_id,
        )
        if current_user.tenant_id:
            stmt = stmt.where(PCBAnalysisRecord.tenant_id == current_user.tenant_id)
        else:
            stmt = stmt.where(PCBAnalysisRecord.tenant_id.is_(None))

        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PCB analysis {analysis_id} not found for board {board_id}",
            )

        # Staleness evaluation
        is_stale = (board.version > record.board_version) or (
            circuit is not None and circuit.version > record.circuit_version
        )

        findings_objs = [PCBFinding(**f) for f in record.findings]

        return PCBAnalysisResponse(
            id=record.id,
            board_id=record.board_id,
            board_version=record.board_version,
            circuit_id=record.circuit_id,
            circuit_version=record.circuit_version,
            tenant_id=record.tenant_id,
            is_stale=is_stale,
            status=record.status,
            ruleset_version=record.ruleset_version,
            snapshot_digest=record.snapshot_digest,
            findings=findings_objs,
            metrics=record.metrics,
            classification=record.classification,
            verification_status=record.verification_status,
            created_at=record.created_at,
        )

    async def create_proposal(
        self,
        db: AsyncSession,
        board_id: str,
        req: PCBProposalCreate,
        current_user: AuthenticatedUser,
    ) -> PCBProposalRecord:
        board = await self.get_board(db, board_id, current_user)

        val_res = PCBProposalEngine.validate_proposal(
            board=board,
            operations=req.operations,
            base_revision=board.version,
        )

        proposal = PCBProposalRecord(
            id=str(uuid.uuid4()),
            board_id=board.id,
            base_revision=board.version,
            circuit_version=board.circuit_version,
            tenant_id=current_user.tenant_id,
            created_by=current_user.id,
            title=req.title,
            description=req.description,
            status=ProposalStatus.PROPOSED.value,
            operations=req.operations,
            validation_result=val_res,
        )

        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal

    async def approve_proposal(
        self,
        db: AsyncSession,
        board_id: str,
        proposal_id: str,
        current_user: AuthenticatedUser,
    ) -> PCBProposalRecord:
        # AI Gate Policy: AUTONOMOUS_PROPOSAL_APPROVAL = DISABLED
        actor_role = (current_user.role or "").lower()
        actor_id = (current_user.id or "").lower()
        if (
            actor_role in ("ai", "ai_agent", "service:ai", "model")
            or actor_id.startswith("ai-")
            or "agent" in actor_id
            or "bot" in actor_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "AI_UNAUTHORIZED_PROPOSAL_APPROVAL",
                    "message": "AI actors are strictly prohibited from approving layout proposals. Explicit human engineering approval is required.",
                },
            )

        board = await self.get_board(db, board_id, current_user)
        stmt = select(PCBProposalRecord).where(
            PCBProposalRecord.id == proposal_id,
            PCBProposalRecord.board_id == board_id,
        )
        if current_user.tenant_id:
            stmt = stmt.where(PCBProposalRecord.tenant_id == current_user.tenant_id)
        res = await db.execute(stmt)
        proposal = res.scalar_one_or_none()
        if not proposal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

        # Staleness check
        if board.version > proposal.base_revision:
            proposal.status = ProposalStatus.STALE.value
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot approve proposal: board revision has advanced from {proposal.base_revision} to {board.version}.",
            )

        proposal.status = ProposalStatus.APPROVED.value
        await db.commit()
        await db.refresh(proposal)
        return proposal

    async def apply_proposal(
        self,
        db: AsyncSession,
        board_id: str,
        proposal_id: str,
        current_user: AuthenticatedUser,
    ) -> EngineeringBoard:
        # AI Gate Policy: AUTONOMOUS_PROPOSAL_APPLICATION = DISABLED
        actor_role = (current_user.role or "").lower()
        actor_id = (current_user.id or "").lower()
        if (
            actor_role in ("ai", "ai_agent", "service:ai", "model")
            or actor_id.startswith("ai-")
            or "agent" in actor_id
            or "bot" in actor_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "AI_UNAUTHORIZED_PROPOSAL_APPLICATION",
                    "message": "AI actors are strictly prohibited from applying layout proposals. Explicit human engineering execution is required.",
                },
            )

        board = await self.get_board(db, board_id, current_user)
        stmt = select(PCBProposalRecord).where(
            PCBProposalRecord.id == proposal_id,
            PCBProposalRecord.board_id == board_id,
        )
        if current_user.tenant_id:
            stmt = stmt.where(PCBProposalRecord.tenant_id == current_user.tenant_id)
        res = await db.execute(stmt)
        proposal = res.scalar_one_or_none()
        if not proposal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

        try:
            PCBProposalEngine.apply_proposal(board=board, proposal=proposal)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        proposal.status = ProposalStatus.APPLIED.value
        proposal.applied_at = datetime.now(timezone.utc)

        await db.commit()
        return board

    async def get_snapshot(
        self,
        db: AsyncSession,
        board_id: str,
        current_user: AuthenticatedUser,
    ) -> PCBSnapshotResponse:
        board = await self.get_board(db, board_id, current_user)
        snap = PCBSnapshotService.generate_canonical_snapshot(board)
        digest = PCBSnapshotService.compute_integrity_digest(snap)

        return PCBSnapshotResponse(
            board_id=str(board.id),
            board_version=int(board.version),
            circuit_id=str(board.circuit_id),
            circuit_version=int(board.circuit_version),
            snapshot_digest=digest,
            provenance_label="PROVENANCE_AND_INTEGRITY_DIGEST",
            content=snap,
        )


pcb_service = PCBService()
