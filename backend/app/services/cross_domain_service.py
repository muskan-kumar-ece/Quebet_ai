"""
Cross-Domain Validation Service for Phase 3 Wave 8: Advanced Engineering Validation, Cross-Domain Consistency & System-Level Verification.
Orchestrates multi-domain data loading, runs deterministic validation engines, persists validation records,
and enforces tenant isolation and dynamic staleness detection.
STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- UNKNOWN != PASS
- Zero synthetic scoring.
"""
from typing import Any, Optional
import uuid
from fastapi import HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db.cross_domain import (
    CrossDomainValidationRecord,
    CrossDomainValidationStatus,
)
from app.models.db.project import Project
from app.models.db.circuit import Circuit
from app.models.db.pcb import EngineeringBoard
from app.models.db.bom import EngineeringBOM
from app.models.db.simulation import SimulationJob, SimulationResultRecord
from app.models.db.dfm import ManufacturingAnalysisRecord
from app.models.db.decision import EngineeringRequirement
from app.models.db.verification import EngineeringDesignReview, EngineeringEvidence
from app.models.db.provenance import EngineeringSource
from app.models.schemas.cross_domain import CrossDomainValidationRequest
from app.services.ai.cross_domain.cross_domain_engine import CrossDomainValidationEngine
from app.services.ai.cross_domain.snapshot import CrossDomainSnapshotEngine


