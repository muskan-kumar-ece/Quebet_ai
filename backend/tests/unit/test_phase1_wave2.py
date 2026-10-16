import pytest
from httpx import AsyncClient
from app.core.security import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token("wave2-eng-1", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-alpha"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_tenant_headers():
    token = create_access_token("wave2-eng-2", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-beta"})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_component_crud_and_refdes_validation(async_client: AsyncClient, auth_headers: dict):
    # 1. Create a parent project and circuit
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Wave2 Project", "project_type": "power"},
        headers=auth_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Wave2 Circuit", "description": "Interactive Canvas Test"},
        headers=auth_headers,
    )
    assert circ_res.status_code == 201
    circuit_id = circ_res.json()["data"]["id"]

    # 2. Add Component (R1)
    comp_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={
            "ref_des": "R1",
            "component_type": "resistor",
            "value": "10k",
            "unit": "ohm",
            "package": "0805",
            "pins": [
                {"pin_number": "1", "pin_name": "1", "pin_type": "passive"},
                {"pin_number": "2", "pin_name": "2", "pin_type": "passive"},
            ],
        },
        headers=auth_headers,
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()["data"]
    assert comp_data["ref_des"] == "R1"
    assert comp_data["value"] == "10k"
    comp_id = comp_data["id"]

    # 3. Duplicate ref_des rejection
    dup_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R1", "component_type": "resistor", "value": "22k"},
        headers=auth_headers,
    )
    assert dup_res.status_code == 400
    assert "Duplicate reference designator" in dup_res.json()["detail"]

    # 4. Update Component
    patch_res = await async_client.patch(
        f"/api/v1/components/{comp_id}",
        json={"value": "47k", "tolerance": "1%"},
        headers=auth_headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["value"] == "47k"
    assert patch_res.json()["data"]["tolerance"] == "1%"

    # 5. Delete Component
    del_res = await async_client.delete(f"/api/v1/components/{comp_id}", headers=auth_headers)
    assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_net_crud_and_uniqueness(async_client: AsyncClient, auth_headers: dict):
    proj_res = await async_client.post("/api/v1/projects", json={"name": "Net Test Proj"}, headers=auth_headers)
    project_id = proj_res.json()["data"]["id"]
    circ_res = await async_client.post(f"/api/v1/projects/{project_id}/circuits", json={"name": "Net Circuit"}, headers=auth_headers)
    circuit_id = circ_res.json()["data"]["id"]

    # Add Net
    net_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/nets",
        json={"name": "VCC", "net_type": "power"},
        headers=auth_headers,
    )
    assert net_res.status_code == 200
    net_id = net_res.json()["data"]["id"]
    assert net_res.json()["data"]["name"] == "VCC"

    # Duplicate Net rejection
    dup_net = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/nets",
        json={"name": "VCC", "net_type": "power"},
        headers=auth_headers,
    )
    assert dup_net.status_code == 400

    # Update Net
    patch_net = await async_client.patch(f"/api/v1/nets/{net_id}", json={"name": "VCC_3V3"}, headers=auth_headers)
    assert patch_net.status_code == 200
    assert patch_net.json()["data"]["name"] == "VCC_3V3"

    # Delete Net
    del_net = await async_client.delete(f"/api/v1/nets/{net_id}", headers=auth_headers)
    assert del_net.status_code == 204


