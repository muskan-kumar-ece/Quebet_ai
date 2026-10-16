import json
import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.core.database import AsyncSessionLocal
from app.models.db.cognitive import CognitiveWorkflowStatus, EngineeringCognitiveWorkflow
from app.models.db.verification import VerificationStatus
from app.models.db.system import EngineeringSystem
from app.models.db.decision import (
    EngineeringRequirement,
    EngineeringAssumption,
    EngineeringDecisionRecord,
    EngineeringDesignReviewSession,
    EngineeringReviewFinding,
    EngineeringReviewAction,
)
from app.models.schemas.cognitive import ActionCenterCategory, EvidenceSufficiencyStatus


def auth_headers(
    user_id: str,
    email: str,
    role: str = "engineer",
    tenant_id: str = "tenant-p2w9-a",
) -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def setup_project_circuit_review(
    async_client: AsyncClient,
    headers: dict[str, str],
    name: str = "Wave 9 Circuit",
) -> tuple[str, str, str, str]:
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": name, "project_type": "power"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    c_payload = {
        "name": f"{name} Topology",
        "description": "Functional circuit topology with power rails",
        "components": [
            {
                "ref_des": "U1",
                "component_type": "regulator",
                "value": "TPS54331",
                "metadata": {"voltage_rating": "28V", "max_current": "3A"},
            },
            {
                "ref_des": "C1",
                "component_type": "capacitor",
                "value": "22uF",
                "metadata": {"voltage_rating": "35V"},
            },
        ],
        "nets": [
            {"name": "VIN", "net_type": "power"},
            {"name": "VOUT", "net_type": "power"},
            {"name": "GND", "net_type": "ground"},
        ],
        "connections": [],
        "assumptions": [],
    }
    c_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json=c_payload,
        headers=headers,
    )
    assert c_res.status_code == 201
    circuit_id = c_res.json()["data"]["id"]

    # Trigger design review generating verification requirements
    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=headers,
    )
    assert rev_res.status_code == 201
    review_data = rev_res.json()["data"]
    review_id = review_data["id"]
    vr_id = review_data["verification_requirements"][0]["id"]

    return project_id, circuit_id, review_id, vr_id


@pytest.mark.asyncio
async def test_01_action_aggregation(async_client: AsyncClient):
    """1. Action aggregation across disparate cognitive and engineering subsystems."""
    headers = auth_headers("usr-w9-1", "usr1@test.com", tenant_id="tenant-w9-1")
    project_id, circuit_id, _, _ = await setup_project_circuit_review(
        async_client, headers, name="Agg Test Circuit"
    )

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert "actions" in data
    assert "summary" in data
    assert data["summary"]["total_actions"] >= 1
    assert data["provenance_integrity_digest"] is not None
    assert len(data["provenance_integrity_digest"]) == 64


@pytest.mark.asyncio
async def test_02_requirement_action(async_client: AsyncClient):
    """2. Requirement action surfaces violated requirements in BLOCKED category."""
    headers = auth_headers("usr-w9-2", "usr2@test.com", tenant_id="tenant-w9-2")
    project_id, circuit_id, _, _ = await setup_project_circuit_review(
        async_client, headers, name="Req Action Circuit"
    )

    async with AsyncSessionLocal() as db:
        sys_obj = EngineeringSystem(
            project_id=project_id,
            tenant_id="tenant-w9-2",
            name="Power Subsystem",
            revision=1,
            created_by="usr-w9-2",
        )
        db.add(sys_obj)
        await db.flush()

        req = EngineeringRequirement(
            project_id=project_id,
            system_id=sys_obj.id,
            tenant_id="tenant-w9-2",
            requirement_key="REQ-PWR-01",
            title="Max VOUT Ripple",
            description="Output ripple must not exceed 20mVpp",
            status="VIOLATED",
            revision=1,
            created_by="usr-w9-2",
        )
        db.add(req)
        await db.commit()

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=BLOCKED",
        headers=headers,
    )
    assert res.status_code == 200
    actions = res.json()["data"]["actions"]
    req_actions = [a for a in actions if a["source_entity_type"] == "ENGINEERING_REQUIREMENT"]
    assert len(req_actions) >= 1
    assert req_actions[0]["category"] == "BLOCKED"
    assert "VIOLATED" in req_actions[0]["current_status"]
    assert req_actions[0]["required_human_action"] is not None


