"""
DFM & Assembly Intelligence Service for Phase 3 Wave 7.
Orchestration layer coordinating physical fabrication checks, assembly rules,
BOM consistency, deterministic resolution proposals, and strict human authorization gates.
"""
from datetime import datetime, timezone
from typing import Any, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AuthenticatedUser
from app.models.db.bom import EngineeringBOM, EngineeringBOMLine
from app.models.db.dfm import (
    ManufacturingAnalysisRecord,
    ManufacturingAnalysisStatus,
    ManufacturingFindingStatus,
    ManufacturingProposalRecord,
    ManufacturingRuleSet,
)
from app.models.db.pcb import BoardFootprint, BoardPad, BoardTraceSegment, BoardVia, EngineeringBoard
from app.models.db.proposal import ProposalStatus
from app.models.schemas.dfm import (
    DFMSnapshotResponse,
    ManufacturingAnalysisCreate,
    ManufacturingFinding,
    ManufacturingProposalCreate,
    ManufacturingRuleSetCreate,
)
from app.services.ai.dfm.assembly_engine import AssemblyDFAEngine
from app.services.ai.dfm.bom_consistency_engine import BOMConsistencyDFMEngine
from app.services.ai.dfm.fabrication_engine import FabricationDFMEngine
from app.services.ai.dfm.proposal_engine import DFMProposalEngine
from app.services.ai.dfm.rule_registry import DEFAULT_RULESETS, compute_ruleset_digest
from app.services.ai.dfm.snapshot import DFMSnapshotService


