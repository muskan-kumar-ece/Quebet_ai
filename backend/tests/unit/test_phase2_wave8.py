import uuid
import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.db.cognitive import CognitiveWorkflowStatus
from app.models.db.verification import VerificationStatus
from app.models.schemas.cognitive import EvidenceSufficiencyStatus


def auth_headers(
    user_id: str,
    email: str,
    role: str = "engineer",
    tenant_id: str = "tenant-p2w8-a",
) -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


async def setup_circuit_and_review(
    async_client: AsyncClient,
    headers: dict[str, str],
    name: str = "Wave 8 Circuit",
) -> tuple[str, str, str, str]:
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


# ============================================================================
# PHASE 2 WAVE 8 TEST SUITE (20 SCENARIOS)
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_1_verification_workspace_synthesis(async_client: AsyncClient):
    """Scenario 1: Verification workspace synthesis with obligations and summary."""
    headers = auth_headers("u-w8-1", "w8-1@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Synthesis Test")

    # Start cognitive workflow
    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": proj_id,
            "circuit_id": circ_id,
            "user_request": "Audit power rail regulation and bench verification obligations",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf_id = wf_res.json()["data"]["id"]

    # Retrieve verification workspace
    ws_res = await async_client.get(
        f"/api/v1/cognitive/workflows/{wf_id}/verification",
        headers=headers,
    )
    assert ws_res.status_code == 200
    ws = ws_res.json()["data"]
    assert ws["project_id"] == proj_id
    assert ws["circuit_id"] == circ_id
    assert len(ws["obligations"]) >= 1
    assert ws["summary"]["total_obligations"] >= 1
    assert len(ws["provenance_integrity_digest"]) == 64


@pytest.mark.asyncio
async def test_scenario_2_attach_traceable_evidence(async_client: AsyncClient):
    """Scenario 2: Attach traceable physical measurement evidence with instrument calibration."""
    headers = auth_headers("u-w8-2", "w8-2@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Traceable Evidence")

    evi_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Bench Test Rig 3",
            "description": "Measured output ripple voltage with active probe under full load",
            "value": "12.4",
            "unit": "mV",
            "is_physical": True,
            "instrument": "Keysight DSOX3024T",
            "instrument_serial": "MY58102214",
            "calibration_status": "CALIBRATED",
            "calibration_reference": "CAL-2026-0301",
        },
        headers=headers,
    )
    assert evi_res.status_code == 200
    evi = evi_res.json()["data"]
    assert evi["evidence_type"] == "MEASUREMENT"
    assert evi["is_physical"] is True
    assert len(evi["cryptographic_hash"]) == 64


@pytest.mark.asyncio
async def test_scenario_3_entity_binding_validation(async_client: AsyncClient):
    """Scenario 3: Valid entity reference is bound successfully."""
    headers = auth_headers("u-w8-3", "w8-3@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Entity Binding")

    evi_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Bench Multimeter",
            "description": "DC output voltage measured directly on circuit net",
            "value": "5.01",
            "unit": "V",
            "is_physical": True,
            "bound_entity_type": "Circuit",
            "bound_entity_id": circ_id,
        },
        headers=headers,
    )
    assert evi_res.status_code == 200
    assert evi_res.json()["data"]["verification_requirement_id"] == vr_id


@pytest.mark.asyncio
async def test_scenario_4_invalid_entity_reference_rejected(async_client: AsyncClient):
    """Scenario 4: Grounding contract rejects non-existent foreign entity reference with 422."""
    headers = auth_headers("u-w8-4", "w8-4@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Invalid Ref")

    phantom_id = str(uuid.uuid4())
    evi_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Bench Test",
            "description": "Testing against phantom circuit",
            "is_physical": True,
            "bound_entity_type": "Circuit",
            "bound_entity_id": phantom_id,
        },
        headers=headers,
    )
    assert evi_res.status_code == 422
    assert "MODEL_INVALID_REFERENCE" in str(evi_res.json())


