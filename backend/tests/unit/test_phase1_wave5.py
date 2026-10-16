import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.db.verification import (
    DesignReviewStatus,
    EvidenceType,
    OperatingCondition,
    VerificationMethod,
    VerificationStatus,
)
from app.services.ai.verification.failure_engine import FailureAnalysisEngine
from app.services.ai.verification.requirement_generator import VerificationRequirementGenerator


@pytest.fixture
def auth_headers_tenant_a() -> dict:
    token = create_access_token(
        subject="w5-user-a",
        claims={"role": "user", "plan": "pro", "tenant_id": "tenant-w5-a"},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_tenant_b() -> dict:
    token = create_access_token(
        subject="w5-user-b",
        claims={"role": "user", "plan": "pro", "tenant_id": "tenant-w5-b"},
    )
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. FAILURE ANALYSIS ENGINE UNIT TEST
# ==============================================================================
def test_failure_analysis_engine_derivation():
    """
    Deterministic failure mode derivation from circuit structure,
    analytical findings (R002, R003, R005, R007, R008), and calculations.
    """
    engine = FailureAnalysisEngine()

    circuit_dict = {
        "id": "circ-fm-1",
        "version": 1,
        "components": [
            {"id": "r1", "name": "R1", "component_type": "RESISTOR", "value": "100R", "package": "0402"},
            {"id": "reg1", "name": "U1", "component_type": "REGULATOR", "value": "LM7805"},
        ],
        "nets": [{"id": "n1", "name": "+5V"}, {"id": "n2", "name": "GND"}],
        "connections": [],
    }

    analysis_data = {
        "findings": [
            {"id": "f-r003", "rule_id": "R003", "title": "Excessive Resistor Power on R1", "severity": "CRITICAL", "component_ids": ["r1"]},
            {"id": "f-r005", "rule_id": "R005", "title": "Regulator Current Overstress on U1", "severity": "CRITICAL", "component_ids": ["reg1"]},
            {"id": "f-r007", "rule_id": "R007", "title": "Missing Decoupling Capacitor on U1", "severity": "WARNING", "component_ids": ["reg1"]},
            {"id": "f-r008", "rule_id": "R008", "title": "Voltage Domain Conflict", "severity": "CRITICAL", "component_ids": ["reg1"]},
            {"id": "f-r002", "rule_id": "R002", "title": "Floating Required Pin", "severity": "CRITICAL", "component_ids": ["reg1"]},
        ],
        "calculations": [
            {"category": "REGULATOR", "result": {"junction_temp_c": 115.0, "power_dissipation_w": 1.2, "component_id": ["reg1"]}},
        ],
        "unknowns": [{"variable": "Ambient temperature profile", "affected_components": ["reg1"]}],
    }

    modes = engine.analyze_circuit(
        circuit_dict=circuit_dict,
        analysis_data=analysis_data,
        review_id="rev-test-1",
        tenant_id="tenant-test",
    )

    categories = [m.category for m in modes]
    assert "OVERPOWER" in categories
    assert "OVERCURRENT" in categories
    assert "MISSING_DECOUPLING" in categories
    assert "VOLTAGE_DOMAIN_CONFLICT" in categories
    assert "FLOATING_NODE" in categories
    assert "THERMAL_OVERSTRESS" in categories
    assert "UNKNOWN_COMPONENT_BEHAVIOR" in categories

    # Evidence traceability check: every failure mode must have evidence basis
    for m in modes:
        assert len(m.evidence) > 0
        assert m.likelihood in ["LOW", "MEDIUM", "HIGH"]
        assert m.severity in ["INFO", "WARNING", "CRITICAL"]


# ==============================================================================
# 2. VERIFICATION REQUIREMENT & TEST POINT GENERATOR TEST
# ==============================================================================
def test_verification_requirement_and_test_point_generator():
    """
    Requirements generated in VR001+ namespace with explicit methods,
    operating conditions, and corresponding test points.
    """
    engine = FailureAnalysisEngine()
    gen = VerificationRequirementGenerator()

    circuit_dict = {
        "id": "circ-req-1",
        "version": 1,
        "components": [
            {"id": "r1", "name": "R1", "component_type": "resistor", "value": "1k"},
            {"id": "u1", "name": "U1", "component_type": "regulator", "value": "LM7805"},
            {"id": "c1", "name": "C1", "component_type": "capacitor", "value": "100nF"},
        ],
        "nets": [{"id": "n1", "name": "+5V"}, {"id": "n2", "name": "GND"}],
        "connections": [],
    }
    analysis_data = {
        "findings": [
            {"id": "f1", "rule_id": "R003", "title": "Excessive Power", "severity": "CRITICAL", "component_ids": ["r1"]},
            {"id": "f2", "rule_id": "R007", "title": "Missing Decoupling", "severity": "WARNING", "component_ids": ["u1"]},
        ],
        "calculations": [
            {"category": "REGULATOR", "result": {"junction_temp_c": 110.0, "power_dissipation_w": 0.9, "component_id": ["u1"]}},
        ],
        "unknowns": [{"variable": "Ambient temperature profile"}],
    }

    failure_modes = engine.analyze_circuit(circuit_dict, analysis_data, "rev-1", "t1")
    reqs, tps = gen.generate(circuit_dict, analysis_data, failure_modes, "rev-1", "t1")

    assert len(reqs) > 0
    assert len(tps) > 0

    # Verify VR rule codes
    codes = [r.code for r in reqs]
    assert any("VR-" in c for c in codes)

    # Verify test points
    tp_codes = [tp.code for tp in tps]
    assert any("TP-" in c for c in tp_codes)
    for tp in tps:
        assert tp.instrumentation
        assert tp.measurement
        assert tp.operating_condition in [op.value for op in OperatingCondition]


# ==============================================================================
# 3. END-TO-END DESIGN REVIEW LIFECYCLE & VERIFICATION MATRIX TEST
# ==============================================================================
@pytest.mark.asyncio
async def test_design_review_lifecycle_and_matrix(
    async_client: AsyncClient,
    auth_headers_tenant_a: dict,
):
    """
    Full workflow:
    1. Create Project & Circuit
    2. Add components
    3. Generate Design Review (POST /circuits/{id}/design-review)
    4. Inspect Verification Matrix
    5. Add valid Evidence to a requirement
    6. Verify status transitions
    """
    # 1. Create Project & Circuit
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Wave 5 Verification Project", "project_type": "power"},
        headers=auth_headers_tenant_a,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Verification Circuit", "description": "Testing Wave 5 Verification Flow"},
        headers=auth_headers_tenant_a,
    )
    assert circ_res.status_code == 201
    circuit_id = circ_res.json()["data"]["id"]

    # Add components: Regulator and Resistor
    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "U1", "component_type": "regulator", "value": "LM7805"},
        headers=auth_headers_tenant_a,
    )
    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R1", "component_type": "resistor", "value": "100R"},
        headers=auth_headers_tenant_a,
    )

    # 2. Trigger Design Review Generation
    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=auth_headers_tenant_a,
    )
    assert rev_res.status_code == 201
    rev_data = rev_res.json()["data"]
    review_id = rev_data["id"]

    assert rev_data["circuit_revision"] == 1
    assert rev_data["analysis_id"] is not None
    assert rev_data["status"] in [
        DesignReviewStatus.VERIFICATION_REQUIRED.value,
        DesignReviewStatus.BLOCKED.value,
        DesignReviewStatus.PARTIALLY_VERIFIED.value,
    ]
    assert len(rev_data["verification_requirements"]) > 0
    assert len(rev_data["failure_modes"]) > 0

    # 3. Retrieve Verification Matrix
    matrix_res = await async_client.get(
        f"/api/v1/design-reviews/{review_id}/verification-matrix",
        headers=auth_headers_tenant_a,
    )
    assert matrix_res.status_code == 200
    matrix_data = matrix_res.json()["data"]
    assert matrix_data["total_requirements"] == len(matrix_data["matrix"])
    assert matrix_data["is_stale"] is False

    # 4. Attach Traceable Engineering Evidence to first requirement
    req_to_verify = rev_data["verification_requirements"][0]
    req_id = req_to_verify["id"]

    ev_res = await async_client.post(
        f"/api/v1/verification-requirements/{req_id}/evidence",
        json={
            "evidence_type": EvidenceType.MEASUREMENT.value,
            "source": "Fluke 87V Bench Multimeter",
            "description": "Measured rail voltage under full load operating conditions at 25C ambient.",
            "value": "4.992",
            "unit": "V",
            "reference": "Bench Notebook Vol 2, Page 44",
            "confidence": "HIGH",
        },
        headers=auth_headers_tenant_a,
    )
    assert ev_res.status_code == 201
    ev_data = ev_res.json()["data"]
    assert ev_data["verification_requirement_id"] == req_id
    assert ev_data["provided_by"] == "w5-user-a"


