from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import AuthenticatedUser
from app.models.schemas.design import (
    DesignComparisonResponse,
    EngineeringDesignAlternative,
    EngineeringDesignObjectiveCreate,
    EngineeringDesignObjectiveResponse,
)
from app.models.schemas.proposal import ProposalCreate, ProposalOperation, ProposalResponse
from app.repositories.circuit_repo import circuit_repo
from app.repositories.design_objective_repo import design_objective_repo
from app.services.ai.analysis.circuit_analysis_service import CircuitAnalysisService
from app.services.ai.design.candidate_generator import DesignCandidateGenerator
from app.services.ai.design.comparison_service import DesignComparisonService
from app.services.ai.design.what_if_sandbox import SandboxedWhatIfSimulator
from app.services.analysis_service import analysis_service
from app.services.circuit_service import circuit_service
from app.services.proposal_service import proposal_service


class DesignIntelligenceService:
    """
    Controlled Engineering Design Intelligence Orchestrator.
    Coordinates design objectives, candidate generation, what-if sandboxed simulation,
    comparison, and conversion to staged proposals.
    Rule: Never mutates the database directly during candidate generation or what-if.
    """

    def __init__(self):
        self.circuit_analyzer = CircuitAnalysisService()
        self.sandbox = SandboxedWhatIfSimulator(self.circuit_analyzer)
        self.candidate_generator = DesignCandidateGenerator(self.sandbox)
        self.comparison_service = DesignComparisonService()

    async def create_objective(
        self,
        db: AsyncSession,
        circuit_id: str,
        objective_in: EngineeringDesignObjectiveCreate,
        current_user: AuthenticatedUser,
    ) -> EngineeringDesignObjectiveResponse:
        # Verify circuit ownership and tenant access
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=circuit_id, tenant_id=current_user.tenant_id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found or unauthorized")

        objective = await design_objective_repo.create(
            db=db,
            circuit_id=circuit_id,
            objective_in=objective_in,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
        return EngineeringDesignObjectiveResponse.model_validate(objective)

    async def generate_alternatives_for_circuit(
        self,
        db: AsyncSession,
        circuit_id: str,
        objective_id: str | None,
        objective_type: str,
        target: dict[str, Any],
        constraints: list[dict[str, Any]],
        current_user: AuthenticatedUser,
        affected_components: list[str] | None = None,
    ) -> list[EngineeringDesignAlternative]:
        # 1. Fetch current circuit detail
        circuit_detail = await circuit_service.get_circuit(db=db, circuit_id=circuit_id, current_user=current_user)

        circuit_dict = {
            "id": circuit_detail.id,
            "version": circuit_detail.version,
            "components": [c.model_dump() for c in circuit_detail.components],
            "nets": [n.model_dump() for n in circuit_detail.nets],
            "connections": [conn.model_dump() for conn in circuit_detail.connections],
            "assumptions": [a.model_dump() for a in circuit_detail.assumptions],
        }

        # 2. Get latest verified analysis
        latest_analysis = await analysis_service.get_latest_analysis(db=db, circuit_id=circuit_id, current_user=current_user)
        analysis_data = latest_analysis.model_dump()

        # 3. Generate candidate alternatives via sandboxed simulation
        alternatives = self.candidate_generator.generate_alternatives(
            circuit_dict=circuit_dict,
            analysis_data=analysis_data,
            objective_id=objective_id or f"obj-ephemeral-{circuit_id}",
            objective_type=objective_type,
            target=target,
            constraints=constraints,
            affected_components=affected_components,
        )

        return alternatives

    async def compare_design_alternatives(
        self,
        db: AsyncSession,
        circuit_id: str,
        alternatives: list[EngineeringDesignAlternative] | list[dict[str, Any]],
        current_user: AuthenticatedUser,
    ) -> DesignComparisonResponse:
        circuit_detail = await circuit_service.get_circuit(db=db, circuit_id=circuit_id, current_user=current_user)
        circuit_dict = {
            "id": circuit_detail.id,
            "version": circuit_detail.version,
            "components": [c.model_dump() for c in circuit_detail.components],
            "nets": [n.model_dump() for n in circuit_detail.nets],
            "connections": [conn.model_dump() for conn in circuit_detail.connections],
        }

        latest_analysis = await analysis_service.get_latest_analysis(db=db, circuit_id=circuit_id, current_user=current_user)
        baseline_analysis = latest_analysis.model_dump()

        return self.comparison_service.compare_alternatives(
            circuit_dict=circuit_dict,
            baseline_analysis=baseline_analysis,
            alternatives=alternatives,
        )

    async def create_proposal_from_alternative(
        self,
        db: AsyncSession,
        circuit_id: str,
        alternative_data: dict[str, Any],
        current_user: AuthenticatedUser,
    ) -> ProposalResponse:
        circuit = await circuit_repo.get_by_id(db=db, circuit_id=circuit_id, tenant_id=current_user.tenant_id)
        if not circuit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Circuit not found")

        # Map proposed changes into ProposalOperation
        operations: list[ProposalOperation] = []
        for ch in alternative_data.get("proposed_changes", []):
            op_name = ch.get("operation", "update_component").lower()
            payload = dict(ch.get("payload") or {})

            if ch.get("component_id"):
                payload["component_id"] = ch.get("component_id")
            if ch.get("ref_des"):
                payload["ref_des"] = ch.get("ref_des")
            if ch.get("field"):
                payload[ch.get("field")] = ch.get("new_value")
            if ch.get("new_value") and "value" not in payload:
                payload["value"] = ch.get("new_value")
            if ch.get("net_name"):
                payload["net_name"] = ch.get("net_name")
            if ch.get("pin_number"):
                payload["pin_number"] = ch.get("pin_number")

            operations.append(ProposalOperation(
                op_type=op_name,
                payload=payload,
                description=ch.get("description"),
            ))

        proposal_in = ProposalCreate(
            title=alternative_data.get("title", "Engineering Design Proposal"),
            description=alternative_data.get("description"),
            source="DESIGN_INTELLIGENCE",
            base_revision=circuit.version,  # Explicit baseline revision for stale protection
            analysis_id=alternative_data.get("before_analysis_id"),
            objective_id=alternative_data.get("objective_id"),
            operations=operations,
            findings_resolved=alternative_data.get("findings_resolved", []),
            findings_introduced=alternative_data.get("findings_introduced", []),
            constraints_evaluated=alternative_data.get("constraint_results", []),
            engineering_effects=alternative_data.get("engineering_effects", []),
            unknowns=alternative_data.get("unknowns", []),
            confidence=alternative_data.get("confidence", "HIGH"),
        )

        return await proposal_service.create_proposal(
            db=db,
            circuit_id=circuit_id,
            proposal_in=proposal_in,
            current_user=current_user,
        )


design_intelligence_service = DesignIntelligenceService()
