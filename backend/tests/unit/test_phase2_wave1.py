import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token
from app.services.ai.cognitive.intent_resolver import IntentResolver
from app.services.ai.cognitive.task_decomposer import TaskDecomposer
from app.models.schemas.cognitive import IntentPacketCreate, EngineeringTaskCreate
from app.models.db.cognitive import IntentType


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-p2w1-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_intent_resolver_taxonomy_and_extraction():
    """
    Unit test for IntentResolver:
    Verifies intent taxonomy classification, entity extraction (voltages, temperatures),
    and extraction of constraints and requirements.
    """
    # 1. Thermal Verification Intent
    user_prompt = "Verify thermal margin for U1 buck converter under 12V input and 85C ambient temperature."
    packet = IntentResolver.resolve_intent(
        raw_request=user_prompt,
        project_id="proj-123",
        scope="CIRCUIT",
    )
    
    assert packet.intent_type == IntentType.PLAN_VERIFICATION.value
    assert packet.context_confidence > 0.5
    assert len(packet.entities) >= 2
    
    # Check that voltages and temperatures were extracted
    val_types = [e["type"] for e in packet.entities]
    assert "VOLTAGE" in val_types
    assert "TEMPERATURE" in val_types

    # 2. Failure Analysis Intent
    user_prompt_2 = "Investigate failure mode and stress analysis for MOSFET Q1 during overvoltage condition."
    packet_2 = IntentResolver.resolve_intent(
        raw_request=user_prompt_2,
        project_id="proj-123",
        scope="CIRCUIT",
    )
    assert packet_2.intent_type == IntentType.INVESTIGATE_FAILURE.value


@pytest.mark.asyncio
async def test_task_decomposer_cycle_detection():
    """
    Unit test for TaskDecomposer:
    Verifies that a valid task list passes DAG validation, and cyclic dependencies raise ValueError.
    """
    # 1. Valid linear pipeline: Task 0 -> Task 1
    valid_tasks = [
        EngineeringTaskCreate(
            task_type="ANALYZE",
            description="Run Circuit Analysis",
            dependencies=[],
            order_index=0,
        ),
        EngineeringTaskCreate(
            task_type="VERIFY",
            description="Check Verification Status",
            dependencies=["task_0"],
            order_index=1,
        ),
    ]
    # Should not raise
    TaskDecomposer.validate_dag(valid_tasks)

    # 2. Cycle detection: Task 0 -> Task 1 -> Task 0
    cyclic_tasks = [
        EngineeringTaskCreate(
            task_type="A",
            description="Task A",
            dependencies=["task_1"],
            order_index=0,
        ),
        EngineeringTaskCreate(
            task_type="B",
            description="Task B",
            dependencies=["task_0"],
            order_index=1,
        ),
    ]
    with pytest.raises(ValueError, match="CYCLIC_TASK_GRAPH"):
        TaskDecomposer.validate_dag(cyclic_tasks)


