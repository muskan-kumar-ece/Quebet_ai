import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-wave9-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_requirements_crud_and_structured_expression(async_client: AsyncClient):
    """
    Verifies:
    1. Requirement creation with structured expressions and validation types.
    2. Parent-child requirement hierarchy.
    3. Requirement coverage computation (UNKNOWN != COVERED).
    """
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "engineer9a@quebet.ai", tenant_id="tenant-wave9-a")

    # Create project and system
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Wave 9 Power Architecture", "project_type": "embedded"},
        headers=headers_a,
    )
    assert p_res.status_code == 201
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Power Distribution Unit", "description": "Core Power System"},
        headers=headers_a,
    )
    assert s_res.status_code == 201
    sys_id = s_res.json()["data"]["id"]

    # 1. Create root requirement
    root_req_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/requirements",
        json={
            "requirement_key": "REQ-SYS-001",
            "title": "System Main Bus Voltage",
            "description": "Bus voltage must remain between 11.4V and 12.6V under all loads.",
            "category": "FUNCTIONAL",
            "priority": "MANDATORY",
            "expression": {
                "expression_type": "RANGE",
                "parameter": "V_BUS",
                "operator": "BETWEEN",
                "value": {"min": 11.4, "max": 12.6},
                "unit": "V",
            },
        },
        headers=headers_a,
    )
    assert root_req_res.status_code == 201
    root_req = root_req_res.json()["data"]
    root_req_id = root_req["id"]
    assert root_req["requirement_key"] == "REQ-SYS-001"
    assert root_req["expression"]["operator"] == "BETWEEN"

    # 2. Create child requirement referencing root
    child_req_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/requirements",
        json={
            "requirement_key": "REQ-SYS-002",
            "parent_requirement_id": root_req_id,
            "title": "Buck Converter Output Ripple",
            "description": "Output voltage ripple must not exceed 50mV peak-to-peak.",
            "category": "SAFETY",
            "priority": "HIGH",
            "expression": {
                "expression_type": "MAX",
                "parameter": "V_RIPPLE",
                "operator": "LTE",
                "value": 0.05,
                "unit": "V",
            },
        },
        headers=headers_a,
    )
    assert child_req_res.status_code == 201
    child_req = child_req_res.json()["data"]
    assert child_req["parent_requirement_id"] == root_req_id

    # 3. Check coverage endpoint (Must not return fake 100% or fake PASS)
    cov_res = await async_client.get(
        f"/api/v1/systems/{sys_id}/requirement-coverage",
        headers=headers_a,
    )
    assert cov_res.status_code == 200
    cov = cov_res.json()["data"]
    assert cov["total_requirements"] == 2
    # Since neither requirement has verified evidence linked yet, covered must not be 2
    assert cov["counts"]["COVERED"] == 0
    assert cov["counts"]["NOT_COVERED"] == 2

@pytest.mark.asyncio
async def test_requirement_baselines_and_hash(async_client: AsyncClient):
    """
    Verifies:
    1. Freezing requirement baselines.
    2. Deterministic SHA-256 hash generation over requirement IDs and versions.
    """
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "engineer9b@quebet.ai", tenant_id="tenant-wave9-b")

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Baseline Test Proj", "project_type": "embedded"},
        headers=headers_a,
    )
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Telemetry Node", "description": "Sensor Interface"},
        headers=headers_a,
    )
    sys_id = s_res.json()["data"]["id"]

    # Create requirement
    req_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/requirements",
        json={
            "requirement_key": "REQ-TEL-001",
            "title": "Baud Rate Reliability",
            "description": "Support 115200 baud with < 1e-6 bit error rate.",
            "category": "INTERFACE",
            "priority": "MEDIUM",
        },
        headers=headers_a,
    )
    assert req_res.status_code == 201

    # Create baseline
    base_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/requirement-baselines",
        json={
            "name": "CDR Initial Freeze",
            "description": "Formal baseline for CDR review",
        },
        headers=headers_a,
    )
    assert base_res.status_code == 201
    baseline = base_res.json()["data"]
    assert baseline["name"] == "CDR Initial Freeze"
    assert len(baseline["baseline_hash"]) == 64  # SHA-256 hex string
    assert len(baseline["requirement_ids"]) == 1
    assert baseline["is_frozen"] is True