class DFMService:
    """
    Orchestration service for PCB Manufacturing / DFM & Assembly Intelligence.
    """

    async def get_or_create_default_ruleset(
        self,
        db: AsyncSession,
        source_key: str = "FAB_STANDARD_2LAYER",
    ) -> ManufacturingRuleSet:
        stmt = select(ManufacturingRuleSet).where(
            ManufacturingRuleSet.source == source_key,
            ManufacturingRuleSet.is_default == True,
        )
        res = await db.execute(stmt)
        ruleset = res.scalar_one_or_none()

        if not ruleset:
            seed = DEFAULT_RULESETS.get(source_key, DEFAULT_RULESETS["FAB_STANDARD_2LAYER"])
            ruleset = ManufacturingRuleSet(
                id=str(uuid.uuid4()),
                tenant_id=None,
                name=seed["name"],
                version=1,
                source=seed["source"],
                source_revision=seed["source_revision"],
                source_digest=seed["source_digest"],
                rules=seed["rules"],
                is_default=seed["is_default"],
                effective_from=datetime.now(timezone.utc),
            )
            db.add(ruleset)
            await db.commit()
            await db.refresh(ruleset)

        return ruleset

    async def create_ruleset(
        self,
        db: AsyncSession,
        current_user: AuthenticatedUser,
        request: ManufacturingRuleSetCreate,
    ) -> ManufacturingRuleSet:
        digest = compute_ruleset_digest(request.rules)
        ruleset = ManufacturingRuleSet(
            id=str(uuid.uuid4()),
            tenant_id=current_user.tenant_id,
            name=request.name,
            version=1,
            source=request.source,
            source_revision=request.source_revision,
            source_digest=digest,
            rules=request.rules,
            is_default=request.is_default,
            effective_from=request.effective_from or datetime.now(timezone.utc),
            metadata_=request.metadata or {},
        )
        db.add(ruleset)
        await db.commit()
        await db.refresh(ruleset)
        return ruleset

    async def list_rulesets(
        self,
        db: AsyncSession,
        current_user: AuthenticatedUser,
    ) -> List[ManufacturingRuleSet]:
        stmt = select(ManufacturingRuleSet).where(
            (ManufacturingRuleSet.tenant_id == current_user.tenant_id)
            | (ManufacturingRuleSet.tenant_id == None)
        )
        res = await db.execute(stmt)
        rulesets = list(res.scalars().all())

        if not rulesets:
            default_rs = await self.get_or_create_default_ruleset(db)
            rulesets = [default_rs]

        return rulesets

    async def get_ruleset(
        self,
        db: AsyncSession,
        ruleset_id: str,
        current_user: AuthenticatedUser,
    ) -> ManufacturingRuleSet:
        stmt = select(ManufacturingRuleSet).where(ManufacturingRuleSet.id == ruleset_id)
        res = await db.execute(stmt)
        ruleset = res.scalar_one_or_none()

        if not ruleset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Manufacturing ruleset {ruleset_id} not found",
            )

        if ruleset.tenant_id and ruleset.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to requested ruleset across tenant boundaries",
            )

        return ruleset

    async def run_analysis(
        self,
        db: AsyncSession,
        current_user: AuthenticatedUser,
        request: ManufacturingAnalysisCreate,
    ) -> ManufacturingAnalysisRecord:
        # 1. Fetch board with full physical hierarchy
        board_stmt = (
            select(EngineeringBoard)
            .options(
                selectinload(EngineeringBoard.layers),
                selectinload(EngineeringBoard.footprints).selectinload(BoardFootprint.pads),
                selectinload(EngineeringBoard.traces),
                selectinload(EngineeringBoard.vias),
            )
            .where(EngineeringBoard.id == request.board_id)
        )
        if current_user.tenant_id:
            board_stmt = board_stmt.where(EngineeringBoard.tenant_id == current_user.tenant_id)

        board_res = await db.execute(board_stmt)
        board = board_res.scalar_one_or_none()

        if not board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engineering board {request.board_id} not found or tenant access denied",
            )

        board_rev = int(getattr(board, "version", 1))

        # 2. Resolve ruleset
        if request.rule_set_id:
            ruleset = await self.get_ruleset(db, request.rule_set_id, current_user)
        else:
            ruleset = await self.get_or_create_default_ruleset(db)

        # 3. Resolve BOM if requested
        bom = None
        if request.include_bom_check:
            bom_stmt = select(EngineeringBOM).options(
                selectinload(EngineeringBOM.lines).selectinload(EngineeringBOMLine.candidates)
            )
            if request.bom_id:
                bom_stmt = bom_stmt.where(EngineeringBOM.id == request.bom_id)
            else:
                bom_stmt = bom_stmt.where(
                    (EngineeringBOM.board_id == board.id) | (EngineeringBOM.circuit_id == board.circuit_id)
                ).order_by(EngineeringBOM.version.desc())

            if current_user.tenant_id:
                bom_stmt = bom_stmt.where(EngineeringBOM.tenant_id == current_user.tenant_id)

            bom_res = await db.execute(bom_stmt)
            bom = bom_res.scalars().first()

        # 4. Execute deterministic domain engines
        findings: list[ManufacturingFinding] = []

        # Fabrication rules (trace width, clearance, drill, annular ring, etc.)
        fab_findings = FabricationDFMEngine.evaluate_board_fabrication(board, ruleset.rules)
        findings.extend(fab_findings)

        # Assembly rules (component clearance, edge setback, pnp centroids, soldering)
        asm_findings = AssemblyDFAEngine.evaluate_board_assembly(board, ruleset.rules)
        findings.extend(asm_findings)

        # BOM consistency rules (package match, pad count)
        bom_findings = BOMConsistencyDFMEngine.evaluate_bom_pcb_consistency(board, bom, ruleset.rules)
        findings.extend(bom_findings)

        # 5. Summarize findings (ZERO synthetic scoring!)
        total_eval = len(findings)
        pass_cnt = sum(1 for f in findings if f.status == ManufacturingFindingStatus.PASS)
        fail_cnt = sum(1 for f in findings if f.status == ManufacturingFindingStatus.FAIL)
        warn_cnt = sum(1 for f in findings if f.status == ManufacturingFindingStatus.WARNING)
        unknown_cnt = sum(1 for f in findings if f.status in (ManufacturingFindingStatus.UNKNOWN, ManufacturingFindingStatus.NOT_EVALUATED))

        critical_violations = [f.message for f in findings if f.status == ManufacturingFindingStatus.FAIL]

        analysis_status = (
            ManufacturingAnalysisStatus.COMPLETED.value
            if fail_cnt == 0
            else ManufacturingAnalysisStatus.FAILED.value
        )

        summary_dict = {
            "total_rules_evaluated": total_eval,
            "pass_count": pass_cnt,
            "fail_count": fail_cnt,
            "warning_count": warn_cnt,
            "unknown_count": unknown_cnt,
            "critical_violations": critical_violations,
            "status": analysis_status,
        }

        # 6. Compute provenance digest
        raw_findings_dict = [f.model_dump() for f in findings]
        digest = DFMSnapshotService.compute_analysis_digest(
            board_id=str(board.id),
            board_revision=board_rev,
            rule_set_id=str(ruleset.id),
            rule_set_revision=str(ruleset.source_revision),
            findings=raw_findings_dict,
            summary=summary_dict,
        )

        analysis_id = str(uuid.uuid4())
        record = ManufacturingAnalysisRecord(
            id=analysis_id,
            board_id=board.id,
            board_revision=board_rev,
            circuit_id=board.circuit_id,
            circuit_revision=getattr(board, "circuit_version", 1),
            tenant_id=current_user.tenant_id,
            rule_set_id=ruleset.id,
            rule_set_revision=ruleset.source_revision,
            status=analysis_status,
            findings=raw_findings_dict,
            summary=summary_dict,
            provenance_digest=digest,
            created_by=current_user.id,
        )
        db.add(record)
        await db.flush()

        # 7. Generate deterministic proposals for actionable findings
        proposals_create = DFMProposalEngine.generate_proposals_for_findings(
            analysis_id=analysis_id,
            board=board,
            findings=findings,
        )
        for pc in proposals_create:
            proposal_rec = ManufacturingProposalRecord(
                id=str(uuid.uuid4()),
                board_id=board.id,
                board_revision=board_rev,
                tenant_id=current_user.tenant_id,
                analysis_id=analysis_id,
                rule_id=pc.rule_id,
                title=pc.title,
                description=pc.description,
                mutation_type=pc.mutation_type,
                proposed_mutations=pc.proposed_mutations,
                diff_preview=pc.diff_preview,
                status=ProposalStatus.PROPOSED.value,
                created_by=current_user.id,
            )
            db.add(proposal_rec)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=board.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.DFM_ANALYSIS_EXECUTED,
            entity_type="DFM_ANALYSIS",
            entity_id=record.id,
            entity_revision=board_rev,
            payload={
                "analysis_id": record.id,
                "board_id": board.id,
                "board_revision": board_rev,
                "rule_set_id": ruleset.id,
                "rule_set_revision": ruleset.source_revision,
                "status": record.status,
                "total_rules_evaluated": summary_dict.get("total_rules_evaluated", 0),
                "fail_count": summary_dict.get("fail_count", 0),
                "provenance_digest": record.provenance_digest,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        await db.refresh(record)
        return record

    async def get_analysis(
        self,
        db: AsyncSession,
        analysis_id: str,
        current_user: AuthenticatedUser,
    ) -> ManufacturingAnalysisRecord:
        stmt = (
            select(ManufacturingAnalysisRecord)
            .options(
                selectinload(ManufacturingAnalysisRecord.proposals),
                selectinload(ManufacturingAnalysisRecord.rule_set),
            )
            .where(ManufacturingAnalysisRecord.id == analysis_id)
        )
        if current_user.tenant_id:
            stmt = stmt.where(ManufacturingAnalysisRecord.tenant_id == current_user.tenant_id)

        res = await db.execute(stmt)
        record = res.scalar_one_or_none()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Manufacturing analysis record {analysis_id} not found or tenant access denied",
            )

        return record

    async def list_proposals(
        self,
        db: AsyncSession,
        analysis_id: str,
        current_user: AuthenticatedUser,
    ) -> List[ManufacturingProposalRecord]:
        stmt = select(ManufacturingProposalRecord).where(
            ManufacturingProposalRecord.analysis_id == analysis_id
        )
        if current_user.tenant_id:
            stmt = stmt.where(ManufacturingProposalRecord.tenant_id == current_user.tenant_id)

        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def approve_proposal(
        self,
        db: AsyncSession,
        proposal_id: str,
        current_user: AuthenticatedUser,
    ) -> ManufacturingProposalRecord:
        # Human authorization gate check
        DFMProposalEngine.enforce_human_approval_gate(current_user)

        stmt = select(ManufacturingProposalRecord).where(
            ManufacturingProposalRecord.id == proposal_id
        )
        if current_user.tenant_id:
            stmt = stmt.where(ManufacturingProposalRecord.tenant_id == current_user.tenant_id)

        res = await db.execute(stmt)
        proposal = res.scalar_one_or_none()

        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DFM proposal {proposal_id} not found or tenant access denied",
            )

        proposal.status = ProposalStatus.APPROVED.value
        proposal.approved_by = current_user.id
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal

    async def apply_proposal(
        self,
        db: AsyncSession,
        proposal_id: str,
        current_user: AuthenticatedUser,
    ) -> ManufacturingProposalRecord:
        # Human authorization gate check
        DFMProposalEngine.enforce_human_approval_gate(current_user)

        stmt = select(ManufacturingProposalRecord).where(
            ManufacturingProposalRecord.id == proposal_id
        )
        if current_user.tenant_id:
            stmt = stmt.where(ManufacturingProposalRecord.tenant_id == current_user.tenant_id)

        res = await db.execute(stmt)
        proposal = res.scalar_one_or_none()

        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"DFM proposal {proposal_id} not found or tenant access denied",
            )

        # Load board
        board_stmt = (
            select(EngineeringBoard)
            .options(
                selectinload(EngineeringBoard.traces),
                selectinload(EngineeringBoard.vias),
                selectinload(EngineeringBoard.footprints).selectinload(BoardFootprint.pads),
            )
            .where(EngineeringBoard.id == proposal.board_id)
        )
        board_res = await db.execute(board_stmt)
        board = board_res.scalar_one_or_none()

        if not board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Engineering board {proposal.board_id} not found",
            )

        if proposal.status != ProposalStatus.APPROVED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"UNAPPROVED_PROPOSAL: DFM proposal {proposal_id} must be in APPROVED status before application (current: {proposal.status}).",
            )

        # Apply mutations with stale check atomically
        try:
            DFMProposalEngine.apply_proposal_mutations(proposal, board, db)

            proposal.status = ProposalStatus.APPLIED.value
            proposal.applied_at = datetime.now(timezone.utc)
            if not proposal.approved_by:
                proposal.approved_by = current_user.id

            db.add(proposal)

            from app.services.audit_ledger_service import AuditLedgerService
            from app.models.db.audit_ledger import AuditEventType

            audit_service = AuditLedgerService(db)
            await audit_service.record_event(
                project_id=board.project_id,
                actor_id=current_user.id,
                actor_role=getattr(current_user, "role", "ENGINEER"),
                event_type=AuditEventType.DFM_PROPOSAL_APPLIED,
                entity_type="DFM_PROPOSAL",
                entity_id=proposal.id,
                entity_revision=board.version,
                payload={
                    "proposal_id": proposal.id,
                    "board_id": board.id,
                    "board_version": board.version,
                    "rule_id": proposal.rule_id,
                    "title": proposal.title,
                    "mutation_type": proposal.mutation_type,
                    "mutations_count": len(proposal.proposed_mutations or []),
                },
                tenant_id=current_user.tenant_id,
                commit=False,
            )

            await db.commit()
            await db.refresh(proposal)
            return proposal
        except Exception:
            await db.rollback()
            raise

    async def get_snapshot(
        self,
        db: AsyncSession,
        analysis_id: str,
        current_user: AuthenticatedUser,
    ) -> DFMSnapshotResponse:
        analysis = await self.get_analysis(db, analysis_id, current_user)
        return DFMSnapshotService.generate_snapshot(analysis)


dfm_service = DFMService()