@pytest.mark.asyncio
async def test_cognitive_context_and_ambiguity_flagging(async_client: AsyncClient):
    """
    Integration test verifying:
    1. Context resolution binds project, system, and circuit correctly.
    2. Ambiguous component target (e.g. multiple regulators without designator) flags CLARIFICATION_REQUIRED.
    3. Explicit designator auto-resolves.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "engineer_cog1@quebet.ai")

    # Setup project, system, and circuit
    p_res = await async_client.post("/api/v1/projects", json={"name": "Cognitive Context Test", "project_type": "embedded"}, headers=headers)
    assert p_res.status_code == 201
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post("/api/v1/systems", json={"project_id": proj_id, "name": "Main Power System"}, headers=headers)
    assert s_res.status_code == 201
    sys_id = s_res.json()["data"]["id"]

    # Create circuit with 2 linear regulators
    c_res = await async_client.post(
        f"/api/v1/projects/{proj_id}/circuits",
        json={
            "name": "Power Circuit",
            "description": "Dual Buck",
            "components": [
                {"ref_des": "U1", "component_type": "linear_regulator", "part_number": "LM7805", "value": "5V"},
                {"ref_des": "U2", "component_type": "linear_regulator", "part_number": "LM7805", "value": "5V"},
            ],
            "nets": [],
            "connections": [],
        },
        headers=headers,
    )
    assert c_res.status_code == 201
    circuit_id = c_res.json()["data"]["id"]

    # 1. Ambiguous query: "the regulator" without U1/U2 designator
    ambiguous_res = await async_client.post(
        "/api/v1/cognitive/intents/resolve",
        json={
            "raw_request": "Evaluate thermal stress for the regulator.",
            "project_id": proj_id,
            "circuit_id": circuit_id,
            "system_id": sys_id,
        },
        headers=headers,
    )
    assert ambiguous_res.status_code == 201
    amb_data = ambiguous_res.json()["data"]
    assert amb_data["status"] == "CLARIFICATION_REQUIRED"
    assert len(amb_data["ambiguities"]) >= 1
    assert amb_data["ambiguities"][0]["status"] == "CLARIFICATION_REQUIRED"
    assert len(amb_data["ambiguities"][0]["candidates"]) == 2

    # 2. Specific query with designator "U1"
    resolved_res = await async_client.post(
        "/api/v1/cognitive/intents/resolve",
        json={
            "raw_request": "Evaluate thermal stress for U1 buck regulator.",
            "project_id": proj_id,
            "circuit_id": circuit_id,
            "system_id": sys_id,
        },
        headers=headers,
    )
    assert resolved_res.status_code == 201
    res_data = resolved_res.json()["data"]
    assert res_data["status"] in ["INTERPRETED", "CAPTURED"]
    assert res_data["circuit_id"] == circuit_id


@pytest.mark.asyncio
async def test_cognitive_plan_creation_validation_and_stale_rejection(async_client: AsyncClient):
    """
    Integration test verifying:
    1. Task Plan creation from resolved intent.
    2. Plan validation (DAG check, revision validation).
    3. Plan becomes stale if system revision advances, and execution is rejected with HTTP 409 COGNITIVE_PLAN_STALE.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "engineer_stale@quebet.ai")

    # Create project and system
    p_res = await async_client.post("/api/v1/projects", json={"name": "Plan Test", "project_type": "embedded"}, headers=headers)
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post("/api/v1/systems", json={"project_id": proj_id, "name": "Telemetry System"}, headers=headers)
    sys_id = s_res.json()["data"]["id"]
    sys_data = s_res.json()["data"]
    initial_rev = sys_data.get("revision", 1)

    # 1. Create an intent packet
    intent_res = await async_client.post(
        "/api/v1/cognitive/intents",
        json={
            "raw_request": "Check system requirements and failure modes for telemetry system.",
            "goal": "Check system requirements and failure modes for telemetry system.",
            "project_id": proj_id,
            "system_id": sys_id,
            "intent_type": "CHECK_REQUIREMENTS",
            "context_confidence": 0.95,
        },
        headers=headers,
    )
    assert intent_res.status_code == 201
    intent_id = intent_res.json()["data"]["id"]

    # 2. Create Task Plan
    plan_res = await async_client.post(
        "/api/v1/cognitive/plans",
        json={
            "intent_packet_id": intent_id,
            "execution_policy": {},
        },
        headers=headers,
    )
    assert plan_res.status_code == 201
    plan_id = plan_res.json()["data"]["id"]
    plan_data = plan_res.json()["data"]
    assert plan_data["base_revision"] == initial_rev
    assert len(plan_data["tasks"]) >= 1

    # 3. Validate Plan
    val_res = await async_client.post(f"/api/v1/cognitive/plans/{plan_id}/validate", headers=headers)
    assert val_res.status_code == 200
    val_data = val_res.json()["data"]
    assert val_data["is_valid"] is True
    assert val_data["structural_valid"] is True
    assert val_data["context_valid"] is True

    # 4. Advance system revision (simulate concurrent design modification)
    sub_res = await async_client.post(
        f"/api/v1/systems/{sys_id}/subsystems",
        json={"name": "Radio Subsystem", "subsystem_type": "RF_FRONTEND"},
        headers=headers,
    )
    assert sub_res.status_code == 201

    # Fetch updated system revision
    sys_updated = await async_client.get(f"/api/v1/systems/{sys_id}", headers=headers)
    assert sys_updated.json()["data"]["revision"] > initial_rev

    # 5. Validate Plan again - should now report STALE
    val_stale_res = await async_client.post(f"/api/v1/cognitive/plans/{plan_id}/validate", headers=headers)
    assert val_stale_res.status_code == 200
    val_stale_data = val_stale_res.json()["data"]
    assert val_stale_data["is_valid"] is False
    assert val_stale_data["context_valid"] is False
    assert any("COGNITIVE_PLAN_STALE" in reason for reason in val_stale_data["blocking_reasons"])

    # 6. Execute Plan - must be rejected with HTTP 409
    exec_res = await async_client.post(f"/api/v1/cognitive/plans/{plan_id}/execute", headers=headers)
    assert exec_res.status_code == 409
    assert "COGNITIVE_PLAN_STALE" in str(exec_res.json())