@pytest.mark.asyncio
async def test_scenario_5_evidence_sufficiency_missing(async_client: AsyncClient):
    """Scenario 5: Obligation with zero attached evidence is evaluated as MISSING."""
    headers = auth_headers("u-w8-5", "w8-5@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Sufficiency Missing")

    obl_res = await async_client.get(
        f"/api/v1/cognitive/verification/{vr_id}",
        headers=headers,
    )
    assert obl_res.status_code == 200
    obl = obl_res.json()["data"]
    assert obl["sufficiency"] == "MISSING"
    assert obl["status"] in ["NOT_STARTED", "PENDING"]


@pytest.mark.asyncio
async def test_scenario_6_evidence_sufficiency_insufficient(async_client: AsyncClient):
    """Scenario 6: Physical obligation with only analytical calculation is INSUFFICIENT."""
    headers = auth_headers("u-w8-6", "w8-6@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Sufficiency Insufficient")

    # Attach only simulation evidence
    await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "SIMULATION_REPORT",
            "source": "SPICE AC Analysis",
            "description": "Simulated gain and phase margin",
            "value": "48.2",
            "unit": "deg",
            "is_physical": False,
        },
        headers=headers,
    )

    obl_res = await async_client.get(
        f"/api/v1/cognitive/verification/{vr_id}",
        headers=headers,
    )
    assert obl_res.status_code == 200
    obl = obl_res.json()["data"]
    # If physical is required, simulation alone must be INSUFFICIENT
    if obl["is_physical_required"]:
        assert obl["sufficiency"] == "INSUFFICIENT"
        assert obl["has_physical_evidence"] is False


@pytest.mark.asyncio
async def test_scenario_7_calculated_vs_physical_evidence_distinction(async_client: AsyncClient):
    """Scenario 7: Epistemic boundary CALCULATED != PHYSICALLY VERIFIED."""
    headers = auth_headers("u-w8-7", "w8-7@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Boundary Test")

    # Upload calculation
    await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "CALCULATION",
            "source": "MathCad Analysis Sheet",
            "description": "Calculated power dissipation = 1.2W",
            "value": "1.2",
            "unit": "W",
            "is_physical": False,
        },
        headers=headers,
    )

    # Review verification gaps
    rev_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/review",
        headers=headers,
    )
    assert rev_res.status_code == 200
    audit = rev_res.json()["data"]
    assert audit["authority"] == "INFORMATIONAL_ONLY"
    if audit["is_physical_required"]:
        assert any("Physical" in gap for gap in audit["remaining_gaps"])


@pytest.mark.asyncio
async def test_scenario_8_physical_evidence_satisfaction(async_client: AsyncClient):
    """Scenario 8: Physical measurement satisfies physical obligation."""
    headers = auth_headers("u-w8-8", "w8-8@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Physical Satisfied")

    # Upload physical measurement
    await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Lab Thermal Camera Rig",
            "description": "Measured thermal camera case temperature at 64.2C",
            "value": "64.2",
            "unit": "C",
            "is_physical": True,
            "instrument": "FLIR E8-XT",
            "calibration_status": "CALIBRATED",
        },
        headers=headers,
    )

    obl_res = await async_client.get(
        f"/api/v1/cognitive/verification/{vr_id}",
        headers=headers,
    )
    assert obl_res.status_code == 200
    obl = obl_res.json()["data"]
    assert obl["has_physical_evidence"] is True
    assert obl["sufficiency"] == "SUFFICIENT"


@pytest.mark.asyncio
async def test_scenario_9_stale_evidence_detection(async_client: AsyncClient):
    """Scenario 9: Modifying circuit advances revision and marks previous evidence STALE."""
    headers = auth_headers("u-w8-9", "w8-9@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Stale Detection")

    # Attach evidence at rev 1
    await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Bench Rig",
            "description": "Bench measurement at rev 1",
            "is_physical": True,
        },
        headers=headers,
    )

    # Advance circuit revision
    upd_res = await async_client.patch(
        f"/api/v1/circuits/{circ_id}",
        json={"version": 2},
        headers=headers,
    )
    assert upd_res.status_code == 200

    # Check obligation - must detect stale revision
    obl_res = await async_client.get(
        f"/api/v1/cognitive/verification/{vr_id}",
        headers=headers,
    )
    assert obl_res.status_code == 200
    obl = obl_res.json()["data"]
    assert obl["is_stale"] is True
    assert len(obl["stale_reasons"]) >= 1