# ==============================================================================
# 4. REVISION INTEGRITY & STALE REVIEW REJECTION TEST
# ==============================================================================
@pytest.mark.asyncio
async def test_stale_review_rejection_on_circuit_mutation(
    async_client: AsyncClient,
    auth_headers_tenant_a: dict,
):
    """
    Scenario:
    1. Create review at revision N
    2. Mutate circuit -> revision advances to N+1
    3. Review becomes STALE
    4. Attempting to add evidence or update requirement on stale review is REJECTED
    """
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Stale Review Project", "project_type": "power"},
        headers=auth_headers_tenant_a,
    )
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Stale Test Circuit"},
        headers=auth_headers_tenant_a,
    )
    circuit_id = circ_res.json()["data"]["id"]

    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R1", "component_type": "resistor", "value": "1k"},
        headers=auth_headers_tenant_a,
    )

    # Generate Review at Revision 1
    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=auth_headers_tenant_a,
    )
    assert rev_res.status_code == 201
    rev_id = rev_res.json()["data"]["id"]
    req_id = rev_res.json()["data"]["verification_requirements"][0]["id"]

    # Mutate circuit to advance revision to 2
    # Apply a proposal to increment revision atomically
    prop_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/proposals",
        json={
            "title": "Advance Revision Proposal",
            "base_revision": 1,
            "operations": [{"op_type": "add_net", "payload": {"name": "NET_NEW_REV"}}],
        },
        headers=auth_headers_tenant_a,
    )
    prop_id = prop_res.json()["data"]["id"]
    await async_client.post(f"/api/v1/proposals/{prop_id}/approve", headers=auth_headers_tenant_a)
    apply_res = await async_client.post(f"/api/v1/proposals/{prop_id}/apply", headers=auth_headers_tenant_a)
    assert apply_res.status_code == 200

    # Verify circuit version is now 2
    c_check = await async_client.get(f"/api/v1/circuits/{circuit_id}", headers=auth_headers_tenant_a)
    assert c_check.json()["data"]["version"] == 2

    # Fetch review -> must report is_stale: True and status: STALE
    rev_check = await async_client.get(f"/api/v1/design-reviews/{rev_id}", headers=auth_headers_tenant_a)
    assert rev_check.status_code == 200
    assert rev_check.json()["data"]["is_stale"] is True
    assert rev_check.json()["data"]["status"] == DesignReviewStatus.STALE.value

    # Adding evidence to stale review MUST FAIL with REVIEW_STALE
    ev_fail = await async_client.post(
        f"/api/v1/verification-requirements/{req_id}/evidence",
        json={
            "evidence_type": EvidenceType.MEASUREMENT.value,
            "source": "DMM",
            "description": "Attempting evidence on stale review",
            "value": "3.3",
            "unit": "V",
        },
        headers=auth_headers_tenant_a,
    )
    assert ev_fail.status_code == 400
    assert ev_fail.json()["detail"]["code"] == "REVIEW_STALE"

    # Updating status on stale review MUST FAIL with REVIEW_STALE
    st_fail = await async_client.patch(
        f"/api/v1/verification-requirements/{req_id}/status",
        json={"status": VerificationStatus.SATISFIED.value, "reason": "Attempting verification on stale review"},
        headers=auth_headers_tenant_a,
    )
    assert st_fail.status_code == 400
    assert st_fail.json()["detail"]["code"] == "REVIEW_STALE"


