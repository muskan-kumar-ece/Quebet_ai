import time
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token
from app.models.schemas.design import (
    ConstraintStatus,
    EngineeringConstraint,
    EngineeringDesignObjectiveCreate,
    ProposedChange,
)
from app.services.ai.analysis.circuit_analysis_service import CircuitAnalysisService
from app.services.ai.analysis.spec_resolver import ComponentSpecificationResolver
from app.services.ai.design.candidate_generator import DesignCandidateGenerator
from app.services.ai.design.comparison_service import DesignComparisonService
from app.services.ai.design.constraint_engine import ConstraintEvaluationEngine
from app.services.ai.design.what_if_sandbox import SandboxedWhatIfSimulator


@pytest.fixture
def auth_headers():
    token = create_access_token("wave4-eng-1", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-wave4-a"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_tenant_headers():
    token = create_access_token("wave4-eng-2", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-wave4-b"})
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. CONSTRAINT EVALUATION ENGINE TESTS
# ==============================================================================
def test_constraint_evaluation_engine():
    engine = ConstraintEvaluationEngine()

    circuit_dict = {
        "components": [
            {"id": "r1", "name": "R1", "package": "0805"},
            {"id": "r2", "name": "R2", "package": "0805"},
        ]
    }
    analysis_data = {
        "calculations": [
            {"category": "OHMS_LAW", "result": {"power_w": 0.15}},
            {"category": "MARGIN", "result": {"margin_pct": 25.0, "utilization_pct": 75.0}},
            {"category": "REGULATOR", "result": {"junction_temp_c": 65.0}},
        ],
        "findings": [],
        "unknowns": [],
    }

    constraints = [
        EngineeringConstraint(id="c1", type="maximum_power", value="0.25W"),
        EngineeringConstraint(id="c2", type="minimum_margin", value=20.0),
        EngineeringConstraint(id="c3", type="maximum_temperature", value=75.0),
        EngineeringConstraint(id="c4", type="preferred_package", value="0805"),
        EngineeringConstraint(id="c5", type="maximum_power", value="0.10W"),  # should violate
    ]

    results = engine.evaluate_constraints(constraints, circuit_dict, analysis_data)
    res_map = {r.constraint_id: r for r in results}

    assert res_map["c1"].status in [ConstraintStatus.PASS.value, ConstraintStatus.SATISFIED.value]
    assert res_map["c2"].status in [ConstraintStatus.PASS.value, ConstraintStatus.SATISFIED.value]
    assert res_map["c3"].status in [ConstraintStatus.PASS.value, ConstraintStatus.SATISFIED.value]
    assert res_map["c4"].status in [ConstraintStatus.PASS.value, ConstraintStatus.SATISFIED.value]
    assert res_map["c5"].status in [ConstraintStatus.FAIL.value, ConstraintStatus.NOT_SATISFIED.value]

    # Rule test: Missing data must produce UNKNOWN, never SATISFIED
    unknown_constraints = [
        EngineeringConstraint(id="c_unk", type="maximum_power", value="0.25W"),
    ]
    empty_analysis = {"calculations": [], "findings": [], "unknowns": []}
    unk_res = engine.evaluate_constraints(unknown_constraints, circuit_dict, empty_analysis)
    assert unk_res[0].status == ConstraintStatus.UNKNOWN.value


# ==============================================================================
# 2. SANDBOXED WHAT-IF SIMULATOR (ZERO DB MUTATION)
# ==============================================================================
def test_sandboxed_what_if_simulation():
    sandbox = SandboxedWhatIfSimulator()

    base_circuit = {
        "id": "circ-whatif",
        "version": 1,
        "components": [
            {"id": "r1", "name": "R1", "component_type": "RESISTOR", "value": "100R", "footprint": "0402"},
        ],
        "nets": [
            {"id": "n1", "name": "+5V"},
            {"id": "n2", "name": "GND"},
        ],
        "connections": [
            {"component_id": "r1", "net_id": "n1"},
            {"component_id": "r1", "net_id": "n2"},
        ],
    }

    analyzer = CircuitAnalysisService()
    before_analysis = analyzer.analyze_circuit(base_circuit)

    # Candidate: Upgrade footprint to 1206 (0.25W rating)
    changes = [
        ProposedChange(
            operation="UPDATE_COMPONENT_RATING",
            component_id="r1",
            ref_des="R1",
            field="package",
            new_value="1206",
            payload={"properties": {"power_rating": "0.25W"}},
        )
    ]

    alt = sandbox.simulate_candidate(
        base_circuit_dict=base_circuit,
        before_analysis=before_analysis,
        objective_id="obj-1",
        title="Upgrade R1 to 1206",
        description="Increases power handling",
        proposed_changes=changes,
        constraints=[],
    )

    # Verify base circuit dictionary was NOT mutated in memory
    assert base_circuit["components"][0]["footprint"] == "0402"
    # Verify candidate alternative received fresh deterministic analysis
    assert alt.status in ["VALIDATED", "PARTIAL"]
    assert len(alt.engineering_effects) > 0
    assert alt.after_analysis is not None


# ==============================================================================
# 3. ENGINEERING INTEGRITY ACCEPTANCE TEST (Section 16 & Section 48)
# ==============================================================================
def test_engineering_integrity_unverified_component():
    """
    Construct a candidate where the user or AI claims:
    'Use component X because its current rating is 3A.'
    If the KB does not contain that rating, system MUST NOT accept claim as fact.
    Expected: SPECIFICATION_NOT_FOUND and candidate status: BLOCKED or PARTIAL.
    """
    generator = DesignCandidateGenerator()

    circuit_dict = {
        "id": "circ-integrity",
        "version": 1,
        "components": [
            {"id": "u1", "name": "U1", "component_type": "REGULATOR", "value": "LM7805"},
        ],
        "nets": [],
        "connections": [],
    }
    analysis_data = {"calculations": [], "findings": [], "unknowns": []}

    # Request unverified phantom regulator claiming 3A
    target = {
        "replacement_part": "PHANTOM_SUPER_REG_3A",
    }

    alternatives = generator.generate_alternatives(
        circuit_dict=circuit_dict,
        analysis_data=analysis_data,
        objective_id="obj-integrity",
        objective_type="SELECT_ALTERNATIVE_COMPONENT",
        target=target,
        constraints=[],
    )

    unverified_alt = next((a for a in alternatives if "PHANTOM_SUPER_REG" in a.title), None)
    assert unverified_alt is not None
    assert unverified_alt.status == "BLOCKED"
    assert "SPECIFICATION_NOT_FOUND" in unverified_alt.provenance
    assert len(unverified_alt.unknowns) > 0
    assert unverified_alt.unknowns[0]["field"] == "part_number"


# ==============================================================================
# 4. DESIGN COMPARISON SERVICE
# ==============================================================================
def test_design_comparison_service():
    service = DesignComparisonService()

    circuit_dict = {"id": "circ-1", "version": 1, "components": [{"id": "c1"}, {"id": "c2"}]}
    baseline_analysis = {
        "findings": [
            {"rule_id": "R003", "title": "Overpower", "severity": "CRITICAL"},
            {"rule_id": "R006", "title": "Margin", "severity": "WARNING"},
        ],
        "calculations": [
            {"category": "OHMS_LAW", "result": {"power_w": 0.25}},
            {"category": "MARGIN", "result": {"utilization_pct": 125.0}},
        ],
        "unknowns": [],
    }

    alt1 = {
        "alternative_id": "alt-1",
        "title": "Upgrade R1 to 1206",
        "status": "VALIDATED",
        "confidence": "HIGH",
        "affected_components": ["c1"],
        "findings_resolved": ["R003: Overpower"],
        "findings_introduced": [],
        "constraint_results": [],
        "after_analysis": {
            "findings": [{"rule_id": "R006", "title": "Margin", "severity": "WARNING"}],
            "calculations": [
                {"category": "OHMS_LAW", "result": {"power_w": 0.25}},
                {"category": "MARGIN", "result": {"utilization_pct": 60.0}},
            ],
            "unknowns": [],
        },
    }

    comparison = service.compare_alternatives(
        circuit_dict=circuit_dict,
        baseline_analysis=baseline_analysis,
        alternatives=[alt1],
    )

    assert comparison.baseline_metrics["critical_findings"] == 1
    assert len(comparison.comparison_table) == 1
    assert comparison.comparison_table[0]["critical_delta"] == -1
    assert comparison.comparison_table[0]["worst_utilization_pct"] == 60.0


# ==============================================================================
# 5. END-TO-END WORKFLOW, STALE PROTECTION, & ATOMIC APPLY
# ==============================================================================
@pytest.mark.asyncio
async def test_end_to_end_wave4_workflow(
    async_client: AsyncClient,
    auth_headers: dict,
    other_tenant_headers: dict,
):
    # 1. Create Project and Circuit
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Wave4 Design Intelligence Project", "project_type": "power"},
        headers=auth_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Power Circuit", "description": "Overpower Test Circuit"},
        headers=auth_headers,
    )
    assert circ_res.status_code == 201
    circuit_id = circ_res.json()["data"]["id"]

    # 2. Add Resistor R1 (100R, 0402 footprint) connected between 5V and GND -> violates R003
    r1_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R1", "component_type": "resistor", "value": "100R", "package": "0402"},
        headers=auth_headers,
    )
    assert r1_res.status_code == 200
    r1_id = r1_res.json()["data"]["id"]

    vcc_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/nets",
        json={"name": "+5V", "net_type": "power"},
        headers=auth_headers,
    )
    assert vcc_res.status_code == 200
    vcc_id = vcc_res.json()["data"]["id"]

    gnd_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/nets",
        json={"name": "GND", "net_type": "ground"},
        headers=auth_headers,
    )
    assert gnd_res.status_code == 200
    gnd_id = gnd_res.json()["data"]["id"]

    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/connections",
        json={"component_id": r1_id, "pin_number": "1", "net_id": vcc_id},
        headers=auth_headers,
    )
    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/connections",
        json={"component_id": r1_id, "pin_number": "2", "net_id": gnd_id},
        headers=auth_headers,
    )

    # 3. Analyze Circuit -> Generates R003 Critical Finding
    an_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/analyze",
        headers=auth_headers,
    )
    assert an_res.status_code == 200
    an_data = an_res.json()["data"]
    rule_ids = {f["rule_id"] for f in an_data["findings"]}
    assert "R003" in rule_ids

    # 4. Create Design Objective: FIX_RULE_VIOLATION
    obj_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design/objectives",
        json={
            "objective_type": "FIX_RULE_VIOLATION",
            "description": "Resolve excessive resistor power dissipation on R1",
            "target": {"rule_id": "R003"},
            "constraints": [{"id": "c1", "type": "maximum_power", "value": "0.15W", "hard_or_soft": "HARD"}],
            "affected_components": [r1_id],
            "affected_nets": [vcc_id, gnd_id],
        },
        headers=auth_headers,
    )
    assert obj_res.status_code == 200
    obj_id = obj_res.json()["data"]["id"]

    # 5. Generate Candidate Alternatives
    gen_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design/alternatives",
        json={
            "objective_id": obj_id,
            "objective_type": "FIX_RULE_VIOLATION",
            "affected_components": [r1_id],
        },
        headers=auth_headers,
    )
    assert gen_res.status_code == 200
    alts = gen_res.json()["data"]
    assert len(alts) >= 1
    selected_alt = alts[0]

    # 6. Compare Alternatives
    comp_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design/compare",
        json={"alternatives": alts},
        headers=auth_headers,
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()["data"]
    assert len(comp_data["comparison_table"]) == len(alts)

    # 7. Promote Alternative to Staged Proposal
    prop_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design/propose",
        json={"alternative": selected_alt},
        headers=auth_headers,
    )
    assert prop_res.status_code == 200
    proposal = prop_res.json()["data"]
    proposal_id = proposal["id"]
    assert proposal["base_revision"] == 1

    # 8. Validate Proposal
    val_res = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/validate",
        headers=auth_headers,
    )
    assert val_res.status_code == 200
    assert val_res.json()["data"]["status"] == "VALIDATED"

    # 9. STALE PROPOSAL PROTECTION TEST
    # User edits circuit (e.g. increments version from 1 to 2 by adding another net)
    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/nets",
        json={"name": "INTERMEDIATE_NET", "net_type": "signal"},
        headers=auth_headers,
    )
    # Circuit is now at version 2 (or updated). Let's explicitly test approval/application of stale proposal!
    # Manually approve proposal first
    appr_res = await async_client.post(
        f"/api/v1/proposals/{proposal_id}/approve",
        headers=auth_headers,
    )
    assert appr_res.status_code == 200

    # Now increment circuit version directly
    await async_client.patch(
        f"/api/v1/circuits/{circuit_id}",
        json={"name": "Updated Circuit Revision"},
        headers=auth_headers,
    )

    # Attempt to apply proposal when base_revision != current circuit revision
    # Let's inspect circuit revision
    c_check = await async_client.get(f"/api/v1/circuits/{circuit_id}", headers=auth_headers)
    curr_rev = c_check.json()["data"]["version"]

    # If revisions match, we artificially increment version or create stale scenario
    # Create a proposal with base_revision = 999 to test stale protection
    stale_prop_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/proposals",
        json={
            "title": "Stale Proposal",
            "base_revision": 999,  # Mismatched base revision
            "operations": [{"op_type": "add_net", "payload": {"name": "STALE_NET"}}],
        },
        headers=auth_headers,
    )
    stale_id = stale_prop_res.json()["data"]["id"]

    # Approving proposal with mismatched base revision must be rejected as STALE!
    stale_appr = await async_client.post(
        f"/api/v1/proposals/{stale_id}/approve",
        headers=auth_headers,
    )
    assert stale_appr.status_code == 400
    assert "STALE" in str(stale_appr.json()["detail"])

    # 10. ATOMIC APPLY & POST-APPLY RE-ANALYSIS
    # Create and apply fresh valid proposal
    fresh_prop_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/proposals",
        json={
            "title": "Fresh Valid Proposal",
            "base_revision": curr_rev,
            "operations": [
                {
                    "op_type": "update_component_value",
                    "payload": {"component_id": r1_id, "ref_des": "R1", "value": "10k"},
                }
            ],
        },
        headers=auth_headers,
    )
    fresh_id = fresh_prop_res.json()["data"]["id"]

    await async_client.post(f"/api/v1/proposals/{fresh_id}/validate", headers=auth_headers)
    await async_client.post(f"/api/v1/proposals/{fresh_id}/approve", headers=auth_headers)

    apply_res = await async_client.post(
        f"/api/v1/proposals/{fresh_id}/apply",
        headers=auth_headers,
    )
    assert apply_res.status_code == 200
    assert apply_res.json()["data"]["status"] == "APPLIED"

    # Verify circuit version was incremented
    after_c_check = await async_client.get(f"/api/v1/circuits/{circuit_id}", headers=auth_headers)
    assert after_c_check.json()["data"]["version"] == curr_rev + 1

    # Verify post-apply automatic re-analysis snapshot was created
    latest_an = await async_client.get(f"/api/v1/circuits/{circuit_id}/analysis/latest", headers=auth_headers)
    assert latest_an.status_code == 200
    assert latest_an.json()["data"]["circuit_version"] == curr_rev + 1

    # 11. TENANT ISOLATION
    other_get = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/design/alternatives",
        json={"objective_id": obj_id, "objective_type": "FIX_RULE_VIOLATION"},
        headers=other_tenant_headers,
    )
    assert other_get.status_code == 404


