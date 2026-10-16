"""
Workspace Service for Phase 3 Wave 9: Unified Engineering Project Workspace,
Revision Navigation & State Synthesis.

Aggregates authoritative project state across all 8 engineering domains without
duplicating data or mutating authoritative records.

STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- UNKNOWN != PASS
- UNKNOWN != CONFIGURED
- MISSING != CONFIGURED
- CALCULATED != PHYSICALLY VERIFIED
- HISTORICAL_VERIFICATION != CURRENT_VERIFICATION
- ZERO SYNTHETIC SCORING
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db.project import Project
from app.models.db.circuit import Circuit
from app.models.db.pcb import EngineeringBoard
from app.models.db.bom import EngineeringBOM
from app.models.db.simulation import SimulationJob
from app.models.db.dfm import ManufacturingAnalysisRecord
from app.models.db.decision import EngineeringRequirement
from app.models.db.verification import EngineeringDesignReview
from app.models.db.cross_domain import CrossDomainValidationRecord
from app.models.schemas.workspace import (
    BoundEntityRef,
    CircuitRevisionLineageItem,
    CrossDomainSummary,
    DomainInventoryItem,
    DomainStatus,
    ProjectActivityItem,
    ProjectActivityTimelineResponse,
    ProjectRevisionLineageResponse,
    ProjectWorkspaceStateResponse,
    TimelineCategory,
)
from app.services.cross_domain_service import CrossDomainService


class WorkspaceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_workspace_state(self, project: Project) -> ProjectWorkspaceStateResponse:
        """
        Aggregates multi-domain engineering inventory, authoritative posture,
        and cross-domain validation staleness for a project.
        """
        project_id = project.id

        # 1. Circuits
        c_stmt = (
            select(Circuit)
            .where(Circuit.project_id == project_id)
            .order_by(desc(Circuit.version), desc(Circuit.created_at))
        )
        c_res = await self.db.execute(c_stmt)
        circuits = list(c_res.scalars().all())
        active_circuit = circuits[0] if circuits else None
        active_circuit_version = active_circuit.version if active_circuit else None

        # 2. Boards
        b_stmt = (
            select(EngineeringBoard)
            .where(EngineeringBoard.project_id == project_id)
            .order_by(desc(EngineeringBoard.version), desc(EngineeringBoard.created_at))
        )
        b_res = await self.db.execute(b_stmt)
        boards = list(b_res.scalars().all())
        latest_board = boards[0] if boards else None

        # 3. BOMs
        bom_stmt = (
            select(EngineeringBOM)
            .where(EngineeringBOM.project_id == project_id)
            .order_by(desc(EngineeringBOM.version), desc(EngineeringBOM.created_at))
        )
        bom_res = await self.db.execute(bom_stmt)
        boms = list(bom_res.scalars().all())
        latest_bom = boms[0] if boms else None

        # 4. Simulations
        sim_stmt = (
            select(SimulationJob)
            .where(SimulationJob.project_id == project_id)
            .order_by(desc(SimulationJob.created_at))
        )
        sim_res = await self.db.execute(sim_stmt)
        simulations = list(sim_res.scalars().all())
        latest_sim = simulations[0] if simulations else None

        # 5. Manufacturing Analyses
        circuit_ids = [c.id for c in circuits]
        board_ids = [b.id for b in boards]
        mfg_analyses: List[ManufacturingAnalysisRecord] = []
        if circuit_ids or board_ids:
            mfg_conditions = []
            if circuit_ids:
                mfg_conditions.append(ManufacturingAnalysisRecord.circuit_id.in_(circuit_ids))
            if board_ids:
                mfg_conditions.append(ManufacturingAnalysisRecord.board_id.in_(board_ids))
            
            from sqlalchemy import or_
            mfg_stmt = (
                select(ManufacturingAnalysisRecord)
                .where(or_(*mfg_conditions))
                .order_by(desc(ManufacturingAnalysisRecord.created_at))
            )
            mfg_res = await self.db.execute(mfg_stmt)
            mfg_analyses = list(mfg_res.scalars().all())
        latest_mfg = mfg_analyses[0] if mfg_analyses else None

        # 6. Requirements
        req_stmt = (
            select(EngineeringRequirement)
            .where(EngineeringRequirement.project_id == project_id)
            .order_by(desc(EngineeringRequirement.created_at))
        )
        req_res = await self.db.execute(req_stmt)
        requirements = list(req_res.scalars().all())
        latest_req = requirements[0] if requirements else None

        # 7. Design Reviews
        rev_stmt = (
            select(EngineeringDesignReview)
            .where(EngineeringDesignReview.project_id == project_id)
            .order_by(desc(EngineeringDesignReview.created_at))
        )
        rev_res = await self.db.execute(rev_stmt)
        reviews = list(rev_res.scalars().all())
        latest_rev = reviews[0] if reviews else None

        # 8. Cross-Domain Validation Records
        cdv_stmt = (
            select(CrossDomainValidationRecord)
            .where(CrossDomainValidationRecord.project_id == project_id)
            .order_by(desc(CrossDomainValidationRecord.created_at))
        )
        cdv_res = await self.db.execute(cdv_stmt)
        cdv_records = list(cdv_res.scalars().all())
        latest_cdv = cdv_records[0] if cdv_records else None

        # --- Evaluate Domain Postures ---
        domains: List[DomainInventoryItem] = []

        # Domain 1: Schematic / Circuit
        if not circuits:
            c_status = DomainStatus.MISSING
            c_reason = "No circuit schematic entities created."
        elif active_circuit.validation_status in ("INVALID", "FAIL", "FAILED"):
            c_status = DomainStatus.FAILING_RULES
            c_reason = f"Active circuit (v{active_circuit.version}) validation failed ({active_circuit.validation_status})."
        elif active_circuit.validation_status in ("DRAFT", "NEEDS_INPUT"):
            c_status = DomainStatus.INCOMPLETE
            c_reason = f"Active circuit (v{active_circuit.version}) is in {active_circuit.validation_status} status."
        elif active_circuit.validation_status in ("VALID", "VALIDATED"):
            c_status = DomainStatus.CONFIGURED
            c_reason = f"Active circuit (v{active_circuit.version}) is validated."
        else:
            c_status = DomainStatus.UNKNOWN
            c_reason = f"Circuit validation status is {active_circuit.validation_status}."

        domains.append(
            DomainInventoryItem(
                domain_name="schematic",
                display_name="Circuit Schematic",
                entity_count=len(circuits),
                latest_entity_id=active_circuit.id if active_circuit else None,
                latest_revision=active_circuit.version if active_circuit else None,
                status=c_status,
                status_reason=c_reason,
                last_updated_at=active_circuit.updated_at if active_circuit else None,
            )
        )

        # Domain 2: PCB Layout
        if not boards:
            b_status = DomainStatus.MISSING
            b_reason = "No physical PCB layout entities created."
        elif active_circuit_version is not None and latest_board.circuit_version < active_circuit_version:
            b_status = DomainStatus.STALE
            b_reason = f"Board v{latest_board.version} bound to older circuit v{latest_board.circuit_version} (active: v{active_circuit_version})."
        elif latest_board.status == "DRAFT":
            b_status = DomainStatus.INCOMPLETE
            b_reason = f"Board v{latest_board.version} is in DRAFT status."
        elif latest_board.status in ("IN_PROGRESS", "REVIEW", "FROZEN"):
            b_status = DomainStatus.CONFIGURED
            b_reason = f"Board v{latest_board.version} is configured ({latest_board.status})."
        else:
            b_status = DomainStatus.UNKNOWN
            b_reason = f"Board status is {latest_board.status}."

        domains.append(
            DomainInventoryItem(
                domain_name="pcb",
                display_name="PCB Layout",
                entity_count=len(boards),
                latest_entity_id=latest_board.id if latest_board else None,
                latest_revision=latest_board.version if latest_board else None,
                status=b_status,
                status_reason=b_reason,
                last_updated_at=latest_board.updated_at if latest_board else None,
            )
        )

        # Domain 3: BOM / Procurement
        if not boms:
            bom_status = DomainStatus.MISSING
            bom_reason = "No Bill of Materials entities created."
        elif active_circuit_version is not None and latest_bom.circuit_version < active_circuit_version:
            bom_status = DomainStatus.STALE
            bom_reason = f"BOM v{latest_bom.version} bound to older circuit v{latest_bom.circuit_version} (active: v{active_circuit_version})."
        elif latest_bom.status == "DRAFT":
            bom_status = DomainStatus.INCOMPLETE
            bom_reason = f"BOM v{latest_bom.version} is in DRAFT status."
        elif latest_bom.status in ("EVALUATED", "REVIEW", "FROZEN"):
            bom_status = DomainStatus.CONFIGURED
            bom_reason = f"BOM v{latest_bom.version} is evaluated and configured."
        else:
            bom_status = DomainStatus.UNKNOWN
            bom_reason = f"BOM status is {latest_bom.status}."

        domains.append(
            DomainInventoryItem(
                domain_name="bom",
                display_name="Bill of Materials",
                entity_count=len(boms),
                latest_entity_id=latest_bom.id if latest_bom else None,
                latest_revision=latest_bom.version if latest_bom else None,
                status=bom_status,
                status_reason=bom_reason,
                last_updated_at=latest_bom.updated_at if latest_bom else None,
            )
        )

        # Domain 4: Simulation
        if not simulations:
            sim_status = DomainStatus.MISSING
            sim_reason = "No SPICE simulation jobs recorded."
        elif active_circuit_version is not None and latest_sim.circuit_version < active_circuit_version:
            sim_status = DomainStatus.STALE
            sim_reason = f"Simulation bound to older circuit v{latest_sim.circuit_version} (active: v{active_circuit_version})."
        elif latest_sim.status in ("FAILED", "INVALID"):
            sim_status = DomainStatus.FAILING_RULES
            sim_reason = f"Simulation job failed ({latest_sim.status})."
        elif latest_sim.status in ("CREATED", "VALIDATING", "QUEUED", "RUNNING"):
            sim_status = DomainStatus.INCOMPLETE
            sim_reason = f"Simulation job in progress ({latest_sim.status})."
        elif latest_sim.status == "COMPLETED":
            sim_status = DomainStatus.CONFIGURED
            sim_reason = f"Simulation completed successfully ({latest_sim.simulation_type})."
        else:
            sim_status = DomainStatus.UNKNOWN
            sim_reason = f"Simulation status is {latest_sim.status}."

        domains.append(
            DomainInventoryItem(
                domain_name="simulation",
                display_name="SPICE Simulation",
                entity_count=len(simulations),
                latest_entity_id=latest_sim.id if latest_sim else None,
                latest_revision=latest_sim.circuit_version if latest_sim else None,
                status=sim_status,
                status_reason=sim_reason,
                last_updated_at=latest_sim.updated_at if latest_sim else None,
            )
        )

        # Domain 5: Manufacturing / DFM
        if not mfg_analyses:
            mfg_status = DomainStatus.MISSING
            mfg_reason = "No manufacturing or DFM analysis records found."
        elif active_circuit_version is not None and latest_mfg.circuit_revision < active_circuit_version:
            mfg_status = DomainStatus.STALE
            mfg_reason = f"DFM analysis targets older circuit v{latest_mfg.circuit_revision} (active: v{active_circuit_version})."
        elif latest_mfg.status == "FAILED":
            mfg_status = DomainStatus.FAILING_RULES
            mfg_reason = "Manufacturing analysis execution failed."
        elif latest_mfg.status == "PENDING":
            mfg_status = DomainStatus.INCOMPLETE
            mfg_reason = "Manufacturing analysis is pending."
        else:
            has_fail_findings = any(
                isinstance(f, dict) and f.get("status") == "FAIL"
                for f in (latest_mfg.findings or [])
            )
            if has_fail_findings:
                mfg_status = DomainStatus.FAILING_RULES
                mfg_reason = "DFM analysis contains failing rule violations."
            else:
                mfg_status = DomainStatus.CONFIGURED
                mfg_reason = "DFM analysis completed with zero critical fabrication failures."

        domains.append(
            DomainInventoryItem(
                domain_name="manufacturing",
                display_name="DFM & Fabrication",
                entity_count=len(mfg_analyses),
                latest_entity_id=latest_mfg.id if latest_mfg else None,
                latest_revision=latest_mfg.circuit_revision if latest_mfg else None,
                status=mfg_status,
                status_reason=mfg_reason,
                last_updated_at=latest_mfg.updated_at if latest_mfg else None,
            )
        )

        # Domain 6: Engineering Requirements
        if not requirements:
            req_status = DomainStatus.MISSING
            req_reason = "No engineering requirements defined."
        else:
            has_violated = any(r.status == "VIOLATED" for r in requirements)
            if has_violated:
                req_status = DomainStatus.FAILING_RULES
                req_reason = "One or more engineering requirements are violated."
            else:
                req_status = DomainStatus.CONFIGURED
                req_reason = f"{len(requirements)} requirement(s) defined and tracked."

        domains.append(
            DomainInventoryItem(
                domain_name="requirements",
                display_name="System Requirements",
                entity_count=len(requirements),
                latest_entity_id=latest_req.id if latest_req else None,
                latest_revision=None,
                status=req_status,
                status_reason=req_reason,
                last_updated_at=latest_req.updated_at if latest_req else None,
            )
        )

        # Domain 7: Design Reviews
        if not reviews:
            rev_status = DomainStatus.MISSING
            rev_reason = "No formal design reviews conducted."
        elif active_circuit_version is not None and latest_rev.circuit_revision < active_circuit_version:
            rev_status = DomainStatus.STALE
            rev_reason = f"Review targets older circuit v{latest_rev.circuit_revision} (active: v{active_circuit_version})."
        elif latest_rev.status == "BLOCKED":
            rev_status = DomainStatus.FAILING_RULES
            rev_reason = "Design review is blocked."
        elif latest_rev.status in ("DRAFT", "REVIEW_IN_PROGRESS", "VERIFICATION_REQUIRED", "PARTIALLY_VERIFIED"):
            rev_status = DomainStatus.INCOMPLETE
            rev_reason = f"Design review is in progress ({latest_rev.status})."
        elif latest_rev.status in ("ANALYSIS_COMPLETE", "VERIFIED"):
            rev_status = DomainStatus.CONFIGURED
            rev_reason = f"Design review completed ({latest_rev.status})."
        else:
            rev_status = DomainStatus.UNKNOWN
            rev_reason = f"Design review status is {latest_rev.status}."

        domains.append(
            DomainInventoryItem(
                domain_name="design_review",
                display_name="Design Reviews",
                entity_count=len(reviews),
                latest_entity_id=latest_rev.id if latest_rev else None,
                latest_revision=latest_rev.circuit_revision if latest_rev else None,
                status=rev_status,
                status_reason=rev_reason,
                last_updated_at=latest_rev.updated_at if latest_rev else None,
            )
        )

        # Domain 8: Cross-Domain Validation
        cd_summary: Optional[CrossDomainSummary] = None
        if not latest_cdv:
            cd_status = DomainStatus.MISSING
            cd_reason = "No cross-domain validation runs recorded."
        else:
            # Dynamically compute staleness
            cd_service = CrossDomainService(self.db)
            await cd_service._check_record_staleness(latest_cdv)

            rule_counts = {"total": 0, "pass": 0, "fail": 0, "warning": 0, "unknown": 0}
            for f in latest_cdv.findings or []:
                if isinstance(f, dict):
                    rule_counts["total"] += 1
                    f_status = str(f.get("status", "unknown")).lower()
                    if f_status in rule_counts:
                        rule_counts[f_status] += 1
                    else:
                        rule_counts["unknown"] += 1

            cdv_status = getattr(latest_cdv, "validation_status", getattr(latest_cdv, "status", "UNKNOWN"))
            cd_summary = CrossDomainSummary(
                record_id=latest_cdv.id,
                evaluated_at=latest_cdv.created_at,
                status=cdv_status,
                is_stale=latest_cdv.is_stale,
                staleness_reasons=latest_cdv.staleness_reasons or [],
                rule_counts=rule_counts,
                snapshot_digest=latest_cdv.snapshot_digest,
            )

            if latest_cdv.is_stale:
                cd_status = DomainStatus.STALE
                cd_reason = f"Validation is stale: {latest_cdv.staleness_reasons[0] if latest_cdv.staleness_reasons else 'State changed'}"
            elif cdv_status == "FAIL" or rule_counts["fail"] > 0:
                cd_status = DomainStatus.FAILING_RULES
                cd_reason = f"Validation has {rule_counts['fail']} failing rule violation(s)."
            elif cdv_status == "PASS" or cdv_status == "COMPLETED":
                cd_status = DomainStatus.CONFIGURED
                cd_reason = "All cross-domain consistency checks passed."
            else:
                cd_status = DomainStatus.UNKNOWN
                cd_reason = f"Validation status is {cdv_status}."

        domains.append(
            DomainInventoryItem(
                domain_name="cross_domain",
                display_name="Cross-Domain Verification",
                entity_count=len(cdv_records),
                latest_entity_id=latest_cdv.id if latest_cdv else None,
                latest_revision=None,
                status=cd_status,
                status_reason=cd_reason,
                last_updated_at=latest_cdv.created_at if latest_cdv else None,
            )
        )

        # Compute deterministic SHA-256 workspace digest
        digest_payload = {
            "project_id": project_id,
            "project_status": project.status,
            "active_circuit_version": active_circuit_version,
            "domains": [
                {
                    "domain_name": d.domain_name,
                    "entity_count": d.entity_count,
                    "latest_entity_id": d.latest_entity_id,
                    "latest_revision": d.latest_revision,
                    "status": d.status.value,
                }
                for d in domains
            ],
            "cross_domain_digest": cd_summary.snapshot_digest if cd_summary else None,
        }
        digest_bytes = json.dumps(digest_payload, sort_keys=True, default=str).encode("utf-8")
        workspace_digest = hashlib.sha256(digest_bytes).hexdigest()

        return ProjectWorkspaceStateResponse(
            project_id=project_id,
            project_name=project.name,
            project_status=project.status,
            active_circuit_version=active_circuit_version,
            domains=domains,
            cross_domain_validation=cd_summary,
            workspace_digest=workspace_digest,
            generated_at=datetime.now(timezone.utc),
        )

    async def get_revision_lineage(self, project: Project) -> ProjectRevisionLineageResponse:
        """
        Groups child engineering entities by circuit revision using persisted
        foreign keys and version bindings. Identifies unbound or uncharacterized entities.
        """
        project_id = project.id

        # 1. Circuits
        c_stmt = (
            select(Circuit)
            .where(Circuit.project_id == project_id)
            .order_by(desc(Circuit.version), desc(Circuit.created_at))
        )
        c_res = await self.db.execute(c_stmt)
        circuits = list(c_res.scalars().all())
        active_version = circuits[0].version if circuits else None

        circuit_by_version: Dict[int, Circuit] = {c.version: c for c in circuits}
        known_circuit_versions = set(circuit_by_version.keys())

        # 2. Boards
        b_stmt = (
            select(EngineeringBoard)
            .where(EngineeringBoard.project_id == project_id)
            .order_by(desc(EngineeringBoard.created_at))
        )
        b_res = await self.db.execute(b_stmt)
        boards = list(b_res.scalars().all())

        # 3. BOMs
        bom_stmt = (
            select(EngineeringBOM)
            .where(EngineeringBOM.project_id == project_id)
            .order_by(desc(EngineeringBOM.created_at))
        )
        bom_res = await self.db.execute(bom_stmt)
        boms = list(bom_res.scalars().all())

        # 4. Simulations
        sim_stmt = (
            select(SimulationJob)
            .where(SimulationJob.project_id == project_id)
            .order_by(desc(SimulationJob.created_at))
        )
        sim_res = await self.db.execute(sim_stmt)
        simulations = list(sim_res.scalars().all())

        # 5. Manufacturing
        circuit_ids = [c.id for c in circuits]
        board_ids = [b.id for b in boards]
        mfg_analyses: List[ManufacturingAnalysisRecord] = []
        if circuit_ids or board_ids:
            from sqlalchemy import or_
            conds = []
            if circuit_ids:
                conds.append(ManufacturingAnalysisRecord.circuit_id.in_(circuit_ids))
            if board_ids:
                conds.append(ManufacturingAnalysisRecord.board_id.in_(board_ids))
            mfg_stmt = select(ManufacturingAnalysisRecord).where(or_(*conds)).order_by(desc(ManufacturingAnalysisRecord.created_at))
            mfg_res = await self.db.execute(mfg_stmt)
            mfg_analyses = list(mfg_res.scalars().all())

        # 6. Reviews
        rev_stmt = (
            select(EngineeringDesignReview)
            .where(EngineeringDesignReview.project_id == project_id)
            .order_by(desc(EngineeringDesignReview.created_at))
        )
        rev_res = await self.db.execute(rev_stmt)
        reviews = list(rev_res.scalars().all())

        # Initialize bucket maps per circuit version
        boards_by_v: Dict[int, List[BoundEntityRef]] = {v: [] for v in known_circuit_versions}
        boms_by_v: Dict[int, List[BoundEntityRef]] = {v: [] for v in known_circuit_versions}
        sims_by_v: Dict[int, List[BoundEntityRef]] = {v: [] for v in known_circuit_versions}
        mfg_by_v: Dict[int, List[BoundEntityRef]] = {v: [] for v in known_circuit_versions}
        revs_by_v: Dict[int, List[BoundEntityRef]] = {v: [] for v in known_circuit_versions}
        unbound: List[BoundEntityRef] = []

        # Distribute Boards
        for b in boards:
            ref = BoundEntityRef(
                entity_id=b.id,
                entity_type="board",
                name_or_type=b.name,
                entity_version=b.version,
                bound_circuit_version=b.circuit_version,
                status=b.status,
                created_at=b.created_at,
            )
            if b.circuit_version in boards_by_v:
                boards_by_v[b.circuit_version].append(ref)
            else:
                unbound.append(ref)

        # Distribute BOMs
        for bom in boms:
            ref = BoundEntityRef(
                entity_id=bom.id,
                entity_type="bom",
                name_or_type=bom.name,
                entity_version=bom.version,
                bound_circuit_version=bom.circuit_version,
                status=bom.status,
                created_at=bom.created_at,
            )
            if bom.circuit_version in boms_by_v:
                boms_by_v[bom.circuit_version].append(ref)
            else:
                unbound.append(ref)

        # Distribute Simulations
        for s in simulations:
            ref = BoundEntityRef(
                entity_id=s.id,
                entity_type="simulation",
                name_or_type=s.simulation_type,
                entity_version=None,
                bound_circuit_version=s.circuit_version,
                status=s.status,
                created_at=s.created_at,
            )
            if s.circuit_version in sims_by_v:
                sims_by_v[s.circuit_version].append(ref)
            else:
                unbound.append(ref)

        # Distribute Manufacturing Analyses
        for m in mfg_analyses:
            ref = BoundEntityRef(
                entity_id=m.id,
                entity_type="manufacturing_analysis",
                name_or_type=m.rule_set_revision or "DFM",
                entity_version=m.board_revision,
                bound_circuit_version=m.circuit_revision,
                status=m.status,
                created_at=m.created_at,
            )
            if m.circuit_revision in mfg_by_v:
                mfg_by_v[m.circuit_revision].append(ref)
            else:
                unbound.append(ref)

        # Distribute Reviews
        for r in reviews:
            ref = BoundEntityRef(
                entity_id=r.id,
                entity_type="design_review",
                name_or_type="Engineering Review",
                entity_version=None,
                bound_circuit_version=r.circuit_revision,
                status=r.status,
                created_at=r.created_at,
            )
            if r.circuit_revision in revs_by_v:
                revs_by_v[r.circuit_revision].append(ref)
            else:
                unbound.append(ref)

        # Build lineage items sorted by circuit_version descending
        lineage_items: List[CircuitRevisionLineageItem] = []
        for v in sorted(known_circuit_versions, reverse=True):
            circ = circuit_by_version[v]
            lineage_items.append(
                CircuitRevisionLineageItem(
                    circuit_id=circ.id,
                    circuit_version=circ.version,
                    is_current=(circ.version == active_version),
                    validation_status=circ.validation_status,
                    created_at=circ.created_at,
                    boards=boards_by_v[v],
                    boms=boms_by_v[v],
                    simulations=sims_by_v[v],
                    manufacturing_analyses=mfg_by_v[v],
                    design_reviews=revs_by_v[v],
                )
            )

        return ProjectRevisionLineageResponse(
            project_id=project_id,
            active_circuit_version=active_version,
            circuit_revisions=lineage_items,
            unbound_entities=unbound,
            generated_at=datetime.now(timezone.utc),
        )

    async def get_activity_timeline(
        self,
        project: Project,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> ProjectActivityTimelineResponse:
        """
        Reconstructs a chronological project activity stream across all persisted
        engineering domain records with deterministic ordering (timestamp desc, entity_id desc).
        """
        project_id = project.id
        events: List[ProjectActivityItem] = []

        # 1. Circuits
        c_stmt = select(Circuit).where(Circuit.project_id == project_id)
        c_res = await self.db.execute(c_stmt)
        for c in c_res.scalars().all():
            events.append(
                ProjectActivityItem(
                    event_id=f"circ-{c.id}-created",
                    category=TimelineCategory.CIRCUIT,
                    event_type="CIRCUIT_CREATED",
                    entity_id=c.id,
                    entity_name=c.name,
                    revision_or_version=c.version,
                    timestamp=c.created_at,
                    summary=f"Circuit schematic '{c.name}' (v{c.version}) was created with status {c.validation_status}.",
                    details={"status": c.validation_status, "created_source": c.created_source},
                )
            )
            if c.updated_at and c.updated_at != c.created_at:
                events.append(
                    ProjectActivityItem(
                        event_id=f"circ-{c.id}-updated",
                        category=TimelineCategory.CIRCUIT,
                        event_type="CIRCUIT_UPDATED",
                        entity_id=c.id,
                        entity_name=c.name,
                        revision_or_version=c.version,
                        timestamp=c.updated_at,
                        summary=f"Circuit schematic '{c.name}' (v{c.version}) was updated.",
                        details={"status": c.validation_status},
                    )
                )

        # 2. Boards
        b_stmt = select(EngineeringBoard).where(EngineeringBoard.project_id == project_id)
        b_res = await self.db.execute(b_stmt)
        for b in b_res.scalars().all():
            events.append(
                ProjectActivityItem(
                    event_id=f"board-{b.id}-created",
                    category=TimelineCategory.BOARD,
                    event_type="BOARD_CREATED",
                    entity_id=b.id,
                    entity_name=b.name,
                    revision_or_version=b.version,
                    timestamp=b.created_at,
                    summary=f"PCB board layout '{b.name}' (v{b.version}) bound to circuit v{b.circuit_version} created (status: {b.status}).",
                    details={"circuit_version": b.circuit_version, "status": b.status},
                )
            )

        # 3. BOMs
        bom_stmt = select(EngineeringBOM).where(EngineeringBOM.project_id == project_id)
        bom_res = await self.db.execute(bom_stmt)
        for bom in bom_res.scalars().all():
            events.append(
                ProjectActivityItem(
                    event_id=f"bom-{bom.id}-created",
                    category=TimelineCategory.BOM,
                    event_type="BOM_CREATED",
                    entity_id=bom.id,
                    entity_name=bom.name,
                    revision_or_version=bom.version,
                    timestamp=bom.created_at,
                    summary=f"Bill of Materials '{bom.name}' (v{bom.version}) bound to circuit v{bom.circuit_version} created (status: {bom.status}).",
                    details={"circuit_version": bom.circuit_version, "status": bom.status},
                )
            )

        # 4. Simulations
        sim_stmt = select(SimulationJob).where(SimulationJob.project_id == project_id)
        sim_res = await self.db.execute(sim_stmt)
        for s in sim_res.scalars().all():
            events.append(
                ProjectActivityItem(
                    event_id=f"sim-{s.id}-created",
                    category=TimelineCategory.SIMULATION,
                    event_type="SIMULATION_JOB_RUN",
                    entity_id=s.id,
                    entity_name=s.simulation_type,
                    revision_or_version=s.circuit_version,
                    timestamp=s.created_at,
                    summary=f"SPICE simulation job '{s.simulation_type}' on circuit v{s.circuit_version} executed ({s.status}).",
                    details={"simulator": s.simulator, "status": s.status},
                )
            )

        # 5. Manufacturing
        # Query via circuits
        c_ids = list((await self.db.execute(select(Circuit.id).where(Circuit.project_id == project_id))).scalars().all())
        if c_ids:
            mfg_stmt = select(ManufacturingAnalysisRecord).where(ManufacturingAnalysisRecord.circuit_id.in_(c_ids))
            mfg_res = await self.db.execute(mfg_stmt)
            for m in mfg_res.scalars().all():
                events.append(
                    ProjectActivityItem(
                        event_id=f"mfg-{m.id}-created",
                        category=TimelineCategory.MANUFACTURING,
                        event_type="DFM_ANALYSIS_EXECUTED",
                        entity_id=m.id,
                        entity_name=f"DFM Run ({m.rule_set_revision})",
                        revision_or_version=m.circuit_revision,
                        timestamp=m.created_at,
                        summary=f"DFM & manufacturing analysis executed on circuit v{m.circuit_revision} / board rev {m.board_revision} ({m.status}).",
                        details={"status": m.status, "board_revision": m.board_revision},
                    )
                )

        # 6. Requirements
        req_stmt = select(EngineeringRequirement).where(EngineeringRequirement.project_id == project_id)
        req_res = await self.db.execute(req_stmt)
        for r in req_res.scalars().all():
            events.append(
                ProjectActivityItem(
                    event_id=f"req-{r.id}-created",
                    category=TimelineCategory.REQUIREMENT,
                    event_type="REQUIREMENT_DEFINED",
                    entity_id=r.id,
                    entity_name=r.requirement_key,
                    revision_or_version=None,
                    timestamp=r.created_at,
                    summary=f"Engineering requirement '{r.requirement_key}' ({r.category}) created (status: {r.status}).",
                    details={"category": r.category, "priority": r.priority, "status": r.status},
                )
            )

        # 7. Reviews
        rev_stmt = select(EngineeringDesignReview).where(EngineeringDesignReview.project_id == project_id)
        rev_res = await self.db.execute(rev_stmt)
        for rev in rev_res.scalars().all():
            events.append(
                ProjectActivityItem(
                    event_id=f"rev-{rev.id}-created",
                    category=TimelineCategory.REVIEW,
                    event_type="DESIGN_REVIEW_INITIATED",
                    entity_id=rev.id,
                    entity_name="Design Review",
                    revision_or_version=rev.circuit_revision,
                    timestamp=rev.created_at,
                    summary=f"Engineering design review initiated for circuit v{rev.circuit_revision} ({rev.status}).",
                    details={"status": rev.status, "circuit_revision": rev.circuit_revision},
                )
            )

        # 8. Cross-Domain Validation Records
        cdv_stmt = select(CrossDomainValidationRecord).where(CrossDomainValidationRecord.project_id == project_id)
        cdv_res = await self.db.execute(cdv_stmt)
        for cdv in cdv_res.scalars().all():
            cdv_status = getattr(cdv, "validation_status", getattr(cdv, "status", "COMPLETED"))
            events.append(
                ProjectActivityItem(
                    event_id=f"cdv-{cdv.id}-created",
                    category=TimelineCategory.CROSS_DOMAIN_VALIDATION,
                    event_type="CROSS_DOMAIN_VALIDATION_RUN",
                    entity_id=cdv.id,
                    entity_name="Consistency Validation",
                    revision_or_version=getattr(cdv, "circuit_version", None),
                    timestamp=cdv.created_at,
                    summary=f"Cross-domain consistency validation run executed ({cdv_status}).",
                    details={"status": cdv_status, "is_stale": cdv.is_stale},
                )
            )

        # Deterministic secondary sort on (timestamp desc, entity_id desc)
        events.sort(key=lambda e: (e.timestamp, e.entity_id), reverse=True)

        total_events = len(events)
        paginated_events = events[:limit]
        has_more = total_events > limit

        return ProjectActivityTimelineResponse(
            project_id=project_id,
            events=paginated_events,
            total_events=total_events,
            limit=limit,
            has_more=has_more,
        )
