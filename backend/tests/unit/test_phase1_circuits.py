import pytest
from httpx import AsyncClient
from app.core.security import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token("engineer-1", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-alpha"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_tenant_headers():
    token = create_access_token("engineer-2", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-beta"})
    return {"Authorization": f"Bearer {token}"}


# -------------------------------------------------------------
# 1. Engineering Projects
# -------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_crud_and_tenant_isolation(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    other_tenant_headers: dict[str, str],
):
    # 1. Unauthenticated creation must return 401
    unauth_resp = await async_client.post("/api/v1/projects", json={"name": "Test Project"})
    assert unauth_resp.status_code == 401

    # 2. Authenticated user creates project
    create_resp = await async_client.post(
        "/api/v1/projects",
        json={
            "name": "5V Power Supply Unit",
            "description": "Regulated bench power supply",
            "project_type": "power",
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    project_id = create_resp.json()["data"]["id"]
    assert create_resp.json()["data"]["name"] == "5V Power Supply Unit"
    assert create_resp.json()["data"]["tenant_id"] == "tenant-alpha"

    # 3. Read project
    get_resp = await async_client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["name"] == "5V Power Supply Unit"

    # 4. Tenant isolation: user from tenant-beta cannot view tenant-alpha project
    cross_tenant_resp = await async_client.get(f"/api/v1/projects/{project_id}", headers=other_tenant_headers)
    assert cross_tenant_resp.status_code == 404

    # 5. Update project
    patch_resp = await async_client.patch(
        f"/api/v1/projects/{project_id}",
        json={"description": "Updated PSU description"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["description"] == "Updated PSU description"

    # 6. List projects
    list_resp = await async_client.get("/api/v1/projects", headers=auth_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["data"]["total"] >= 1

    # 7. Soft delete project
    del_resp = await async_client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    # 8. Soft-deleted project cannot be fetched
    after_del_resp = await async_client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert after_del_resp.status_code == 404


# -------------------------------------------------------------
# 2. Circuit Graph and Structural Validation
# -------------------------------------------------------------


@pytest.mark.asyncio
async def test_circuit_creation_and_structural_validation(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
):
    # 1. Create a parent project
    proj_resp = await async_client.post(
        "/api/v1/projects",
        json={"name": "Linear Regulator Testbed", "project_type": "circuit"},
        headers=auth_headers,
    )
    assert proj_resp.status_code == 201
    project_id = proj_resp.json()["data"]["id"]

    # 2. Create structured circuit with components, nets, and assumptions
    circuit_payload = {
        "name": "LM7805 Typical Application Circuit",
        "description": "Standard 5V linear regulation with 0.33uF and 0.1uF decoupling",
        "components": [
            {
                "ref_des": "U1",
                "component_type": "linear_regulator",
                "part_number": "LM7805",
                "value": "5V",
                "package": "TO-220",
                "pins": [
                    {"pin_number": "1", "pin_name": "VI"},
                    {"pin_number": "2", "pin_name": "GND"},
                    {"pin_number": "3", "pin_name": "VO"},
                ],
            },
            {
                "ref_des": "C1",
                "component_type": "capacitor",
                "value": "0.33uF",
                "unit": "uF",
                "package": "0805",
            },
            {
                "ref_des": "C2",
                "component_type": "capacitor",
                "value": "0.1uF",
                "unit": "uF",
                "package": "0603",
            },
        ],
        "nets": [
            {"name": "VCC_IN", "net_type": "power"},
            {"name": "VOUT_5V", "net_type": "power"},
            {"name": "GND", "net_type": "ground"},
        ],
        "connections": [],
        "schematic_objects": [
            {"object_type": "symbol", "pos_x": 100.0, "pos_y": 150.0},
        ],
        "assumptions": [
            {
                "field": "ambient_temp",
                "value": "25",
                "unit": "C",
                "source": "default",
                "confidence": 0.95,
                "user_confirmed": True,
            }
        ],
    }

    circ_resp = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json=circuit_payload,
        headers=auth_headers,
    )
    assert circ_resp.status_code == 201
    circuit_id = circ_resp.json()["data"]["id"]
    circuit_data = circ_resp.json()["data"]
    assert len(circuit_data["components"]) == 3
    assert len(circuit_data["nets"]) == 3
    assert len(circuit_data["assumptions"]) == 1

    # 3. Read circuit detail
    detail_resp = await async_client.get(f"/api/v1/circuits/{circuit_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["data"]["id"] == circuit_id

    # 4. Execute deterministic structural validation
    val_resp = await async_client.post(f"/api/v1/circuits/{circuit_id}/validate", headers=auth_headers)
    assert val_resp.status_code == 200
    val_data = val_resp.json()["data"]
    assert val_data["status"] == "passed"
    assert val_data["score"] == 1.0


# -------------------------------------------------------------
# 3. Structural Validation Error Detection
# -------------------------------------------------------------


@pytest.mark.asyncio
async def test_circuit_schema_validator_catches_duplicate_ref_des():
    from app.services.ai.validators.circuit_validator import circuit_schema_validator

    # Payload with duplicate R1
    invalid_payload = {
        "components": [
            {"ref_des": "R1", "component_type": "resistor", "value": "10k"},
            {"ref_des": "R1", "component_type": "resistor", "value": "220R"},
        ],
        "nets": [{"name": "GND"}],
        "connections": [],
    }

    result = await circuit_schema_validator.validate(invalid_payload)
    assert result.status == "failed"
    codes = [e.code for e in result.errors]
    assert "DUPLICATE_REF_DES" in codes


@pytest.mark.asyncio
async def test_circuit_schema_validator_catches_invalid_pin_and_net():
    from app.services.ai.validators.circuit_validator import circuit_schema_validator

    invalid_payload = {
        "components": [
            {"ref_des": "U1", "component_type": "ic", "value": "LM7805"},
        ],
        "nets": [
            {"name": "GND"},
        ],
        "connections": [
            # References non-existent net VCC_FAKE
            {"component_id": "U1", "pin_number": "1", "net_id": "VCC_FAKE"},
            # References non-existent component U99
            {"component_id": "U99", "pin_number": "2", "net_id": "GND"},
            # Missing pin_number
            {"component_id": "U1", "pin_number": "", "net_id": "GND"},
        ],
    }

    result = await circuit_schema_validator.validate(invalid_payload)
    assert result.status == "failed"
    codes = [e.code for e in result.errors]
    assert "INVALID_NET_REFERENCE" in codes
    assert "INVALID_COMPONENT_REFERENCE" in codes
    assert "INVALID_PIN_REFERENCE" in codes


# -------------------------------------------------------------
# 4. AI Circuit Intent & Missing Requirement Tracking
# -------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_intent_detects_complete_specification(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
):
    req_body = {"prompt": "I need a 12V input to 5V regulated output at 500mA"}
    resp = await async_client.post("/api/v1/circuits/intent", json=req_body, headers=auth_headers)
    assert resp.status_code == 200

    intent = resp.json()["data"]
    assert intent["input_voltage"] == "12V"
    assert intent["output_voltage"] == "5V"
    assert "500" in intent["output_current"]
    assert intent["is_complete"] is True
    assert len(intent["missing_requirements"]) == 0
    assert len(intent["proposed_components"]) >= 3  # U1, C1, C2

    # Verify explicit assumption tracking
    assumption_fields = [a["field"] for a in intent["assumptions"]]
    assert "ambient_temperature" in assumption_fields
    assert "regulator_ic" in assumption_fields


@pytest.mark.asyncio
async def test_ai_intent_detects_missing_current_requirement(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
):
    # Prompt without current requirement
    req_body = {"prompt": "I want a 12V to 5V regulator"}
    resp = await async_client.post("/api/v1/circuits/intent", json=req_body, headers=auth_headers)
    assert resp.status_code == 200

    intent = resp.json()["data"]
    assert intent["input_voltage"] == "12V"
    assert intent["output_voltage"] == "5V"
    assert intent["output_current"] is None
    assert intent["is_complete"] is False

    # Must explicitly flag output_current as missing requirement
    missing_fields = [m["field"] for m in intent["missing_requirements"]]
    assert "output_current" in missing_fields


# -------------------------------------------------------------
# 5. Component Knowledge Base Search
# -------------------------------------------------------------


@pytest.mark.asyncio
async def test_component_knowledge_search(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
):
    resp = await async_client.get("/api/v1/components/search?q=LM7805", headers=auth_headers)
    assert resp.status_code == 200
    results = resp.json()["data"]
    assert len(results) > 0
    part_numbers = [r.get("part_number") for r in results]
    assert "LM7805" in part_numbers