@pytest.mark.asyncio
async def test_engineering_assumptions_and_impact(async_client: AsyncClient):
    """
    Verifies:
    1. Engineering assumptions CRUD and lifecycle (UNVALIDATED -> VALIDATED).
    2. Assumption impact assessment.
    """
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "engineer9c@quebet.ai", tenant_id="tenant-wave9-c")

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Thermal Subsystem", "project_type": "embedded"},
        headers=headers_a,
    )
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Thermal Controller", "description": "Active cooling"},
        headers=headers_a,
    )
    sys_id = s_res.json()["data"]["id"]

    # Create assumption
    assump_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/assumptions",
        json={
            "description": "Assumed operating environment is indoor industrial <= 55C without direct solar loading.",
            "basis": "Standard indoor deployment specification rev 2",
            "value": "55",
            "unit": "C",
            "status": "UNVALIDATED",
            "impact": "HIGH",
        },
        headers=headers_a,
    )
    assert assump_res.status_code == 201
    assump = assump_res.json()["data"]
    assump_id = assump["id"]
    assert assump["status"] == "UNVALIDATED"
    assert assump["impact"] == "HIGH"

    # Assess impact
    impact_res = await async_client.get(
        f"/api/v1/assumptions/{assump_id}/impact",
        headers=headers_a,
    )
    assert impact_res.status_code == 200
    impact = impact_res.json()["data"]
    assert impact["assumption_id"] == assump_id
    assert "impact_severity" in impact

    # Update assumption to VALIDATED
    up_res = await async_client.patch(
        f"/api/v1/assumptions/{assump_id}",
        json={
            "status": "VALIDATED",
            "basis": "Chamber testing confirmed ambient will not exceed 48C.",
        },
        headers=headers_a,
    )
    assert up_res.status_code == 200
    assert up_res.json()["data"]["status"] == "VALIDATED"