@pytest.mark.asyncio
async def test_03_unknown_action(async_client: AsyncClient):
    """3. UNKNOWN action surfaces unvalidated assumptions with UNKNOWN disposition."""
    headers = auth_headers("usr-w9-3", "usr3@test.com", tenant_id="tenant-w9-3")
    project_id, circuit_id, _, _ = await setup_project_circuit_review(
        async_client, headers, name="Unknown Action Circuit"
    )

    async with AsyncSessionLocal() as db:
        sys_obj = EngineeringSystem(
            project_id=project_id,
            tenant_id="tenant-w9-3",
            name="Power Subsystem",
            revision=1,
            created_by="usr-w9-3",
        )
        db.add(sys_obj)
        await db.flush()

        asm = EngineeringAssumption(
            system_id=sys_obj.id,
            tenant_id="tenant-w9-3",
            description="Ambient operating temperature max 70C",
            basis="Preliminary requirement from field spec",
            status="UNKNOWN",
            impact="REVIEW_REQUIRED",
        )
        db.add(asm)
        await db.commit()

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=UNKNOWN",
        headers=headers,
    )
    assert res.status_code == 200
    actions = res.json()["data"]["actions"]
    unknown_actions = [a for a in actions if a["source_entity_type"] == "ENGINEERING_ASSUMPTION"]
    assert len(unknown_actions) >= 1
    assert unknown_actions[0]["category"] == "UNKNOWN"
    assert "Validate" in unknown_actions[0]["required_human_action"]


@pytest.mark.asyncio
async def test_04_finding_action(async_client: AsyncClient):
    """4. Finding action surfaces blocker review findings."""
    headers = auth_headers("usr-w9-4", "usr4@test.com", tenant_id="tenant-w9-4")
    project_id, circuit_id, review_id, _ = await setup_project_circuit_review(
        async_client, headers, name="Finding Action Circuit"
    )

    async with AsyncSessionLocal() as db:
        sys_obj = EngineeringSystem(
            project_id=project_id,
            tenant_id="tenant-w9-4",
            name="Power Subsystem",
            revision=1,
            created_by="usr-w9-4",
        )
        db.add(sys_obj)
        await db.flush()

        sess = EngineeringDesignReviewSession(
            system_id=sys_obj.id,
            tenant_id="tenant-w9-4",
            title="PDR Session",
            chairperson="Chief Architect",
            system_revision=1,
        )
        db.add(sess)
        await db.flush()

        finding = EngineeringReviewFinding(
            review_id=sess.id,
            source_analysis="ThermalSim",
            severity="BLOCKER",
            description="Inductor Saturation Current Insufficient: Peak inductor current exceeds Isat.",
        )
        db.add(finding)
        await db.commit()

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=BLOCKED",
        headers=headers,
    )
    assert res.status_code == 200
    actions = res.json()["data"]["actions"]
    finding_actions = [a for a in actions if a["source_entity_type"] == "ENGINEERING_REVIEW_FINDING"]
    assert len(finding_actions) >= 1
    assert finding_actions[0]["category"] == "BLOCKED"
    assert "BLOCKER" in finding_actions[0]["title"] or "Inductor" in finding_actions[0]["title"]


@pytest.mark.asyncio
async def test_05_evidence_action(async_client: AsyncClient):
    """5. Evidence action surfaces unverified requirements lacking physical evidence."""
    headers = auth_headers("usr-w9-5", "usr5@test.com", tenant_id="tenant-w9-5")
    project_id, circuit_id, _, vr_id = await setup_project_circuit_review(
        async_client, headers, name="Evidence Action Circuit"
    )

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=EVIDENCE",
        headers=headers,
    )
    assert res.status_code == 200
    actions = res.json()["data"]["actions"]
    evidence_actions = [a for a in actions if a["source_entity_id"] == vr_id]
    assert len(evidence_actions) >= 1
    assert evidence_actions[0]["category"] == "EVIDENCE"
    assert evidence_actions[0]["route_target"] == f"/api/v1/cognitive/verification/{vr_id}"


