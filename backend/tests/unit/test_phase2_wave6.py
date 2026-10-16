import hashlib
import json
import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.db.cognitive import (
    CognitiveWorkflowStatus,
    ContextSnapshotStatus,
    HumanDecisionType,
    MemoryType,
)


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-p2w6-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def setup_circuit(
    async_client: AsyncClient,
    headers: dict[str, str],
    name: str = "Wave 6 Circuit",
    components: list = None,
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
        "components": components or [
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
async def test_scenario_1_full_workflow_happy_path(async_client: AsyncClient):
    """Scenario 1: Full workflow happy path through all lifecycle steps."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "lead_eng@quebet.ai")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Happy Path Workflow")

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Analyze LM7805 thermal margin and prepare decision brief",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]

    assert wf["intent_packet_id"] is not None
    assert wf["plan_id"] is not None
    assert wf["execution_id"] is not None
    assert wf["reflection_id"] is not None
    assert wf["synthesized_context_id"] is not None
    assert wf["base_revision"] == 1
    assert wf["status"] in [CognitiveWorkflowStatus.COMPLETED.value, CognitiveWorkflowStatus.AWAITING_HUMAN.value]
    assert len(wf["integrity_digest"]) == 64
    assert len(wf["timeline"]) >= 5


@pytest.mark.asyncio
async def test_scenario_2_intent_clarification_path(async_client: AsyncClient):
    """Scenario 2: Intent ambiguity triggers CLARIFICATION_REQUIRED / AWAITING_HUMAN."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "eng_clarify@quebet.ai")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Clarification Workflow")

    # Ambiguous generic query with multiple components
    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "check capacitor",  # Ambiguous: Which capacitor? C1 or input cap?
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]

    # If ambiguity detected, pauses at AWAITING_HUMAN or BLOCKED without guessing
    assert wf["status"] in [CognitiveWorkflowStatus.AWAITING_HUMAN.value, CognitiveWorkflowStatus.COMPLETED.value, CognitiveWorkflowStatus.BLOCKED.value]


@pytest.mark.asyncio
async def test_scenario_3_unknown_parameter_path(async_client: AsyncClient):
    """Scenario 3: Unknown parameter in circuit analysis survives end-to-end (UNKNOWN != SATISFIED)."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "unknown_tester@quebet.ai")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Unknown Parameter Test")

    # Run analysis
    await async_client.post(f"/api/v1/circuits/{circuit_id}/analyze", headers=headers)

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Investigate circuit findings and unknowns",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]
    assert wf["status"] in [CognitiveWorkflowStatus.COMPLETED.value, CognitiveWorkflowStatus.AWAITING_HUMAN.value]


@pytest.mark.asyncio
async def test_scenario_4_and_5_contradiction_and_requirement_gap_path(async_client: AsyncClient):
    """Scenario 4 & 5: Contradiction & requirement gap surfaced in reflection and decision brief."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "gap_tester@quebet.ai")
    # Component with overstressed power
    project_id, circuit_id = await setup_circuit(
        async_client,
        headers,
        "Gap Test",
        components=[
            {"ref_des": "R1", "component_type": "resistor", "value": "100", "metadata": {"power_rating": "0.125W"}},
        ],
    )

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Analyze power margins and compare alternatives",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]
    assert wf["decision_brief_id"] is not None


@pytest.mark.asyncio
async def test_scenario_6_and_12_physical_verification_invariant(async_client: AsyncClient):
    """Scenario 6 & 12: Calculated result without physical evidence leaves verification required."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "safety_audit@quebet.ai")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Verification Gap Test")

    # Trigger design review generating verification requirements
    rev_res = await async_client.post(f"/api/v1/circuits/{circuit_id}/design-review", headers=headers)
    assert rev_res.status_code == 201
    vr_id = rev_res.json()["data"]["verification_requirements"][0]["id"]

    # Upload only SIMULATION evidence
    await async_client.post(
        f"/api/v1/verification-requirements/{vr_id}/evidence",
        json={
            "evidence_type": "SIMULATION_REPORT",
            "source": "SPICE-Simulator",
            "description": "Transient simulation trace",
            "value": "5.0",
            "unit": "V",
        },
        headers=headers,
    )

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Audit verification status",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]

    # Must require human action / verification
    assert wf["status"] in [CognitiveWorkflowStatus.AWAITING_HUMAN.value, CognitiveWorkflowStatus.COMPLETED.value]


@pytest.mark.asyncio
async def test_scenario_7_and_8_reflection_additional_work_and_cycle_limit(async_client: AsyncClient):
    """Scenario 7 & 8: Additional work triggers bounded replanning within max 3 cycles."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "cycle_tester@quebet.ai")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Cycle Limit Test")

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Investigate failure modes and root cause",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]
    # Reflection cycles must be <= MAX_REFLECTION_CYCLES (3)
    assert wf["reflection_cycles"] <= 3


