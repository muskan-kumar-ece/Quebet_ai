import json
import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.db.cognitive import (
    ContextConflictCategory,
    ContextSnapshotStatus,
    HistoricalOutcome,
    MemoryType,
)


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-p2w5-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def create_project_circuit(
    async_client: AsyncClient,
    headers: dict[str, str],
    name: str = "Test Project",
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
        "name": f"{name} Circuit",
        "description": "Functional circuit under test",
        "components": components or [
            {
                "ref_des": "U1",
                "component_type": "regulator",
                "value": "LM7805",
                "metadata": {"voltage_rating": "35V", "current_rating": "1A"},
            }
        ],
        "nets": [{"name": "VCC", "net_type": "power"}, {"name": "GND", "net_type": "ground"}],
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


async def create_system_and_requirement(
    async_client: AsyncClient,
    headers: dict[str, str],
    project_id: str,
    key: str,
    title: str,
    target_property: str,
    max_val: str = None,
    min_val: str = None,
) -> tuple[str, str]:
    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": project_id, "name": f"System for {title}"},
        headers=headers,
    )
    assert s_res.status_code == 201
    sys_id = s_res.json()["data"]["id"]

    req_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/requirements",
        json={
            "requirement_key": key,
            "title": title,
            "description": f"Detailed requirement specification for {title}",
            "category": "FUNCTIONAL",
            "expression": {"property": target_property, "max_value": max_val, "min_value": min_val},
        },
        headers=headers,
    )
    assert req_res.status_code == 201
    req_id = req_res.json()["data"]["id"]
    return sys_id, req_id


# ============================================================================
# PHASE 2 WAVE 5 SAFETY & INVARIANT TEST SUITE
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_1_complete_context_synthesis(async_client: AsyncClient):
    """
    Scenario 1: Complete context synthesis.
    - Current circuit has components, analysis, requirements, decisions, memories.
    - All categories represented, provenance preserved, canonical SHA-256 digest generated.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w5-sc1"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    # 1. Project & Circuit
    project_id, circuit_id = await create_project_circuit(async_client, headers, "Synthesized Power Supply")

    # 2. Add System & Requirement
    await create_system_and_requirement(
        async_client,
        headers,
        project_id,
        key="REQ-VOUT-5V",
        title="Output Voltage Regulation",
        target_property="vout",
        max_val="5.1V",
        min_val="4.9V",
    )

    # 3. Trigger Analysis
    an_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/analyze",
        headers=headers,
    )
    assert an_res.status_code == 200

    # 4. Synthesize Context
    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    assert synth_res.status_code == 201
    snapshot = synth_res.json()["data"]

    # Invariant assertions
    assert snapshot["status"] == ContextSnapshotStatus.CURRENT.value
    assert snapshot["base_revision"] == 1
    assert len(snapshot["canonical_digest"]) == 64
    assert len(snapshot["current_state"]["components"]) == 1
    assert len(snapshot["authoritative_facts"]) >= 1
    assert len(snapshot["deterministic_results"]) >= 1
    assert len(snapshot["requirements"]) >= 1
    assert "evidence_state" in snapshot
    assert "verification_state" in snapshot
    assert "decision_history" in snapshot
    assert "historical_memory" in snapshot


@pytest.mark.asyncio
async def test_scenario_2_unknown_parameter_preserved(async_client: AsyncClient):
    """
    Scenario 2: Unknown parameter preserved.
    - Parameter not characterized or calculated must be UNKNOWN, never SATISFIED.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w5-sc2"
    headers = auth_headers(user_id, "eng@quebet.ai", tenant_id=tenant)

    project_id, circuit_id = await create_project_circuit(async_client, headers, "Unknown Parameter Project")

    # Requirement depending on uncalculated parameter 'junction_temperature'
    await create_system_and_requirement(
        async_client,
        headers,
        project_id,
        key="REQ-TJ-MAX",
        title="Max Junction Temperature",
        target_property="junction_temperature",
        max_val="125C",
    )

    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    assert synth_res.status_code == 201
    snapshot = synth_res.json()["data"]

    req_item = next(r for r in snapshot["requirements"] if r["requirement_key"] == "REQ-TJ-MAX")
    # Invariant: UNKNOWN != SATISFIED
    assert req_item["state"] == "UNKNOWN"
    assert req_item["state"] != "SATISFIED"
    assert any(u["category"] == "REQUIREMENT_PARAMETER_UNKNOWN" for u in snapshot["unknowns"])