@pytest.mark.asyncio
async def test_scenario_10_stale_revision_closure_rejected(async_client: AsyncClient):
    """Scenario 10: Attempting to close verification on superseded revision raises 409."""
    headers = auth_headers("u-w8-10", "w8-10@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Stale Closure")

    # Advance revision
    upd_res = await async_client.patch(
        f"/api/v1/circuits/{circ_id}",
        json={"version": 2},
        headers=headers,
    )
    assert upd_res.status_code == 200

    # Attempt human closure specifying stale revision 1
    close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/close",
        json={
            "decision": "VERIFIED",
            "rationale": "Attempting verification against old baseline.",
            "actor": "Staff Hardware Engineer",
            "current_revision": 1,
        },
        headers=headers,
    )
    assert close_res.status_code == 409
    assert "VERIFICATION_STALE_REVISION" in str(close_res.json())


@pytest.mark.asyncio
async def test_scenario_11_unknown_requirement_boundary(async_client: AsyncClient):
    """Scenario 11: UNKNOWN != SATISFIED boundary is preserved."""
    headers = auth_headers("u-w8-11", "w8-11@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Unknown Boundary")

    # Without evidence, obligation status is NOT_STARTED/PENDING, not SATISFIED
    obl_res = await async_client.get(
        f"/api/v1/cognitive/verification/{vr_id}",
        headers=headers,
    )
    assert obl_res.status_code == 200
    obl = obl_res.json()["data"]
    assert obl["status"] in ["NOT_STARTED", "PENDING"]
    assert obl["status"] != "SATISFIED"


@pytest.mark.asyncio
async def test_scenario_12_unresolved_blocking_findings(async_client: AsyncClient):
    """Scenario 12: Review readiness detects unresolved blocker findings."""
    headers = auth_headers("u-w8-12", "w8-12@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Blocker Finding")

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Scenario 12 System"},
        headers=headers,
    )
    assert s_res.status_code == 201
    sys_id = s_res.json()["data"]["id"]

    rev_session_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/design-reviews",
        json={"title": "Thermal CDR"},
        headers=headers,
    )
    assert rev_session_res.status_code == 201
    session_id = rev_session_res.json()["data"]["id"]

    # Add a blocker finding to the review
    f_res = await async_client.post(
        f"/api/v1/design-reviews/{session_id}/findings",
        json={
            "source_analysis": "THERMAL",
            "severity": "BLOCKER",
            "description": "LM7805 exceeds junction maximum under elevated ambient",
        },
        headers=headers,
    )
    assert f_res.status_code == 201

    # Check review readiness
    ready_res = await async_client.get(
        f"/api/v1/design-reviews/{session_id}/readiness",
        headers=headers,
    )
    assert ready_res.status_code == 200
    ready = ready_res.json()["data"]
    assert ready["overall_status"] == "BLOCKED"
    assert len(ready["blockers"]) >= 1


@pytest.mark.asyncio
async def test_scenario_13_human_verification_closure_success(async_client: AsyncClient):
    """Scenario 13: Authorized human engineer closes verification with mandatory rationale."""
    headers = auth_headers("u-w8-13", "w8-13@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Human Closure")

    # Attach physical evidence
    await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Lab DMM Rig",
            "description": "Output voltage 5.02V meets +/- 2% spec",
            "is_physical": True,
            "instrument": "Keithley DMM6500",
            "calibration_status": "CALIBRATED",
        },
        headers=headers,
    )

    # Human closes obligation
    close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/close",
        json={
            "decision": "VERIFIED",
            "rationale": "Measured bench values conform to specification with 15% design margin.",
            "actor": "Lead Hardware Engineer Jane Doe",
            "current_revision": 1,
        },
        headers=headers,
    )
    assert close_res.status_code == 200
    res_data = close_res.json()["data"]
    assert res_data["status"] == "SATISFIED"
    assert res_data["decision"] == "VERIFIED"
    assert res_data["closed_by"] == "Lead Hardware Engineer Jane Doe"
    assert "audit_event_id" in res_data


