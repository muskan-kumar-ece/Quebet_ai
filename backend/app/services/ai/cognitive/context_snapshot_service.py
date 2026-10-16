import hashlib
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.cognitive import EngineeringCognitiveContextSnapshot, EngineeringIntentPacket
from app.repositories.project_repo import ProjectRepository
from app.repositories.system_repo import SystemRepository
from app.repositories.circuit_repo import CircuitRepository
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.decision_repo import DecisionRepository
from app.repositories.knowledge_repo import KnowledgeRepo


class ContextSnapshotService:
    """
    Manages creation and deterministic canonical hashing of EngineeringCognitiveContextSnapshots.
    Guarantees:
    1. Same logical context references produce identical SHA-256 digests.
    2. Meaningful context revision changes produce distinct digests.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def compute_canonical_digest(
        project_id: str,
        project_revision: int,
        system_id: Optional[str],
        system_revision: Optional[int],
        circuit_id: Optional[str],
        circuit_revision: Optional[int],
        analysis_id: Optional[str],
        requirement_baseline_id: Optional[str],
        knowledge_snapshot_id: Optional[str],
        assumption_ids: List[str],
        scenario_ids: List[str],
        engine_versions: Dict[str, Any],
        rule_set_version: str = "v1.0.0",
    ) -> str:
        """
        Computes a deterministic, canonical SHA-256 digest over sorted, normalized references.
        """
        canonical_dict = {
            "project_id": str(project_id or ""),
            "project_revision": int(project_revision or 1),
            "system_id": str(system_id or ""),
            "system_revision": int(system_revision) if system_revision is not None else None,
            "circuit_id": str(circuit_id or ""),
            "circuit_revision": int(circuit_revision) if circuit_revision is not None else None,
            "analysis_id": str(analysis_id or ""),
            "requirement_baseline_id": str(requirement_baseline_id or ""),
            "knowledge_snapshot_id": str(knowledge_snapshot_id or ""),
            "assumption_ids": sorted([str(a) for a in assumption_ids]),
            "scenario_ids": sorted([str(s) for s in scenario_ids]),
            "engine_versions": {k: str(engine_versions[k]) for k in sorted(engine_versions.keys())},
            "rule_set_version": str(rule_set_version or "v1.0.0"),
        }

        canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    async def create_snapshot(
        self,
        intent: EngineeringIntentPacket,
        tenant_id: str,
        engine_versions: Optional[Dict[str, Any]] = None,
        rule_set_version: str = "v1.0.0",
    ) -> EngineeringCognitiveContextSnapshot:
        proj_repo = ProjectRepository()
        project = await proj_repo.get_by_id(self.db, intent.project_id, tenant_id=tenant_id)
        project_rev = getattr(project, "version", 1) if project else 1

        sys_rev: Optional[int] = None
        if intent.system_id:
            sys_repo = SystemRepository(self.db)
            system = await sys_repo.get_system(intent.system_id, tenant_id=tenant_id, load_relations=True)
            if system:
                sys_rev = system.revision

        circ_rev: Optional[int] = None
        if intent.circuit_id:
            circ_repo = CircuitRepository()
            circuit = await circ_repo.get_by_id(self.db, intent.circuit_id, tenant_id=tenant_id)
            if circuit:
                circ_rev = circuit.version

        # Latest Analysis
        analysis_id: Optional[str] = None
        if intent.circuit_id:
            an_repo = AnalysisRepository()
            analyses = await an_repo.list_for_circuit(self.db, intent.circuit_id)
            if analyses:
                analysis_id = analyses[0].id

        # Requirement Baseline
        baseline_id: Optional[str] = None
        assumption_ids: List[str] = []
        if intent.system_id:
            dec_repo = DecisionRepository(self.db)
            baselines = await dec_repo.get_baselines_by_system(intent.system_id, tenant_id=tenant_id)
            if baselines:
                baseline_id = baselines[0].id
            assumptions = await dec_repo.get_assumptions_by_system(intent.system_id, tenant_id=tenant_id)
            assumption_ids = [a.id for a in assumptions]

        # Knowledge Snapshot
        knowledge_snap_id: Optional[str] = None
        try:
            k_repo = KnowledgeRepo(self.db)
            snaps = await k_repo.list_snapshots(tenant_id=tenant_id)
            if snaps:
                knowledge_snap_id = snaps[0].id
        except Exception:
            pass

        scenario_ids = [s.get("name", str(i)) for i, s in enumerate(intent.scenarios or [])]
        engines = engine_versions or {
            "circuit_analysis_engine": "v3.1.0",
            "system_architecture_engine": "v2.0.0",
            "rule_set_version": rule_set_version,
        }

        digest = self.compute_canonical_digest(
            project_id=intent.project_id,
            project_revision=project_rev,
            system_id=intent.system_id,
            system_revision=sys_rev,
            circuit_id=intent.circuit_id,
            circuit_revision=circ_rev,
            analysis_id=analysis_id,
            requirement_baseline_id=baseline_id,
            knowledge_snapshot_id=knowledge_snap_id,
            assumption_ids=assumption_ids,
            scenario_ids=scenario_ids,
            engine_versions=engines,
            rule_set_version=rule_set_version,
        )

        snapshot = EngineeringCognitiveContextSnapshot(
            tenant_id=tenant_id,
            project_id=intent.project_id,
            project_revision=project_rev,
            system_id=intent.system_id,
            system_revision=sys_rev,
            circuit_id=intent.circuit_id,
            circuit_revision=circ_rev,
            analysis_id=analysis_id,
            requirement_baseline_id=baseline_id,
            knowledge_snapshot_id=knowledge_snap_id,
            assumption_ids=assumption_ids,
            scenario_ids=scenario_ids,
            engine_versions=engines,
            rule_set_version=rule_set_version,
            context_digest=digest,
            context_payload={
                "project_name": getattr(project, "name", "Project") if project else "Project",
                "system_id": intent.system_id,
                "circuit_id": intent.circuit_id,
                "entities_count": len(intent.entities or []),
                "ambiguities": intent.ambiguities or [],
            },
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot
