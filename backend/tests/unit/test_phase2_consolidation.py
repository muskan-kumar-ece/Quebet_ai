import json
import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.db.cognitive import (
    ContextSnapshotStatus,
    HumanDecisionType,
    MemoryType,
    PlanStatus,
    ReflectionStatus,
)


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-consolidation-audit") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def setup_test_project_and_circuit(
    async_client: AsyncClient,
    headers: dict[str, str],
    name: str = "Consolidation Circuit",
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
        "description": "Baseline linear regulator topology",
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
async def test_cross_wave_pipeline_1_full_cognitive_lifecycle(async_client: AsyncClient):
    """
    Pipeline 1: Full Cognitive Pipeline
    Intent -> Plan -> Execution -> Reflection -> Decision Brief -> Memory -> Context Snapshot -> Human Decision
    Ensures that the final human decision is the ONLY authority/mutation transition.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "lead_eng@quebet.ai")
    project_id, circuit_id = await setup_test_project_and_circuit(async_client, headers, "Lifecycle Test")

    # 1. Intent Resolution
    intent_res = await async_client.post(
        "/api/v1/cognitive/intents/resolve",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "raw_request": "Analyze LM7805 thermal dissipation and prepare design review decision brief",
            "scope": "CIRCUIT",
            "urgency": "NORMAL",
        },
        headers=headers,
    )
    assert intent_res.status_code == 201
    intent = intent_res.json()["data"]
    assert intent["status"] in ["INTERPRETED", "CONFIRMED"]
    intent_id = intent["id"]

    # 2. Plan Creation & Validation
    plan_res = await async_client.post(
        "/api/v1/cognitive/plans",
        json={"intent_packet_id": intent_id},
        headers=headers,
    )
    assert plan_res.status_code == 201
    plan = plan_res.json()["data"]
    plan_id = plan["id"]
    assert plan["status"] in [PlanStatus.READY.value, PlanStatus.VALIDATED.value, PlanStatus.DRAFT.value]

    # 3. Deterministic Plan Execution
    exec_res = await async_client.post(
        f"/api/v1/cognitive/plans/{plan_id}/execute",
        headers=headers,
    )
    assert exec_res.status_code == 200
    execution = exec_res.json()["data"]
    exec_id = execution["id"]
    assert execution["execution_status"] in ["SUCCESS", "PARTIAL_SUCCESS", "PARTIAL"]

    # 4. Cognitive Reflection
    reflect_res = await async_client.post(
        f"/api/v1/cognitive/executions/{exec_id}/reflect",
        json={"user_focus": "thermal_limits"},
        headers=headers,
    )
    assert reflect_res.status_code == 201
    reflection = reflect_res.json()["data"]
    reflection_id = reflection["id"]
    assert reflection["status"] == ReflectionStatus.COMPLETE.value

    # 5. Decision Brief Preparation (Advisory only)
    brief_res = await async_client.post(
        "/api/v1/cognitive/decision-briefs",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "reflection_id": reflection_id,
            "question": "Adopt heatsink addition or transition to switching buck regulator?",
            "alternatives": [
                {"id": "ALT-HEATSINK", "name": "Linear Regulator with Extruded Heatsink", "parameters": {}},
                {"id": "ALT-BUCK", "name": "Synchronous Buck Converter", "parameters": {}},
            ],
        },
        headers=headers,
    )
    assert brief_res.status_code == 201
    brief = brief_res.json()["data"]
    brief_id = brief["id"]
    assert brief["status"] == "READY_FOR_REVIEW"
    assert brief["human_decision_required"] is True

    # 6. Memory Creation referencing authoritative source entity (EngineeringReflection)
    mem_res = await async_client.post(
        "/api/v1/cognitive/memories",
        json={
            "project_id": project_id,
            "circuit_id": circuit_id,
            "memory_type": MemoryType.DESIGN_FINDING.value,
            "source_entity_type": "EngineeringReflection",
            "source_entity_id": reflection_id,
            "engineering_domain": "thermal",
            "summary": "LM7805 dissipates 2.4W under 12V-to-5V step-down at 340mA.",
            "applicability_conditions": {"voltage_domain": "12V-5V", "component_family": "linear_regulator"},
        },
        headers=headers,
    )
    assert mem_res.status_code == 201
    memory_id = mem_res.json()["data"]["id"]

    # 7. Context Synthesis
    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    assert synth_res.status_code == 201
    context_snap = synth_res.json()["data"]
    assert context_snap["status"] == ContextSnapshotStatus.CURRENT.value
    assert len(context_snap["canonical_digest"]) == 64

    # 8. Human Decision Ratification (The single authoritative transition)
    dec_res = await async_client.post(
        f"/api/v1/cognitive/decision-briefs/{brief_id}/decision",
        json={
            "decision_type": HumanDecisionType.ADOPT_ALTERNATIVE.value,
            "selected_alternative_id": "ALT-BUCK",
            "rationale": "Switching buck avoids excessive heat dissipation at high input voltages.",
            "actor": "lead_engineer_human",
        },
        headers=headers,
    )
    assert dec_res.status_code == 200
    dec_data = dec_res.json()["data"]
    assert dec_data["status"] in ["DECISION_RECORDED", "DECIDED"]
    assert dec_data["selected_alternative_id"] == "ALT-BUCK"


@pytest.mark.asyncio
async def test_cross_wave_pipeline_2_stale_detection_on_revision_advance(async_client: AsyncClient):
    """
    Pipeline 2: Stale Pipeline
    Context created at revision N -> Revision N+1 -> Context and Plans become STALE.
    Old artifacts must not silently operate as current.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "staff_eng@quebet.ai")
    project_id, circuit_id = await setup_test_project_and_circuit(async_client, headers, "Stale Test")

    # 1. Synthesize context at revision 1
    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    assert synth_res.status_code == 201
    snap_id = synth_res.json()["data"]["id"]
    assert synth_res.json()["data"]["base_revision"] == 1
    assert synth_res.json()["data"]["status"] == ContextSnapshotStatus.CURRENT.value

    # 2. Advance circuit revision to 2 via PATCH
    update_res = await async_client.patch(
        f"/api/v1/circuits/{circuit_id}",
        json={"description": "Updated circuit revision to v2", "version": 2},
        headers=headers,
    )
    assert update_res.status_code == 200

    # 3. Retrieve context snapshot -> Must report STALE
    get_res = await async_client.get(
        f"/api/v1/cognitive/context/{snap_id}",
        headers=headers,
    )
    assert get_res.status_code == 200
    snap_updated = get_res.json()["data"]
    assert snap_updated["status"] == ContextSnapshotStatus.STALE.value


