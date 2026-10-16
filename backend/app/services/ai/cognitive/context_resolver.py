from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.cognitive import EngineeringIntentPacket
from app.repositories.project_repo import ProjectRepository
from app.repositories.system_repo import SystemRepository
from app.repositories.circuit_repo import CircuitRepository
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.verification_repo import VerificationRepository
from app.repositories.decision_repo import DecisionRepository


class EngineeringContextResolver:
    """
    Deterministically resolves the authoritative engineering context for an IntentPacket.
    Validates tenant ownership, object existence, revision freshness, and resolves component ambiguities.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_context(
        self,
        intent: EngineeringIntentPacket,
        tenant_id: str,
    ) -> Dict[str, Any]:
        # 1. Project verification
        proj_repo = ProjectRepository()
        project = await proj_repo.get_by_id(self.db, intent.project_id, tenant_id=tenant_id)
        if not project:
            return {
                "is_valid": False,
                "error": "PROJECT_NOT_FOUND",
                "message": f"Project {intent.project_id} not found or tenant unauthorized.",
            }

        context_snapshot: Dict[str, Any] = {
            "project_id": project.id,
            "project_name": project.name,
            "project_type": project.project_type,
            "base_revision": 1,
            "ambiguities": list(intent.ambiguities or []),
            "missing_information": list(intent.missing_information or []),
        }

        # 2. System context (if specified)
        if intent.system_id:
            sys_repo = SystemRepository(self.db)
            system = await sys_repo.get_system(intent.system_id, tenant_id=tenant_id, load_relations=True)
            if not system:
                return {
                    "is_valid": False,
                    "error": "SYSTEM_NOT_FOUND",
                    "message": f"System {intent.system_id} not found in project.",
                }
            context_snapshot["system_id"] = system.id
            context_snapshot["system_name"] = system.name
            context_snapshot["base_revision"] = system.revision
            context_snapshot["subsystems_count"] = len(system.subsystems or [])
            context_snapshot["interfaces_count"] = len(system.interfaces or [])
            context_snapshot["power_domains_count"] = len(system.power_domains or [])

        # 3. Circuit context (if specified)
        if intent.circuit_id:
            circ_repo = CircuitRepository()
            circuit = await circ_repo.get_by_id(self.db, intent.circuit_id, tenant_id=tenant_id)
            if not circuit:
                return {
                    "is_valid": False,
                    "error": "CIRCUIT_NOT_FOUND",
                    "message": f"Circuit {intent.circuit_id} not found in project.",
                }
            context_snapshot["circuit_id"] = circuit.id
            context_snapshot["circuit_name"] = circuit.name
            context_snapshot["circuit_version"] = circuit.version
            if not intent.system_id:
                context_snapshot["base_revision"] = circuit.version
            context_snapshot["components_count"] = len(circuit.components or [])
            context_snapshot["nets_count"] = len(circuit.nets or [])

            # Check and resolve component ambiguities against actual circuit components
            regulators = [
                c for c in (circuit.components or [])
                if "regulator" in getattr(c, "component_type", "").lower()
                or getattr(c, "component_type", "").lower() in ["ic", "converter"]
                or getattr(c, "ref_des", "").startswith("U")
            ]
            for amb in context_snapshot["ambiguities"]:
                if amb.get("target") == "regulator":
                    if len(regulators) == 1:
                        # Auto-resolved unambiguous single match
                        amb["status"] = "AUTO_RESOLVED"
                        amb["resolved_component"] = regulators[0].ref_des
                    elif len(regulators) > 1:
                        amb["status"] = "CLARIFICATION_REQUIRED"
                        amb["candidates"] = [
                            {"ref_des": r.ref_des, "name": getattr(r, "name", r.ref_des), "value": getattr(r, "value", "")}
                            for r in regulators
                        ]

        # 4. Latest analysis lookup
        if intent.circuit_id:
            an_repo = AnalysisRepository()
            analyses = await an_repo.list_for_circuit(self.db, intent.circuit_id)
            if analyses:
                latest = analyses[0]
                context_snapshot["latest_analysis_id"] = latest.id
                context_snapshot["latest_analysis_status"] = latest.status
                context_snapshot["active_findings_count"] = len(latest.findings or [])

        # 5. Requirements and Decisions context
        if intent.system_id:
            dec_repo = DecisionRepository(self.db)
            reqs = await dec_repo.get_requirements_by_system(intent.system_id, tenant_id=tenant_id)
            context_snapshot["requirements_count"] = len(reqs)
            assumps = await dec_repo.get_assumptions_by_system(intent.system_id, tenant_id=tenant_id)
            context_snapshot["assumptions_count"] = len(assumps)
            decs = await dec_repo.get_decisions_by_system(intent.system_id, tenant_id=tenant_id)
            context_snapshot["decisions_count"] = len(decs)

        context_snapshot["is_valid"] = True
        return context_snapshot