@pytest.mark.asyncio
async def test_stale_proposal_on_apply_rejection(
    async_client: AsyncClient,
    auth_headers: dict,
):
    """Verify that approving a proposal, then modifying the circuit, prevents apply due to stale revision."""
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Stale Apply Test Project", "project_type": "power"},
        headers=auth_headers,
    )
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Circuit A"},
        headers=auth_headers,
    )
    circuit_id = circ_res.json()["data"]["id"]
    base_rev = circ_res.json()["data"]["version"]

    # Create and approve proposal at base_revision
    prop_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/proposals",
        json={
            "title": "Proposal at Revision 1",
            "base_revision": base_rev,
            "operations": [{"op_type": "add_net", "payload": {"name": "NET_A"}}],
        },
        headers=auth_headers,
    )
    prop_id = prop_res.json()["data"]["id"]

    await async_client.post(f"/api/v1/proposals/{prop_id}/approve", headers=auth_headers)

    # Now mutate circuit directly, advancing version to 2
    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R_EXTRA", "component_type": "resistor", "value": "1k"},
        headers=auth_headers,
    )
    # Circuit is updated, version incremented
    await async_client.patch(
        f"/api/v1/circuits/{circuit_id}",
        json={"name": "Circuit A Updated"},
        headers=auth_headers,
    )

    # Artificially increment version to simulate circuit advance
    from app.core.database import AsyncSessionLocal as async_session_factory
    from app.repositories.circuit_repo import circuit_repo
    async with async_session_factory() as db:
        c = await circuit_repo.get_by_id(db, circuit_id, allow_unscoped=True)
        c.version = 10
        await db.commit()

    # Now attempt to apply the previously approved proposal
    apply_res = await async_client.post(
        f"/api/v1/proposals/{prop_id}/apply",
        headers=auth_headers,
    )
    assert apply_res.status_code == 400
    assert "STALE" in str(apply_res.json()["detail"])