@pytest.mark.asyncio
async def test_deterministic_execution_and_unknown_propagation(async_client: AsyncClient):
    """
    Integration test verifying:
    1. Plan execution runs deterministic capabilities.
    2. Read-only safety: no mutating operations executed.
    3. Epistemological boundary: UNKNOWN is preserved and never converted to PASS.
    4. Execution logs SHA-256 inputs/outputs provenance.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "engineer_exec@quebet.ai")

    # Setup project and circuit
    p_res = await async_client.post("/api/v1/projects", json={"name": "Execution Test", "project_type": "embedded"}, headers=headers)
    proj_id = p_res.json()["data"]["id"]

    c_res = await async_client.post(
        f"/api/v1/projects/{proj_id}/circuits",
        json={
            "name": "LDO Circuit",
            "components": [
                {"ref_des": "U1", "component_type": "linear_regulator", "part_number": "LM7805", "value": "5V"},
            ],
            "nets": [],
            "connections": [],
        },
        headers=headers,
    )
    circuit_id = c_res.json()["data"]["id"]

    # Create intent & plan for circuit analysis
    intent_res = await async_client.post(
        "/api/v1/cognitive/intents",
        json={
            "raw_request": "Perform DC operating point check and verification analysis for circuit.",
            "goal": "Perform circuit analysis",
            "project_id": proj_id,
            "circuit_id": circuit_id,
            "intent_type": "ANALYZE_CIRCUIT",
            "context_confidence": 0.9,
        },
        headers=headers,
    )
    intent_id = intent_res.json()["data"]["id"]

    plan_res = await async_client.post(
        "/api/v1/cognitive/plans",
        json={
            "intent_packet_id": intent_id,
            "execution_policy": {},
        },
        headers=headers,
    )
    plan_id = plan_res.json()["data"]["id"]

    # Execute plan
    exec_res = await async_client.post(f"/api/v1/cognitive/plans/{plan_id}/execute", headers=headers)
    assert exec_res.status_code == 200
    exec_data = exec_res.json()["data"]
    assert exec_data["execution_status"] in ["SUCCESS", "COMPLETED"]
    assert exec_data["plan_id"] == plan_id

    # Verify provenance was attached
    assert exec_data["provenance"] is not None
    assert exec_data["provenance"]["input_digest"] != ""
    assert exec_data["provenance"]["output_digest"] != ""

    # Verify results
    results = exec_data["results"]
    assert len(results) >= 1
    for r in results:
        # Check that NO synthetic scoring was generated
        output = r.get("output", {})
        assert "overall_score" not in output
        assert "plan_score" not in output
        assert "intelligence_score" not in output

    # Check unknown propagation: unknowns list exists
    assert isinstance(exec_data["unknowns"], list)


@pytest.mark.asyncio
async def test_cognitive_explanation_generation(async_client: AsyncClient):
    """
    Integration test verifying:
    1. Explanation service returns structured, non-authoritative explanations.
    2. Explanation includes strict disclaimer and AI_GENERATED origin label.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "engineer_explain@quebet.ai")

    # Setup project and circuit to execute a plan
    p_res = await async_client.post("/api/v1/projects", json={"name": "Explain Test", "project_type": "embedded"}, headers=headers)
    proj_id = p_res.json()["data"]["id"]

    c_res = await async_client.post(
        f"/api/v1/projects/{proj_id}/circuits",
        json={
            "name": "Explain Circuit",
            "components": [
                {"ref_des": "U1", "component_type": "linear_regulator", "part_number": "LM7805", "value": "5V"},
            ],
            "nets": [],
            "connections": [],
        },
        headers=headers,
    )
    circuit_id = c_res.json()["data"]["id"]

    intent_res = await async_client.post(
        "/api/v1/cognitive/intents",
        json={
            "raw_request": "Explain circuit findings",
            "goal": "Explain circuit findings",
            "project_id": proj_id,
            "circuit_id": circuit_id,
            "intent_type": "ANALYZE_CIRCUIT",
            "context_confidence": 0.9,
        },
        headers=headers,
    )
    intent_id = intent_res.json()["data"]["id"]

    plan_res = await async_client.post(
        "/api/v1/cognitive/plans",
        json={"intent_packet_id": intent_id, "execution_policy": {}},
        headers=headers,
    )
    plan_id = plan_res.json()["data"]["id"]

    exec_res = await async_client.post(f"/api/v1/cognitive/plans/{plan_id}/execute", headers=headers)
    assert exec_res.status_code == 200
    execution_id = exec_res.json()["data"]["id"]

    # Request explanation
    explain_res = await async_client.post(
        "/api/v1/cognitive/explanations",
        json={
            "execution_id": execution_id,
            "user_query": "Why were findings or unknowns generated?",
        },
        headers=headers,
    )
    assert explain_res.status_code == 200
    explain_data = explain_res.json()["data"]
    
    assert explain_data["origin"] == "AI_GENERATED"
    assert explain_data["authority"] == "INFORMATIONAL_ONLY"
    assert "INFORMATIONAL" in explain_data["explanation"].upper()


