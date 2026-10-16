import uuid
from typing import Any, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.provenance import EngineeringAnalysisProvenance


class ProvenanceRepo:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_analysis_provenance(
        self,
        analysis_id: str,
        circuit_id: str,
        circuit_revision: int,
        engine_versions: dict[str, str],
        rule_set_version: str,
        input_values: dict[str, Any],
        assumptions: list[dict[str, Any]],
        calculation_methods: list[str],
        knowledge_snapshot_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> EngineeringAnalysisProvenance:
        # Check if already exists for this analysis_id (immutable once written)
        stmt = select(EngineeringAnalysisProvenance).where(
            EngineeringAnalysisProvenance.analysis_id == analysis_id
        )
        res = await self.db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        provenance = EngineeringAnalysisProvenance(
            id=str(uuid.uuid4()),
            analysis_id=analysis_id,
            circuit_id=circuit_id,
            circuit_revision=circuit_revision,
            tenant_id=tenant_id,
            engine_versions=engine_versions,
            rule_set_version=rule_set_version,
            knowledge_snapshot_id=knowledge_snapshot_id,
            input_values=input_values,
            assumptions=assumptions,
            calculation_methods=calculation_methods,
        )
        self.db.add(provenance)
        await self.db.commit()
        await self.db.refresh(provenance)
        return provenance

    async def get_analysis_provenance(
        self,
        analysis_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringAnalysisProvenance]:
        stmt = select(EngineeringAnalysisProvenance).where(
            EngineeringAnalysisProvenance.analysis_id == analysis_id
        )
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringAnalysisProvenance.tenant_id == tenant_id,
                    EngineeringAnalysisProvenance.tenant_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def list_by_circuit(
        self,
        circuit_id: str,
        tenant_id: Optional[str] = None,
    ) -> list[EngineeringAnalysisProvenance]:
        stmt = (
            select(EngineeringAnalysisProvenance)
            .where(EngineeringAnalysisProvenance.circuit_id == circuit_id)
            .order_by(EngineeringAnalysisProvenance.circuit_revision.desc())
        )
        if tenant_id:
            stmt = stmt.where(
                or_(
                    EngineeringAnalysisProvenance.tenant_id == tenant_id,
                    EngineeringAnalysisProvenance.tenant_id.is_(None),
                )
            )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())
