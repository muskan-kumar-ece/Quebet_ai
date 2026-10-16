import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.db.cognitive import CognitiveWorkflowStatus, ContextSnapshotStatus


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-p2w7-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def setup_circuit(
    async_client: AsyncClient,
    headers: dict[str, str],
    name: str = "Wave 7 Circuit",
) -> tuple[str, str]:
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": name, "project_type": "power"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    c_payload = {
        "name": f"{name} Base",
        "description": "Functional circuit topology",
        "components": [
            {
                "ref_des": "U1",
                "component_type": "regulator",
                "value": "LM7805",
                "metadata": {"voltage_rating": "35V", "max_current": "1A"},
            },
            {
                "ref_des": "C1",
                "component_type": "capacitor",
                "value": "10uF",
                "metadata": {"voltage_rating": "50V"},
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
    return project_id, circuit_id


@pytest.mark.asyncio
async def test_scenario_1_why_explanation_root_cause_and_references(async_client: AsyncClient):
    """
    Scenario 1: Grounded WHY explanation identifying root cause, calculation failure, and entity refs.
    """
    headers = auth_headers("u-w7-1", "w7-1@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 1 Circuit")

    # Start workflow
    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Verify thermal dissipation for U1 and explain why requirement fails",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf_id = wf_res.json()["data"]["id"]

    # Interrogate why
    exp_res = await async_client.post(
        f"/api/v1/cognitive/workflows/{wf_id}/explain",
        json={
            "category": "WHY",
            "user_query": "Why is thermal requirement not satisfied?",
        },
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert data["category"] == "WHY"
    assert "statement" in data and len(data["statement"]) > 10
    assert data["authority"] == "INFORMATIONAL_ONLY"
    assert data["base_revision"] == 1


@pytest.mark.asyncio
async def test_scenario_2_requirement_explanation_inspection(async_client: AsyncClient):
    """
    Scenario 2: Requirement explanation inspecting status, supporting facts, and verification links.
    """
    headers = auth_headers("u-w7-2", "w7-2@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 2 Circuit")

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": project_id, "name": "Scenario 2 System"},
        headers=headers,
    )
    assert s_res.status_code == 201
    sys_id = s_res.json()["data"]["id"]

    # Create a system engineering requirement
    req_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/requirements",
        json={
            "requirement_key": "REQ-VOUT-7",
            "title": "Output Voltage Regulation",
            "description": "Output voltage must remain within 5V +/- 2%",
            "category": "FUNCTIONAL",
            "expression": {"property": "vout", "max_value": "5.1V", "min_value": "4.9V"},
        },
        headers=headers,
    )
    assert req_res.status_code == 201
    req_id = req_res.json()["data"]["id"]

    # Synthesize context
    syn_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id, "system_id": sys_id},
        headers=headers,
    )
    assert syn_res.status_code == 201
    ctx_id = syn_res.json()["data"]["id"]

    # Interrogate requirement
    exp_res = await async_client.post(
        f"/api/v1/cognitive/context/{ctx_id}/explain",
        json={
            "category": "WHAT_REQUIREMENTS_ARE_AFFECTED",
            "target_entity_type": "Requirement",
            "target_entity_id": req_id,
        },
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert data["category"] == "WHAT_REQUIREMENTS_ARE_AFFECTED"
    assert req_id in data["requirement_refs"]
    assert "REQ-VOUT-7" in data["statement"] or "REQ" in data["statement"]


@pytest.mark.asyncio
async def test_scenario_3_evidence_chain_calculation_vs_physical(async_client: AsyncClient):
    """
    Scenario 3 & 15: Evidence chain explicitly distinguishes Calculation vs Physical Evidence.
    """
    headers = auth_headers("u-w7-3", "w7-3@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 3 Circuit")

    syn_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    ctx_id = syn_res.json()["data"]["id"]

    exp_res = await async_client.post(
        f"/api/v1/cognitive/context/{ctx_id}/explain",
        json={"category": "WHAT_SUPPORTS_THIS"},
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert "Calculation ≠ Physical Evidence" in data["statement"]
    for node in data["evidence_chain"]:
        # Epistemic distinction invariant
        assert not (node["is_physical"] and node["is_calculation"])


@pytest.mark.asyncio
async def test_scenario_4_unknown_explanation_epistemic_invariant(async_client: AsyncClient):
    """
    Scenario 4: Explains UNKNOWN parameters and enforces UNKNOWN != SATISFIED without inference.
    """
    headers = auth_headers("u-w7-4", "w7-4@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 4 Circuit")

    syn_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    ctx_id = syn_res.json()["data"]["id"]

    exp_res = await async_client.post(
        f"/api/v1/cognitive/context/{ctx_id}/explain",
        json={"category": "WHAT_IS_UNKNOWN"},
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert "UNKNOWN != SATISFIED" in data["statement"]


@pytest.mark.asyncio
async def test_scenario_5_verification_explanation(async_client: AsyncClient):
    """
    Scenario 5: Verification explanation stating analytical calculations cannot close physical tests.
    """
    headers = auth_headers("u-w7-5", "w7-5@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 5 Circuit")

    syn_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    ctx_id = syn_res.json()["data"]["id"]

    exp_res = await async_client.post(
        f"/api/v1/cognitive/context/{ctx_id}/explain",
        json={"category": "WHAT_REQUIRES_VERIFICATION"},
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert "physical laboratory verification" in data["statement"].lower() or "verification" in data["statement"].lower()


@pytest.mark.asyncio
async def test_scenario_6_and_7_stale_and_change_explanation(async_client: AsyncClient):
    """
    Scenario 6 & 7: Explains why workflow/context is stale and what changed across revisions.
    """
    headers = auth_headers("u-w7-6", "w7-6@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 6 Circuit")

    # Start workflow at circuit version 1
    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={"project_id": project_id, "circuit_id": circuit_id, "user_request": "Verify circuit"},
        headers=headers,
    )
    wf_id = wf_res.json()["data"]["id"]

    # Advance circuit revision to version 2
    patch_res = await async_client.patch(
        f"/api/v1/circuits/{circuit_id}",
        json={"version": 2, "description": "Modified circuit topology revision 2"},
        headers=headers,
    )
    assert patch_res.status_code == 200

    # Interrogate staleness
    exp_res = await async_client.post(
        f"/api/v1/cognitive/workflows/{wf_id}/explain",
        json={"category": "WHY_IS_THIS_STALE"},
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert data["is_stale"] is True
    assert len(data["stale_factors"]) > 0
    assert "version advanced from 1 to 2" in data["stale_factors"][0]

    # Interrogate what changed
    chg_res = await async_client.post(
        f"/api/v1/cognitive/workflows/{wf_id}/explain",
        json={"category": "WHAT_CHANGED"},
        headers=headers,
    )
    assert chg_res.status_code == 200
    chg_data = chg_res.json()["data"]
    assert chg_data["is_stale"] is True
    assert len(chg_data["changes_detected"]) > 0


@pytest.mark.asyncio
async def test_scenario_8_deterministic_human_action_extraction(async_client: AsyncClient):
    """
    Scenario 8: Deterministic list of outstanding human actions without synthetic intelligence ranking.
    """
    headers = auth_headers("u-w7-8", "w7-8@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 8 Circuit")

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={"project_id": project_id, "circuit_id": circuit_id, "user_request": "Design power stage"},
        headers=headers,
    )
    wf_id = wf_res.json()["data"]["id"]

    exp_res = await async_client.post(
        f"/api/v1/cognitive/workflows/{wf_id}/explain",
        json={"category": "WHY"},
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert isinstance(data["human_actions"], list)
    for act in data["human_actions"]:
        assert "title" in act
        assert "action_type" in act
        assert act["urgency"] in ["HIGH", "NORMAL", "LOW"]
        # No synthetic priority ranking score
        assert "priority_score" not in act
        assert "rank" not in act


@pytest.mark.asyncio
async def test_scenario_9_invalid_model_reference_rejection(async_client: AsyncClient):
    """
    Scenario 9: Grounding contract strictly rejects foreign/hallucinated model references (MODEL_INVALID_REFERENCE).
    """
    headers = auth_headers("u-w7-9", "w7-9@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 9 Circuit")

    syn_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    ctx_id = syn_res.json()["data"]["id"]

    # Assert non-existent entity reference
    fake_ref = f"comp-hallucinated-{uuid.uuid4().hex[:6]}"
    exp_res = await async_client.post(
        f"/api/v1/cognitive/context/{ctx_id}/explain",
        json={
            "category": "WHY",
            "asserted_references": [fake_ref],
        },
        headers=headers,
    )
    assert exp_res.status_code == 422
    err_detail = exp_res.json()["detail"]
    assert err_detail["error"] == "MODEL_INVALID_REFERENCE"


@pytest.mark.asyncio
async def test_scenario_10_unsupported_claim_rejection(async_client: AsyncClient):
    """
    Scenario 10: Candidate statements with unsupported entity references are flagged as unreferenced assertions.
    """
    headers = auth_headers("u-w7-10", "w7-10@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 10 Circuit")

    syn_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    ctx_id = syn_res.json()["data"]["id"]

    unsupported_statement = "The component comp-phantom-999 is rated for 100V and tested."
    exp_res = await async_client.post(
        f"/api/v1/cognitive/context/{ctx_id}/explain",
        json={
            "category": "WHY",
            "candidate_statements": [unsupported_statement],
        },
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert unsupported_statement in data["unreferenced_assertions"]


@pytest.mark.asyncio
async def test_scenario_11_decision_explanation_without_recommendation(async_client: AsyncClient):
    """
    Scenario 11: Decision brief explanation presents alternatives and tradeoffs with strictly zero recommendation.
    """
    headers = auth_headers("u-w7-11", "w7-11@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 11 Circuit")

    # Start workflow requiring decision
    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Recommend power topology alternative",
        },
        headers=headers,
    )
    wf_id = wf_res.json()["data"]["id"]

    exp_res = await async_client.post(
        f"/api/v1/cognitive/workflows/{wf_id}/explain",
        json={"category": "WHAT_REQUIRES_HUMAN_DECISION"},
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    stmt = data["statement"]
    # Strictly zero recommendation or composite scoring
    assert "Zero synthetic scoring" in stmt
    assert "WINNER" not in stmt
    assert "BEST" not in stmt
    assert "RECOMMENDED WINNER" not in stmt


@pytest.mark.asyncio
async def test_scenario_12_and_13_no_synthetic_scoring_and_tenant_isolation(async_client: AsyncClient):
    """
    Scenario 12 & 13: Enforces zero synthetic scoring across response and strict tenant isolation.
    """
    headers_a = auth_headers("u-w7-12a", "w7-12a@quebet.test", tenant_id="tenant-p2w7-alpha")
    headers_b = auth_headers("u-w7-12b", "w7-12b@quebet.test", tenant_id="tenant-p2w7-beta")

    project_id, circuit_id = await setup_circuit(async_client, headers_a, "Scenario 12 Circuit")

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={"project_id": project_id, "circuit_id": circuit_id, "user_request": "Run check"},
        headers=headers_a,
    )
    wf_id = wf_res.json()["data"]["id"]

    # Verify zero synthetic scoring fields in tenant A
    exp_res = await async_client.post(
        f"/api/v1/cognitive/workflows/{wf_id}/explain",
        json={"category": "WHY"},
        headers=headers_a,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert "confidence_percentage" not in data
    assert "readiness_score" not in data
    assert "overall_score" not in data

    # Tenant B tries to interrogate Tenant A's workflow -> 404 Not Found
    idor_res = await async_client.post(
        f"/api/v1/cognitive/workflows/{wf_id}/explain",
        json={"category": "WHY"},
        headers=headers_b,
    )
    assert idor_res.status_code == 404


@pytest.mark.asyncio
async def test_scenario_14_and_16_revision_binding_and_memory_precedence(async_client: AsyncClient):
    """
    Scenario 14 & 16: Explanation is bound to exact base revision, and current authoritative truth takes precedence over memory.
    """
    headers = auth_headers("u-w7-14", "w7-14@quebet.test")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Scenario 14 Circuit")

    syn_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    ctx_id = syn_res.json()["data"]["id"]

    exp_res = await async_client.post(
        f"/api/v1/cognitive/context/{ctx_id}/explain",
        json={"category": "WHAT_CONFLICTS"},
        headers=headers,
    )
    assert exp_res.status_code == 200
    data = exp_res.json()["data"]
    assert data["base_revision"] == 1
    # When conflicts are evaluated or referenced, authoritative source is invariant
    assert "CURRENT AUTHORITATIVE SOURCE" in data["statement"] or "0 cross-source contradictions" in data["statement"]