@pytest.mark.asyncio
async def test_scenario_14_human_verification_closure_waiver(async_client: AsyncClient):
    """Scenario 14: Human engineer waives verification requirement with mandatory waiver reason."""
    headers = auth_headers("u-w8-14", "w8-14@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Waiver Closure")

    close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/close",
        json={
            "decision": "WAIVED",
            "rationale": "Bench testing waived due to existing qualification on identical platform.",
            "waiver_reason": "Approved exemption ECO-7749 signed by Chief Engineer",
            "actor": "Principal Systems Engineer",
            "current_revision": 1,
        },
        headers=headers,
    )
    assert close_res.status_code == 200
    res_data = close_res.json()["data"]
    assert res_data["status"] == "NOT_APPLICABLE"
    assert res_data["decision"] == "WAIVED"
    assert res_data["waiver_reason"] is not None


@pytest.mark.asyncio
async def test_scenario_15_human_verification_closure_missing_rationale(async_client: AsyncClient):
    """Scenario 15: Closing verification without rationale is rejected."""
    headers = auth_headers("u-w8-15", "w8-15@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Missing Rationale")

    close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/close",
        json={
            "decision": "VERIFIED",
            "rationale": "   ",  # Blank rationale
            "actor": "Test Engineer",
        },
        headers=headers,
    )
    assert close_res.status_code == 422


@pytest.mark.asyncio
async def test_scenario_16_ai_unauthorized_closure_rejected(async_client: AsyncClient):
    """Scenario 16: AI actor attempting verification closure is rejected with 403."""
    headers = auth_headers("u-w8-16", "w8-16@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "AI Closure Rejection")

    ai_actors = ["ai-assistant", "agent-orchestrator", "copilot-model-v2", "bot-verifier"]
    for ai_actor in ai_actors:
        close_res = await async_client.post(
            f"/api/v1/cognitive/verification/{vr_id}/close",
            json={
                "decision": "VERIFIED",
                "rationale": "AI verified thermal calculation matches model.",
                "actor": ai_actor,
            },
            headers=headers,
        )
        assert close_res.status_code == 403
        assert "AI_UNAUTHORIZED_VERIFICATION_CLOSURE" in str(close_res.json())


@pytest.mark.asyncio
async def test_scenario_17_autonomous_closure_disabled(async_client: AsyncClient):
    """Scenario 17: AUTONOMOUS_VERIFICATION_CLOSURE = DISABLED invariant is enforced."""
    headers = auth_headers("u-w8-17", "w8-17@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Autonomous Closure")

    close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/close",
        json={
            "decision": "VERIFIED",
            "rationale": "Automated workflow auto-closure.",
            "actor": "model-autonomous-agent",
        },
        headers=headers,
    )
    assert close_res.status_code == 403
    assert "AI verification authority is NONE" in str(close_res.json())


@pytest.mark.asyncio
async def test_scenario_18_cross_tenant_isolation(async_client: AsyncClient):
    """Scenario 18: Tenant B cannot access or modify Tenant A's verification obligations."""
    headers_a = auth_headers("u-w8-18a", "w8-18a@tenant-a.test", tenant_id="tenant-w8-a")
    headers_b = auth_headers("u-w8-18b", "w8-18b@tenant-b.test", tenant_id="tenant-w8-b")

    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers_a, "Tenant A Rig")

    # Tenant B tries to inspect Tenant A's obligation -> 404
    obl_res = await async_client.get(
        f"/api/v1/cognitive/verification/{vr_id}",
        headers=headers_b,
    )
    assert obl_res.status_code == 404

    # Tenant B tries to attach evidence to Tenant A's obligation -> 404
    evi_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Unauthorized Tenant B Bench",
            "description": "Cross-tenant intrusion attempt",
            "is_physical": True,
        },
        headers=headers_b,
    )
    assert evi_res.status_code == 404


