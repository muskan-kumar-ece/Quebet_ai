import json
import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.db.cognitive import (
    HistoricalOutcome,
    MemoryApplicability,
    MemoryFeedbackType,
    MemoryType,
)


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-p2w4-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def create_system_and_decision(
    async_client: AsyncClient,
    headers: dict[str, str],
    project_id: str,
    title: str,
    description: str = "",
) -> str:
    """Helper to create a system and an authoritative decision record."""
    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": project_id, "name": f"System for {title}"},
        headers=headers,
    )
    assert s_res.status_code == 201
    sys_id = s_res.json()["data"]["id"]

    dec_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/decisions",
        json={
            "title": title,
            "decision_key": f"DEC-{uuid.uuid4().hex[:6].upper()}",
            "description": description or title,
            "decision_type": "ARCHITECTURE",
        },
        headers=headers,
    )
    assert dec_res.status_code == 201
    return dec_res.json()["data"]["id"]


# ============================================================================
# PHASE 2 WAVE 4 SAFETY & INVARIANT TEST SUITE
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_1_relevant_historical_decision(async_client: AsyncClient):
    """
    Scenario 1: Current circuit matches historical context.
    - Historical decision on LM7805 regulator thermal design.
    - Memory surfaced as APPLICABLE or POTENTIALLY_APPLICABLE.
    - Source trace to authentic EngineeringDecisionRecord present.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w4-sc1"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    # 1. Create project
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "5V Power Supply Revision 1", "project_type": "power"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    # 2. Create authoritative Decision Record (Phase 1)
    decision_id = await create_system_and_decision(
        async_client,
        headers,
        project_id,
        title="5V Regulator Thermal Architecture Decision",
        description="Selected LM7805 with extruded heatsink after thermal dissipation analysis.",
    )

    # 3. Create Engineering Memory Record pointing to this decision
    mem_payload = {
        "project_id": project_id,
        "memory_type": MemoryType.DECISION_HISTORY.value,
        "source_entity_type": "EngineeringDecisionRecord",
        "source_entity_id": decision_id,
        "engineering_domain": "thermal",
        "summary": "Previous project used LM7805 regulator with 15 degC/W heatsink for 5V output under 500mA load.",
        "applicability_conditions": {
            "component_family": "LM7805",
            "voltage_domain": "5V",
            "current_range": "300mA - 600mA",
            "engineering_domain": "thermal",
        },
        "historical_outcome": HistoricalOutcome.VERIFIED_SUCCESS.value,
    }
    mem_res = await async_client.post("/api/v1/cognitive/memories", json=mem_payload, headers=headers)
    assert mem_res.status_code == 201
    memory_id = mem_res.json()["data"]["id"]

    # 4. Current engineering retrieval for matching context
    retrieval_payload = {
        "project_id": project_id,
        "engineering_domain": "thermal",
        "component_family": "LM7805",
        "voltage_domain": "5V",
    }
    ret_res = await async_client.post(
        f"/api/v1/cognitive/projects/{project_id}/memories/retrieve",
        json=retrieval_payload,
        headers=headers,
    )
    assert ret_res.status_code == 200
    ret_data = ret_res.json()["data"]

    assert ret_data["total_surfaced"] >= 1
    surfaced_item = next(m for m in ret_data["memories"] if m["memory"]["id"] == memory_id)
    assert surfaced_item["applicability"] in [
        MemoryApplicability.APPLICABLE.value,
        MemoryApplicability.POTENTIALLY_APPLICABLE.value,
    ]
    assert surfaced_item["memory"]["source_entity_id"] == decision_id
    assert surfaced_item["memory"]["source_entity_type"] == "EngineeringDecisionRecord"
    assert "Historical context — not current engineering verification." in surfaced_item["warnings"]


@pytest.mark.asyncio
async def test_scenario_2_irrelevant_historical_decision(async_client: AsyncClient):
    """
    Scenario 2: Irrelevant historical decision (domain mismatch).
    - Thermal power regulator memory evaluated against RF transceiver design.
    - Expected: NOT_APPLICABLE, not presented as relevant guidance.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w4-sc2"
    headers = auth_headers(user_id, "rf_eng@quebet.ai", tenant_id=tenant)

    # Create project
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "2.4GHz RF Front-End", "project_type": "rf"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    # Authoritative decision in thermal domain
    decision_id = await create_system_and_decision(
        async_client,
        headers,
        project_id,
        title="Battery Charging Thermal Cutoff",
        description="Cutoff threshold at 45 degC",
    )

    # Memory in thermal domain
    mem_res = await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": project_id,
            "memory_type": MemoryType.DECISION_HISTORY.value,
            "source_entity_type": "EngineeringDecisionRecord",
            "source_entity_id": decision_id,
            "engineering_domain": "thermal",
            "summary": "Battery charging thermal cutoff limits charging rate.",
            "applicability_conditions": {"engineering_domain": "thermal"},
        },
        headers=headers,
    )
    assert mem_res.status_code == 201
    memory_id = mem_res.json()["data"]["id"]

    # Retrieve with RF domain
    ret_res = await async_client.post(
        f"/api/v1/cognitive/projects/{project_id}/memories/retrieve",
        json={"project_id": project_id, "engineering_domain": "rf", "component_family": "BGA-Transceiver"},
        headers=headers,
    )
    assert ret_res.status_code == 200
    surfaced = ret_res.json()["data"]["memories"]
    item = next(m for m in surfaced if m["memory"]["id"] == memory_id)
    assert item["applicability"] == MemoryApplicability.NOT_APPLICABLE.value
    assert "Domain mismatch" in item["why_surfaced"]


