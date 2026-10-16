from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.analysis import CircuitAnalysis


class AnalysisRepository:
    """Data access repository for Circuit Analyses with strict tenant isolation."""

    async def get_by_id(
        self,
        db: AsyncSession,
        analysis_id: str,
        tenant_id: str | None = None,
        owner_id: str | None = None,
        allow_unscoped: bool = False,
    ) -> CircuitAnalysis | None:
        stmt = select(CircuitAnalysis).where(
            CircuitAnalysis.id == analysis_id,
            CircuitAnalysis.deleted_at.is_(None),
        )
        if tenant_id:
            stmt = stmt.where(CircuitAnalysis.tenant_id == tenant_id)
        elif owner_id:
            stmt = stmt.where(CircuitAnalysis.tenant_id.is_(None), CircuitAnalysis.created_by == owner_id)
        elif allow_unscoped:
            pass
        else:
            return None

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_circuit(
        self,
        db: AsyncSession,
        circuit_id: str,
        tenant_id: str | None = None,
        owner_id: str | None = None,
        allow_unscoped: bool = False,
    ) -> CircuitAnalysis | None:
        stmt = (
            select(CircuitAnalysis)
            .where(
                CircuitAnalysis.circuit_id == circuit_id,
                CircuitAnalysis.deleted_at.is_(None),
            )
            .order_by(CircuitAnalysis.created_at.desc())
            .limit(1)
        )
        if tenant_id:
            stmt = stmt.where(CircuitAnalysis.tenant_id == tenant_id)
        elif owner_id:
            stmt = stmt.where(CircuitAnalysis.tenant_id.is_(None), CircuitAnalysis.created_by == owner_id)
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
    ) -> list[CircuitAnalysis]:
        stmt = (
            select(CircuitAnalysis)
            .where(
                CircuitAnalysis.circuit_id == circuit_id,
                CircuitAnalysis.deleted_at.is_(None),
            )
            .order_by(CircuitAnalysis.created_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(CircuitAnalysis.tenant_id == tenant_id)
        elif owner_id:
            stmt = stmt.where(CircuitAnalysis.tenant_id.is_(None), CircuitAnalysis.created_by == owner_id)
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
        circuit_version: int,
        user_id: str,
        tenant_id: str | None,
        analysis_data: dict,
    ) -> CircuitAnalysis:
        analysis = CircuitAnalysis(
            circuit_id=circuit_id,
            circuit_version=circuit_version,
            tenant_id=tenant_id,
            created_by=user_id,
            status=analysis_data.get("status", "COMPLETE"),
            confidence=analysis_data.get("confidence", "HIGH"),
            graph_summary=analysis_data.get("graph_summary", {}),
            calculations=analysis_data.get("calculations", []),
            findings=analysis_data.get("findings", []),
            unknowns=analysis_data.get("unknowns", []),
            assumptions=analysis_data.get("assumptions", []),
            execution_time_ms=analysis_data.get("execution_time_ms", 0.0),
        )
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        return analysis


analysis_repo = AnalysisRepository()
