from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.db.system_synthesis import (
    EngineeringScenario,
    EngineeringScenarioCondition,
    EngineeringScenarioResult,
    EngineeringScenarioSnapshot,
    EngineeringSystemCandidate,
    EngineeringSystemDesignConstraint,
    EngineeringSystemDesignObjective,
    EngineeringSystemProposal,
    SystemProposalStatus,
)


class SystemSynthesisRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------------------------------------------------
    # Objectives & Constraints
    # ---------------------------------------------------------

    async def get_objective(
        self,
        objective_id: str,
        tenant_id: Optional[str] = None,
        load_relations: bool = True,
    ) -> Optional[EngineeringSystemDesignObjective]:
        stmt = select(EngineeringSystemDesignObjective).where(
            EngineeringSystemDesignObjective.id == objective_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemDesignObjective.tenant_id == tenant_id)
        if load_relations:
            stmt = stmt.options(
                selectinload(EngineeringSystemDesignObjective.constraints),
                selectinload(EngineeringSystemDesignObjective.candidates),
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_objectives_for_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemDesignObjective]:
        stmt = select(EngineeringSystemDesignObjective).where(
            EngineeringSystemDesignObjective.system_id == system_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemDesignObjective.tenant_id == tenant_id)
        stmt = stmt.options(
            selectinload(EngineeringSystemDesignObjective.constraints),
            selectinload(EngineeringSystemDesignObjective.candidates),
        ).order_by(desc(EngineeringSystemDesignObjective.created_at))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_objective(
        self,
        objective: EngineeringSystemDesignObjective,
    ) -> EngineeringSystemDesignObjective:
        self.db.add(objective)
        await self.db.flush()
        return objective

    async def create_constraint(
        self,
        constraint: EngineeringSystemDesignConstraint,
    ) -> EngineeringSystemDesignConstraint:
        self.db.add(constraint)
        await self.db.flush()
        return constraint

    async def get_constraints_for_objective(
        self,
        objective_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemDesignConstraint]:
        stmt = select(EngineeringSystemDesignConstraint).where(
            EngineeringSystemDesignConstraint.objective_id == objective_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemDesignConstraint.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Scenarios & Conditions
    # ---------------------------------------------------------

    async def get_scenario(
        self,
        scenario_id: str,
        tenant_id: Optional[str] = None,
        load_relations: bool = True,
    ) -> Optional[EngineeringScenario]:
        stmt = select(EngineeringScenario).where(EngineeringScenario.id == scenario_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringScenario.tenant_id == tenant_id)
        if load_relations:
            stmt = stmt.options(
                selectinload(EngineeringScenario.conditions),
                selectinload(EngineeringScenario.results),
            )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_scenarios_for_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringScenario]:
        stmt = select(EngineeringScenario).where(EngineeringScenario.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringScenario.tenant_id == tenant_id)
        stmt = stmt.options(
            selectinload(EngineeringScenario.conditions),
            selectinload(EngineeringScenario.results),
        ).order_by(desc(EngineeringScenario.created_at))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_scenario(self, scenario: EngineeringScenario) -> EngineeringScenario:
        self.db.add(scenario)
        await self.db.flush()
        return scenario

    async def create_scenario_condition(
        self, condition: EngineeringScenarioCondition
    ) -> EngineeringScenarioCondition:
        self.db.add(condition)
        await self.db.flush()
        return condition

    async def get_conditions_for_scenario(
        self,
        scenario_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringScenarioCondition]:
        stmt = select(EngineeringScenarioCondition).where(
            EngineeringScenarioCondition.scenario_id == scenario_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringScenarioCondition.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Scenario Snapshots & Results
    # ---------------------------------------------------------

    async def create_scenario_snapshot(
        self, snapshot: EngineeringScenarioSnapshot
    ) -> EngineeringScenarioSnapshot:
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def create_scenario_result(
        self, result: EngineeringScenarioResult
    ) -> EngineeringScenarioResult:
        self.db.add(result)
        await self.db.flush()
        return result

    async def get_latest_scenario_result(
        self,
        scenario_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringScenarioResult]:
        stmt = (
            select(EngineeringScenarioResult)
            .where(EngineeringScenarioResult.scenario_id == scenario_id)
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringScenarioResult.tenant_id == tenant_id)
        stmt = stmt.order_by(desc(EngineeringScenarioResult.created_at)).limit(1)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_scenario_results(
        self,
        scenario_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringScenarioResult]:
        stmt = select(EngineeringScenarioResult).where(
            EngineeringScenarioResult.scenario_id == scenario_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringScenarioResult.tenant_id == tenant_id)
        stmt = stmt.order_by(desc(EngineeringScenarioResult.created_at))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    # ---------------------------------------------------------
    # Candidates
    # ---------------------------------------------------------

    async def get_candidate(
        self,
        candidate_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSystemCandidate]:
        stmt = select(EngineeringSystemCandidate).where(
            EngineeringSystemCandidate.id == candidate_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemCandidate.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_candidates_for_objective(
        self,
        objective_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemCandidate]:
        stmt = select(EngineeringSystemCandidate).where(
            EngineeringSystemCandidate.objective_id == objective_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemCandidate.tenant_id == tenant_id)
        stmt = stmt.order_by(desc(EngineeringSystemCandidate.created_at))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_candidates_for_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemCandidate]:
        stmt = select(EngineeringSystemCandidate).where(
            EngineeringSystemCandidate.system_id == system_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemCandidate.tenant_id == tenant_id)
        stmt = stmt.order_by(desc(EngineeringSystemCandidate.created_at))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_candidate(
        self, candidate: EngineeringSystemCandidate
    ) -> EngineeringSystemCandidate:
        self.db.add(candidate)
        await self.db.flush()
        return candidate

    # ---------------------------------------------------------
    # System Proposals
    # ---------------------------------------------------------

    async def get_proposal(
        self,
        proposal_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSystemProposal]:
        stmt = select(EngineeringSystemProposal).where(
            EngineeringSystemProposal.id == proposal_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemProposal.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_proposals_for_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemProposal]:
        stmt = select(EngineeringSystemProposal).where(
            EngineeringSystemProposal.system_id == system_id
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemProposal.tenant_id == tenant_id)
        stmt = stmt.order_by(desc(EngineeringSystemProposal.created_at))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_proposal(
        self, proposal: EngineeringSystemProposal
    ) -> EngineeringSystemProposal:
        self.db.add(proposal)
        await self.db.flush()
        return proposal

    async def mark_proposals_stale_for_system(
        self,
        system_id: str,
        current_revision: int,
        tenant_id: Optional[str] = None,
    ) -> int:
        stmt = (
            update(EngineeringSystemProposal)
            .where(
                EngineeringSystemProposal.system_id == system_id,
                EngineeringSystemProposal.base_revision < current_revision,
                EngineeringSystemProposal.status.in_(
                    [SystemProposalStatus.PROPOSED.value, SystemProposalStatus.VALIDATED.value]
                ),
            )
            .values(status=SystemProposalStatus.STALE.value)
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemProposal.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.rowcount