@pytest.mark.asyncio
async def test_scenario_3_historical_current_conflict(async_client: AsyncClient):
    """
    Scenario 3: Historical record conflicts with current authoritative source.
    - Historical memory: component rated for 1A.
    - Current datasheet/spec: component rated for 600mA.
    - Expected: Current source wins, historical memory marked is_conflicting=True, no silent merge.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w4-sc3"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Power Distribution", "project_type": "power"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    decision_id = await create_system_and_decision(
        async_client,
        headers,
        project_id,
        title="Pass Element Selection",
        description="Selected legacy pass transistor.",
    )

    mem_res = await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": project_id,
            "memory_type": MemoryType.DECISION_HISTORY.value,
            "source_entity_type": "EngineeringDecisionRecord",
            "source_entity_id": decision_id,
            "engineering_domain": "power",
            "summary": "Legacy pass transistor operated up to 1A.",
            "applicability_conditions": {
                "engineering_domain": "power",
                "component_family": "LDO-Transistor",
                "component_specifications": {"current_rating": "1A"},
            },
        },
        headers=headers,
    )
    assert mem_res.status_code == 201
    memory_id = mem_res.json()["data"]["id"]

    # Current context with authoritative current rating = 600mA
    ret_res = await async_client.post(
        f"/api/v1/cognitive/projects/{project_id}/memories/retrieve",
        json={
            "project_id": project_id,
            "engineering_domain": "power",
            "component_family": "LDO-Transistor",
            "current_parameters": {"current_rating": "600mA"},
        },
        headers=headers,
    )
    assert ret_res.status_code == 200
    item = next(m for m in ret_res.json()["data"]["memories"] if m["memory"]["id"] == memory_id)

    assert item["is_conflicting"] is True
    assert item["conflict_details"]["parameter"] == "current_rating"
    assert item["conflict_details"]["current_authoritative_value"] == "600mA"
    assert item["conflict_details"]["historical_memory_value"] == "1A"
    assert "CURRENT AUTHORITATIVE SOURCE > HISTORICAL MEMORY" in item["conflict_details"]["authoritative_rule"]
    assert any("CONFLICT DETECTED" in w for w in item["warnings"])


@pytest.mark.asyncio
async def test_scenario_4_missing_provenance_rejected(async_client: AsyncClient):
    """
    Scenario 4: Attempt to create memory without valid source entity.
    - Expected: HTTP 422 with error code INVALID_MEMORY_PROVENANCE.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w4-sc4"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Isolated Project", "project_type": "circuit"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    fake_entity_id = str(uuid.uuid4())
    bad_payload = {
        "project_id": project_id,
        "memory_type": MemoryType.DESIGN_FINDING.value,
        "source_entity_type": "EngineeringDecisionRecord",
        "source_entity_id": fake_entity_id,
        "summary": "This memory points to an imaginary decision.",
    }

    create_res = await async_client.post("/api/v1/cognitive/memories", json=bad_payload, headers=headers)
    assert create_res.status_code == 422
    err_body = create_res.json()["detail"]
    assert err_body["error"] == "INVALID_MEMORY_PROVENANCE"


