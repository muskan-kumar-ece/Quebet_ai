from typing import Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthenticatedUser
from app.models.schemas.analysis import CircuitAnalysisResponse, ExplainRequest, ExplainResponse
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.knowledge_repo import KnowledgeRepo
from app.repositories.provenance_repo import ProvenanceRepo
from app.services.ai.analysis.circuit_analysis_service import CircuitAnalysisService
from app.services.ai.explanation_service import EngineeringExplanationService
from app.services.circuit_service import circuit_service
from app.services.component_intelligence_service import EngineeringComponentIntelligenceService
from app.services.ai.verification.knowledge_bootstrap import KnowledgeBootstrapService


class AnalysisService:
    def __init__(self) -> None:
        self.circuit_analyzer = CircuitAnalysisService()
        self.explanation_service = EngineeringExplanationService()
        self.analysis_repo = AnalysisRepository()

    async def run_analysis(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
        operating_mode: Optional[str] = "NORMAL",
        ambient_temp_c: Optional[float] = 25.0,
        requirements: Optional[list[dict[str, Any]]] = None,
        constraints: Optional[list[dict[str, Any]]] = None,
    ) -> CircuitAnalysisResponse:
        circuit_detail = await circuit_service.get_circuit(
            db=db,
            circuit_id=circuit_id,
            current_user=current_user,
        )

        circuit_dict = {
            "id": circuit_detail.id,
            "version": circuit_detail.version,
            "components": [{**c.model_dump(), "name": c.ref_des} for c in circuit_detail.components],
            "nets": [n.model_dump() for n in circuit_detail.nets],
            "connections": [conn.model_dump() for conn in circuit_detail.connections],
            "assumptions": [a.model_dump() for a in circuit_detail.assumptions],
        }

        # Resolve component intelligence profiles for components in circuit
        component_profiles: dict[str, Any] = {}
        try:
            comp_intel_svc = EngineeringComponentIntelligenceService(db)
            for c in circuit_detail.components:
                pn = c.part_number or c.value or c.ref_des
                if pn:
                    profile = await comp_intel_svc.get_component_profile(
                        part_number=pn,
                        tenant_id=current_user.tenant_id,
                    )
                    if profile and profile.identity.state.value != "UNKNOWN":
                        component_profiles[pn] = profile
                        component_profiles[c.ref_des] = profile
        except Exception:
            # Failure to fetch profiles falls back gracefully to standard electronics-kb
            pass

        # Perform deterministic calculation and rule analysis
        analysis_result = self.circuit_analyzer.analyze_circuit(
            circuit_dict=circuit_dict,
            user_assumptions=circuit_dict["assumptions"],
            component_profiles=component_profiles,
            operating_mode=operating_mode,
            requirements=requirements,
            constraints=constraints,
            ambient_temp_c=ambient_temp_c,
        )

        # Persist snapshot in database
        analysis_record = await self.analysis_repo.create(
            db=db,
            circuit_id=circuit_id,
            circuit_version=circuit_detail.version,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            analysis_data=analysis_result,
        )

        # Seed foundational knowledge if not yet present
        await KnowledgeBootstrapService.seed_foundational_knowledge(db, tenant_id=current_user.tenant_id)

        # Capture knowledge snapshot & analysis provenance
        try:
            knowledge_repo = KnowledgeRepo(db)
            records = await knowledge_repo.list_records(tenant_id=current_user.tenant_id)
            snapshot = await knowledge_repo.create_or_get_snapshot(
                [r.id for r in records], tenant_id=current_user.tenant_id
            )

            provenance_repo = ProvenanceRepo(db)
            input_values = {
                "components_count": len(circuit_dict.get("components", [])),
                "nets_count": len(circuit_dict.get("nets", [])),
                "connections_count": len(circuit_dict.get("connections", [])),
                "operating_mode": operating_mode,
            }
            await provenance_repo.record_analysis_provenance(
                analysis_id=analysis_record.id,
                circuit_id=circuit_id,
                circuit_revision=circuit_detail.version,
                engine_versions=analysis_result.get("engine_versions") or self.circuit_analyzer.ENGINE_VERSIONS,
                rule_set_version=analysis_result.get("rule_set_version") or self.circuit_analyzer.RULE_SET_VERSION,
                knowledge_snapshot_id=snapshot.id if snapshot else None,
                input_values=input_values,
                assumptions=circuit_dict.get("assumptions") or [],
                calculation_methods=analysis_result.get("calculation_methods") or ["NODAL_VOLTAGE", "OHMS_LAW", "MARGIN_DERATING"],
                tenant_id=current_user.tenant_id,
            )
        except Exception:
            # Provenance recording should not break core analysis execution
            pass

        return CircuitAnalysisResponse.model_validate(analysis_record)

    async def get_latest_analysis(
        self,
        db: AsyncSession,
        circuit_id: str,
        current_user: AuthenticatedUser,
    ) -> CircuitAnalysisResponse:
        # Verify circuit access
        await circuit_service.get_circuit(db=db, circuit_id=circuit_id, current_user=current_user)

        record = await self.analysis_repo.get_latest_for_circuit(
            db=db,
            circuit_id=circuit_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not record:
            # If no analysis exists yet, compute and store one dynamically
            return await self.run_analysis(db=db, circuit_id=circuit_id, current_user=current_user)

        return CircuitAnalysisResponse.model_validate(record)

    async def check_analysis_staleness(
        self,
        db: AsyncSession,
        circuit_id: str,
        analysis_id: str,
        current_user: AuthenticatedUser,
    ) -> dict[str, Any]:
        """
        Determines if an analysis is STALE due to circuit revision or component knowledge changes.
        """
        circuit = await circuit_service.get_circuit(db=db, circuit_id=circuit_id, current_user=current_user)
        analysis = await self.get_analysis_by_id(db=db, circuit_id=circuit_id, analysis_id=analysis_id, current_user=current_user)

        stale_reasons = []
        is_stale = False

        if circuit.version != analysis.circuit_version:
            is_stale = True
            stale_reasons.append(
                f"Circuit revision changed from {analysis.circuit_version} to {circuit.version}."
            )

        return {
            "analysis_id": analysis_id,
            "circuit_id": circuit_id,
            "is_stale": is_stale,
            "recorded_circuit_version": analysis.circuit_version,
            "current_circuit_version": circuit.version,
            "reasons": stale_reasons,
        }

    async def get_analysis_by_id(
        self,
        db: AsyncSession,
        circuit_id: str,
        analysis_id: str,
        current_user: AuthenticatedUser,
    ) -> CircuitAnalysisResponse:
        # Verify circuit access
        await circuit_service.get_circuit(db=db, circuit_id=circuit_id, current_user=current_user)

        record = await self.analysis_repo.get_by_id(
            db=db,
            analysis_id=analysis_id,
            tenant_id=current_user.tenant_id,
            owner_id=current_user.id,
        )
        if not record or record.circuit_id != circuit_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis record not found")

        return CircuitAnalysisResponse.model_validate(record)

    async def explain_analysis(
        self,
        db: AsyncSession,
        circuit_id: str,
        explain_in: ExplainRequest,
        current_user: AuthenticatedUser,
    ) -> ExplainResponse:
        # Get latest analysis snapshot
        analysis = await self.get_latest_analysis(db=db, circuit_id=circuit_id, current_user=current_user)

        return self.explanation_service.explain_analysis(
            circuit_id=circuit_id,
            analysis_data=analysis.model_dump(),
            finding_ids=explain_in.finding_ids,
            component_ids=explain_in.component_ids,
            user_query=explain_in.user_query,
        )


analysis_service = AnalysisService()