@pytest.mark.asyncio
async def test_scenario_19_zero_synthetic_scoring(async_client: AsyncClient):
    """Scenario 19: Prohibits synthetic scores in verification workspace and obligations."""
    headers = auth_headers("u-w8-19", "w8-19@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "Zero Scoring")

    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": proj_id,
            "circuit_id": circ_id,
            "user_request": "Audit verification completeness",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf_id = wf_res.json()["data"]["id"]

    ws_res = await async_client.get(
        f"/api/v1/cognitive/workflows/{wf_id}/verification",
        headers=headers,
    )
    assert ws_res.status_code == 200
    raw_json = ws_res.text

    forbidden_tokens = [
        "evidence_score",
        "verification_score",
        "verification_percentage",
        "confidence_score",
        "confidence_percentage",
        "readiness_score",
        "best_evidence",
    ]
    for token in forbidden_tokens:
        assert token not in raw_json, f"Forbidden synthetic score token '{token}' found in verification workspace"


@pytest.mark.asyncio
async def test_scenario_20_end_to_end_verification_lifecycle(async_client: AsyncClient):
    """Scenario 20: Full verification lifecycle: workflow -> workspace -> review gaps -> attach evidence -> human close."""
    headers = auth_headers("u-w8-20", "w8-20@quebet.test")
    proj_id, circ_id, rev_id, vr_id = await setup_circuit_and_review(async_client, headers, "End to End Lifecycle")

    # 1. Start cognitive workflow
    wf_res = await async_client.post(
        "/api/v1/cognitive/workflows",
        json={
            "project_id": proj_id,
            "circuit_id": circ_id,
            "user_request": "Execute end-to-end verification audit",
        },
        headers=headers,
    )
    assert wf_res.status_code == 201
    wf_id = wf_res.json()["data"]["id"]

    # 2. Get verification workspace
    ws_res = await async_client.get(
        f"/api/v1/cognitive/workflows/{wf_id}/verification",
        headers=headers,
    )
    assert ws_res.status_code == 200
    ws = ws_res.json()["data"]
    verified_before = ws["summary"]["verified_count"]

    # 3. Review obligation gaps (informational)
    rev_gap_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/review",
        headers=headers,
    )
    assert rev_gap_res.status_code == 200
    assert rev_gap_res.json()["data"]["authority"] == "INFORMATIONAL_ONLY"

    # 4. Attach traceable physical lab evidence
    evi_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/evidence",
        json={
            "evidence_type": "MEASUREMENT",
            "source": "Calibrated Bench Rig",
            "description": "Final acceptance measurement under worst-case loading",
            "value": "4.99",
            "unit": "V",
            "is_physical": True,
            "instrument": "Keysight 34461A",
            "calibration_status": "CALIBRATED",
        },
        headers=headers,
    )
    assert evi_res.status_code == 200

    # 5. Human engineer closes obligation
    close_res = await async_client.post(
        f"/api/v1/cognitive/verification/{vr_id}/close",
        json={
            "decision": "VERIFIED",
            "rationale": "Hardware bench test confirms voltage regulation satisfies all constraints.",
            "actor": "Chief Verification Engineer Dr. Smith",
            "current_revision": 1,
        },
        headers=headers,
    )
    assert close_res.status_code == 200
    assert close_res.json()["data"]["status"] == "SATISFIED"

    # 6. Re-inspect workspace -> verified count increments
    ws_final_res = await async_client.get(
        f"/api/v1/cognitive/workflows/{wf_id}/verification",
        headers=headers,
    )
    assert ws_final_res.status_code == 200
    ws_final = ws_final_res.json()["data"]
    assert ws_final["summary"]["verified_count"] == verified_before + 1
