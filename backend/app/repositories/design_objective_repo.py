from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db.design_objective import EngineeringDesignObjective
from app.models.schemas.design import EngineeringDesignObjectiveCreate


class DesignObjectiveRepository:
    """Data access repository for EngineeringDesignObjective with tenant isolation."""

    async def get_by_id(
        self,
        db: AsyncSession,
        objective_id: str,
        tenant_id: str | None = None,
    ) -> EngineeringDesignObjective | None:
        stmt = select(EngineeringDesignObjective).where(
            EngineeringDesignObjective.id == objective_id,
            EngineeringDesignObjective.deleted_at.is_(None),
        )
        if tenant_id:
            stmt = stmt.where(EngineeringDesignObjective.tenant_id == tenant_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_circuit(
        self,
        db: AsyncSession,
        circuit_id: str,
        tenant_id: str | None = None,
    ) -> list[EngineeringDesignObjective]:
        stmt = (
            select(EngineeringDesignObjective)
            .where(
                EngineeringDesignObjective.circuit_id == circuit_id,
                EngineeringDesignObjective.deleted_at.is_(None),
            )
            .order_by(EngineeringDesignObjective.created_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(EngineeringDesignObjective.tenant_id == tenant_id)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        circuit_id: str,
        objective_in: EngineeringDesignObjectiveCreate,
        user_id: str,
        tenant_id: str | None = None,
    ) -> EngineeringDesignObjective:
        objective = EngineeringDesignObjective(
            circuit_id=circuit_id,
            tenant_id=tenant_id,
            created_by=user_id,
            objective_type=objective_in.objective_type,
            description=objective_in.description,
            target=objective_in.target,
            constraints=[c.model_dump() for c in objective_in.constraints],
            affected_components=objective_in.affected_components,
            affected_nets=objective_in.affected_nets,
            source=objective_in.source,
        )
        db.add(objective)
        await db.commit()
        await db.refresh(objective)
        return objective


design_objective_repo = DesignObjectiveRepository()