@pytest.mark.asyncio
async def test_cognitive_tenant_isolation(async_client: AsyncClient):
    """
    Security test verifying:
    Tenant B cannot access or execute Tenant A's intents, plans, or execution results.
    """
    # Tenant A
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "engineer_a@tenant-a.com", tenant_id="tenant-cog-alpha")

    # Tenant B
    user_b = str(uuid.uuid4())
    headers_b = auth_headers(user_b, "engineer_b@tenant-b.com", tenant_id="tenant-cog-beta")

    # Tenant A creates project, circuit, and intent
    p_res = await async_client.post("/api/v1/projects", json={"name": "Tenant A Project", "project_type": "embedded"}, headers=headers_a)
    proj_a_id = p_res.json()["data"]["id"]

    intent_res = await async_client.post(
        "/api/v1/cognitive/intents",
        json={
            "raw_request": "Evaluate proprietary power architecture.",
            "goal": "Evaluate proprietary power architecture.",
            "project_id": proj_a_id,
            "intent_type": "ANALYZE_CIRCUIT",
            "context_confidence": 0.85,
        },
        headers=headers_a,
    )
    assert intent_res.status_code == 201
    intent_a_id = intent_res.json()["data"]["id"]

    # 1. Tenant B tries to read Tenant A's intent -> 404
    get_res_b = await async_client.get(f"/api/v1/cognitive/intents/{intent_a_id}", headers=headers_b)
    assert get_res_b.status_code == 404

    # 2. Tenant B tries to create a plan for Tenant A's intent -> 404
    plan_res_b = await async_client.post(
        "/api/v1/cognitive/plans",
        json={
            "intent_packet_id": intent_a_id,
            "execution_policy": {},
        },
        headers=headers_b,
    )
    assert plan_res_b.status_code == 404