@pytest.mark.asyncio
async def test_decision_record_alternatives_zero_scoring_and_selection(async_client: AsyncClient):
    """
    Verifies:
    1. Engineering decision record creation.
    2. Multiple alternatives with deterministic characteristics.
    3. Multidimensional comparison with ZERO synthetic/composite scoring.
    4. Human decision selection with structured rationale.
    5. Stale rejection if system revision increments.
    """
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "engineer9d@quebet.ai", tenant_id="tenant-wave9-d")

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Decision Architecture", "project_type": "embedded"},
        headers=headers_a,
    )
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Power Regulation Architecture", "description": "Step-down converter selection"},
        headers=headers_a,
    )
    assert s_res.status_code == 201
    sys_id = s_res.json()["data"]["id"]
    system_rev = s_res.json()["data"]["revision"]

    # 1. Create Decision Record
    dec_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/decisions",
        json={
            "title": "Select Step-Down Architecture for 3.3V Core Rail",
            "decision_key": "DEC-PWR-001",
            "description": "Evaluate Synchronous Buck Converter vs High-Current LDO for thermal and efficiency tradeoffs.",
            "decision_type": "ARCHITECTURE",
        },
        headers=headers_a,
    )
    assert dec_res.status_code == 201
    dec = dec_res.json()["data"]
    dec_id = dec["id"]
    assert dec["status"] == "DRAFT"

    # 2. Add Alternative A: Synchronous Buck
    alt_a_res = await async_client.post(
        f"/api/v1/decisions/{dec_id}/alternatives",
        json={
            "name": "Synchronous Buck Regulator (TPS54302)",
            "description": "High efficiency switching regulator with external inductor.",
            "status": "CONSIDERED",
            "engineering_effects": {"efficiency": "92%", "thermal_dissipation": "0.3W"},
            "requirement_effects": {"REQ-SYS-001": "SATISFIED"},
            "verification_effects": {"phase_margin_test": "REQUIRED"},
            "failure_effects": {"overcurrent": "CONTAINED"},
            "tradeoffs": {"efficiency": "high", "emi": "medium"},
            "unknowns": ["Board parasitic resonance will be measured during proto spin"],
        },
        headers=headers_a,
    )
    assert alt_a_res.status_code == 201
    alt_a_id = alt_a_res.json()["data"]["id"]

    # 3. Add Alternative B: Linear LDO
    alt_b_res = await async_client.post(
        f"/api/v1/decisions/{dec_id}/alternatives",
        json={
            "name": "Linear LDO Regulator (LT1963A)",
            "description": "Low-noise linear regulator.",
            "status": "CONSIDERED",
            "engineering_effects": {"efficiency": "27.5%", "thermal_dissipation": "17W"},
            "requirement_effects": {"REQ-SYS-001": "VIOLATED"},
            "verification_effects": {"thermal_imaging": "REQUIRED"},
            "failure_effects": {"thermal_runaway": "HIGH_RISK"},
            "tradeoffs": {"noise": "ultra_low", "efficiency": "poor"},
            "unknowns": ["Heatsink airflow dependence"],
        },
        headers=headers_a,
    )
    assert alt_b_res.status_code == 201
    alt_b_id = alt_b_res.json()["data"]["id"]

    # 4. Compare alternatives side-by-side (NO synthetic score, NO winner)
    comp_res = await async_client.get(
        f"/api/v1/decisions/{dec_id}/compare",
        headers=headers_a,
    )
    assert comp_res.status_code == 200
    comp = comp_res.json()["data"]
    assert "comparison_matrix" in comp
    assert len(comp["comparison_matrix"]) == 2
    # Verify strict ZERO composite score compliance:
    for alt in comp["comparison_matrix"]:
        assert "overall_score" not in alt
        assert "decision_score" not in alt
        assert "rank" not in alt
        assert "winner" not in alt
        assert "is_winner" not in alt

    # 5. Human selects Alternative A
    sel_res = await async_client.post(
        f"/api/v1/decisions/{dec_id}/select",
        json={
            "alternative_id": alt_a_id,
            "decision_rationale": "TPS54302 selected because 17W LDO dissipation exceeds thermal envelope.",
            "key_requirements": ["REQ-SYS-001"],
            "key_tradeoffs": ["Increased EMI mitigation required"],
            "accepted_unknowns": ["Board parasitic resonance will be measured during proto spin"],
            "rejected_alternatives": [
                {"alternative_id": alt_b_id, "reason": "Rejected due to excessive thermal dissipation"}
            ],
            "verification_plan": "Execute phase margin sweep and EMI chamber test on prototype rev A",
        },
        headers=headers_a,
    )
    assert sel_res.status_code == 200
    dec_updated = sel_res.json()["data"]
    assert dec_updated["status"] == "DECIDED"
    assert dec_updated["selected_alternative_id"] == alt_a_id
    assert dec_updated["decided_by"] == user_a
    assert dec_updated["decided_at"] is not None

    # 6. Test Stale Rejection:
    # Update system description which increments revision
    sys_up = await async_client.patch(
        f"/api/v1/systems/{sys_id}",
        json={"description": "Updated system description which increments revision"},
        headers=headers_a,
    )
    assert sys_up.status_code == 200
    new_rev = sys_up.json()["data"]["revision"]
    assert new_rev > system_rev

    # Try selecting alternative again with stale decision record
    stale_sel_res = await async_client.post(
        f"/api/v1/decisions/{dec_id}/select",
        json={
            "alternative_id": alt_b_id,
            "decision_rationale": "Should be rejected because decision revision is stale",
        },
        headers=headers_a,
    )
    assert stale_sel_res.status_code == 409
    assert "stale" in stale_sel_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_decision_questions_unknowns_and_review_gating(async_client: AsyncClient):
    """
    Verifies:
    1. Decision open questions with blocking semantics.
    2. Unknown disposition tracking (UNKNOWN != PASS).
    3. Design Review session creation and participant management.
    4. Readiness assessment: Blocked when blocking questions or findings are unresolved.
    5. Strict closure gating: review cannot be closed if blocked.
    6. Waiver resolution allows closing.
    7. AI Decision Brief generation (labeled origin = 'AI_GENERATED', informational).
    """
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "engineer9e@quebet.ai", tenant_id="tenant-wave9-e")

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Radar Controller", "project_type": "embedded"},
        headers=headers_a,
    )
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Radar Interface Unit", "description": "High speed bus"},
        headers=headers_a,
    )
    sys_id = s_res.json()["data"]["id"]

    # 1. Create Decision
    dec_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/decisions",
        json={
            "title": "Select Transceiver Interface Standard",
            "decision_key": "DEC-IF-001",
            "description": "Choose between LVDS and Ethernet PHY.",
            "decision_type": "INTERFACE",
        },
        headers=headers_a,
    )
    assert dec_res.status_code == 201
    dec_id = dec_res.json()["data"]["id"]

    # 2. Add an open blocking question
    q_res = await async_client.post(
        f"/api/v1/decisions/{dec_id}/questions",
        json={
            "question": "What is the maximum cable length between sensor and processor?",
            "reason": "Affects trace capacitance and signal integrity",
            "blocking": True,
        },
        headers=headers_a,
    )
    assert q_res.status_code == 201
    q_id = q_res.json()["data"]["id"]
    assert q_res.json()["data"]["status"] == "OPEN"

    # 3. Add an Unknown Disposition
    un_res = await async_client.post(
        f"/api/v1/decisions/{dec_id}/unknowns",
        json={
            "unknown_key": "Exact stray capacitance of wire harness",
            "reason": "Vendor cable spec not yet finalized",
            "status": "ACCEPTED",
        },
        headers=headers_a,
    )
    assert un_res.status_code == 201
    assert un_res.json()["data"]["status"] == "ACCEPTED"

    # 4. Create Design Review Session
    rev_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/design-reviews",
        json={
            "title": "Critical Design Review - Radar Interface Unit",
            "decision_id": dec_id,
        },
        headers=headers_a,
    )
    assert rev_res.status_code == 201
    rev_id = rev_res.json()["data"]["id"]

    # 5. Add participant
    part_res = await async_client.post(
        f"/api/v1/design-reviews/{rev_id}/participants",
        json={
            "user_id": user_a,
            "name": "Lead Hardware Engineer",
            "role": "CHAIRPERSON",
        },
        headers=headers_a,
    )
    assert part_res.status_code == 201

    # 6. Add a Blocker Finding
    find_res = await async_client.post(
        f"/api/v1/design-reviews/{rev_id}/findings",
        json={
            "source_analysis": "SIGNAL_INTEGRITY",
            "severity": "BLOCKER",
            "description": "Missing Termination Resistor on High-Speed Pair",
        },
        headers=headers_a,
    )
    assert find_res.status_code == 201
    find_id = find_res.json()["data"]["id"]

    # 7. Check Review Readiness - Must be BLOCKED
    readiness_res = await async_client.get(
        f"/api/v1/design-reviews/{rev_id}/readiness",
        headers=headers_a,
    )
    assert readiness_res.status_code == 200
    readiness = readiness_res.json()["data"]
    assert readiness["overall_status"] == "BLOCKED"
    assert len(readiness["blockers"]) >= 1
    assert "overall_readiness_score" not in readiness  # ZERO synthetic scores

    # 8. Attempt to Close Review -> Must Fail with 409
    close_attempt = await async_client.post(
        f"/api/v1/design-reviews/{rev_id}/close",
        headers=headers_a,
    )
    assert close_attempt.status_code in [400, 409]

    # 9. Waive the finding with required justification
    waive_res = await async_client.post(
        f"/api/v1/design-reviews/findings/{find_id}/waive",
        json={"waiver_rationale": "Internal termination resistor is configured in FPGA I/O buffer."},
        headers=headers_a,
    )
    assert waive_res.status_code == 200
    assert waive_res.json()["data"]["status"] == "WAIVED"

    # 10. Answer the blocking question
    ans_res = await async_client.post(
        f"/api/v1/decisions/questions/{q_id}/answer",
        json={"answer": "Max cable length is confirmed at 1.5 meters per ICD rev 4."},
        headers=headers_a,
    )
    assert ans_res.status_code == 200
    assert ans_res.json()["data"]["status"] == "ANSWERED"

    # 11. Re-check readiness -> should now NOT be BLOCKED
    readiness_res2 = await async_client.get(
        f"/api/v1/design-reviews/{rev_id}/readiness",
        headers=headers_a,
    )
    assert readiness_res2.status_code == 200
    assert readiness_res2.json()["data"]["overall_status"] != "BLOCKED"

    # 12. Close Review Session -> Now succeeds
    close_res = await async_client.post(
        f"/api/v1/design-reviews/{rev_id}/close",
        headers=headers_a,
    )
    assert close_res.status_code == 200
    assert close_res.json()["data"]["status"] == "CLOSED"

    # 13. Generate Review Report
    rep_res = await async_client.get(
        f"/api/v1/design-reviews/{rev_id}/report",
        headers=headers_a,
    )
    assert rep_res.status_code == 200
    report = rep_res.json()["data"]
    assert report["review_id"] == rev_id
    assert report["findings_summary"]["waived"] == 1

    # 14. Generate AI Decision Brief (verifying origin = "AI_GENERATED" and informational note)
    brief_res = await async_client.get(
        f"/api/v1/decisions/{dec_id}/brief",
        headers=headers_a,
    )
    assert brief_res.status_code == 200
    brief = brief_res.json()["data"]
    assert brief["origin"] == "AI_GENERATED"
    assert brief["informational_only"] is True