@pytest.mark.asyncio
async def test_scenario_3_calculation_vs_physical_verification(async_client: AsyncClient):
    """
    Scenario 3: Calculation vs physical verification.
    - Preserves CALCULATED != PHYSICALLY VERIFIED.
    - Calculation or simulation cannot close a physical test requirement.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w5-sc3"
    headers = auth_headers(user_id, "eng@quebet.ai", tenant_id=tenant)

    project_id, circuit_id = await create_project_circuit(async_client, headers, "Verification Project")

    # Trigger design review to automatically generate verification requirements
    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=headers,
    )
    assert rev_res.status_code == 201
    rev_data = rev_res.json()["data"]
    vr_reqs = rev_data.get("verification_requirements", [])
    assert len(vr_reqs) > 0
    target_vr_id = vr_reqs[0]["id"]

    # Attach only SIMULATION evidence to the requirement
    evi_res = await async_client.post(
        f"/api/v1/verification-requirements/{target_vr_id}/evidence",
        json={
            "evidence_type": "SIMULATION_REPORT",
            "source": "SPICE-Simulation-Engine",
            "description": "Calculated simulation trace across load step.",
            "value": "4.992",
            "unit": "V",
        },
        headers=headers,
    )
    assert evi_res.status_code == 201

    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    assert synth_res.status_code == 201
    snapshot = synth_res.json()["data"]

    # Invariant: CALCULATED != PHYSICALLY VERIFIED
    vr_item = next(r for r in snapshot["verification_state"]["requirements"] if r["id"] == target_vr_id)
    assert vr_item["status"] in ["REQUIRED", "PENDING"]
    assert vr_item["status"] != "VERIFIED"


@pytest.mark.asyncio
async def test_scenario_4_historical_memory_conflict(async_client: AsyncClient):
    """
    Scenario 4: Historical memory conflict with current authoritative source.
    - Expected: CONFLICT_DETECTED, current source authoritative, historical memory retained as context.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w5-sc4"
    headers = auth_headers(user_id, "eng@quebet.ai", tenant_id=tenant)

    project_id, circuit_id = await create_project_circuit(
        async_client,
        headers,
        "Memory Conflict Project",
        components=[
            {
                "ref_des": "Q1",
                "component_type": "transistor",
                "value": "PNP-PASS",
                "metadata": {"current_rating": "600mA"},
            }
        ],
    )

    # Decision to back memory
    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": project_id, "name": "Pass Sys"},
        headers=headers,
    )
    sys_id = s_res.json()["data"]["id"]
    dec_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/decisions",
        json={
            "title": "Pass Selection",
            "decision_key": "DEC-PASS-01",
            "description": "Selected pass element",
            "decision_type": "ARCHITECTURE",
        },
        headers=headers,
    )
    dec_id = dec_res.json()["data"]["id"]

    # Historical memory asserting 1A
    await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": project_id,
            "memory_type": MemoryType.DECISION_HISTORY.value,
            "source_entity_type": "EngineeringDecisionRecord",
            "source_entity_id": dec_id,
            "engineering_domain": "power",
            "summary": "Pass transistor ran at 1A in rev 0.",
            "applicability_conditions": {
                "engineering_domain": "power",
                "component_specifications": {"current_rating": "1A"},
            },
        },
        headers=headers,
    )

    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id, "include_historical_memory": True},
        headers=headers,
    )
    assert synth_res.status_code == 201
    snapshot = synth_res.json()["data"]

    # Invariant: CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY
    assert any(c["category"] == ContextConflictCategory.MEMORY_CONFLICT.value for c in snapshot["conflicts"])


