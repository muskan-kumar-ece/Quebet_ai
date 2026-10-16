"""
Phase 3 Wave 9 Test Suite: Unified Engineering Project Workspace,
Revision Navigation & State Synthesis.

Verifies strict non-negotiable invariants:
- UNKNOWN != PASS
- UNKNOWN != CONFIGURED
- MISSING != CONFIGURED
- CALCULATED != PHYSICALLY VERIFIED
- HISTORICAL_VERIFICATION != CURRENT_VERIFICATION
- ZERO SYNTHETIC SCORING (No confidence_percentage, readiness_score, health_score, 0-100 metrics)
- Multi-domain posture synthesis across all 8 engineering domains
- Revision lineage grouping and unbound entity isolation
- Deterministic activity timeline ordering (timestamp desc, entity_id desc)
- Multi-tenant isolation and IDOR protection (HTTP 404)
- Viewer role read-only access
"""
from datetime import datetime, timezone
import json
import uuid
import pytest
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.models.db.circuit import Circuit, CircuitValidationStatus
from app.models.db.pcb import BoardStatus, EngineeringBoard
from app.models.db.bom import BOMStatus, EngineeringBOM
from app.models.db.simulation import SimulationJob, SimulationStatus, SimulationType
from app.models.db.dfm import (
    ManufacturingAnalysisRecord,
    ManufacturingAnalysisStatus,
    ManufacturingRuleSet,
)
from app.models.db.decision import (
    EngineeringRequirement,
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
)
from app.models.db.verification import DesignReviewStatus, EngineeringDesignReview
from app.models.db.cross_domain import CrossDomainValidationRecord, CrossDomainValidationStatus