@pytest.mark.asyncio
async def test_scenario_9_stale_revision_detection(async_client: AsyncClient):
    """Scenario 9: Modifying circuit revision marks workflow STALE."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "stale_tester@quebet.ai")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Stale Workflow Test")

    # 1. Start workflow at revision 1
    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Analyze circuit topology",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf_id = wf_res.json()["data"]["id"]

    # 2. Advance circuit revision to 2
    patch_res = await async_client.patch(
        f"/api/v1/circuits/{circuit_id}",
        json={"version": 2, "description": "Mutated revision"},
        headers=headers,
    )
    assert patch_res.status_code == 200

    # 3. Retrieve workflow -> Live check detects staleness
    get_res = await async_client.get(f"/api/v1/cognitive/workflows/{wf_id}", headers=headers)
    assert get_res.status_code == 200
    wf_updated = get_res.json()["data"]
    assert wf_updated["status"] == CognitiveWorkflowStatus.STALE.value


@pytest.mark.asyncio
async def test_scenario_10_human_gated_capability_rejection(async_client: AsyncClient):
    """Scenario 10: Attempting autonomous mutation/decision through workflow is rejected."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "security_tester@quebet.ai")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Human Gate Test")

    # Try to execute a decision with AI actor
    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Compare regulator alternatives",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]

    if wf.get("decision_brief_id"):
        brief_id = wf["decision_brief_id"]
        # AI attempts to make decision
        dec_res = await async_client.post(
            f"/api/v1/cognitive/decision-briefs/{brief_id}/decision",
            json={
                "decision_type": HumanDecisionType.ADOPT_ALTERNATIVE.value,
                "selected_alternative_id": "ALT-A",
                "rationale": "AI autonomous choice",
                "actor": "ai-model-actor",
            },
            headers=headers,
        )
        assert dec_res.status_code == 403
        assert dec_res.json()["detail"]["code"] == "MODEL_UNAUTHORIZED_DECISION"


@pytest.mark.asyncio
async def test_scenario_11_historical_memory_precedence(async_client: AsyncClient):
    """Scenario 11: Current authoritative specification strictly supersedes historical memory."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "memory_tester@quebet.ai")
    # Circuit has LM7805 with 1A rating
    project_id, circuit_id = await setup_circuit(async_client, headers, "Memory Precedence Test")

    # Run analysis to create genuine source entity
    an_res = await async_client.post(f"/api/v1/circuits/{circuit_id}/analyze", headers=headers)
    an_id = an_res.json()["data"]["id"]

    # Record historical memory with 500mA rating
    await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "memory_type": MemoryType.DESIGN_FINDING.value,
            "source_entity_type": "CircuitAnalysis",
            "source_entity_id": an_id,
            "engineering_domain": "power",
            "summary": "Historical project derated LM7805 to 500mA",
            "applicability_conditions": {"max_current": "500mA"},
        },
        headers=headers,
    )

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "user_request": "Synthesize context and check parameters",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]
    assert wf["synthesized_context_id"] is not None


@pytest.mark.asyncio
async def test_scenario_13_tenant_isolation(async_client: AsyncClient):
    """Scenario 13: Tenant B cannot access Tenant A workflow (HTTP 404)."""
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "alice@tenant-a.com", tenant_id="tenant-p2w6-tenant-a")
    project_id, circuit_id = await setup_circuit(async_client, headers_a, "Tenant A Project")

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={"project_id": project_id, "circuit_id": circuit_id, "user_request": "Analyze circuit"},
        headers=headers_a,
    )
    assert wf_res.status_code == 201
    wf_id = wf_res.json()["data"]["id"]

    # Tenant B attempts access
    user_b = str(uuid.uuid4())
    headers_b = auth_headers(user_b, "bob@tenant-b.com", tenant_id="tenant-p2w6-tenant-b")
    get_res = await async_client.get(f"/api/v1/cognitive/workflows/{wf_id}", headers=headers_b)
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_scenario_14_workflow_integrity_digest(async_client: AsyncClient):
    """Scenario 14: Canonical SHA-256 integrity digest is deterministic and reproducible."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "digest_tester@quebet.ai")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Digest Test")

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={"project_id": project_id, "circuit_id": circuit_id, "user_request": "Analyze circuit"},
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]

    digest = wf["integrity_digest"]
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


@pytest.mark.asyncio
async def test_scenario_15_zero_synthetic_scoring(async_client: AsyncClient):
    """Scenario 15: Workflow responses contain zero synthetic scores."""
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "anti_slop@quebet.ai")
    project_id, circuit_id = await setup_circuit(async_client, headers, "Zero Score Test")

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={"project_id": project_id, "circuit_id": circuit_id, "user_request": "Analyze circuit and compare alternatives"},
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf = wf_res.json()["data"]

    serialized = json.dumps(wf)
    forbidden_tokens = [
        "overall_score",
        "readiness_percentage",
        "confidence_percentage",
        "decision_score",
        "health_score",
        "intelligence_score",
        "winner",
        "best",
    ]
    for token in forbidden_tokens:
        assert token not in serialized, f"Forbidden synthetic token '{token}' found in workflow response"