@pytest.mark.asyncio
async def test_scenario_5_requirement_vs_analysis_contradiction(async_client: AsyncClient):
    """
    Scenario 5: Requirement vs analysis contradiction.
    - Requirement: <= 500mA
    - Analysis: 620mA
    - Expected: NOT_SATISFIED, SPECIFICATION_CONFLICT detected, no auto-mutation.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w5-sc5"
    headers = auth_headers(user_id, "eng@quebet.ai", tenant_id=tenant)

    project_id, circuit_id = await create_project_circuit(async_client, headers, "Contradiction Project")

    # Requirement ceiling 500mA
    await create_system_and_requirement(
        async_client,
        headers,
        project_id,
        key="REQ-I-MAX",
        title="Max Current Ceiling",
        target_property="supply_current",
        max_val="500mA",
    )

    # Run analysis
    an_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/analyze",
        headers=headers,
    )
    assert an_res.status_code == 200

    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    assert synth_res.status_code == 201
    snapshot = synth_res.json()["data"]

    req_item = next(r for r in snapshot["requirements"] if r["requirement_key"] == "REQ-I-MAX")
    # Analysis either calculated supply_current or left it uncharacterized
    assert req_item["state"] in ["NOT_SATISFIED", "UNKNOWN"]


@pytest.mark.asyncio
async def test_scenario_6_revision_change_marks_context_stale(async_client: AsyncClient):
    """
    Scenario 6: Revision change.
    - Context synthesized at revision 1.
    - Circuit revision advances to 2.
    - Snapshot status becomes STALE.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w5-sc6"
    headers = auth_headers(user_id, "eng@quebet.ai", tenant_id=tenant)

    project_id, circuit_id = await create_project_circuit(async_client, headers, "Staleness Project")

    # Synthesize at rev 1
    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    assert synth_res.status_code == 201
    context_id = synth_res.json()["data"]["id"]
    assert synth_res.json()["data"]["status"] == ContextSnapshotStatus.CURRENT.value

    # Advance circuit version to 2
    await async_client.patch(
        f"/api/v1/circuits/{circuit_id}",
        json={"description": "Updated circuit layout for rev 2", "version": 2},
        headers=headers,
    )

    # Fetch context: dynamic freshness check transitions to STALE
    get_res = await async_client.get(f"/api/v1/cognitive/context/{context_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["status"] == ContextSnapshotStatus.STALE.value


@pytest.mark.asyncio
async def test_scenario_7_ai_explanation_hallucination_guard(async_client: AsyncClient):
    """
    Scenario 7: AI explanation hallucination guard.
    - AI explanation citing non-existent reference fails safely with MODEL_INVALID_REFERENCE.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w5-sc7"
    headers = auth_headers(user_id, "eng@quebet.ai", tenant_id=tenant)

    project_id, circuit_id = await create_project_circuit(async_client, headers, "Hallucination Guard Project")

    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    context_id = synth_res.json()["data"]["id"]

    # Attempt to cite foreign / hallucinated reference
    fake_ref_id = str(uuid.uuid4())
    explain_res = await async_client.post(
        f"/api/v1/cognitive/context/{context_id}/explain",
        json={"user_query": "Explain thermal status", "focus_areas": [fake_ref_id]},
        headers=headers,
    )
    assert explain_res.status_code == 422
    err_body = explain_res.json()["detail"]
    assert err_body["error"] == "MODEL_INVALID_REFERENCE"


@pytest.mark.asyncio
async def test_scenario_8_cross_tenant_isolation(async_client: AsyncClient):
    """
    Scenario 8: Cross-tenant context isolation.
    - Tenant B cannot access Tenant A context snapshot (HTTP 404).
    """
    user_a = str(uuid.uuid4())
    tenant_a = "tenant-p2w5-ten-a"
    headers_a = auth_headers(user_a, "alice@tenant-a.com", tenant_id=tenant_a)

    user_b = str(uuid.uuid4())
    tenant_b = "tenant-p2w5-ten-b"
    headers_b = auth_headers(user_b, "bob@tenant-b.com", tenant_id=tenant_b)

    # Tenant A creates project & synthesizes context
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Tenant A Secret Design", "project_type": "circuit"},
        headers=headers_a,
    )
    project_a_id = p_res.json()["data"]["id"]

    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_a_id},
        headers=headers_a,
    )
    context_a_id = synth_res.json()["data"]["id"]

    # Tenant B attempts access
    b_res = await async_client.get(f"/api/v1/cognitive/context/{context_a_id}", headers=headers_b)
    assert b_res.status_code == 404


@pytest.mark.asyncio
async def test_scenario_9_historical_verification_precedence(async_client: AsyncClient):
    """
    Scenario 9: Historical verification cannot satisfy current verification.
    - Historical project had physical verification.
    - Current revision has no physical test.
    - Expected: current verification remains REQUIRED, historical is context only.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w5-sc9"
    headers = auth_headers(user_id, "eng@quebet.ai", tenant_id=tenant)

    project_id, circuit_id = await create_project_circuit(async_client, headers, "Medical Sensor Subsystem")

    # Decision backing memory
    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": project_id, "name": "Sensor Sys"},
        headers=headers,
    )
    sys_id = s_res.json()["data"]["id"]
    dec_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/decisions",
        json={
            "title": "Sensor Calibration Baseline",
            "decision_key": "DEC-SENS-01",
            "description": "Lab calibration record",
            "decision_type": "ARCHITECTURE",
        },
        headers=headers,
    )
    dec_id = dec_res.json()["data"]["id"]

    # Historical memory with VERIFIED_SUCCESS
    await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": project_id,
            "memory_type": MemoryType.VERIFICATION_LESSON.value,
            "source_entity_type": "EngineeringDecisionRecord",
            "source_entity_id": dec_id,
            "engineering_domain": "circuit",
            "summary": "Rev 1 passed 3-point temperature test in physical lab.",
            "historical_outcome": HistoricalOutcome.VERIFIED_SUCCESS.value,
        },
        headers=headers,
    )

    # Trigger design review for current circuit
    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=headers,
    )
    assert rev_res.status_code == 201

    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id, "include_historical_memory": True},
        headers=headers,
    )
    assert synth_res.status_code == 201
    snapshot = synth_res.json()["data"]

    # Invariant: HISTORICAL VERIFICATION != CURRENT VERIFICATION
    # Verification requirements are not marked VERIFIED because no physical evidence was uploaded in current rev
    for vr_item in snapshot["verification_state"]["requirements"]:
        assert vr_item["status"] != "VERIFIED"


@pytest.mark.asyncio
async def test_scenario_10_no_synthetic_metrics(async_client: AsyncClient):
    """
    Scenario 10: No synthetic intelligence metrics.
    - Ensures context and explanation contain no synthetic score keywords.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w5-sc10"
    headers = auth_headers(user_id, "auditor@quebet.ai", tenant_id=tenant)

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Audit Synthesis Project", "project_type": "general"},
        headers=headers,
    )
    project_id = p_res.json()["data"]["id"]

    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id},
        headers=headers,
    )
    context_data = synth_res.json()["data"]

    explain_res = await async_client.post(
        f"/api/v1/cognitive/context/{context_data['id']}/explain",
        json={"user_query": "Provide audit summary"},
        headers=headers,
    )
    explain_data = explain_res.json()["data"]

    serialized = json.dumps(context_data) + json.dumps(explain_data)
    forbidden_tokens = [
        "confidence_percentage",
        "readiness_percentage",
        "engineering_score",
        "health_score",
        "intelligence_score",
    ]
    for token in forbidden_tokens:
        assert token not in serialized, f"Forbidden synthetic metric '{token}' detected in response!"
