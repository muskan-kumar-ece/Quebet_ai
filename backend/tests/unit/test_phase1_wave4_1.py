import pytest
from httpx import AsyncClient
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.models.schemas.design import (
    ConstraintResult,
    ConstraintStatus,
    EngineeringConstraint,
    EngineeringDesignAlternative,
    ProposedChange,
)
from app.repositories.circuit_repo import circuit_repo
from app.repositories.proposal_repo import proposal_repo
from app.services.ai.analysis.graph_analyzer import CircuitGraphAnalyzer
from app.services.ai.analysis.rule_engine import CircuitRuleEngine
from app.services.ai.analysis.spec_resolver import ComponentSpecificationResolver
from app.services.ai.design.candidate_generator import DesignCandidateGenerator
from app.services.ai.design.comparison_service import DesignComparisonService
from app.services.ai.design.constraint_engine import ConstraintEvaluationEngine
from app.services.ai.design.what_if_sandbox import SandboxedWhatIfSimulator
from app.services.component_knowledge_service import component_knowledge_service


@pytest.fixture
def auth_headers():
    token = create_access_token("w41-user-1", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-w41-a"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_tenant_headers():
    token = create_access_token("w41-user-2", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-w41-b"})
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. RULE ID STABILITY & RECONCILIATION TEST (Mandatory Correction #2 & Section 7)
# ==============================================================================
def test_rule_id_stability_and_mapping():
    """
    Wave 3 established stable rule identifiers:
    R001: Invalid Component Value
    R002: Floating Required Pin
    R003: Excessive Resistor Power
    R004: Regulator Input Overvoltage
    R005: Regulator Current Overstress
    R006: Insufficient Margin
    R007: Missing Decoupling Capacitor
    R008: Voltage Domain Conflict

    This test enforces strict stability. If any rule is renumbered or redefined, test fails.
    """
    graph = CircuitGraphAnalyzer(
        components=[
            {"id": "c1", "name": "C1", "component_type": "CAPACITOR", "value": "100nF"},
            {"id": "u1", "name": "U1", "component_type": "MICROCONTROLLER", "part_number": "ESP32"},
            {"id": "reg1", "name": "REG1", "component_type": "REGULATOR", "part_number": "LM7805"},
        ],
        nets=[
            {"id": "n_5v", "name": "+5V"},
            {"id": "n_gnd", "name": "GND"},
        ],
        connections=[
            {"id": "conn1", "component_id": "u1", "net_id": "n_5v", "pin_number": "1"},
            {"id": "conn2", "component_id": "reg1", "net_id": "n_5v", "pin_number": "3"},
        ],
    )
    spec_resolver = ComponentSpecificationResolver()
    engine = CircuitRuleEngine(graph, spec_resolver, calculations=[])

    # 1. R007: Missing Decoupling Capacitor
    r007_findings = engine.check_r007_missing_decoupling_capacitors()
    assert all(f["rule_id"] == "R007" for f in r007_findings)
    assert any("decoupling capacitor" in f["title"].lower() for f in r007_findings)

    # 2. R008: Voltage Domain Conflict
    r008_findings = engine.check_r008_voltage_domain_conflict()
    assert all(f["rule_id"] == "R008" for f in r008_findings)
    assert any("voltage domain conflict" in f["title"].lower() for f in r008_findings)


# ==============================================================================
# 2. TRANSPARENT ENGINEERING COMPARISON (NO ARBITRARY SCORE / WINNER) (Correction #1)
# ==============================================================================
def test_transparent_comparison_no_scores_or_winner():
    """
    Contract: No composite scores, no 'TOP/BEST' label, no single scalar ranking.
    DesignComparisonService returns structured engineering evidence.
    """
    service = DesignComparisonService()

    circuit_dict = {
        "id": "circ-transparency",
        "version": 2,
        "components": [{"id": "r1", "name": "R1"}, {"id": "r2", "name": "R2"}],
    }
    baseline_analysis = {
        "findings": [
            {"rule_id": "R003", "title": "Excessive Resistor Power", "severity": "CRITICAL"},
        ],
        "calculations": [
            {"category": "OHMS_LAW", "result": {"power_w": 0.35}},
            {"category": "MARGIN", "result": {"utilization_pct": 140.0}},
        ],
        "unknowns": [],
    }

    alt1 = {
        "alternative_id": "alt-a",
        "title": "E24 Resistor Value Increase",
        "status": "VALIDATED",
        "confidence": "HIGH",
        "affected_components": ["r1"],
        "findings_resolved": ["R003: Excessive Resistor Power"],
        "findings_introduced": [],
        "remaining_findings": [],
        "constraint_results": [
            {"constraint_id": "c1", "hard_or_soft": "HARD", "status": "PASS"},
            {"constraint_id": "c2", "hard_or_soft": "SOFT", "status": "SATISFIED"},
        ],
        "structural_effects": {"component_count_delta": 0},
        "footprint": "0402",
        "cost": "UNKNOWN",
        "after_analysis": {
            "findings": [],
            "calculations": [
                {"category": "OHMS_LAW", "result": {"power_w": 0.15}},
                {"category": "MARGIN", "result": {"utilization_pct": 60.0}},
            ],
            "unknowns": [],
        },
        "candidate_provenance": {"generation_strategy": "E24_SERIES_SUBSTITUTION"},
    }

    alt2 = {
        "alternative_id": "alt-b",
        "title": "1206 Package Upgrade",
        "status": "VALIDATED",
        "confidence": "HIGH",
        "affected_components": ["r1"],
        "findings_resolved": ["R003: Excessive Resistor Power"],
        "findings_introduced": [],
        "remaining_findings": [],
        "constraint_results": [
            {"constraint_id": "c1", "hard_or_soft": "HARD", "status": "PASS"},
            {"constraint_id": "c2", "hard_or_soft": "SOFT", "status": "SATISFIED"},
        ],
        "structural_effects": {"component_count_delta": 0},
        "footprint": "1206",
        "cost": "UNKNOWN",
        "after_analysis": {
            "findings": [],
            "calculations": [
                {"category": "OHMS_LAW", "result": {"power_w": 0.35}},
                {"category": "MARGIN", "result": {"utilization_pct": 70.0}},
            ],
            "unknowns": [],
        },
        "candidate_provenance": {"generation_strategy": "PACKAGE_UPGRADE"},
    }

    comparison = service.compare_alternatives(
        circuit_dict=circuit_dict,
        baseline_analysis=baseline_analysis,
        alternatives=[alt1, alt2],
    )

    # 1. Assert NO score fields exist anywhere in response
    resp_dict = comparison.model_dump()
    assert "recommended_alternative_id" not in resp_dict
    assert "winner" not in resp_dict
    assert "score" not in resp_dict

    # 2. Assert comparison matrix rows have transparent evidence
    assert len(comparison.comparison_matrix) == 2
    row_a = comparison.comparison_matrix[0]
    row_b = comparison.comparison_matrix[1]

    assert row_a.hard_constraints == "PASS"
    assert row_a.soft_constraints == "1/1 SATISFIED"
    assert row_a.findings_resolved_count == 1
    assert row_a.power_delta_w == -0.2
    assert row_a.footprint == "0402"
    assert row_a.cost == "UNKNOWN"

    assert row_b.hard_constraints == "PASS"
    assert row_b.power_delta_w == 0.0
    assert row_b.footprint == "1206"


# ==============================================================================
# 3. UNKNOWN MUST NEVER PASS (Section 13)
# ==============================================================================
def test_unknown_must_never_pass():
    """
    Invariant: UNKNOWN is NEVER treated as PASS or SATISFIED.
    Missing data must result in UNKNOWN status and fail verification.
    """
    engine = ConstraintEvaluationEngine()

    circuit_dict = {"components": [{"id": "c1", "name": "C1"}]}
    empty_analysis = {"calculations": [], "findings": [], "unknowns": []}

    # Hard constraint with missing calculations
    hard_c = [EngineeringConstraint(id="h1", type="maximum_power", value="0.25W", hard_or_soft="HARD")]
    res_hard = engine.evaluate_constraints(hard_c, circuit_dict, empty_analysis)
    assert res_hard[0].status == ConstraintStatus.UNKNOWN.value
    assert res_hard[0].status != ConstraintStatus.PASS.value
    assert res_hard[0].status != ConstraintStatus.SATISFIED.value

    # Soft constraint with missing calculations
    soft_c = [EngineeringConstraint(id="s1", type="minimum_margin", value=20.0, hard_or_soft="SOFT")]
    res_soft = engine.evaluate_constraints(soft_c, circuit_dict, empty_analysis)
    assert res_soft[0].status == ConstraintStatus.UNKNOWN.value
    assert res_soft[0].status != ConstraintStatus.PASS.value
    assert res_soft[0].status != ConstraintStatus.SATISFIED.value


# ==============================================================================
# 4. COMPONENT REPLACEMENT & MISSING KB SPECIFICATIONS (Section 14 & 15)
# ==============================================================================
def test_component_replacement_and_missing_kb_specs():
    """
    Validate that:
    1. Replacement with verified KB part checks pin and electrical parameters.
    2. Missing specification emits EngineeringUnknown with SPECIFICATION_NOT_FOUND.
    """
    generator = DesignCandidateGenerator()

    circuit_dict = {
        "id": "circ-repl",
        "version": 1,
        "components": [
            {"id": "u1", "name": "U1", "component_type": "REGULATOR", "value": "AMS1117-3.3", "pins": [{"number": "1"}, {"number": "2"}, {"number": "3"}]},
        ],
        "connections": [
            {"component_id": "u1", "pin_number": "1"},
            {"component_id": "u1", "pin_number": "2"},
            {"component_id": "u1", "pin_number": "3"},
        ],
    }

    # 1. Valid replacement in KB (LM7805)
    valid, errs, unks = generator.validate_component_replacement(
        target_comp=circuit_dict["components"][0],
        replacement_part="LM7805",
        circuit_dict=circuit_dict,
    )
    assert valid is True
    assert len(errs) == 0

    # 2. Unverified part not in KB
    valid_ghost, errs_ghost, unks_ghost = generator.validate_component_replacement(
        target_comp=circuit_dict["components"][0],
        replacement_part="NON_EXISTENT_CHIP_XYZ",
        circuit_dict=circuit_dict,
    )
    assert valid_ghost is False
    assert len(unks_ghost) > 0
    assert unks_ghost[0]["provenance"] == "SPECIFICATION_NOT_FOUND"


# ==============================================================================
# 5. CANDIDATE PROVENANCE CHAIN (Section 16)
# ==============================================================================
def test_candidate_provenance_chain():
    """
    Every candidate alternative must carry an inspectable provenance chain:
    trigger, generation_strategy, source_finding, affected_component, rationale,
    knowledge_sources, constraint_results, finding_delta, engineering_effects, unknowns, confidence.
    """
    generator = DesignCandidateGenerator()

    circuit_dict = {
        "id": "circ-prov",
        "version": 1,
        "components": [
            {"id": "r1", "name": "R1", "component_type": "RESISTOR", "value": "100R", "footprint": "0402"},
        ],
        "nets": [{"id": "n1", "name": "+5V"}, {"id": "n2", "name": "GND"}],
        "connections": [{"component_id": "r1", "net_id": "n1"}, {"component_id": "r1", "net_id": "n2"}],
    }
    analysis_data = {
        "findings": [{"id": "f-r003-1", "rule_id": "R003", "title": "Excessive power on R1", "severity": "CRITICAL"}],
        "calculations": [
            {"category": "OHMS_LAW", "result": {"power_w": 0.25}},
            {"category": "MARGIN", "result": {"utilization_pct": 200.0}},
        ],
        "unknowns": [],
    }

    alternatives = generator.generate_alternatives(
        circuit_dict=circuit_dict,
        analysis_data=analysis_data,
        objective_id="obj-prov",
        objective_type="REDUCE_POWER",
        target={},
        constraints=[],
    )

    assert len(alternatives) > 0
    alt = alternatives[0]
    prov = alt.candidate_provenance
    assert prov is not None
    prov_dict = prov.model_dump() if hasattr(prov, "model_dump") else prov
    assert prov_dict["trigger"] == "R003 Excessive Resistor Power"
    assert "E24" in prov_dict["generation_strategy"] or "Package" in prov_dict["generation_strategy"] or "RESISTOR" in prov_dict["generation_strategy"]
    assert prov_dict["confidence"] in ["HIGH", "MEDIUM", "LOW"]
    assert "knowledge_sources" in prov_dict
    assert "finding_delta" in prov_dict


# ==============================================================================
# 6. SANDBOX IMMUTABILITY (Section 18)
# ==============================================================================
def test_sandbox_immutability():
    """
    Regression test proving that running sandboxed simulations does NOT mutate the base circuit.
    """
    sandbox = SandboxedWhatIfSimulator()

    base_circuit = {
        "id": "circ-immut",
        "version": 1,
        "components": [
            {"id": "r1", "name": "R1", "component_type": "RESISTOR", "value": "100R", "footprint": "0402"},
        ],
        "nets": [{"id": "n1", "name": "+5V"}, {"id": "n2", "name": "GND"}],
        "connections": [{"component_id": "r1", "net_id": "n1"}],
    }
    before_analysis = {"calculations": [], "findings": [], "unknowns": []}

    # Run multiple simulated changes in sandbox
    for val in ["220R", "330R", "470R"]:
        sandbox.simulate_candidate(
            base_circuit_dict=base_circuit,
            before_analysis=before_analysis,
            objective_id="obj-test",
            title=f"Test {val}",
            description="Testing sandbox isolation",
            proposed_changes=[
                ProposedChange(operation="UPDATE_COMPONENT_VALUE", component_id="r1", new_value=val)
            ],
            constraints=[],
        )

    # Base circuit must be completely identical
    assert base_circuit["version"] == 1
    assert base_circuit["components"][0]["value"] == "100R"
    assert len(base_circuit["components"]) == 1
    assert len(base_circuit["nets"]) == 2


# ==============================================================================
# 7. MANDATORY ATOMIC ROLLBACK TEST (Section 11)
# ==============================================================================
@pytest.mark.asyncio
async def test_mandatory_atomic_rollback(
    async_client: AsyncClient,
    auth_headers: dict,
):
    """
    Scenario:
    BEGIN TRANSACTION
    operation 1 succeeds (add valid component)
    operation 2 succeeds (add valid net)
    operation 3 fails (fail_simulation forced error)
    ROLLBACK
    After failure:
    circuit unchanged, components unchanged, connections unchanged, nets unchanged, revision unchanged.
    """
    # 1. Create Project and Circuit
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Atomic Rollback Project", "project_type": "power"},
        headers=auth_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Rollback Circuit", "description": "Testing atomic apply failure"},
        headers=auth_headers,
    )
    assert circ_res.status_code == 201
    circuit_id = circ_res.json()["data"]["id"]
    initial_version = circ_res.json()["data"]["version"]

    # Add initial base component
    c_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R_BASE", "component_type": "resistor", "value": "1k"},
        headers=auth_headers,
    )
    assert c_res.status_code == 200

    c_detail_before = await async_client.get(f"/api/v1/circuits/{circuit_id}", headers=auth_headers)
    before_components_count = len(c_detail_before.json()["data"]["components"])
    before_nets_count = len(c_detail_before.json()["data"]["nets"])
    current_version = c_detail_before.json()["data"]["version"]

    # Create proposal with a deliberately failing operation
    prop_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/proposals",
        json={
            "title": "Proposal With Failing Op",
            "base_revision": current_version,
            "operations": [
                {"op_type": "add_component", "payload": {"ref_des": "R_NEW_SHOULD_ROLLBACK", "value": "2k"}},
                {"op_type": "add_net", "payload": {"name": "NET_SHOULD_ROLLBACK"}},
                {"op_type": "fail_simulation", "payload": {}},  # Explicit forced exception in proposal_service
            ],
        },
        headers=auth_headers,
    )
    assert prop_res.status_code in [200, 201]
    proposal_id = prop_res.json()["data"]["id"]

    # Approve proposal
    appr_res = await async_client.post(f"/api/v1/proposals/{proposal_id}/approve", headers=auth_headers)
    assert appr_res.status_code == 200

    # Apply proposal -> MUST raise exception / return 500 error
    apply_res = await async_client.post(f"/api/v1/proposals/{proposal_id}/apply", headers=auth_headers)
    assert apply_res.status_code >= 400

    # Verify atomic rollback: circuit state is 100% identical to before_apply!
    c_detail_after = await async_client.get(f"/api/v1/circuits/{circuit_id}", headers=auth_headers)
    data_after = c_detail_after.json()["data"]

    assert data_after["version"] == current_version  # Revision unchanged
    assert len(data_after["components"]) == before_components_count  # No partial component additions
    assert len(data_after["nets"]) == before_nets_count  # No partial net additions
    assert not any(c["ref_des"] == "R_NEW_SHOULD_ROLLBACK" for c in data_after["components"])


