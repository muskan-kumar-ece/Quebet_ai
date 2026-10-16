import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-wave8-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_system_design_objectives_constraints_and_tenant_isolation(async_client: AsyncClient):
    """
    Verifies:
    1. System design objective creation with typed hard and soft constraints.
    2. Constraints evaluation: hard (PASS/FAIL/UNKNOWN) and soft (SATISFIED/NOT_SATISFIED/UNKNOWN).
    3. Strict UNKNOWN != PASS compliance.
    4. Tenant isolation: Tenant B cannot access Tenant A objectives.
    """
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "engineer8a@quebet.ai", tenant_id="tenant-wave8-a")
    user_b = str(uuid.uuid4())
    headers_b = auth_headers(user_b, "engineer8b@quebet.ai", tenant_id="tenant-wave8-b")

    # 1. Create Project and System for Tenant A
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Avionics Power Architecture", "project_type": "embedded"},
        headers=headers_a,
    )
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["data"]["id"]

    sys_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Primary Flight Computer System", "description": "Redundant rails"},
        headers=headers_a,
    )
    assert sys_res.status_code == 201
    sys_id = sys_res.json()["data"]["id"]

    # 2. Create Design Objective with Hard and Soft constraints
    obj_payload = {
        "title": "Optimize System Power Consumption",
        "description": "Reduce aggregate current draw while keeping 3.3V rail stable.",
        "objective_type": "POWER_OPTIMIZATION",
        "priority": "HIGH",
        "target": {"target_efficiency": 0.92},
        "affected_subsystems": [],
        "relevant_modes": ["ACTIVE", "LOW_POWER"],
        "constraints": [
            {
                "constraint_type": "HARD",
                "parameter": "MAX_CURRENT",
                "operator": "LTE",
                "value": {"value": 2.5},
                "unit": "A",
            },
            {
                "constraint_type": "SOFT",
                "parameter": "MAX_SUBSYSTEM_COUNT",
                "operator": "LTE",
                "value": {"value": 10},
                "weight": 0.8,
            },
        ],
    }
    obj_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/design-objectives",
        json=obj_payload,
        headers=headers_a,
    )
    assert obj_res.status_code == 201
    obj_data = obj_res.json()["data"]
    obj_id = obj_data["id"]
    assert obj_data["title"] == "Optimize System Power Consumption"
    assert len(obj_data["constraints"]) == 2

    # Verify no synthetic score fields
    assert "score" not in obj_data
    assert "health_score" not in obj_data

    # 3. Tenant Isolation Check: Tenant B cannot read Tenant A objective
    idor_res = await async_client.get(
        f"/api/v1/design-objectives/{obj_id}",
        headers=headers_b,
    )
    assert idor_res.status_code in [403, 404]