@pytest.mark.asyncio
async def test_06_verification_action(async_client: AsyncClient):
    """6. Verification action surfaces verification requirements ready for human closure or testing."""
    headers = auth_headers("usr-w9-6", "usr6@test.com", tenant_id="tenant-w9-6")
    project_id, circuit_id, _, vr_id = await setup_project_circuit_review(
        async_client, headers, name="Verification Action Circuit"
    )

    # Attach physical evidence so obligation moves from EVIDENCE to VERIFICATION closure state
    await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Lab DMM Rig",
            "description": "Output voltage meets spec",
            "is_physical": True,
            "instrument": "Keithley DMM6500",
            "calibration_status": "CALIBRATED",
        },
        headers=headers,
    )

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=VERIFICATION",
        headers=headers,
    )
    assert res.status_code == 200
    actions = res.json()["data"]["actions"]
    assert any(a["source_entity_id"] == vr_id for a in actions)


@pytest.mark.asyncio
async def test_07_decision_action(async_client: AsyncClient):
    """7. Decision action surfaces pending decisions."""
    headers = auth_headers("usr-w9-7", "usr7@test.com", tenant_id="tenant-w9-7")
    project_id, circuit_id, _, _ = await setup_project_circuit_review(
        async_client, headers, name="Decision Action Circuit"
    )

    async with AsyncSessionLocal() as db:
        sys_obj = EngineeringSystem(
            project_id=project_id,
            tenant_id="tenant-w9-7",
            name="Switcher Subsystem",
            revision=1,
            created_by="usr-w9-7",
        )
        db.add(sys_obj)
        await db.flush()

        dec = EngineeringDecisionRecord(
            project_id=project_id,
            system_id=sys_obj.id,
            tenant_id="tenant-w9-7",
            title="Select Switcher Topology",
            decision_key="DEC-TOP-01",
            description="Select Switcher Topology for Buck stage",
            decision_type="ARCHITECTURE",
            status="PENDING_DECISION",
            system_revision=1,
        )
        db.add(dec)
        await db.commit()

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=DECISIONS",
        headers=headers,
    )
    assert res.status_code == 200
    actions = res.json()["data"]["actions"]
    dec_actions = [a for a in actions if a["source_entity_type"] == "ENGINEERING_DECISION_RECORD"]
    assert len(dec_actions) >= 1
    assert dec_actions[0]["category"] == "DECISIONS"
    assert "/api/v1/cognitive/decision-records/" in dec_actions[0]["route_target"]


@pytest.mark.asyncio
async def test_08_review_action(async_client: AsyncClient):
    """8. Review action surfaces open review sessions and actions."""
    headers = auth_headers("usr-w9-8", "usr8@test.com", tenant_id="tenant-w9-8")
    project_id, circuit_id, review_id, _ = await setup_project_circuit_review(
        async_client, headers, name="Review Action Circuit"
    )

    async with AsyncSessionLocal() as db:
        sys_obj = EngineeringSystem(
            project_id=project_id,
            tenant_id="tenant-w9-8",
            name="Power Subsystem",
            revision=1,
            created_by="usr-w9-8",
        )
        db.add(sys_obj)
        await db.flush()

        sess = EngineeringDesignReviewSession(
            system_id=sys_obj.id,
            tenant_id="tenant-w9-8",
            title="CDR Session",
            chairperson="Chief Architect",
            system_revision=1,
        )
        db.add(sess)
        await db.flush()

        act = EngineeringReviewAction(
            review_id=sess.id,
            description="Perform EMI shielding audit for inductor L1",
            owner="usr-w9-8",
            status="OPEN",
        )
        db.add(act)
        await db.commit()

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=REVIEWS",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()["data"]
    assert "actions" in data
    assert len(data["actions"]) >= 1