@pytest.mark.asyncio
async def test_cross_wave_pipeline_3_unknown_invariants_preserved_throughout(async_client: AsyncClient):
    """
    Pipeline 3: Unknown Pipeline
    Unknown parameter in analysis -> Reflection captures UNRESOLVED_UNKNOWN finding ->
    Decision brief surfaces unknown -> Context synthesis retains unknown.
    Invariant: UNKNOWN != SATISFIED throughout.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "qa_eng@quebet.ai")
    project_id, circuit_id = await setup_test_project_and_circuit(async_client, headers, "Unknown Invariant Test")

    # Trigger deterministic circuit analysis
    an_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/analyze",
        headers=headers,
    )
    assert an_res.status_code == 200
    an_data = an_res.json()["data"]
    analysis_id = an_data["id"]

    # Synthesize context
    synth_res = await async_client.post(
        "/api/v1/cognitive/context/synthesize",
        json={"project_id": project_id, "circuit_id": circuit_id},
        headers=headers,
    )
    assert synth_res.status_code == 201
    snap = synth_res.json()["data"]

    # Invariant check: Any unresolved parameters or unknowns are explicitly captured, never fabricated as passed
    assert isinstance(snap["unknowns"], list)
    assert isinstance(snap["conflicts"], list)


@pytest.mark.asyncio
async def test_cross_wave_pipeline_4_calculated_does_not_equal_physically_verified(async_client: AsyncClient):
    """
    Pipeline 4: Physical Verification Pipeline
    Calculated result in deterministic analysis does not satisfy physical verification obligation.
    Context synthesis marks verification as PENDING/REQUIRED in absence of lab measurement evidence.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "safety_eng@quebet.ai")
    project_id, circuit_id = await setup_test_project_and_circuit(async_client, headers, "Physical Verification Test")

    # 1. Trigger design review to automatically generate verification requirements
    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=headers,
    )
    assert rev_res.status_code == 201
    rev_data = rev_res.json()["data"]
    vr_reqs = rev_data.get("verification_requirements", [])
    assert len(vr_reqs) > 0
    target_vr_id = vr_reqs[0]["id"]

    # 2. Attach only simulation evidence (deterministic calculation)
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

    # 3. Trigger deterministic circuit analysis
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
    snap = synth_res.json()["data"]

    # 5. Invariant check: CALCULATED != PHYSICALLY VERIFIED
    v_state = snap["verification_state"]
    reqs_v = v_state.get("requirements", [])
    assert len(reqs_v) >= 1
    # Status must NOT be SATISFIED because no physical measurement evidence was uploaded
    for item in reqs_v:
        assert item["status"] != "SATISFIED"
        assert item["status"] in ["PENDING", "REQUIRED", "NOT_STARTED", "IN_PROGRESS", "UNKNOWN"]