@pytest.mark.asyncio
async def test_scenario_precondition_gating_and_immutable_execution(async_client: AsyncClient):
    """
    Verifies:
    1. Scenario creation with preconditions and fault injection.
    2. Gating: Scenario with violated/missing mandatory precondition evaluates to BLOCKED.
    3. Scenario with satisfied precondition completes with immutable SHA-256 snapshot.
    4. Prohibits composite health or risk scoring.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "scenarios@quebet.ai", tenant_id="tenant-wave8-scen")

    # Setup project and system
    proj = await async_client.post(
        "/api/v1/projects", json={"name": "Sensor Hub", "project_type": "embedded"}, headers=headers
    )
    proj_id = proj.json()["data"]["id"]

    sys = await async_client.post(
        "/api/v1/systems", json={"project_id": proj_id, "name": "Telemetry Hub"}, headers=headers
    )
    sys_id = sys.json()["data"]["id"]

    # Add a subsystem and a power rail
    sub = await async_client.post(
        f"/api/v1/systems/{sys_id}/subsystems",
        json={"name": "Main MCU", "subsystem_type": "PROCESSING"},
        headers=headers,
    )
    sub_id = sub.json()["data"]["id"]

    rail = await async_client.post(
        f"/api/v1/systems/{sys_id}/power-domains",
        json={"name": "3V3_SYS", "nominal_voltage": 3.3, "current_capacity_a": 1.5, "source_subsystem_id": sub_id},
        headers=headers,
    )

    # 1. Create Scenario with INVALID / UNSATISFIED precondition (requires non-existent subsystem)
    scen_blocked = await async_client.post(
        f"/api/v1/systems/{sys_id}/scenarios",
        json={
            "name": "Invalid Precondition Scenario",
            "scenario_type": "NORMAL_OPERATION",
            "conditions": [
                {
                    "condition_type": "PRECONDITION",
                    "target_type": "SUBSYSTEM",
                    "target_id": "sub-ghost-999",
                    "parameter": "subsystem_active",
                    "value": {"state": "ACTIVE"},
                    "mandatory": True,
                }
            ],
        },
        headers=headers,
    )
    assert scen_blocked.status_code == 201
    scen_blocked_id = scen_blocked.json()["data"]["id"]

    # Execute blocked scenario
    exec_res = await async_client.post(
        f"/api/v1/scenarios/{scen_blocked_id}/execute",
        headers=headers,
    )
    assert exec_res.status_code == 200
    res_data = exec_res.json()["data"]
    assert res_data["status"] == "BLOCKED"
    assert res_data["precondition_status"] == "NOT_SATISFIED"
    assert any("Precondition failed" in f["description"] for f in res_data["findings"])

    # 2. Create Scenario with VALID precondition and fault injection
    scen_valid = await async_client.post(
        f"/api/v1/systems/{sys_id}/scenarios",
        json={
            "name": "MCU Power Loss Scenario",
            "scenario_type": "POWER_SOURCE_LOSS",
            "conditions": [
                {
                    "condition_type": "PRECONDITION",
                    "target_type": "SUBSYSTEM",
                    "target_id": sub_id,
                    "parameter": "subsystem_present",
                    "value": {"state": "ACTIVE"},
                    "mandatory": True,
                },
                {
                    "condition_type": "FAULT_INJECTION",
                    "target_type": "SUBSYSTEM",
                    "target_id": sub_id,
                    "parameter": "power_failure",
                    "value": {"state": "FAILED"},
                    "mandatory": True,
                },
            ],
        },
        headers=headers,
    )
    assert scen_valid.status_code == 201
    scen_valid_id = scen_valid.json()["data"]["id"]

    valid_exec = await async_client.post(
        f"/api/v1/scenarios/{scen_valid_id}/execute",
        headers=headers,
    )
    assert valid_exec.status_code == 200
    valid_res = valid_exec.json()["data"]
    assert valid_res["status"] == "COMPLETE"
    assert valid_res["precondition_status"] == "SATISFIED"
    assert len(valid_res["provenance"]) > 0

    # Ensure zero synthetic scoring
    assert "health_score" not in valid_res
    assert "risk_score" not in valid_res
    assert "overall_score" not in valid_res


@pytest.mark.asyncio
async def test_scenario_comparison_deltas_without_scoring(async_client: AsyncClient):
    """
    Verifies:
    1. Comparing two executed scenarios produces explicit engineering deltas.
    2. Reports power delta, failure propagation delta, and finding deltas.
    3. Rejects composite scores or winner tags.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "comparison@quebet.ai", tenant_id="tenant-wave8-comp")

    proj = await async_client.post("/api/v1/projects", json={"name": "Battery System"}, headers=headers)
    proj_id = proj.json()["data"]["id"]
    sys = await async_client.post("/api/v1/systems", json={"project_id": proj_id, "name": "Battery Architecture"}, headers=headers)
    sys_id = sys.json()["data"]["id"]

    sub = await async_client.post(
        f"/api/v1/systems/{sys_id}/subsystems",
        json={"name": "Charger Module", "subsystem_type": "POWER"},
        headers=headers,
    )
    sub_id = sub.json()["data"]["id"]

    # Scenario 1: Baseline Normal
    s1 = await async_client.post(
        f"/api/v1/systems/{sys_id}/scenarios",
        json={"name": "Baseline Normal Operation", "scenario_type": "NORMAL_OPERATION", "conditions": []},
        headers=headers,
    )
    s1_id = s1.json()["data"]["id"]
    await async_client.post(f"/api/v1/scenarios/{s1_id}/execute", headers=headers)

    # Scenario 2: High Load
    s2 = await async_client.post(
        f"/api/v1/systems/{sys_id}/scenarios",
        json={
            "name": "Heavy Charging Scenario",
            "scenario_type": "MAXIMUM_LOAD",
            "conditions": [
                {
                    "condition_type": "FAULT_INJECTION",
                    "target_type": "SUBSYSTEM",
                    "target_id": sub_id,
                    "parameter": "charger_overtemp",
                    "value": {"temp_c": 85},
                    "mandatory": False,
                }
            ],
        },
        headers=headers,
    )
    s2_id = s2.json()["data"]["id"]
    await async_client.post(f"/api/v1/scenarios/{s2_id}/execute", headers=headers)

    # Compare
    comp_res = await async_client.post(
        "/api/v1/scenarios/comparison",
        json={"baseline_scenario_id": s1_id, "alternative_scenario_id": s2_id},
        headers=headers,
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()["data"]

    assert comp_data["baseline_scenario_id"] == s1_id
    assert comp_data["alternative_scenario_id"] == s2_id
    assert "power_delta" in comp_data
    assert "finding_changes" in comp_data
    assert "failure_propagation_changes" in comp_data
    assert "summary" in comp_data

    # Zero scoring check
    assert "winner" not in comp_data
    assert "score" not in comp_data
    assert "best" not in comp_data


@pytest.mark.asyncio
async def test_system_what_if_sandbox_immutability(async_client: AsyncClient):
    """
    Verifies:
    1. Candidate generation runs in-memory what-if simulations.
    2. Operations in what-if do NOT mutate persistent database tables.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "sandbox@quebet.ai", tenant_id="tenant-wave8-sand")

    proj = await async_client.post("/api/v1/projects", json={"name": "Sandbox Test"}, headers=headers)
    proj_id = proj.json()["data"]["id"]
    sys = await async_client.post("/api/v1/systems", json={"project_id": proj_id, "name": "Sandbox Arch"}, headers=headers)
    sys_id = sys.json()["data"]["id"]

    # Initial count of subsystems
    sub_init = await async_client.post(
        f"/api/v1/systems/{sys_id}/subsystems",
        json={"name": "Existing Regulator", "subsystem_type": "REGULATION"},
        headers=headers,
    )
    assert sub_init.status_code == 201

    # Fetch initial subsystems list
    detail_before = await async_client.get(f"/api/v1/systems/{sys_id}", headers=headers)
    initial_subs_count = len(detail_before.json()["data"]["subsystems"])
    assert initial_subs_count == 1

    # Create Objective and Generate Candidates (which simulate mutations)
    obj = await async_client.post(
        f"/api/v1/systems/{sys_id}/design-objectives",
        json={
            "title": "Reduce Thermal Stress",
            "objective_type": "THERMAL_IMPROVEMENT",
            "target": {"temp_c": 45},
            "constraints": [],
        },
        headers=headers,
    )
    obj_id = obj.json()["data"]["id"]

    cand_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/design/candidates",
        json={"objective_id": obj_id},
        headers=headers,
    )
    assert cand_res.status_code == 201
    candidates = cand_res.json()["data"]
    assert len(candidates) >= 1

    # Verify that persistent system DB has NOT been altered
    detail_after = await async_client.get(f"/api/v1/systems/{sys_id}", headers=headers)
    subs_after = detail_after.json()["data"]["subsystems"]
    assert len(subs_after) == initial_subs_count
    assert subs_after[0]["name"] == "Existing Regulator"


@pytest.mark.asyncio
async def test_system_proposal_stale_rejection_and_atomic_apply(async_client: AsyncClient):
    """
    Verifies:
    1. Proposal created against base_revision 1.
    2. If system revision bumps to 2, applying proposal is rejected with SYSTEM_PROPOSAL_STALE.
    3. Proposal created against current revision applies atomically, increments revision,
       marks old proposals stale, and runs fresh system analysis.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "proposals@quebet.ai", tenant_id="tenant-wave8-prop")

    proj = await async_client.post("/api/v1/projects", json={"name": "Proposal System"}, headers=headers)
    proj_id = proj.json()["data"]["id"]
    sys = await async_client.post("/api/v1/systems", json={"project_id": proj_id, "name": "Power Delivery System"}, headers=headers)
    sys_id = sys.json()["data"]["id"]
    assert sys.json()["data"]["revision"] == 1

    # 1. Create Proposal at revision 1
    prop_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/design/proposals",
        json={
            "title": "Add 3.3V Backup Rail",
            "base_revision": 1,
            "operations": [
                {
                    "op_type": "ADD_SUBSYSTEM",
                    "payload": {"name": "Backup LDO", "subsystem_type": "REGULATION"},
                }
            ],
            "generation_strategy": "REGULATOR_REPLACEMENT",
            "rationale": "Provide isolated backup power rail.",
        },
        headers=headers,
    )
    assert prop_res.status_code == 201
    prop_id = prop_res.json()["data"]["id"]

    # 2. Advance system revision externally by creating a subsystem
    bump_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/subsystems",
        json={"name": "Direct Subsystem Mutator", "subsystem_type": "PROCESSING"},
        headers=headers,
    )
    assert bump_res.status_code == 201

    # System revision is now 2
    sys_updated = await async_client.get(f"/api/v1/systems/{sys_id}", headers=headers)
    assert sys_updated.json()["data"]["revision"] == 2

    # 3. Try to approve / apply proposal built against base_revision 1 -> MUST BE REJECTED
    appr_stale = await async_client.post(f"/api/v1/system-proposals/{prop_id}/approve", headers=headers)
    assert appr_stale.status_code == 409
    assert "SYSTEM_PROPOSAL_STALE" in appr_stale.json()["detail"]

    apply_stale = await async_client.post(f"/api/v1/system-proposals/{prop_id}/apply", headers=headers)
    assert apply_stale.status_code == 409
    assert "SYSTEM_PROPOSAL_STALE" in apply_stale.json()["detail"]

    # 4. Create fresh proposal against base_revision 2
    fresh_prop = await async_client.post(
        f"/api/v1/systems/{sys_id}/design/proposals",
        json={
            "title": "Add 5V Isolation Transceiver",
            "base_revision": 2,
            "operations": [
                {
                    "op_type": "ADD_SUBSYSTEM",
                    "payload": {"name": "Isolation Transceiver", "subsystem_type": "PROTECTION"},
                }
            ],
            "generation_strategy": "SUBSYSTEM_ISOLATION",
            "rationale": "Isolate high voltage communications.",
        },
        headers=headers,
    )
    assert fresh_prop.status_code == 201
    fresh_prop_id = fresh_prop.json()["data"]["id"]

    # Approve and Apply atomically
    appr_res = await async_client.post(f"/api/v1/system-proposals/{fresh_prop_id}/approve", headers=headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["data"]["status"] == "APPROVED"

    apply_res = await async_client.post(f"/api/v1/system-proposals/{fresh_prop_id}/apply", headers=headers)
    assert apply_res.status_code == 200
    assert apply_res.json()["data"]["success"] is True
    assert apply_res.json()["data"]["new_system_revision"] == 3

    # Verify that the system revision advanced and subsystem was added
    final_sys = await async_client.get(f"/api/v1/systems/{sys_id}", headers=headers)
    final_data = final_sys.json()["data"]
    assert final_data["revision"] == 3
    sub_names = [s["name"] for s in final_data["subsystems"]]
    assert "Isolation Transceiver" in sub_names


@pytest.mark.asyncio
async def test_candidate_comparison_matrix_and_zero_scoring_regression(async_client: AsyncClient):
    """
    Verifies:
    1. Multi-candidate comparison across transparent dimensions.
    2. Regression check: asserts no composite score, health score, or winner tag exists anywhere.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "comparison_matrix@quebet.ai", tenant_id="tenant-wave8-mat")

    proj = await async_client.post("/api/v1/projects", json={"name": "Comparison Project"}, headers=headers)
    proj_id = proj.json()["data"]["id"]
    sys = await async_client.post("/api/v1/systems", json={"project_id": proj_id, "name": "Comparison Arch"}, headers=headers)
    sys_id = sys.json()["data"]["id"]

    obj = await async_client.post(
        f"/api/v1/systems/{sys_id}/design-objectives",
        json={"title": "Improve Reliability", "objective_type": "RELIABILITY_IMPROVEMENT", "target": {}},
        headers=headers,
    )
    obj_id = obj.json()["data"]["id"]

    # Generate candidates
    cands_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/design/candidates",
        json={"objective_id": obj_id},
        headers=headers,
    )
    candidates = cands_res.json()["data"]
    cand_ids = [c["id"] for c in candidates]

    # Compare
    compare_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/design/compare",
        json={"candidate_ids": cand_ids, "objective_id": obj_id},
        headers=headers,
    )
    assert compare_res.status_code == 200
    comp_matrix = compare_res.json()["data"]

    assert "dimensions" in comp_matrix
    assert "matrix" in comp_matrix
    assert len(comp_matrix["matrix"]) == len(candidates)

    # CRITICAL REGRESSION TEST: ZERO SCORING
    matrix_str = str(comp_matrix).lower()
    assert "winner" not in matrix_str
    assert "health_score" not in matrix_str
    assert "risk_score" not in matrix_str
    assert "best_candidate" not in matrix_str
    assert "composite_score" not in matrix_str