@pytest.mark.asyncio
async def test_scenario_5_cross_tenant_isolation(async_client: AsyncClient):
    """
    Scenario 5: Tenant A requests Tenant B memory.
    - Expected: HTTP 404, strictly isolated.
    """
    user_a = str(uuid.uuid4())
    tenant_a = "tenant-p2w4-tenant-a"
    headers_a = auth_headers(user_a, "alice@tenant-a.com", tenant_id=tenant_a)

    user_b = str(uuid.uuid4())
    tenant_b = "tenant-p2w4-tenant-b"
    headers_b = auth_headers(user_b, "bob@tenant-b.com", tenant_id=tenant_b)

    # Tenant A creates project & decision & memory
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Tenant A Secret Circuit", "project_type": "circuit"},
        headers=headers_a,
    )
    assert p_res.status_code == 201
    proj_a_id = p_res.json()["data"]["id"]

    dec_a_id = await create_system_and_decision(
        async_client,
        headers_a,
        proj_a_id,
        title="Proprietary Architecture Choice",
        description="Sensitive architectural selection.",
    )

    mem_res = await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": proj_a_id,
            "memory_type": MemoryType.DECISION_HISTORY.value,
            "source_entity_type": "EngineeringDecisionRecord",
            "source_entity_id": dec_a_id,
            "summary": "Tenant A proprietary design memory.",
        },
        headers=headers_a,
    )
    assert mem_res.status_code == 201
    mem_a_id = mem_res.json()["data"]["id"]

    # Tenant B attempts to retrieve Tenant A's memory
    b_res = await async_client.get(f"/api/v1/cognitive/memories/{mem_a_id}", headers=headers_b)
    assert b_res.status_code == 404


@pytest.mark.asyncio
async def test_scenario_6_ai_generated_false_memory_rejected(async_client: AsyncClient):
    """
    Scenario 6: AI-generated false memory.
    - LLM actor attempts to create "Engineer previously verified this design" without an actual verified record.
    - Expected: HTTP 422 INVALID_MEMORY_PROVENANCE.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w4-sc6"
    headers = auth_headers(user_id, "ai_assistant@quebet.ai", tenant_id=tenant)

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Verification Project", "project_type": "circuit"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    # AI actor attempts to assert VERIFIED_SUCCESS using non-existent or fabricated requirement
    fake_req_id = str(uuid.uuid4())
    ai_false_memory = {
        "project_id": project_id,
        "memory_type": MemoryType.VERIFICATION_LESSON.value,
        "source_entity_type": "EngineeringVerificationRequirement",
        "source_entity_id": fake_req_id,
        "summary": "Engineer previously verified this design at 100 degC.",
        "historical_outcome": HistoricalOutcome.VERIFIED_SUCCESS.value,
        "actor": "ai",
    }

    create_res = await async_client.post("/api/v1/cognitive/memories", json=ai_false_memory, headers=headers)
    assert create_res.status_code == 422
    err_body = create_res.json()["detail"]
    assert err_body["error"] == "INVALID_MEMORY_PROVENANCE"


@pytest.mark.asyncio
async def test_scenario_7_historical_memory_cannot_satisfy_verification(async_client: AsyncClient):
    """
    Scenario 7: Historical memory cannot satisfy verification.
    - Historical successful verification exists.
    - Current hardware revision differs.
    - Expected: Warning that historical verification cannot close current requirement, physical verification still REQUIRED.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w4-sc7"
    headers = auth_headers(user_id, "lead_eng@quebet.ai", tenant_id=tenant)

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Medical Sensor Subsystem", "project_type": "circuit"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    # Valid Decision Record to back the memory
    dec_id = await create_system_and_decision(
        async_client,
        headers,
        project_id,
        title="Sensor Calibration Standard",
        description="Calibrated against reference lab standard.",
    )

    mem_res = await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": project_id,
            "memory_type": MemoryType.VERIFICATION_LESSON.value,
            "source_entity_type": "EngineeringDecisionRecord",
            "source_entity_id": dec_id,
            "engineering_domain": "analog",
            "summary": "Rev 1 passed 3-point temperature chamber test successfully.",
            "revision_context": {"baseline_revision": 1},
            "historical_outcome": HistoricalOutcome.VERIFIED_SUCCESS.value,
        },
        headers=headers,
    )
    assert mem_res.status_code == 201
    memory_id = mem_res.json()["data"]["id"]

    # Retrieve in current context
    ret_res = await async_client.post(
        f"/api/v1/cognitive/projects/{project_id}/memories/retrieve",
        json={"project_id": project_id, "engineering_domain": "analog"},
        headers=headers,
    )
    assert ret_res.status_code == 200
    item = next(m for m in ret_res.json()["data"]["memories"] if m["memory"]["id"] == memory_id)

    # Invariant check: HISTORICAL VERIFICATION != CURRENT VERIFICATION
    assert any(
        "Historical verification cannot close current verification obligations" in w
        for w in item["warnings"]
    )