@pytest.mark.asyncio
async def test_09_stale_action(async_client: AsyncClient):
    """9. Stale action surfaces stale workflows and invalidated baselines."""
    headers = auth_headers("usr-w9-9", "usr9@test.com", tenant_id="tenant-w9-9")
    project_id, circuit_id, _, _ = await setup_project_circuit_review(
        async_client, headers, name="Stale Action Circuit"
    )

    async with AsyncSessionLocal() as db:
        wf = EngineeringCognitiveWorkflow(
            project_id=project_id,
            circuit_id=circuit_id,
            tenant_id="tenant-w9-9",
            user_request="Verify loop stability",
            status=CognitiveWorkflowStatus.STALE.value,
            base_revision=1,
        )
        db.add(wf)
        await db.commit()

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=STALE",
        headers=headers,
    )
    assert res.status_code == 200
    actions = res.json()["data"]["actions"]
    stale_wfs = [a for a in actions if a["source_entity_type"] == "ENGINEERING_COGNITIVE_WORKFLOW"]
    assert len(stale_wfs) >= 1
    assert stale_wfs[0]["is_stale"] is True
    assert len(stale_wfs[0]["stale_factors"]) >= 1


@pytest.mark.asyncio
async def test_10_dependency_representation(async_client: AsyncClient):
    """10. Dependency representation correctly links blocking_reason and depends_on."""
    headers = auth_headers("usr-w9-10", "usr10@test.com", tenant_id="tenant-w9-10")
    project_id, circuit_id, review_id, _ = await setup_project_circuit_review(
        async_client, headers, name="Dep Rep Circuit"
    )

    async with AsyncSessionLocal() as db:
        sys_obj = EngineeringSystem(
            project_id=project_id,
            tenant_id="tenant-w9-10",
            name="Power Subsystem",
            revision=1,
            created_by="usr-w9-10",
        )
        db.add(sys_obj)
        await db.flush()

        sess = EngineeringDesignReviewSession(
            system_id=sys_obj.id,
            tenant_id="tenant-w9-10",
            title="CDR Session",
            chairperson="Chief Architect",
            system_revision=1,
        )
        db.add(sess)
        await db.flush()

        finding = EngineeringReviewFinding(
            review_id=sess.id,
            source_analysis="ThermalSim",
            severity="BLOCKER",
            description="FET temperature exceeds 125C rating.",
        )
        db.add(finding)
        await db.commit()

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=BLOCKED",
        headers=headers,
    )
    assert res.status_code == 200
    actions = res.json()["data"]["actions"]
    finding_actions = [a for a in actions if a["source_entity_type"] == "ENGINEERING_REVIEW_FINDING"]
    assert len(finding_actions) >= 1
    assert finding_actions[0]["blocking_reason"] is not None
    assert finding_actions[0]["depends_on"] == [sess.id]


@pytest.mark.asyncio
async def test_11_action_source_traceability(async_client: AsyncClient):
    """11. Action source traceability retrieves individual action item by entity type and ID."""
    headers = auth_headers("usr-w9-11", "usr11@test.com", tenant_id="tenant-w9-11")
    project_id, circuit_id, _, vr_id = await setup_project_circuit_review(
        async_client, headers, name="Traceability Circuit"
    )

    res = await async_client.get(
        f"/api/v1/cognitive/actions/ENGINEERING_VERIFICATION_REQUIREMENT/{vr_id}",
        headers=headers,
    )
    assert res.status_code == 200
    item = res.json()["data"]
    assert item["source_entity_id"] == vr_id
    assert item["source_entity_type"] == "ENGINEERING_VERIFICATION_REQUIREMENT"
    assert item["project_id"] == project_id
    assert item["route_target"] == f"/api/v1/cognitive/verification/{vr_id}"


@pytest.mark.asyncio
async def test_12_wave7_explanation_integration(async_client: AsyncClient):
    """12. Wave 7 explanation integration provides grounded non-authoritative explanation."""
    headers = auth_headers("usr-w9-12", "usr12@test.com", tenant_id="tenant-w9-12")
    project_id, circuit_id, _, vr_id = await setup_project_circuit_review(
        async_client, headers, name="Explain Circuit"
    )

    res = await async_client.post(
        f"/api/v1/cognitive/actions/ENGINEERING_VERIFICATION_REQUIREMENT/{vr_id}/explain",
        json={"category": "WHY"},
        headers=headers,
    )
    assert res.status_code == 200
    explanation = res.json()["data"]
    assert explanation["authority"] == "INFORMATIONAL_ONLY"
    assert "explanation" in explanation
    assert len(explanation["evidence_chain"]) >= 1
    assert vr_id in str(explanation["evidence_chain"])


