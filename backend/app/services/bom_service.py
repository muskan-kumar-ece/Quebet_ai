"""
BOM Service.

Orchestration layer for BOM & Supply-Chain Intelligence.
Enforces multi-tenant security, human-gated approval boundaries, deterministic
engineering compatibility evaluations, and SHA-256 integrity snapshots.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import AuthenticatedUser
from app.models.db.bom import (
    EngineeringBOM,
    EngineeringBOMLine,
    ComponentPartCandidate,
    BOMSubstitutionProposal,
    BOMStatus,
    BOMLineStatus,
    PartLifecycleStatus,
    PartAvailabilityStatus,
    PartCompatibilityStatus,
)
from app.models.db.circuit import Circuit
from app.repositories.circuit_repo import circuit_repo
from app.models.schemas.bom import (
    EngineeringBOMCreate,
    ComponentPartCandidateCreate,
    BOMSubstitutionProposalCreate,
)
from app.services.ai.bom.bom_generator import BOMGenerator
from app.services.ai.bom.compatibility_engine import BOMCompatibilityEngine
from app.services.ai.bom.snapshot import BOMSnapshotService
from app.services.ai.bom.substitute_validator import BOMSubstituteValidator
from app.services.ai.bom.supply_intelligence_engine import BOMSupplyIntelligenceEngine


class BOMService:
    """Orchestrates BOM lifecycle, part candidate intelligence, compatibility, and human approvals."""

    async def create_bom(
        self,
        db: AsyncSession,
        current_user: AuthenticatedUser,
        request: EngineeringBOMCreate,
    ) -> EngineeringBOM:
        """Generates and persists an EngineeringBOM for the given circuit."""
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

        bom = BOMGenerator.generate_from_circuit(circuit=circuit, revision=1)
        bom.tenant_id = current_user.tenant_id
        if request.name:
            bom.name = request.name
        bom.created_by = current_user.id

        digest = BOMSnapshotService.compute_bom_digest(bom)
        bom.integrity_digest = digest

        db.add(bom)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=circuit.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.BOM_CREATED,
            entity_type="BOM",
            entity_id=bom.id,
            entity_revision=bom.version,
            payload={
                "bom_id": bom.id,
                "circuit_id": bom.circuit_id,
                "name": bom.name,
                "version": bom.version,
                "lines_count": len(bom.lines) if bom.lines else 0,
                "integrity_digest": bom.integrity_digest,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        await db.refresh(bom)
        return await self.get_bom(db, bom.id, current_user)

    async def get_bom(
        self,
        db: AsyncSession,
        bom_id: str,
        current_user: AuthenticatedUser,
    ) -> EngineeringBOM:
        """Fetches an EngineeringBOM with lines, candidates, and proposals eagerly loaded."""
        stmt = (
            select(EngineeringBOM)
            .options(
                selectinload(EngineeringBOM.lines).selectinload(EngineeringBOMLine.candidates),
                selectinload(EngineeringBOM.substitutions),
            )
            .where(EngineeringBOM.id == bom_id)
        )
        if current_user.tenant_id:
            stmt = stmt.where(EngineeringBOM.tenant_id == current_user.tenant_id)
        else:
            stmt = stmt.where(EngineeringBOM.tenant_id.is_(None), EngineeringBOM.created_by == current_user.id)

        res = await db.execute(stmt)
        bom = res.scalar_one_or_none()
        if not bom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BOM {bom_id} not found or tenant access denied",
            )
        return bom

    async def get_bom_by_circuit(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> EngineeringBOM:
        """Fetches the latest revision EngineeringBOM for a given circuit."""
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
            select(EngineeringBOM)
            .options(
                selectinload(EngineeringBOM.lines).selectinload(EngineeringBOMLine.candidates),
                selectinload(EngineeringBOM.substitutions),
            )
            .where(EngineeringBOM.circuit_id == circuit_id)
            .order_by(EngineeringBOM.version.desc())
        )
        if current_user.tenant_id:
            stmt = stmt.where(EngineeringBOM.tenant_id == current_user.tenant_id)
        else:
            stmt = stmt.where(EngineeringBOM.tenant_id.is_(None), EngineeringBOM.created_by == current_user.id)

        res = await db.execute(stmt)
        bom = res.scalars().first()
        if not bom:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No BOM found for circuit {circuit_id}",
            )
        return bom

    async def list_lines(
        self,
        db: AsyncSession,
        bom_id: str,
        current_user: AuthenticatedUser,
    ) -> List[EngineeringBOMLine]:
        """Lists all lines for a BOM."""
        bom = await self.get_bom(db, bom_id, current_user)
        return sorted(bom.lines, key=lambda l: l.reference_designator or "")

    async def add_candidate(
        self,
        db: AsyncSession,
        line_id: str,
        candidate_in: ComponentPartCandidateCreate,
        current_user: AuthenticatedUser,
    ) -> ComponentPartCandidate:
        """Adds a ComponentPartCandidate to a BOMLine and evaluates compatibility & supply."""
        stmt = (
            select(EngineeringBOMLine)
            .options(
                selectinload(EngineeringBOMLine.bom),
                selectinload(EngineeringBOMLine.candidates),
            )
            .where(EngineeringBOMLine.id == line_id)
        )
        res = await db.execute(stmt)
        line = res.scalar_one_or_none()
        if not line or (current_user.tenant_id and line.bom.tenant_id != current_user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BOMLine {line_id} not found or tenant access denied",
            )

        candidate_dict = candidate_in.model_dump()
        reqs = line.engineering_requirements or {}
        cand_params = candidate_dict.get("parameters") or {}
        cand_pkg = candidate_dict.get("package") or line.design_package

        compat_status, evals = BOMCompatibilityEngine.evaluate(
            requirements=reqs,
            candidate_parameters=cand_params,
            candidate_package=cand_pkg,
            candidate_mpn=candidate_in.mpn,
        )

        supply_eval = BOMSupplyIntelligenceEngine.evaluate_supply_sources(
            candidate_dict.get("supply_sources") or []
        )

        candidate = ComponentPartCandidate(
            id=str(uuid.uuid4()),
            bom_line_id=line.id,
            manufacturer=candidate_in.manufacturer,
            mpn=candidate_in.mpn,
            package=cand_pkg,
            description=candidate_in.description,
            datasheet_url=candidate_in.datasheet_url,
            compatibility_status=compat_status,
            compatibility_evaluations=[e.model_dump() for e in evals],
            parameters=cand_params,
            lifecycle_status=candidate_in.lifecycle_status,
            availability_status=supply_eval["availability_status"],
            lead_time_weeks=candidate_in.lead_time_weeks,
            supply_sources=candidate_dict.get("supply_sources") or [],
            is_primary=False,
            provenance={"source": "USER_CANDIDATE_ENTRY"},
        )

        if not line.manufacturer_part_number or line.status == BOMLineStatus.UNMATCHED.value:
            if compat_status == PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value:
                line.manufacturer = candidate.manufacturer
                line.manufacturer_part_number = candidate.mpn
                line.status = BOMLineStatus.SOURCED.value
                candidate.is_primary = True

        db.add(candidate)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=line.bom.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.PART_CANDIDATE_SELECTED,
            entity_type="PART_CANDIDATE",
            entity_id=candidate.id,
            entity_revision=line.bom.version,
            payload={
                "candidate_id": candidate.id,
                "bom_id": line.bom.id,
                "bom_line_id": line.id,
                "mpn": candidate.mpn,
                "manufacturer": candidate.manufacturer,
                "compatibility_status": candidate.compatibility_status,
                "is_primary": candidate.is_primary,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        await db.refresh(candidate)
        return candidate

    async def evaluate_bom(
        self,
        db: AsyncSession,
        bom_id: str,
        current_user: AuthenticatedUser,
    ) -> EngineeringBOM:
        """
        Re-evaluates compatibility and supply sources for all lines and candidates.
        Updates line statuses and checks for conflicts.
        """
        bom = await self.get_bom(db, bom_id, current_user)

        for line in bom.lines:
            line_has_compatible = False
            line_has_conflict = False

            for cand in line.candidates:
                reqs = line.engineering_requirements or {}
                cand_params = cand.parameters or {}
                cand_pkg = cand.package or line.design_package

                compat_status, evals = BOMCompatibilityEngine.evaluate(
                    requirements=reqs,
                    candidate_parameters=cand_params,
                    candidate_package=cand_pkg,
                    candidate_mpn=cand.mpn,
                )
                cand.compatibility_status = compat_status
                cand.compatibility_evaluations = [e.model_dump() for e in evals]

                supply_eval = BOMSupplyIntelligenceEngine.evaluate_supply_sources(
                    cand.supply_sources or []
                )
                cand.availability_status = supply_eval["availability_status"]

                if compat_status == PartCompatibilityStatus.ENGINEERING_COMPATIBLE.value:
                    line_has_compatible = True
                elif compat_status == PartCompatibilityStatus.NOT_COMPATIBLE.value:
                    if cand.is_primary:
                        line_has_conflict = True

            if line_has_conflict:
                line.status = BOMLineStatus.INCOMPATIBLE.value
            elif line.manufacturer_part_number or line_has_compatible:
                line.status = BOMLineStatus.SOURCED.value
            else:
                line.status = BOMLineStatus.UNMATCHED.value

        bom.status = BOMStatus.EVALUATED.value
        bom.integrity_digest = BOMSnapshotService.compute_bom_digest(bom)
        await db.commit()
        return await self.get_bom(db, bom.id, current_user)

    async def create_substitution_proposal(
        self,
        db: AsyncSession,
        proposal_in: BOMSubstitutionProposalCreate,
        current_user: AuthenticatedUser,
    ) -> BOMSubstitutionProposal:
        """Proposes a part candidate substitution for a BOM line."""
        stmt = (
            select(EngineeringBOMLine)
            .options(
                selectinload(EngineeringBOMLine.bom),
                selectinload(EngineeringBOMLine.candidates),
            )
            .where(EngineeringBOMLine.id == proposal_in.bom_line_id)
        )
        res = await db.execute(stmt)
        line = res.scalar_one_or_none()
        if not line or (current_user.tenant_id and line.bom.tenant_id != current_user.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Line {proposal_in.bom_line_id} not found or tenant access denied",
            )

        candidate = next((c for c in line.candidates if str(c.id) == proposal_in.candidate_id), None)
        if not candidate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidate {proposal_in.candidate_id} not found on line {line.id}",
            )

        proposal = BOMSubstituteValidator.create_proposal(
            bom=line.bom,
            line=line,
            candidate=candidate,
            proposed_by=current_user.id,
            justification=proposal_in.rationale,
        )

        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal

    async def approve_substitution_proposal(
        self,
        db: AsyncSession,
        proposal_id: str,
        current_user: AuthenticatedUser,
    ) -> BOMSubstitutionProposal:
        """
        Enforces human approval boundary and applies candidate substitution.
        Rejects AI actors with HTTP 403 AI_UNAUTHORIZED_SUBSTITUTION.
        Rejects stale proposals if BOM revision has mutated.
        """
        stmt = (
            select(BOMSubstitutionProposal)
            .options(
                selectinload(BOMSubstitutionProposal.bom),
                selectinload(BOMSubstitutionProposal.bom_line).selectinload(EngineeringBOMLine.candidates),
            )
            .where(BOMSubstitutionProposal.id == proposal_id)
        )
        res = await db.execute(stmt)
        proposal = res.scalar_one_or_none()
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Proposal {proposal_id} not found",
            )

        if current_user.tenant_id and proposal.tenant_id != current_user.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to substitution proposal",
            )

        candidate = next(
            (c for c in proposal.bom_line.candidates if str(c.id) == proposal.candidate_id),
            None,
        )
        if not candidate:
            # Fallback query candidate
            cand_stmt = select(ComponentPartCandidate).where(ComponentPartCandidate.id == proposal.candidate_id)
            cand_res = await db.execute(cand_stmt)
            candidate = cand_res.scalar_one_or_none()
            if not candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Candidate {proposal.candidate_id} not found",
                )

        BOMSubstituteValidator.validate_and_apply_approval(
            proposal=proposal,
            line=proposal.bom_line,
            bom=proposal.bom,
            candidate=candidate,
            user=current_user,
        )

        proposal.bom.integrity_digest = BOMSnapshotService.compute_bom_digest(proposal.bom)

        from app.services.audit_ledger_service import AuditLedgerService
        from app.models.db.audit_ledger import AuditEventType

        audit_service = AuditLedgerService(db)
        await audit_service.record_event(
            project_id=proposal.bom.project_id,
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "ENGINEER"),
            event_type=AuditEventType.BOM_MUTATED,
            entity_type="BOM_SUBSTITUTION",
            entity_id=proposal.id,
            entity_revision=proposal.bom.version,
            payload={
                "proposal_id": proposal.id,
                "bom_id": proposal.bom.id,
                "bom_line_id": proposal.bom_line_id,
                "candidate_id": proposal.candidate_id,
                "status": proposal.status,
                "resulting_bom_version": proposal.bom.version,
                "integrity_digest": proposal.bom.integrity_digest,
            },
            tenant_id=current_user.tenant_id,
            commit=False,
        )

        await db.commit()
        await db.refresh(proposal)
        return proposal

    async def get_snapshot(
        self,
        db: AsyncSession,
        bom_id: str,
        current_user: AuthenticatedUser,
    ) -> Dict[str, Any]:
        """Generates canonical snapshot and SHA-256 integrity digest."""
        bom = await self.get_bom(db, bom_id, current_user)
        return BOMSnapshotService.create_snapshot_record(bom)


bom_service = BOMService()