@pytest.mark.asyncio
async def test_scenario_8_human_feedback_updates_retrieval(async_client: AsyncClient):
    """
    Scenario 8: Human feedback updates retrieval preference.
    - Engineer marks memory NOT_APPLICABLE.
    - Subsequent retrieval reflects NOT_APPLICABLE.
    - Authoritative source record remains unmodified.
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w4-sc8"
    headers = auth_headers(user_id, "engineer@quebet.ai", tenant_id=tenant)

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Audio Preamp", "project_type": "circuit"},
        headers=headers,
    )
    assert p_res.status_code == 201
    project_id = p_res.json()["data"]["id"]

    dec_id = await create_system_and_decision(
        async_client,
        headers,
        project_id,
        title="OpAmp Selection",
        description="NE5532 selected.",
    )

    mem_res = await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": project_id,
            "memory_type": MemoryType.DECISION_HISTORY.value,
            "source_entity_type": "EngineeringDecisionRecord",
            "source_entity_id": dec_id,
            "engineering_domain": "analog",
            "summary": "NE5532 historical experience in preamp.",
        },
        headers=headers,
    )
    assert mem_res.status_code == 201
    memory_id = mem_res.json()["data"]["id"]

    # Engineer submits feedback: NOT_APPLICABLE
    fb_res = await async_client.post(
        f"/api/v1/cognitive/memories/{memory_id}/feedback",
        json={
            "feedback_type": MemoryFeedbackType.NOT_APPLICABLE.value,
            "engineer_identity": "Senior Audio Engineer",
            "notes": "Different supply rails prevent using this topology.",
        },
        headers=headers,
    )
    assert fb_res.status_code == 201

    # Retrieve again: should now be marked NOT_APPLICABLE per human feedback
    ret_res = await async_client.post(
        f"/api/v1/cognitive/projects/{project_id}/memories/retrieve",
        json={"project_id": project_id, "engineering_domain": "analog"},
        headers=headers,
    )
    assert ret_res.status_code == 200
    item = next(m for m in ret_res.json()["data"]["memories"] if m["memory"]["id"] == memory_id)
    assert item["applicability"] == MemoryApplicability.NOT_APPLICABLE.value
    assert "marked NOT_APPLICABLE by human engineer feedback" in item["why_surfaced"]

    # Verify authoritative decision is untouched
    orig_dec = await async_client.get(f"/api/v1/decisions/{dec_id}", headers=headers)
    assert orig_dec.status_code == 200
    assert orig_dec.json()["data"]["title"] == "OpAmp Selection"


@pytest.mark.asyncio
async def test_zero_synthetic_scoring_invariant(async_client: AsyncClient):
    """
    Verifies that no synthetic scoring metrics exist in any memory schemas or responses:
    - memory_score
    - memory_confidence
    - learning_score
    - relevance_percentage
    - historical_success_score
    """
    user_id = str(uuid.uuid4())
    tenant = "tenant-p2w4-zeroscore"
    headers = auth_headers(user_id, "auditor@quebet.ai", tenant_id=tenant)

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Audit Project", "project_type": "general"},
        headers=headers,
    )
    project_id = p_res.json()["data"]["id"]

    dec_id = await create_system_and_decision(
        async_client,
        headers,
        project_id,
        title="Audit Decision",
        description="Audit baseline.",
    )

    mem_res = await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": project_id,
            "memory_type": MemoryType.DECISION_HISTORY.value,
            "source_entity_type": "EngineeringDecisionRecord",
            "source_entity_id": dec_id,
            "summary": "Audit memory record.",
        },
        headers=headers,
    )
    mem_body = mem_res.json()

    ret_res = await async_client.post(
        f"/api/v1/cognitive/projects/{project_id}/memories/retrieve",
        json={"project_id": project_id},
        headers=headers,
    )
    ret_body = ret_res.json()

    serialized = json.dumps(mem_body) + json.dumps(ret_body)
    forbidden_score_tokens = [
        "memory_score",
        "memory_confidence",
        "learning_score",
        "relevance_percentage",
        "historical_success_score",
    ]
    for token in forbidden_score_tokens:
        assert token not in serialized, f"Forbidden synthetic metric '{token}' found in memory API response!"