@pytest.mark.asyncio
async def test_13_wave8_verification_integration(async_client: AsyncClient):
    """13. Wave 8 verification integration routes to verification workspace."""
    headers = auth_headers("usr-w9-13", "usr13@test.com", tenant_id="tenant-w9-13")
    project_id, circuit_id, _, vr_id = await setup_project_circuit_review(
        async_client, headers, name="Wave 8 Route Circuit"
    )

    res = await async_client.get(
        f"/api/v1/cognitive/actions/ENGINEERING_VERIFICATION_REQUIREMENT/{vr_id}",
        headers=headers,
    )
    assert res.status_code == 200
    route = res.json()["data"]["route_target"]
    assert route == f"/api/v1/cognitive/verification/{vr_id}"

    # Verify that the target route actually exists and responds
    vr_res = await async_client.get(route, headers=headers)
    assert vr_res.status_code == 200
    assert vr_res.json()["data"]["verification_requirement_id"] == vr_id


@pytest.mark.asyncio
async def test_14_existing_capability_policy_enforcement(async_client: AsyncClient):
    """14. Existing capability policy enforcement rejects unauthorized mutations."""
    # Ensure anonymous or missing auth cannot query Action Center
    res = await async_client.get(
        f"/api/v1/cognitive/projects/{uuid.uuid4()}/actions",
    )
    assert res.status_code in [401, 403]


@pytest.mark.asyncio
async def test_15_cross_tenant_isolation(async_client: AsyncClient):
    """15. Cross-tenant isolation blocks Tenant B from querying Tenant A's actions."""
    headers_a = auth_headers("usr-w9-15a", "usr15a@test.com", tenant_id="tenant-w9-15a")
    headers_b = auth_headers("usr-w9-15b", "usr15b@test.com", tenant_id="tenant-w9-15b")

    project_id, _, _, vr_id = await setup_project_circuit_review(
        async_client, headers_a, name="Tenant A Circuit"
    )

    # Tenant B tries to query Tenant A's project actions -> 404
    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions",
        headers=headers_b,
    )
    assert res.status_code == 404

    # Tenant B tries to query Tenant A's action item -> 404
    res_item = await async_client.get(
        f"/api/v1/cognitive/actions/ENGINEERING_VERIFICATION_REQUIREMENT/{vr_id}",
        headers=headers_b,
    )
    assert res_item.status_code == 404

    # Tenant B tries to explain Tenant A's action item -> 404
    res_exp = await async_client.post(
        f"/api/v1/cognitive/actions/ENGINEERING_VERIFICATION_REQUIREMENT/{vr_id}/explain",
        json={"category": "WHY"},
        headers=headers_b,
    )
    assert res_exp.status_code == 404


@pytest.mark.asyncio
async def test_16_revision_binding(async_client: AsyncClient):
    """16. Revision binding returns current base_revision from circuit/system."""
    headers = auth_headers("usr-w9-16", "usr16@test.com", tenant_id="tenant-w9-16")
    project_id, circuit_id, _, _ = await setup_project_circuit_review(
        async_client, headers, name="Revision Binding Circuit"
    )

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?circuit_id={circuit_id}",
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["data"]["base_revision"] >= 1


@pytest.mark.asyncio
async def test_17_no_synthetic_prioritization(async_client: AsyncClient):
    """17. No synthetic prioritization: strictly no priority_score or confidence_score."""
    headers = auth_headers("usr-w9-17", "usr17@test.com", tenant_id="tenant-w9-17")
    project_id, _, _, _ = await setup_project_circuit_review(
        async_client, headers, name="No Synthetic Circuit"
    )

    res = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions",
        headers=headers,
    )
    assert res.status_code == 200
    raw_text = res.text

    forbidden_tokens = [
        "priority_score",
        "risk_score",
        "confidence_score",
        "importance_score",
        "readiness_score",
        "AI_priority",
        "ai_priority",
        "rank_score",
    ]
    for token in forbidden_tokens:
        assert token not in raw_text, f"Forbidden synthetic score token '{token}' detected in response."