def test_voltage_domain_and_decoupling_generation():
    """Verify candidate generation for R007 and R008 workflows."""
    generator = DesignCandidateGenerator()

    circuit_dict = {
        "id": "circ-workflows",
        "version": 1,
        "components": [
            {"id": "u_esp", "name": "ESP32", "component_type": "MICROCONTROLLER", "value": "ESP32-WROOM-32"},
            {"id": "u_reg", "name": "U1", "component_type": "REGULATOR", "value": "LM7805"},
        ],
        "nets": [{"id": "n_5v", "name": "+5V"}],
        "connections": [{"component_id": "u_esp", "net_id": "n_5v"}],
    }
    analysis_data = {
        "findings": [
            {"rule_id": "R008", "title": "Voltage Domain Conflict", "severity": "CRITICAL", "component_ids": ["u_esp"]},
            {"rule_id": "R007", "title": "Missing Decoupling Capacitor", "severity": "WARNING"},
        ],
        "calculations": [],
        "unknowns": [],
    }

    alts = generator.generate_alternatives(
        circuit_dict=circuit_dict,
        analysis_data=analysis_data,
        objective_id="obj-wf",
        objective_type="FIX_RULE_VIOLATION",
        target={},
        constraints=[],
    )

    titles = [a.title for a in alts]
    assert any("3.3V LDO Regulator" in t for t in titles)
    assert any("Decoupling Capacitor" in t for t in titles)

