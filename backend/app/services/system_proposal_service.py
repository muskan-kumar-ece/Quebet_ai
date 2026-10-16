import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.system import (
    EngineeringPowerDomain,
    EngineeringSubsystem,
    EngineeringSystem,
    EngineeringSystemInterface,
    SystemStatus,
)
from app.models.db.system_synthesis import (
    EngineeringSystemProposal,
    SystemProposalStatus,
)
from app.repositories.system_repo import SystemRepository
from app.repositories.system_synthesis_repo import SystemSynthesisRepository
from app.services.system_service import SystemService


class SystemProposalService:
    """
    Manages the lifecycle, stale validation, human approval, and atomic application
    of system-level architecture proposals.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.system_repo = SystemRepository(db)
        self.synthesis_repo = SystemSynthesisRepository(db)

    async def create_proposal(
        self,
        system_id: str,
        user_id: str,
        title: str,
        description: Optional[str],
        base_revision: int,
        operations: List[Dict[str, Any]],
        generation_strategy: str = "MANUAL",
        rationale: str = "",
        candidate_id: Optional[str] = None,
        objective_id: Optional[str] = None,
        scenario_ids: Optional[List[str]] = None,
        engineering_effects: Optional[List[Dict[str, Any]]] = None,
        requirement_effects: Optional[List[Dict[str, Any]]] = None,
        verification_effects: Optional[List[Dict[str, Any]]] = None,
        failure_effects: Optional[Dict[str, Any]] = None,
        unknowns: Optional[List[str]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> EngineeringSystemProposal:
        system = await self.system_repo.get_system(system_id, tenant_id=tenant_id)
        if not system:
            raise HTTPException(status_code=404, detail="System not found")

        # Validate base revision
        status = SystemProposalStatus.PROPOSED.value
        if base_revision != system.revision:
            status = SystemProposalStatus.STALE.value

        proposal = EngineeringSystemProposal(
            id=str(uuid.uuid4()),
            system_id=system_id,
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            objective_id=objective_id,
            title=title,
            description=description,
            status=status,
            base_revision=base_revision,
            scenario_ids=scenario_ids or [],
            operations=operations,
            generation_strategy=generation_strategy,
            rationale=rationale or "User-defined system proposal",
            engineering_effects=engineering_effects or [],
            requirement_effects=requirement_effects or [],
            verification_effects=verification_effects or [],
            failure_effects=failure_effects or {},
            unknowns=unknowns or [],
            provenance=provenance or {"source": "USER", "timestamp": datetime.utcnow().isoformat()},
            created_by=user_id,
        )
        created = await self.synthesis_repo.create_proposal(proposal)
        await self.db.commit()
        await self.db.refresh(created)
        return created

    async def approve_proposal(
        self,
        proposal_id: str,
        user_id: str,
        tenant_id: Optional[str] = None,
    ) -> EngineeringSystemProposal:
        proposal = await self.synthesis_repo.get_proposal(proposal_id, tenant_id=tenant_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="System proposal not found")

        system = await self.system_repo.get_system(proposal.system_id, tenant_id=tenant_id)
        if not system:
            raise HTTPException(status_code=404, detail="System not found")

        if proposal.base_revision != system.revision:
            proposal.status = SystemProposalStatus.STALE.value
            await self.db.commit()
            raise HTTPException(
                status_code=409,
                detail=f"SYSTEM_PROPOSAL_STALE: Base revision {proposal.base_revision} does not match current system revision {system.revision}",
            )

        proposal.status = SystemProposalStatus.APPROVED.value
        proposal.approved_by = user_id
        await self.db.commit()
        await self.db.refresh(proposal)
        return proposal

    async def apply_proposal(
        self,
        proposal_id: str,
        user_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Atomically applies proposal operations to the persistent database.
        Increments system revision, marks stale proposals, and runs fresh analysis.
        Rolls back completely on any failure.
        """
        proposal = await self.synthesis_repo.get_proposal(proposal_id, tenant_id=tenant_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="System proposal not found")

        system = await self.system_repo.get_system(proposal.system_id, tenant_id=tenant_id)
        if not system:
            raise HTTPException(status_code=404, detail="System not found")

        # 1. Stale proposal protection
        if proposal.base_revision != system.revision:
            proposal.status = SystemProposalStatus.STALE.value
            await self.db.commit()
            raise HTTPException(
                status_code=409,
                detail=f"SYSTEM_PROPOSAL_STALE: Base revision {proposal.base_revision} does not match current system revision {system.revision}",
            )

        try:
            # 2. Execute operations
            for op in proposal.operations:
                op_type = op.get("op_type")
                payload = op.get("payload", {})

                if op_type == "ADD_SUBSYSTEM":
                    sub_id = payload.get("id") or str(uuid.uuid4())
                    new_sub = EngineeringSubsystem(
                        id=sub_id,
                        system_id=system.id,
                        tenant_id=tenant_id,
                        name=payload.get("name", "New Subsystem"),
                        subsystem_type=payload.get("subsystem_type", "OTHER"),
                        parent_subsystem_id=payload.get("parent_subsystem_id"),
                        circuit_id=payload.get("circuit_id"),
                        revision=1,
                        status="ACTIVE",
                    )
                    self.db.add(new_sub)

                elif op_type == "REMOVE_SUBSYSTEM":
                    sub_id = payload.get("subsystem_id") or payload.get("id")
                    if sub_id:
                        sub_to_del = await self.system_repo.get_subsystem(sub_id, tenant_id=tenant_id)
                        if sub_to_del:
                            await self.db.delete(sub_to_del)

                elif op_type == "REPLACE_SUBSYSTEM":
                    target_id = payload.get("target_subsystem_id") or payload.get("id")
                    if target_id:
                        sub = await self.system_repo.get_subsystem(target_id, tenant_id=tenant_id)
                        if sub:
                            if "name" in payload:
                                sub.name = payload["name"]
                            if "subsystem_type" in payload:
                                sub.subsystem_type = payload["subsystem_type"]
                            sub.revision += 1

                elif op_type == "ADD_INTERFACE":
                    iface_id = payload.get("id") or str(uuid.uuid4())
                    new_iface = EngineeringSystemInterface(
                        id=iface_id,
                        system_id=system.id,
                        tenant_id=tenant_id,
                        name=payload.get("name", "New Interface"),
                        interface_type=payload.get("interface_type", "DATA"),
                        source_subsystem_id=payload.get("source_subsystem_id"),
                        destination_subsystem_id=payload.get("destination_subsystem_id"),
                        contract=payload.get("contract", {}),
                        status="ACTIVE",
                    )
                    self.db.add(new_iface)

                elif op_type == "ADD_POWER_DOMAIN":
                    dom_id = payload.get("id") or str(uuid.uuid4())
                    new_dom = EngineeringPowerDomain(
                        id=dom_id,
                        system_id=system.id,
                        tenant_id=tenant_id,
                        name=payload.get("name", "New Rail"),
                        nominal_voltage=payload.get("nominal_voltage", 3.3),
                        min_voltage=payload.get("min_voltage"),
                        max_voltage=payload.get("max_voltage"),
                        source_subsystem_id=payload.get("source_subsystem_id"),
                        regulator_subsystem_id=payload.get("regulator_subsystem_id"),
                        current_capacity_a=payload.get("current_capacity_a"),
                        status="ACTIVE",
                    )
                    self.db.add(new_dom)

            # 3. Increment system revision
            system.revision += 1
            proposal.status = SystemProposalStatus.APPLIED.value
            proposal.applied_at = datetime.utcnow()

            # 4. Mark older proposals stale
            await self.synthesis_repo.mark_proposals_stale_for_system(
                system.id, system.revision, tenant_id=tenant_id
            )

            # 5. Mark older analyses stale
            await self.system_repo.mark_analyses_stale(system.id, tenant_id=tenant_id)

            await self.db.flush()

            # 6. Run fresh deterministic system analysis
            system_service = SystemService(self.db)
            fresh_analysis = await system_service.run_system_analysis(system.id, tenant_id=tenant_id)

            await self.db.commit()

            return {
                "success": True,
                "proposal_id": proposal.id,
                "new_system_revision": system.revision,
                "fresh_analysis_id": fresh_analysis.id if fresh_analysis else None,
            }

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to apply proposal atomically: {str(e)}")