@pytest.mark.asyncio
async def test_18_no_autonomous_closure(async_client: AsyncClient):
    """18. No autonomous closure: Action Center provides no automated closure endpoint."""
    headers = auth_headers("usr-w9-18", "usr18@test.com", tenant_id="tenant-w9-18")
    project_id, _, _, vr_id = await setup_project_circuit_review(
        async_client, headers, name="No Auto Close Circuit"
    )

    # POST /api/v1/cognitive/actions/close does NOT exist (404 / 405)
    res = await async_client.post(
        f"/api/v1/cognitive/actions/ENGINEERING_VERIFICATION_REQUIREMENT/{vr_id}/close",
        headers=headers,
    )
    assert res.status_code in [404, 405]


@pytest.mark.asyncio
async def test_19_no_duplicate_source_of_truth(async_client: AsyncClient):
    """19. No duplicate source of truth: closing an obligation in Wave 8 immediately updates Action Center."""
    headers = auth_headers("usr-w9-19", "usr19@test.com", tenant_id="tenant-w9-19")
    project_id, circuit_id, _, vr_id = await setup_project_circuit_review(
        async_client, headers, name="Truth Source Circuit"
    )

    # Initially, obligation is in EVIDENCE / VERIFICATION category
    res_before = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=EVIDENCE",
        headers=headers,
    )
    assert res_before.status_code == 200
    initial_evidence_count = res_before.json()["data"]["summary"]["evidence_count"]
    assert initial_evidence_count >= 1

    # Close verification obligation via authoritative Wave 8 endpoint as human (WAIVED with reason)
    close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/close",
        json={
            "decision": "WAIVED",
            "rationale": "Authoritative qualification on identical platform.",
            "waiver_reason": "Approved exemption ECO-883 signed by Lead Engineer",
            "actor": "Lead Hardware Engineer",
            "current_revision": 1,
        },
        headers=headers,
    )
    assert close_res.status_code == 200

    # Query Action Center again immediately
    res_after = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions?category=EVIDENCE",
        headers=headers,
    )
    assert res_after.status_code == 200
    updated_evidence_count = res_after.json()["data"]["summary"]["evidence_count"]
    # Obligation is no longer an outstanding evidence action
    assert updated_evidence_count < initial_evidence_count


@pytest.mark.asyncio
async def test_20_full_action_center_integration(async_client: AsyncClient):
    """20. Full Action Center integration test end-to-end."""
    headers = auth_headers("usr-w9-20", "usr20@test.com", tenant_id="tenant-w9-20")
    project_id, circuit_id, review_id, vr_id = await setup_project_circuit_review(
        async_client, headers, name="Full Integration Circuit"
    )

    # 1. Start a cognitive workflow
    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Execute end-to-end power rail verification",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201

    # 2. Query Action Center with category ALL
    res_all = await async_client.get(
        f"/api/v1/cognitive/projects/{project_id}/actions",
        headers=headers,
    )
    assert res_all.status_code == 200
    body = res_all.json()["data"]
    assert body["project_id"] == project_id
    assert body["summary"]["total_actions"] > 0
    assert len(body["actions"]) > 0

    # 3. Fetch single action item
    first_action = body["actions"][0]
    res_item = await async_client.get(
        f"/api/v1/cognitive/actions/{first_action['source_entity_type']}/{first_action['source_entity_id']}",
        headers=headers,
    )
    assert res_item.status_code == 200
    item = res_item.json()["data"]
    assert item["action_id"] == first_action["action_id"]

    # 4. Explain action item via Wave 7 Grounded Explanation
    res_exp = await async_client.post(
        f"/api/v1/cognitive/actions/{first_action['source_entity_type']}/{first_action['source_entity_id']}/explain",
        json={"category": "WHY"},
        headers=headers,
    )
    assert res_exp.status_code == 200
    exp = res_exp.json()["data"]
    assert exp["authority"] == "INFORMATIONAL_ONLY"
    assert exp["explanation"] is not None

    # 5. Verify cryptographic digest format
    assert len(body["provenance_integrity_digest"]) == 64