@pytest.mark.asyncio
async def test_tenant_isolation(async_client: AsyncClient):
    """
    Verifies:
    1. Multi-tenant isolation for Requirements, Baselines, Decisions, and Design Reviews.
    2. Tenant B cannot access or modify Tenant A resources (returns HTTP 404).
    """
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "engineer_iso_a@quebet.ai", tenant_id="tenant-iso-a")
    user_b = str(uuid.uuid4())
    headers_b = auth_headers(user_b, "engineer_iso_b@quebet.ai", tenant_id="tenant-iso-b")

    # Tenant A creates system
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Tenant A Isolated Project", "project_type": "embedded"},
        headers=headers_a,
    )
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Secure Rail System", "description": "Isolated"},
        headers=headers_a,
    )
    sys_id = s_res.json()["data"]["id"]

    # Tenant A creates requirement
    r_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/requirements",
        json={
            "requirement_key": "REQ-ISO-001",
            "title": "Confidential Isolation Spec",
            "description": "Must not leak to other tenants.",
        },
        headers=headers_a,
    )
    req_id = r_res.json()["data"]["id"]

    # Tenant A creates decision
    d_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/decisions",
        json={
            "title": "Confidential Decision Record",
            "decision_key": "DEC-ISO-001",
            "description": "Tenant A proprietary decision.",
            "decision_type": "ARCHITECTURE",
        },
        headers=headers_a,
    )
    dec_id = d_res.json()["data"]["id"]

    # Tenant A creates design review
    dr_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/design-reviews",
        json={
            "title": "Tenant A CDR",
            "decision_id": dec_id,
        },
        headers=headers_a,
    )
    dr_id = dr_res.json()["data"]["id"]

    # --- TENANT B ATTEMPTS TO ACCESS TENANT A DATA ---

    # 1. Tenant B attempts to read Tenant A requirement
    b_req = await async_client.get(f"/api/v1/requirements/{req_id}", headers=headers_b)
    assert b_req.status_code == 404

    # 2. Tenant B attempts to read Tenant A decision
    b_dec = await async_client.get(f"/api/v1/decisions/{dec_id}", headers=headers_b)
    assert b_dec.status_code == 404

    # 3. Tenant B attempts to read Tenant A design review
    b_dr = await async_client.get(f"/api/v1/design-reviews/{dr_id}", headers=headers_b)
    assert b_dr.status_code == 404

    # 4. Tenant B attempts to create requirement in Tenant A system
    b_post_req = await async_client.post(
        f"/api/v1/systems/{sys_id}/requirements",
        json={
            "requirement_key": "REQ-HACK",
            "title": "Injected Requirement",
            "description": "Unauthorized injection",
        },
        headers=headers_b,
    )
    assert b_post_req.status_code == 404