class CrossDomainService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _check_record_staleness(self, record: CrossDomainValidationRecord) -> None:
        """
        Dynamically computes the current multi-domain engineering snapshot digest.
        If the current digest does not match record.snapshot_digest, marks record as stale
        and identifies precise staleness reasons.
        """
        project_id = record.project_id

        # Load current circuit
        c_stmt = select(Circuit).where(Circuit.project_id == project_id).options(
            selectinload(Circuit.components),
            selectinload(Circuit.nets),
            selectinload(Circuit.connections),
        ).order_by(desc(Circuit.created_at))
        c_res = await self.db.execute(c_stmt)
        circuit = c_res.scalars().first()

        # Load current board
        b_stmt = select(EngineeringBoard).where(EngineeringBoard.project_id == project_id).options(
            selectinload(EngineeringBoard.footprints),
            selectinload(EngineeringBoard.traces),
            selectinload(EngineeringBoard.vias),
            selectinload(EngineeringBoard.layers),
        ).order_by(desc(EngineeringBoard.created_at))
        b_res = await self.db.execute(b_stmt)
        board = b_res.scalars().first()

        # Load current BOM
        bom_stmt = select(EngineeringBOM).where(EngineeringBOM.project_id == project_id).options(
            selectinload(EngineeringBOM.lines),
        ).order_by(desc(EngineeringBOM.created_at))
        bom_res = await self.db.execute(bom_stmt)
        bom = bom_res.scalars().first()

        # Load current simulation job
        sim_stmt = select(SimulationJob).where(SimulationJob.project_id == project_id)
        if circuit:
            sim_stmt = sim_stmt.where(SimulationJob.circuit_id == circuit.id)
        sim_stmt = sim_stmt.order_by(desc(SimulationJob.created_at))
        sim_res = await self.db.execute(sim_stmt)
        simulation_job = sim_res.scalars().first()

        # Load current DFM analysis
        dfm_analysis = None
        if board:
            dfm_stmt = select(ManufacturingAnalysisRecord).where(
                ManufacturingAnalysisRecord.board_id == board.id
            ).order_by(desc(ManufacturingAnalysisRecord.created_at))
            d_res = await self.db.execute(dfm_stmt)
            dfm_analysis = d_res.scalars().first()

        # Load requirements
        req_stmt = select(EngineeringRequirement).where(
            EngineeringRequirement.project_id == project_id
        ).order_by(desc(EngineeringRequirement.created_at))
        req_res = await self.db.execute(req_stmt)
        requirements = list(req_res.scalars().all())

        # Load verifications
        ver_stmt = select(EngineeringDesignReview).where(
            EngineeringDesignReview.project_id == project_id
        )
        if circuit:
            ver_stmt = ver_stmt.where(EngineeringDesignReview.circuit_id == circuit.id)
        ver_stmt = ver_stmt.order_by(desc(EngineeringDesignReview.created_at))
        ver_res = await self.db.execute(ver_stmt)
        verifications = list(ver_res.scalars().all())

        # Compute current canonical snapshot & digest
        curr_snapshot = CrossDomainSnapshotEngine.serialize_domain_state(
            project_id=project_id,
            circuit=circuit,
            board=board,
            bom=bom,
            simulation_job=simulation_job,
            dfm_analysis=dfm_analysis,
            requirements=requirements,
            verifications=verifications,
        )
        curr_digest = CrossDomainSnapshotEngine.compute_canonical_digest(curr_snapshot)

        if curr_digest != record.snapshot_digest:
            record.is_stale = True
            reasons = []
            if record.circuit_id != (circuit.id if circuit else None):
                reasons.append("Active circuit entity has changed or been superseded.")
            if record.board_id != (board.id if board else None):
                reasons.append("Active PCB board layout has changed or been superseded.")
            if record.bom_id != (bom.id if bom else None):
                reasons.append("Active procurement BOM has changed or been superseded.")
            reasons.append(
                f"Multi-domain design state snapshot digest mismatch: "
                f"validated={record.snapshot_digest[:8]}... vs current={curr_digest[:8]}..."
            )
            record.staleness_reasons = reasons
        else:
            record.is_stale = False
            record.staleness_reasons = []

    async def validate_project(
        self,
        project_id: str,
        tenant_id: Optional[str] = None,
        request: Optional[CrossDomainValidationRequest] = None,
    ) -> CrossDomainValidationRecord:
        # Verify project existence and tenant boundary
        stmt = select(Project).where(Project.id == project_id)
        if tenant_id:
            stmt = stmt.where(Project.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        project = res.scalars().first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or unauthorized")

        # 1. Load Circuit
        circuit = None
        c_stmt = select(Circuit).where(Circuit.project_id == project_id).options(
            selectinload(Circuit.components),
            selectinload(Circuit.nets),
            selectinload(Circuit.connections),
        )
        if request and request.circuit_id:
            c_stmt = c_stmt.where(Circuit.id == request.circuit_id)
        else:
            c_stmt = c_stmt.order_by(desc(Circuit.created_at))
        c_res = await self.db.execute(c_stmt)
        circuit = c_res.scalars().first()

        # 2. Load Board
        board = None
        b_stmt = select(EngineeringBoard).where(EngineeringBoard.project_id == project_id).options(
            selectinload(EngineeringBoard.footprints),
            selectinload(EngineeringBoard.traces),
            selectinload(EngineeringBoard.vias),
            selectinload(EngineeringBoard.layers),
        )
        if request and request.board_id:
            b_stmt = b_stmt.where(EngineeringBoard.id == request.board_id)
        else:
            b_stmt = b_stmt.order_by(desc(EngineeringBoard.created_at))
        b_res = await self.db.execute(b_stmt)
        board = b_res.scalars().first()

        # 3. Load BOM
        bom = None
        bom_stmt = select(EngineeringBOM).where(EngineeringBOM.project_id == project_id).options(
            selectinload(EngineeringBOM.lines),
        )
        if request and request.bom_id:
            bom_stmt = bom_stmt.where(EngineeringBOM.id == request.bom_id)
        else:
            bom_stmt = bom_stmt.order_by(desc(EngineeringBOM.created_at))
        bom_res = await self.db.execute(bom_stmt)
        bom = bom_res.scalars().first()

        # 4. Load Simulation
        simulation_job = None
        simulation_result = None
        if not request or request.include_simulation:
            sim_stmt = select(SimulationJob).where(SimulationJob.project_id == project_id)
            if circuit:
                sim_stmt = sim_stmt.where(SimulationJob.circuit_id == circuit.id)
            sim_stmt = sim_stmt.order_by(desc(SimulationJob.created_at))
            sim_res = await self.db.execute(sim_stmt)
            simulation_job = sim_res.scalars().first()

            if simulation_job:
                res_stmt = select(SimulationResultRecord).where(SimulationResultRecord.simulation_job_id == simulation_job.id)
                r_res = await self.db.execute(res_stmt)
                simulation_result = r_res.scalars().first()

        # 5. Load DFM Analysis
        dfm_analysis = None
        current_board_digest = None
        if not request or request.include_dfm:
            if board:
                dfm_stmt = select(ManufacturingAnalysisRecord).where(
                    ManufacturingAnalysisRecord.board_id == board.id
                ).order_by(desc(ManufacturingAnalysisRecord.created_at))
                d_res = await self.db.execute(dfm_stmt)
                dfm_analysis = d_res.scalars().first()

        # 6. Load Requirements
        requirements = []
        if not request or request.include_requirements:
            req_stmt = select(EngineeringRequirement).where(
                EngineeringRequirement.project_id == project_id
            ).order_by(desc(EngineeringRequirement.created_at))
            req_res = await self.db.execute(req_stmt)
            requirements = list(req_res.scalars().all())

        # 7. Load Verifications & Evidence
        verifications = []
        evidence_items = []
        if not request or request.include_verification:
            ver_stmt = select(EngineeringDesignReview).where(
                EngineeringDesignReview.project_id == project_id
            )
            if circuit:
                ver_stmt = ver_stmt.where(EngineeringDesignReview.circuit_id == circuit.id)
            ver_stmt = ver_stmt.order_by(desc(EngineeringDesignReview.created_at))
            ver_res = await self.db.execute(ver_stmt)
            verifications = list(ver_res.scalars().all())

            if verifications:
                ver_ids = [str(v.id) for v in verifications]
                ev_stmt = select(EngineeringEvidence).where(
                    EngineeringEvidence.review_id.in_(ver_ids)
                ).order_by(desc(EngineeringEvidence.provided_at))
                ev_res = await self.db.execute(ev_stmt)
                evidence_items = list(ev_res.scalars().all())

        # 8. Load Sources
        src_stmt = select(EngineeringSource)
        if tenant_id:
            src_stmt = src_stmt.where((EngineeringSource.tenant_id == tenant_id) | (EngineeringSource.tenant_id.is_(None)))
        src_stmt = src_stmt.order_by(desc(EngineeringSource.created_at))
        src_res = await self.db.execute(src_stmt)
        sources = list(src_res.scalars().all())

        # Run cross-domain orchestration engine
        summary, findings, digest, domain_snapshots = CrossDomainValidationEngine.run_cross_domain_validation(
            project_id=project_id,
            circuit=circuit,
            board=board,
            bom=bom,
            simulation_job=simulation_job,
            simulation_result=simulation_result,
            dfm_analysis=dfm_analysis,
            current_board_digest=current_board_digest,
            requirements=requirements,
            verifications=verifications,
            evidence_items=evidence_items,
            sources=sources,
        )

        validation_id = str(uuid.uuid4())
        findings_dicts = [f.model_dump(mode="json") for f in findings]
        for fd in findings_dicts:
            fd["validation_id"] = validation_id
            fd["tenant_id"] = tenant_id

        # Persist validation record
        record = CrossDomainValidationRecord(
            id=validation_id,
            tenant_id=tenant_id,
            project_id=project_id,
            circuit_id=circuit.id if circuit else None,
            board_id=board.id if board else None,
            bom_id=bom.id if bom else None,
            validation_status=CrossDomainValidationStatus.COMPLETED,
            summary=summary.model_dump(mode="json"),
            findings=findings_dicts,
            domain_snapshots=domain_snapshots,
            is_stale=False,
            staleness_reasons=[],
            snapshot_digest=digest,
        )

        self.db.add(record)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(self.db)
        await audit_service.record_event(
            project_id=project_id,
            actor_id="system",
            actor_role="ENGINEER",
            event_type=AuditEventType.CROSS_DOMAIN_VALIDATED,
            entity_type="CROSS_DOMAIN_VALIDATION",
            entity_id=record.id,
            entity_revision=None,
            payload={
                "validation_id": record.id,
                "project_id": project_id,
                "circuit_id": record.circuit_id,
                "board_id": record.board_id,
                "bom_id": record.bom_id,
                "snapshot_digest": record.snapshot_digest,
                "findings_count": len(findings_dicts),
                "fail_count": summary.fail_count,
                "warning_count": summary.warning_count,
            },
            tenant_id=tenant_id,
            commit=False,
        )

        await self.db.commit()
        await self.db.refresh(record)

        return record

    async def get_validations(
        self,
        project_id: str,
        tenant_id: Optional[str] = None,
    ) -> list[CrossDomainValidationRecord]:
        stmt = select(CrossDomainValidationRecord).where(
            CrossDomainValidationRecord.project_id == project_id
        )
        if tenant_id:
            stmt = stmt.where(CrossDomainValidationRecord.tenant_id == tenant_id)
        stmt = stmt.order_by(desc(CrossDomainValidationRecord.created_at))
        res = await self.db.execute(stmt)
        records = list(res.scalars().all())
        for rec in records:
            await self._check_record_staleness(rec)
        return records

    async def get_validation(
        self,
        validation_id: str,
        project_id: str,
        tenant_id: Optional[str] = None,
    ) -> CrossDomainValidationRecord:
        stmt = select(CrossDomainValidationRecord).where(
            CrossDomainValidationRecord.id == validation_id,
            CrossDomainValidationRecord.project_id == project_id,
        )
        if tenant_id:
            stmt = stmt.where(CrossDomainValidationRecord.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        record = res.scalars().first()
        if not record:
            raise HTTPException(status_code=404, detail="Cross-domain validation record not found")
        await self._check_record_staleness(record)
        return record

    async def get_latest_validation(
        self,
        project_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[CrossDomainValidationRecord]:
        stmt = select(CrossDomainValidationRecord).where(
            CrossDomainValidationRecord.project_id == project_id,
        )
        if tenant_id:
            stmt = stmt.where(CrossDomainValidationRecord.tenant_id == tenant_id)
        stmt = stmt.order_by(desc(CrossDomainValidationRecord.created_at))
        res = await self.db.execute(stmt)
        record = res.scalars().first()
        if record:
            await self._check_record_staleness(record)
        return record