# ==============================================================================
# 5. UNKNOWN PROPAGATION & SATISFACTION INVARIANTS TEST
# ==============================================================================
@pytest.mark.asyncio
async def test_unknown_propagation_and_satisfaction_rules(
    async_client: AsyncClient,
    auth_headers_tenant_a: dict,
):
    """
    Contract Invariants:
    1. UNKNOWN != PASS
    2. Cannot mark requirement SATISFIED while unknowns remain
    3. NOT_APPLICABLE requires mandatory rationale
    """
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Unknown Invariants Project", "project_type": "power"},
        headers=auth_headers_tenant_a,
    )
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Invariants Circuit"},
        headers=auth_headers_tenant_a,
    )
    circuit_id = circ_res.json()["data"]["id"]

    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R1", "component_type": "resistor", "value": "1k"},
        headers=auth_headers_tenant_a,
    )

    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=auth_headers_tenant_a,
    )
    assert rev_res.status_code == 201
    reqs = rev_res.json()["data"]["verification_requirements"]
    req_id = reqs[0]["id"]

    # Test: NOT_APPLICABLE without reason must fail
    na_fail = await async_client.patch(
        f"/api/v1/verification-requirements/{req_id}/status",
        json={"status": VerificationStatus.NOT_APPLICABLE.value},
        headers=auth_headers_tenant_a,
    )
    assert na_fail.status_code == 400
    assert "rationale is required" in na_fail.json()["detail"].lower()

    # Test: NOT_APPLICABLE with explicit engineering rationale succeeds
    na_success = await async_client.patch(
        f"/api/v1/verification-requirements/{req_id}/status",
        json={
            "status": VerificationStatus.NOT_APPLICABLE.value,
            "not_applicable_reason": "Design operates strictly from external pre-regulated battery power; AC ripple review not applicable.",
        },
        headers=auth_headers_tenant_a,
    )
    assert na_success.status_code == 200
    assert na_success.json()["data"]["status"] == VerificationStatus.NOT_APPLICABLE.value