@pytest.mark.asyncio
async def test_connection_validation_and_integrity(async_client: AsyncClient, auth_headers: dict):
    proj_res = await async_client.post("/api/v1/projects", json={"name": "Conn Test Proj"}, headers=auth_headers)
    project_id = proj_res.json()["data"]["id"]
    circ_res = await async_client.post(f"/api/v1/projects/{project_id}/circuits", json={"name": "Conn Circuit"}, headers=auth_headers)
    circuit_id = circ_res.json()["data"]["id"]

    # Add component U1 with pins 1, 2, 3
    comp_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={
            "ref_des": "U1",
            "component_type": "regulator",
            "value": "LM7805",
            "pins": [
                {"pin_number": "1", "pin_name": "IN"},
                {"pin_number": "2", "pin_name": "GND"},
                {"pin_number": "3", "pin_name": "OUT"},
            ],
        },
        headers=auth_headers,
    )
    comp_id = comp_res.json()["data"]["id"]

    # Add Net VIN
    net_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/nets",
        json={"name": "VIN", "net_type": "power"},
        headers=auth_headers,
    )
    net_id = net_res.json()["data"]["id"]

    # 1. Connect valid pin (pin 1 -> VIN)
    conn_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/connections",
        json={"component_id": comp_id, "pin_number": "1", "net_id": net_id},
        headers=auth_headers,
    )
    assert conn_res.status_code == 200
    conn_id = conn_res.json()["data"]["id"]

    # 2. Duplicate connection rejection
    dup_conn = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/connections",
        json={"component_id": comp_id, "pin_number": "1", "net_id": net_id},
        headers=auth_headers,
    )
    assert dup_conn.status_code == 400
    assert "Duplicate connection" in dup_conn.json()["detail"]

    # 3. Invalid pin rejection (pin 99 does not exist on U1)
    inv_pin = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/connections",
        json={"component_id": comp_id, "pin_number": "99", "net_id": net_id},
        headers=auth_headers,
    )
    assert inv_pin.status_code == 400
    assert "Invalid pin reference" in inv_pin.json()["detail"]

    # 4. Delete connection
    del_conn = await async_client.delete(f"/api/v1/connections/{conn_id}", headers=auth_headers)
    assert del_conn.status_code == 204


@pytest.mark.asyncio
async def test_tenant_isolation_idor(
    async_client: AsyncClient,
    auth_headers: dict,
    other_tenant_headers: dict,
):
    # Tenant Alpha creates project and circuit
    proj = await async_client.post("/api/v1/projects", json={"name": "Tenant Alpha Proj"}, headers=auth_headers)
    proj_id = proj.json()["data"]["id"]
    circ = await async_client.post(f"/api/v1/projects/{proj_id}/circuits", json={"name": "Tenant Alpha Circ"}, headers=auth_headers)
    circ_id = circ.json()["data"]["id"]

    # Tenant Beta attempts to access Tenant Alpha circuit -> 404
    b_get = await async_client.get(f"/api/v1/circuits/{circ_id}", headers=other_tenant_headers)
    assert b_get.status_code == 404

    # Tenant Beta attempts to add component to Tenant Alpha circuit -> 404
    b_add = await async_client.post(
        f"/api/v1/circuits/{circ_id}/components",
        json={"ref_des": "R1", "component_type": "resistor", "value": "1k"},
        headers=other_tenant_headers,
    )
    assert b_add.status_code == 404


