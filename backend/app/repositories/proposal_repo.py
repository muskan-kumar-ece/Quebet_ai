from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.proposal import EngineeringProposal, ProposalStatus
from app.models.schemas.proposal import ProposalCreate


class ProposalRepository:
    """Data access repository for Engineering Proposals."""

    async def get_by_id(
        self,
        db: AsyncSession,
        proposal_id: str,
        tenant_id: str | None = None,
        owner_id: str | None = None,
        allow_unscoped: bool = False,
    ) -> EngineeringProposal | None:
        stmt = select(EngineeringProposal).where(
            EngineeringProposal.id == proposal_id,
            EngineeringProposal.deleted_at.is_(None),
        )
        if tenant_id:
            stmt = stmt.where(EngineeringProposal.tenant_id == tenant_id)
        elif owner_id:
            stmt = stmt.where(EngineeringProposal.tenant_id.is_(None), EngineeringProposal.created_by == owner_id)
        elif allow_unscoped:
            pass
        else:
            return None

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_circuit(
        self,
        db: AsyncSession,
        circuit_id: str,
        tenant_id: str | None = None,
        owner_id: str | None = None,
        allow_unscoped: bool = False,
    ) -> list[EngineeringProposal]:
        stmt = (
            select(EngineeringProposal)
            .where(
                EngineeringProposal.circuit_id == circuit_id,
                EngineeringProposal.deleted_at.is_(None),
            )
            .order_by(EngineeringProposal.created_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(EngineeringProposal.tenant_id == tenant_id)
        elif owner_id:
            stmt = stmt.where(EngineeringProposal.tenant_id.is_(None), EngineeringProposal.created_by == owner_id)
        elif allow_unscoped:
            pass
        else:
            return []

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        circuit_id: str,
        proposal_in: ProposalCreate,
        user_id: str,
        tenant_id: str | None = None,
    ) -> EngineeringProposal:
        proposal = EngineeringProposal(
            circuit_id=circuit_id,
            tenant_id=tenant_id,
            created_by=user_id,
            source=proposal_in.source,
            title=proposal_in.title,
            description=proposal_in.description,
            status=ProposalStatus.PROPOSED.value,
            base_revision=proposal_in.base_revision,
            analysis_id=proposal_in.analysis_id,
            objective_id=proposal_in.objective_id,
            operations=[op.model_dump() for op in proposal_in.operations],
            assumptions=proposal_in.assumptions,
            findings_resolved=proposal_in.findings_resolved,
            findings_introduced=proposal_in.findings_introduced,
            constraints_evaluated=proposal_in.constraints_evaluated,
            engineering_effects=proposal_in.engineering_effects,
            unknowns=proposal_in.unknowns,
            confidence=proposal_in.confidence,
        )
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        return proposal

    async def update_status(
        self,
        db: AsyncSession,
        proposal: EngineeringProposal,
        status: ProposalStatus,
        validation_result: dict | None = None,
        applied_at: datetime | None = None,
        commit: bool = True,
    ) -> EngineeringProposal:
        proposal.status = status.value
        if validation_result is not None:
            proposal.validation_result = validation_result
        if applied_at is not None:
            proposal.applied_at = applied_at
        proposal.updated_at = datetime.now(timezone.utc)
        if commit:
            await db.commit()
            await db.refresh(proposal)
        else:
            await db.flush()
        return proposal


proposal_repo = ProposalRepository()