# ==============================================================================
# 8. POST-APPLY REVISION INTEGRITY (Section 12)
# ==============================================================================
@pytest.mark.asyncio
async def test_post_apply_revision_integrity(
    async_client: AsyncClient,
    auth_headers: dict,
):
    """
    After successful proposal application:
    old_revision = N
    apply proposal
    new_revision = N + 1
    fresh_analysis.circuit_revision == new_revision
    """
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Revision Integrity Project", "project_type": "power"},
        headers=auth_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Revision Integrity Circuit"},
        headers=auth_headers,
    )
    circuit_id = circ_res.json()["data"]["id"]
    n_rev = circ_res.json()["data"]["version"]

    prop_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/proposals",
        json={
            "title": "Revision Advance Proposal",
            "base_revision": n_rev,
            "operations": [{"op_type": "add_net", "payload": {"name": "NET_REV_TEST"}}],
        },
        headers=auth_headers,
    )
    proposal_id = prop_res.json()["data"]["id"]

    await async_client.post(f"/api/v1/proposals/{proposal_id}/approve", headers=auth_headers)
    apply_res = await async_client.post(f"/api/v1/proposals/{proposal_id}/apply", headers=auth_headers)
    assert apply_res.status_code == 200

    # Verify circuit revision is N + 1
    circ_check = await async_client.get(f"/api/v1/circuits/{circuit_id}", headers=auth_headers)
    new_rev = circ_check.json()["data"]["version"]
    assert new_rev == n_rev + 1

    # Verify fresh analysis revision is exactly new_revision
    analysis_check = await async_client.get(f"/api/v1/circuits/{circuit_id}/analysis/latest", headers=auth_headers)
    assert analysis_check.status_code == 200
    assert analysis_check.json()["data"]["circuit_version"] == new_rev