@pytest.mark.asyncio
async def test_proposal_lifecycle_validation_approval_apply(async_client: AsyncClient, auth_headers: dict):
    proj = await async_client.post("/api/v1/projects", json={"name": "Proposal Proj"}, headers=auth_headers)
    proj_id = proj.json()["data"]["id"]
    circ = await async_client.post(f"/api/v1/projects/{proj_id}/circuits", json={"name": "Proposal Circuit"}, headers=auth_headers)
    circ_id = circ.json()["data"]["id"]
    assert circ.json()["data"]["version"] == 1

    # 1. Create Proposal (e.g. from AI)
    proposal_res = await async_client.post(
        f"/api/v1/circuits/{circ_id}/proposals",
        json={
            "title": "Add Decoupling Capacitor C1",
            "description": "0.1uF decoupling capacitor across VCC and GND",
            "source": "AI",
            "operations": [
                {
                    "op_type": "add_component",
                    "payload": {
                        "ref_des": "C1",
                        "component_type": "capacitor",
                        "value": "100nF",
                        "pins": [{"pin_number": "1"}, {"pin_number": "2"}],
                        "pos_x": 200,
                        "pos_y": 150,
                    },
                },
                {
                    "op_type": "add_net",
                    "payload": {"name": "GND", "net_type": "ground"},
                },
            ],
            "assumptions": [
                {"field": "dielectric", "value": "X7R", "confidence": 0.95}
            ],
        },
        headers=auth_headers,
    )
    assert proposal_res.status_code == 200
    prop_id = proposal_res.json()["data"]["id"]
    assert proposal_res.json()["data"]["status"] == "PROPOSED"

    # 2. Validate Proposal
    val_res = await async_client.post(f"/api/v1/proposals/{prop_id}/validate", headers=auth_headers)
    assert val_res.status_code == 200
    assert val_res.json()["data"]["status"] == "VALIDATED"
    assert val_res.json()["data"]["validation_result"]["status"] == "passed"

    # 3. Attempting to apply before approval must fail (400)
    apply_fail = await async_client.post(f"/api/v1/proposals/{prop_id}/apply", headers=auth_headers)
    assert apply_fail.status_code == 400
    assert "must be APPROVED" in apply_fail.json()["detail"]

    # 4. User Approves Proposal
    app_res = await async_client.post(f"/api/v1/proposals/{prop_id}/approve", headers=auth_headers)
    assert app_res.status_code == 200
    assert app_res.json()["data"]["status"] == "APPROVED"

    # 5. User Applies Approved Proposal
    applied_res = await async_client.post(f"/api/v1/proposals/{prop_id}/apply", headers=auth_headers)
    assert applied_res.status_code == 200
    assert applied_res.json()["data"]["status"] == "APPLIED"

    # 6. Verify circuit now contains C1 and GND and version was bumped to 2
    circ_check = await async_client.get(f"/api/v1/circuits/{circ_id}", headers=auth_headers)
    circ_data = circ_check.json()["data"]
    assert circ_data["version"] == 2
    comp_refs = [c["ref_des"] for c in circ_data["components"]]
    assert "C1" in comp_refs
    net_names = [n["name"] for n in circ_data["nets"]]
    assert "GND" in net_names


@pytest.mark.asyncio
async def test_circuit_export_json(async_client: AsyncClient, auth_headers: dict):
    proj = await async_client.post("/api/v1/projects", json={"name": "Export Proj"}, headers=auth_headers)
    proj_id = proj.json()["data"]["id"]
    circ = await async_client.post(f"/api/v1/projects/{proj_id}/circuits", json={"name": "Export Circuit"}, headers=auth_headers)
    circ_id = circ.json()["data"]["id"]

    exp_res = await async_client.get(f"/api/v1/circuits/{circ_id}/export/json", headers=auth_headers)
    assert exp_res.status_code == 200
    export_data = exp_res.json()["data"]
    assert export_data["format"] == "quebet_circuit_v1"
    assert export_data["circuit"]["id"] == circ_id


@pytest.mark.asyncio
async def test_schematic_objects_batch_update(async_client: AsyncClient, auth_headers: dict):
    proj = await async_client.post("/api/v1/projects", json={"name": "Batch Proj"}, headers=auth_headers)
    proj_id = proj.json()["data"]["id"]
    circ = await async_client.post(f"/api/v1/projects/{proj_id}/circuits", json={"name": "Batch Circuit"}, headers=auth_headers)
    circ_id = circ.json()["data"]["id"]

    # Add component which creates a schematic_object
    comp = await async_client.post(
        f"/api/v1/circuits/{circ_id}/components",
        json={"ref_des": "R1", "component_type": "resistor", "value": "10k"},
        headers=auth_headers,
    )
    assert comp.status_code == 200

    # Retrieve circuit to find schematic object ID
    detail = await async_client.get(f"/api/v1/circuits/{circ_id}", headers=auth_headers)
    schem_objects = detail.json()["data"]["schematic_objects"]
    assert len(schem_objects) == 1
    obj_id = schem_objects[0]["id"]

    # Batch update coordinates
    batch_res = await async_client.post(
        f"/api/v1/circuits/{circ_id}/schematic-objects/batch",
        json={
            "items": [
                {"id": obj_id, "pos_x": 340.0, "pos_y": 280.0, "rotation": 90.0}
            ]
        },
        headers=auth_headers,
    )
    assert batch_res.status_code == 200
    updated_objs = batch_res.json()["data"]
    assert len(updated_objs) == 1
    assert updated_objs[0]["pos_x"] == 340.0
    assert updated_objs[0]["pos_y"] == 280.0
    assert updated_objs[0]["rotation"] == 90.0