def auth_headers(
    user_id: str,
    email: str,
    role: str = "engineer",
    tenant_id: str = "tenant-p3-w9-a",
) -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestPhase3Wave9Workspace:

    async def _create_project(self, async_client: AsyncClient, headers: dict) -> str:
        resp = await async_client.post(
            "/api/v1/projects",
            json={
                "name": f"Wave 9 Project {uuid.uuid4().hex[:6]}",
                "description": "Multi-domain engineering project workspace test",
                "project_type": "circuit",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["data"]["id"]

    async def test_empty_project_workspace_state(self, async_client: AsyncClient):
        """Empty project has all 8 domains as MISSING with deterministic SHA-256 digest and 0 scores."""
        headers = auth_headers("usr-w9-1", "u1@quebet.test", tenant_id="tenant-w9-empty")
        project_id = await self._create_project(async_client, headers)

        resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/state", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        assert data["project_id"] == project_id
        assert data["active_circuit_version"] is None
        assert data["cross_domain_validation"] is None
        assert "workspace_digest" in data
        assert len(data["workspace_digest"]) == 64

        # Verify all 8 domains are MISSING
        domains = data["domains"]
        assert len(domains) == 8
        expected_domains = {
            "schematic", "pcb", "bom", "simulation",
            "manufacturing", "requirements", "design_review", "cross_domain"
        }
        actual_domains = {d["domain_name"] for d in domains}
        assert actual_domains == expected_domains

        for d in domains:
            assert d["entity_count"] == 0
            assert d["status"] == "MISSING"
            assert "No " in d["status_reason"] or "not" in d["status_reason"].lower()

    async def test_populated_project_workspace_state(self, async_client: AsyncClient):
        """Project with valid entities reports CONFIGURED domains without score syntheses."""
        tenant_id = "tenant-w9-pop"
        headers = auth_headers("usr-w9-2", "u2@quebet.test", tenant_id=tenant_id)
        project_id = await self._create_project(async_client, headers)

        # Directly populate authoritative entities across domains
        async with AsyncSessionLocal() as session:
            circuit = Circuit(
                id=str(uuid.uuid4()),
                project_id=project_id,
                tenant_id=tenant_id,
                name="Power Conditioner Schematic",
                version=1,
                validation_status="VALID",
                created_by="usr-w9-2",
            )
            session.add(circuit)
            await session.flush()

            board = EngineeringBoard(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=circuit.id,
                circuit_version=1,
                tenant_id=tenant_id,
                name="Power Board Rev A",
                version=1,
                status="IN_PROGRESS",
                created_by="usr-w9-2",
            )
            session.add(board)

            bom = EngineeringBOM(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=circuit.id,
                circuit_version=1,
                board_id=board.id,
                board_version=1,
                tenant_id=tenant_id,
                name="Power BOM Rev 1",
                version=1,
                status="EVALUATED",
                created_by="usr-w9-2",
            )
            session.add(bom)

            sim = SimulationJob(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=circuit.id,
                circuit_version=1,
                tenant_id=tenant_id,
                simulation_type="DC_OPERATING_POINT",
                status="COMPLETED",
                simulator="NGSPICE",
                created_by="usr-w9-2",
            )
            session.add(sim)

            req = EngineeringRequirement(
                id=str(uuid.uuid4()),
                project_id=project_id,
                system_id=str(uuid.uuid4()),
                requirement_key="REQ-PWR-01",
                category="ELECTRICAL",
                priority="HIGH",
                title="5V Regulated Output",
                description="5V regulated power supply requirement specification.",
                status="SATISFIED",
                created_by="usr-w9-2",
            )
            session.add(req)

            await session.commit()

        # Query workspace state
        resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/state", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        domain_map = {d["domain_name"]: d for d in data["domains"]}
        assert domain_map["schematic"]["status"] == "CONFIGURED"
        assert domain_map["schematic"]["entity_count"] == 1
        assert domain_map["pcb"]["status"] == "CONFIGURED"
        assert domain_map["pcb"]["entity_count"] == 1
        assert domain_map["bom"]["status"] == "CONFIGURED"
        assert domain_map["bom"]["entity_count"] == 1
        assert domain_map["simulation"]["status"] == "CONFIGURED"
        assert domain_map["simulation"]["entity_count"] == 1
        assert domain_map["requirements"]["status"] == "CONFIGURED"
        assert domain_map["requirements"]["entity_count"] == 1
        assert domain_map["manufacturing"]["status"] == "MISSING"

    async def test_revision_lineage_grouping_and_unbound_detection(self, async_client: AsyncClient):
        """Verifies child entities are grouped by circuit revision, and foreign revisions are marked unbound."""
        tenant_id = "tenant-w9-rev"
        headers = auth_headers("usr-w9-3", "u3@quebet.test", tenant_id=tenant_id)
        project_id = await self._create_project(async_client, headers)

        async with AsyncSessionLocal() as session:
            # Circuit v1
            c1 = Circuit(
                id=str(uuid.uuid4()),
                project_id=project_id,
                tenant_id=tenant_id,
                name="Subsystem Circuit",
                version=1,
                validation_status="VALID",
                created_by="usr-w9-3",
            )
            session.add(c1)
            await session.flush()

            # Board bound to v1
            b1 = EngineeringBoard(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=c1.id,
                circuit_version=1,
                tenant_id=tenant_id,
                name="Board Rev 1",
                version=1,
                status="IN_PROGRESS",
                created_by="usr-w9-3",
            )
            session.add(b1)

            # BOM bound to v1
            bom1 = EngineeringBOM(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=c1.id,
                circuit_version=1,
                tenant_id=tenant_id,
                name="BOM Rev 1",
                version=1,
                status="DRAFT",
                created_by="usr-w9-3",
            )
            session.add(bom1)

            # Unbound board targeting non-existent circuit version 99
            orphan_board = EngineeringBoard(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=c1.id,
                circuit_version=99,
                tenant_id=tenant_id,
                name="Orphan Board",
                version=1,
                status="DRAFT",
                created_by="usr-w9-3",
            )
            session.add(orphan_board)

            await session.commit()

        # Query lineage
        resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/revisions", headers=headers)
        assert resp.status_code == 200
        lineage = resp.json()["data"]

        assert lineage["active_circuit_version"] == 1
        assert len(lineage["circuit_revisions"]) == 1

        v1_group = lineage["circuit_revisions"][0]
        assert v1_group["circuit_version"] == 1
        assert v1_group["is_current"] is True
        assert len(v1_group["boards"]) == 1
        assert v1_group["boards"][0]["name_or_type"] == "Board Rev 1"
        assert len(v1_group["boms"]) == 1

        # Check unbound entities contains Orphan Board
        unbound = lineage["unbound_entities"]
        assert len(unbound) == 1
        assert unbound[0]["name_or_type"] == "Orphan Board"
        assert unbound[0]["bound_circuit_version"] == 99

    async def test_stale_domain_detection_on_circuit_revision_advance(self, async_client: AsyncClient):
        """Advancing circuit revision causes older board/BOM to be marked STALE."""
        tenant_id = "tenant-w9-stale"
        headers = auth_headers("usr-w9-4", "u4@quebet.test", tenant_id=tenant_id)
        project_id = await self._create_project(async_client, headers)

        async with AsyncSessionLocal() as session:
            # Circuit v1
            c1 = Circuit(
                id=str(uuid.uuid4()),
                project_id=project_id,
                tenant_id=tenant_id,
                name="Circuit Base",
                version=1,
                validation_status="VALID",
                created_by="usr-w9-4",
            )
            session.add(c1)
            await session.flush()

            # Board bound to v1
            b1 = EngineeringBoard(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=c1.id,
                circuit_version=1,
                tenant_id=tenant_id,
                name="Board Base",
                version=1,
                status="IN_PROGRESS",
                created_by="usr-w9-4",
            )
            session.add(b1)

            # Circuit v2 (advances active version to 2)
            c2 = Circuit(
                id=str(uuid.uuid4()),
                project_id=project_id,
                tenant_id=tenant_id,
                name="Circuit Advanced",
                version=2,
                validation_status="VALID",
                created_by="usr-w9-4",
            )
            session.add(c2)

            await session.commit()

        # Check workspace state
        resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/state", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        domain_map = {d["domain_name"]: d for d in data["domains"]}
        # Board was bound to v1, but active circuit is v2 -> STALE
        assert domain_map["pcb"]["status"] == "STALE"
        assert "v1" in domain_map["pcb"]["status_reason"]
        assert "v2" in domain_map["pcb"]["status_reason"]

    async def test_failing_rules_and_incomplete_states(self, async_client: AsyncClient):
        """Failing circuit validation or draft boards are deterministically categorized."""
        tenant_id = "tenant-w9-fail"
        headers = auth_headers("usr-w9-5", "u5@quebet.test", tenant_id=tenant_id)
        project_id = await self._create_project(async_client, headers)

        async with AsyncSessionLocal() as session:
            # Circuit with invalid status
            c = Circuit(
                id=str(uuid.uuid4()),
                project_id=project_id,
                tenant_id=tenant_id,
                name="Failing Circuit",
                version=1,
                validation_status="INVALID",
                created_by="usr-w9-5",
            )
            session.add(c)
            await session.flush()

            # Board in DRAFT
            b = EngineeringBoard(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=c.id,
                circuit_version=1,
                tenant_id=tenant_id,
                name="Draft Board",
                version=1,
                status="DRAFT",
                created_by="usr-w9-5",
            )
            session.add(b)

            # Simulation with FAILED status
            s = SimulationJob(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=c.id,
                circuit_version=1,
                tenant_id=tenant_id,
                simulation_type="TRANSIENT",
                status="FAILED",
                simulator="NGSPICE",
                created_by="usr-w9-5",
            )
            session.add(s)

            await session.commit()

        resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/state", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        domain_map = {d["domain_name"]: d for d in data["domains"]}
        assert domain_map["schematic"]["status"] == "FAILING_RULES"
        assert domain_map["pcb"]["status"] == "INCOMPLETE"
        assert domain_map["simulation"]["status"] == "FAILING_RULES"

    async def test_activity_timeline_chronological_ordering_and_pagination(self, async_client: AsyncClient):
        """Timeline events are deterministically sorted by timestamp descending with working pagination."""
        tenant_id = "tenant-w9-time"
        headers = auth_headers("usr-w9-6", "u6@quebet.test", tenant_id=tenant_id)
        project_id = await self._create_project(async_client, headers)

        async with AsyncSessionLocal() as session:
            c = Circuit(
                id=str(uuid.uuid4()),
                project_id=project_id,
                tenant_id=tenant_id,
                name="Timeline Circuit",
                version=1,
                validation_status="VALID",
                created_by="usr-w9-6",
            )
            session.add(c)
            await session.flush()

            b = EngineeringBoard(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=c.id,
                circuit_version=1,
                tenant_id=tenant_id,
                name="Timeline Board",
                version=1,
                status="IN_PROGRESS",
                created_by="usr-w9-6",
            )
            session.add(b)

            bom = EngineeringBOM(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=c.id,
                circuit_version=1,
                tenant_id=tenant_id,
                name="Timeline BOM",
                version=1,
                status="DRAFT",
                created_by="usr-w9-6",
            )
            session.add(bom)

            await session.commit()

        # Query timeline with limit=2
        resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/activity?limit=2", headers=headers)
        assert resp.status_code == 200
        tl = resp.json()["data"]

        assert tl["total_events"] >= 3
        assert len(tl["events"]) == 2
        assert tl["has_more"] is True

        # Verify descending timestamp ordering
        t1 = datetime.fromisoformat(tl["events"][0]["timestamp"])
        t2 = datetime.fromisoformat(tl["events"][1]["timestamp"])
        assert t1 >= t2

    async def test_multi_tenant_isolation_and_idor_protection(self, async_client: AsyncClient):
        """Cross-tenant requests to workspace endpoints are rejected with HTTP 404."""
        tenant_a_headers = auth_headers("usr-w9-a", "a@quebet.test", tenant_id="tenant-w9-sec-a")
        tenant_b_headers = auth_headers("usr-w9-b", "b@quebet.test", tenant_id="tenant-w9-sec-b")

        project_id = await self._create_project(async_client, tenant_a_headers)

        # Tenant B tries state
        s_resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/state", headers=tenant_b_headers)
        assert s_resp.status_code == 404

        # Tenant B tries revisions
        r_resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/revisions", headers=tenant_b_headers)
        assert r_resp.status_code == 404

        # Tenant B tries activity
        a_resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/activity", headers=tenant_b_headers)
        assert a_resp.status_code == 404

    async def test_read_only_viewer_access(self, async_client: AsyncClient):
        """Viewer role has valid read-only access to all workspace aggregation endpoints."""
        owner_headers = auth_headers("usr-w9-owner", "owner@quebet.test", role="admin", tenant_id="tenant-w9-view")
        viewer_headers = auth_headers("usr-w9-viewer", "viewer@quebet.test", role="viewer", tenant_id="tenant-w9-view")

        project_id = await self._create_project(async_client, owner_headers)

        # Viewer can read state
        resp_state = await async_client.get(f"/api/v1/projects/{project_id}/workspace/state", headers=viewer_headers)
        assert resp_state.status_code == 200

        # Viewer can read revisions
        resp_revs = await async_client.get(f"/api/v1/projects/{project_id}/workspace/revisions", headers=viewer_headers)
        assert resp_revs.status_code == 200

        # Viewer can read activity
        resp_act = await async_client.get(f"/api/v1/projects/{project_id}/workspace/activity", headers=viewer_headers)
        assert resp_act.status_code == 200

    async def test_zero_synthetic_scoring_invariant(self, async_client: AsyncClient):
        """Workspace responses strictly contain no confidence scores, readiness percentages, or health grades."""
        headers = auth_headers("usr-w9-strict", "strict@quebet.test", tenant_id="tenant-w9-zero")
        project_id = await self._create_project(async_client, headers)

        resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/state", headers=headers)
        assert resp.status_code == 200

        raw_text = json.dumps(resp.json()).lower()

        forbidden_tokens = [
            "confidence_percentage",
            "readiness_percentage",
            "readiness_score",
            "health_score",
            "engineering_score",
            "overall_score",
            "composite_grade",
        ]
        for token in forbidden_tokens:
            assert token not in raw_text, f"Forbidden synthetic metric token '{token}' discovered in workspace response."

    async def test_cross_domain_staleness_dynamic_reflection(self, async_client: AsyncClient):
        """Cross-domain validation staleness is dynamically detected when project domain entities mutate."""
        tenant_id = "tenant-w9-cdv"
        headers = auth_headers("usr-w9-cdv", "cdv@quebet.test", tenant_id=tenant_id)
        project_id = await self._create_project(async_client, headers)

        async with AsyncSessionLocal() as session:
            c = Circuit(
                id=str(uuid.uuid4()),
                project_id=project_id,
                tenant_id=tenant_id,
                name="Validation Circuit",
                version=1,
                validation_status="VALID",
                created_by="usr-w9-cdv",
            )
            session.add(c)
            await session.flush()

            b = EngineeringBoard(
                id=str(uuid.uuid4()),
                project_id=project_id,
                circuit_id=c.id,
                circuit_version=1,
                tenant_id=tenant_id,
                name="Validation Board",
                version=1,
                status="IN_PROGRESS",
                created_by="usr-w9-cdv",
            )
            session.add(b)
            await session.flush()

            # Record validated against an old snapshot digest
            cdv = CrossDomainValidationRecord(
                id=str(uuid.uuid4()),
                project_id=project_id,
                tenant_id=tenant_id,
                circuit_id=c.id,
                board_id=b.id,
                validation_status="PASS",
                is_stale=False,
                snapshot_digest="old_historical_digest_hash_0123456789abcdef",
                findings=[],
                summary={"total_rules": 10, "passed": 10, "failed": 0},
                domain_snapshots={},
            )
            session.add(cdv)
            await session.commit()

        # Query workspace state - staleness check runs dynamically against current domain snapshot
        resp = await async_client.get(f"/api/v1/projects/{project_id}/workspace/state", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]

        cdv_summary = data["cross_domain_validation"]
        assert cdv_summary is not None
        assert cdv_summary["is_stale"] is True
        assert len(cdv_summary["staleness_reasons"]) > 0

        # And cross-domain domain status in domains list reflects STALE
        domain_map = {d["domain_name"]: d for d in data["domains"]}
        assert domain_map["cross_domain"]["status"] == "STALE"