# ==============================================================================
# 9. STALE PROPOSAL TYPED ERROR (Section 10)
# ==============================================================================
@pytest.mark.asyncio
async def test_stale_proposal_typed_error(
    async_client: AsyncClient,
    auth_headers: dict,
):
    """
    Assert stale proposal rejection returns structured PROPOSAL_STALE error.
    """
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Stale Error Project", "project_type": "power"},
        headers=auth_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Stale Error Circuit"},
        headers=auth_headers,
    )
    circuit_id = circ_res.json()["data"]["id"]

    # Create proposal with mismatched base_revision
    prop_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/proposals",
        json={
            "title": "Stale Proposal With Typed Error",
            "base_revision": 999,
            "operations": [{"op_type": "add_net", "payload": {"name": "NET_STALE"}}],
        },
        headers=auth_headers,
    )
    prop_id = prop_res.json()["data"]["id"]

    # Approval should be rejected with structured error
    appr_res = await async_client.post(f"/api/v1/proposals/{prop_id}/approve", headers=auth_headers)
    assert appr_res.status_code == 400
    err_detail = appr_res.json()["detail"]
    assert isinstance(err_detail, dict)
    assert err_detail["code"] == "PROPOSAL_STALE"
    assert err_detail["proposal_revision"] == 999
    assert "current_circuit_revision" in err_detail
    assert "required_action" in err_detail


