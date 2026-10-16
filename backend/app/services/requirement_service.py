from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.decision import (
    EngineeringRequirement,
    EngineeringRequirementBaseline,
    EngineeringAssumption,
)
from app.repositories.decision_repo import DecisionRepository
from app.repositories.system_repo import SystemRepository
from app.services.ai.decision.requirement_coverage_service import RequirementCoverageService
from app.services.ai.decision.requirement_change_impact_service import RequirementChangeImpactService
from app.services.ai.decision.assumption_impact_service import AssumptionImpactService


class RequirementService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DecisionRepository(db)
        self.system_repo = SystemRepository(db)

    async def get_system_requirement_coverage(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        requirements = await self.repo.get_requirements_by_system(system_id, tenant_id=tenant_id)
        decisions = await self.repo.get_decisions_by_system(system_id, tenant_id=tenant_id)
        return RequirementCoverageService.evaluate_requirement_coverage(
            requirements=requirements,
            decisions=decisions,
        )

    async def calculate_requirement_impact(
        self,
        requirement_id: str,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        req = await self.repo.get_requirement(requirement_id, tenant_id=tenant_id)
        if not req:
            raise HTTPException(status_code=404, detail="Requirement not found")

        subsystems = await self.system_repo.get_subsystems(system_id, tenant_id=tenant_id)
        interfaces = await self.system_repo.get_interfaces(system_id, tenant_id=tenant_id)
        decisions = await self.repo.get_decisions_by_system(system_id, tenant_id=tenant_id)

        return RequirementChangeImpactService.calculate_impact(
            changed_requirement_id=requirement_id,
            system_id=system_id,
            subsystems=subsystems,
            interfaces=interfaces,
            analyses=[],
            decisions=decisions,
        )

    async def calculate_assumption_impact(
        self,
        assumption_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        assump = await self.repo.get_assumption(assumption_id, tenant_id=tenant_id)
        if not assump:
            raise HTTPException(status_code=404, detail="Assumption not found")

        decisions = await self.repo.get_decisions_by_system(assump.system_id, tenant_id=tenant_id)

        return AssumptionImpactService.evaluate_assumption_impact(
            assumption=assump,
            analyses=[],
            decisions=decisions,
        )