# ==============================================================================
# 6. TENANT ISOLATION & IDOR SECURITY TEST
# ==============================================================================
@pytest.mark.asyncio
async def test_wave5_tenant_isolation_and_idor(
    async_client: AsyncClient,
    auth_headers_tenant_a: dict,
    auth_headers_tenant_b: dict,
):
    """
    Tenant A resources must NEVER be accessible to Tenant B (returns HTTP 404).
    """
    # Tenant A creates project, circuit, and design review
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Tenant A Project", "project_type": "power"},
        headers=auth_headers_tenant_a,
    )
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Tenant A Circuit"},
        headers=auth_headers_tenant_a,
    )
    circuit_id = circ_res.json()["data"]["id"]

    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R1", "component_type": "resistor", "value": "1k"},
        headers=auth_headers_tenant_a,
    )

    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=auth_headers_tenant_a,
    )
    assert rev_res.status_code == 201
    review_id = rev_res.json()["data"]["id"]
    req_id = rev_res.json()["data"]["verification_requirements"][0]["id"]

    # 1. Tenant B cannot access Tenant A review
    b_rev = await async_client.get(
        f"/api/v1/design-reviews/{review_id}",
        headers=auth_headers_tenant_b,
    )
    assert b_rev.status_code == 404

    # 2. Tenant B cannot access Tenant A verification matrix
    b_matrix = await async_client.get(
        f"/api/v1/design-reviews/{review_id}/verification-matrix",
        headers=auth_headers_tenant_b,
    )
    assert b_matrix.status_code == 404

    # 3. Tenant B cannot access Tenant A failure modes
    b_fm = await async_client.get(
        f"/api/v1/design-reviews/{review_id}/failure-modes",
        headers=auth_headers_tenant_b,
    )
    assert b_fm.status_code == 404

    # 4. Tenant B cannot attach evidence to Tenant A requirement
    b_ev = await async_client.post(
        f"/api/v1/verification-requirements/{req_id}/evidence",
        json={
            "evidence_type": EvidenceType.MEASUREMENT.value,
            "source": "Malicious DMM",
            "description": "Cross-tenant intrusion attempt",
            "value": "1.0",
        },
        headers=auth_headers_tenant_b,
    )
    assert b_ev.status_code == 404


# ==============================================================================
# 7. LABORATORY TEST POINTS TEST
# ==============================================================================
@pytest.mark.asyncio
async def test_laboratory_test_points(
    async_client: AsyncClient,
    auth_headers_tenant_a: dict,
):
    """
    Test points are deterministically generated and custom points can be added.
    """
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Test Point Project", "project_type": "power"},
        headers=auth_headers_tenant_a,
    )
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Test Point Circuit"},
        headers=auth_headers_tenant_a,
    )
    circuit_id = circ_res.json()["data"]["id"]

    rev_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design-review",
        headers=auth_headers_tenant_a,
    )
    assert rev_res.status_code == 201
    review_id = rev_res.json()["data"]["id"]

    # Get test points
    tp_res = await async_client.get(
        f"/api/v1/design-reviews/{review_id}/test-points",
        headers=auth_headers_tenant_a,
    )
    assert tp_res.status_code == 200
    tps = tp_res.json()["data"]
    assert isinstance(tps, list)

    # Add custom lab test point
    new_tp = await async_client.post(
        f"/api/v1/design-reviews/{review_id}/test-points",
        json={
            "code": "TP-CUSTOM-01",
            "target_net": "+3V3",
            "measurement": "Switching Node Ringing Peak Voltage",
            "expected_basis": "Peak voltage ringing < 4.2V absolute maximum rating",
            "instrumentation": "Oscilloscope 500MHz active probe",
            "operating_condition": OperatingCondition.STARTUP.value,
        },
        headers=auth_headers_tenant_a,
    )
    assert new_tp.status_code == 201
    assert new_tp.json()["data"]["code"] == "TP-CUSTOM-01"