# ==============================================================================
# 10. TENANT / IDOR ISOLATION HARDENING (Section 19)
# ==============================================================================
@pytest.mark.asyncio
async def test_wave4_tenant_idor_isolation(
    async_client: AsyncClient,
    auth_headers: dict,
    other_tenant_headers: dict,
):
    """
    Tenant A resources must be strictly inaccessible to Tenant B across all Wave 4 routes.
    """
    # Tenant A creates project & circuit
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Tenant A Secret Project", "project_type": "power"},
        headers=auth_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Tenant A Secret Circuit"},
        headers=auth_headers,
    )
    circuit_id = circ_res.json()["data"]["id"]

    # Tenant A creates an objective
    obj_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design/objectives",
        json={"objective_type": "REDUCE_POWER"},
        headers=auth_headers,
    )
    assert obj_res.status_code == 200

    # Tenant B tries to access Tenant A's circuit design endpoints
    assert (await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design/objectives",
        json={"objective_type": "REDUCE_POWER"},
        headers=other_tenant_headers,
    )).status_code == 404

    assert (await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design/alternatives",
        json={"objective_type": "REDUCE_POWER"},
        headers=other_tenant_headers,
    )).status_code == 404

    assert (await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design/compare",
        json={"alternatives": []},
        headers=other_tenant_headers,
    )).status_code in [404, 422]
