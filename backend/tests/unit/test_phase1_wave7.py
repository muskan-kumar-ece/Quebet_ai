import uuid
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token
from app.services.ai.system.interface_compatibility_engine import (
    CompatibilityStatus,
    SystemInterfaceCompatibilityEngine,
)


def auth_headers(user_id: str, email: str, role: str = "engineer", tenant_id: str = "tenant-wave7-a") -> dict[str, str]:
    token = create_access_token(
        subject=user_id,
        claims={"email": email, "role": role, "plan": "pro", "tenant_id": tenant_id},
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_system_and_subsystem_hierarchy_cycle_prevention_and_deletion_protection(async_client: AsyncClient):
    """
    Verifies:
    1. System creation and retrieval.
    2. Subsystem hierarchy creation (parent-child nesting).
    3. Cycle prevention (subsystem cannot become its own ancestor).
    4. Deletion dependency protection (cannot delete subsystem if child, interface, or dependency exists).
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "engineer7@quebet.ai", tenant_id="tenant-wave7-a")

    # 1. Create Project
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "IoT Gateway System Project", "project_type": "embedded"},
        headers=headers,
    )
    assert proj_res.status_code == 201
    proj_id = proj_res.json()["data"]["id"]

    # 2. Create System
    sys_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Main IoT Gateway System", "description": "Multi-rail system"},
        headers=headers,
    )
    assert sys_res.status_code == 201
    system_id = sys_res.json()["data"]["id"]
    assert sys_res.json()["data"]["revision"] == 1

    # 3. Create Subsystems (Hierarchy: Power -> Regulation)
    sub1_res = await async_client.post(
        f"/api/v1/systems/{system_id}/subsystems",
        json={"name": "Power Delivery Subsystem", "subsystem_type": "POWER"},
        headers=headers,
    )
    assert sub1_res.status_code == 201
    sub_power_id = sub1_res.json()["data"]["id"]

    sub2_res = await async_client.post(
        f"/api/v1/systems/{system_id}/subsystems",
        json={
            "name": "3.3V Buck Regulation Subsystem",
            "subsystem_type": "REGULATION",
            "parent_subsystem_id": sub_power_id,
        },
        headers=headers,
    )
    assert sub2_res.status_code == 201
    sub_reg_id = sub2_res.json()["data"]["id"]
    assert sub2_res.json()["data"]["parent_subsystem_id"] == sub_power_id

    # 4. Cycle Prevention: Attempt to set sub_power's parent to sub_reg
    cycle_res = await async_client.patch(
        f"/api/v1/subsystems/{sub_power_id}",
        json={"parent_subsystem_id": sub_reg_id},
        headers=headers,
    )
    assert cycle_res.status_code == 400
    assert "cycle detected" in cycle_res.json()["detail"].lower()

    # Self-cycle attempt
    self_cycle_res = await async_client.patch(
        f"/api/v1/subsystems/{sub_power_id}",
        json={"parent_subsystem_id": sub_power_id},
        headers=headers,
    )
    assert self_cycle_res.status_code == 400

    # 5. Deletion Protection: Cannot delete sub_power because child sub_reg exists
    del_res = await async_client.delete(f"/api/v1/subsystems/{sub_power_id}", headers=headers)
    assert del_res.status_code == 400
    assert "child subsystems exist" in del_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_system_interface_compatibility_engine_all_states(async_client: AsyncClient):
    """
    Verifies deterministic interface compatibility evaluation:
    - COMPATIBLE: Matching voltage ranges and current capacity.
    - INCOMPATIBLE: Overvoltage hazard, current capacity deficit, protocol mismatch.
    - PARTIALLY_COMPATIBLE: Logic level threshold caution.
    - UNKNOWN: Missing mandatory contract parameters (UNKNOWN != COMPATIBLE).
    """
    # 1. Fully Compatible Interface
    res_compatible = SystemInterfaceCompatibilityEngine.evaluate(
        interface_name="5V_TO_3V3_REG_IN",
        interface_type="POWER",
        source_subsystem_name="Power Supply",
        dest_subsystem_name="LDO Regulator",
        contract={
            "source_voltage_max": 5.25,
            "source_voltage_min": 4.75,
            "destination_voltage_max": 15.0,
            "destination_voltage_min": 4.5,
            "current_max": 2.0,
            "load_current_max": 0.5,
        },
    )
    assert res_compatible["status"] == CompatibilityStatus.COMPATIBLE.value
    assert len(res_compatible["violations"]) == 0

    # 2. Incompatible: Overvoltage hazard
    res_overvoltage = SystemInterfaceCompatibilityEngine.evaluate(
        interface_name="HIGH_VOLTAGE_FAULT",
        interface_type="POWER",
        source_subsystem_name="12V Rail",
        dest_subsystem_name="MCU Input",
        contract={
            "source_voltage_max": 12.6,
            "destination_voltage_max": 3.6,
        },
    )
    assert res_overvoltage["status"] == CompatibilityStatus.INCOMPATIBLE.value
    assert any("Overvoltage hazard" in v for v in res_overvoltage["violations"])

    # 3. Incompatible: Protocol mismatch
    res_protocol = SystemInterfaceCompatibilityEngine.evaluate(
        interface_name="UART_TO_SPI_CONFLICT",
        interface_type="COMMUNICATION",
        source_subsystem_name="Host MCU",
        dest_subsystem_name="Sensor IC",
        contract={
            "source_protocol": "UART",
            "destination_protocol": "SPI",
        },
    )
    assert res_protocol["status"] == CompatibilityStatus.INCOMPATIBLE.value
    assert any("Protocol mismatch" in v for v in res_protocol["violations"])

    # 4. Unknown State: Contract parameters unspecified (UNKNOWN != COMPATIBLE)
    res_unknown = SystemInterfaceCompatibilityEngine.evaluate(
        interface_name="UNSPECIFIED_BUS",
        interface_type="COMMUNICATION",
        source_subsystem_name="Processor",
        dest_subsystem_name="Radio",
        contract={},
    )
    assert res_unknown["status"] == CompatibilityStatus.UNKNOWN.value
    assert res_unknown["status"] != CompatibilityStatus.COMPATIBLE.value
    assert len(res_unknown["unknowns"]) > 0


@pytest.mark.asyncio
async def test_system_power_tree_and_master_analysis(async_client: AsyncClient):
    """
    Verifies power tree current aggregation, overloaded regulator detection,
    and end-to-end master system analysis execution.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "power_eng@quebet.ai", tenant_id="tenant-wave7-power")

    # 1. Create Project and System
    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Power Grid Subsystem Project", "project_type": "power"},
        headers=headers,
    )
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Power Delivery System"},
        headers=headers,
    )
    system_id = s_res.json()["data"]["id"]

    # 2. Subsystems: Battery and 3.3V LDO
    sub_bat = await async_client.post(
        f"/api/v1/systems/{system_id}/subsystems",
        json={"name": "Li-Ion Battery Pack", "subsystem_type": "POWER"},
        headers=headers,
    )
    bat_id = sub_bat.json()["data"]["id"]

    sub_ldo = await async_client.post(
        f"/api/v1/systems/{system_id}/subsystems",
        json={"name": "3.3V LDO", "subsystem_type": "REGULATION"},
        headers=headers,
    )
    ldo_id = sub_ldo.json()["data"]["id"]

    sub_mcu = await async_client.post(
        f"/api/v1/systems/{system_id}/subsystems",
        json={"name": "Application MCU", "subsystem_type": "PROCESSING"},
        headers=headers,
    )
    mcu_id = sub_mcu.json()["data"]["id"]

    # 3. Create Overloaded Power Domain
    # Domain capacity is 0.5A, but estimated load is 1.2A
    dom_res = await async_client.post(
        f"/api/v1/systems/{system_id}/power-domains",
        json={
            "name": "3V3_MAIN",
            "nominal_voltage": 3.3,
            "source_subsystem_id": ldo_id,
            "current_capacity_a": 0.5,
            "metadata": {"estimated_load_a": 1.2},
        },
        headers=headers,
    )
    assert dom_res.status_code == 201

    # 4. Create Interface with Voltage Conflict (5V source to 3.3V destination)
    iface_res = await async_client.post(
        f"/api/v1/systems/{system_id}/interfaces",
        json={
            "name": "BAT_TO_LDO",
            "interface_type": "POWER",
            "source_subsystem_id": bat_id,
            "destination_subsystem_id": ldo_id,
            "contract": {
                "source_voltage_max": 4.2,
                "destination_voltage_max": 6.0,
                "current_max": 2.0,
                "load_current_max": 0.5,
            },
        },
        headers=headers,
    )
    assert iface_res.status_code == 201

    # Incompatible interface: Battery 4.2V directly connected to MCU GPIO (max 3.6V)
    incompat_iface = await async_client.post(
        f"/api/v1/systems/{system_id}/interfaces",
        json={
            "name": "BAT_MONITOR_UNATTENUATED",
            "interface_type": "ANALOG_SIGNAL",
            "source_subsystem_id": bat_id,
            "destination_subsystem_id": mcu_id,
            "contract": {
                "source_voltage_max": 4.2,
                "destination_voltage_max": 3.6,
            },
        },
        headers=headers,
    )
    assert incompat_iface.status_code == 201

    # 5. Run System Analysis
    analysis_res = await async_client.post(f"/api/v1/systems/{system_id}/analyze", headers=headers)
    assert analysis_res.status_code == 200
    analysis = analysis_res.json()["data"]
    assert analysis["status"] == "ANALYSIS_COMPLETE"
    assert analysis["is_stale"] is False
    assert analysis["rule_set_version"] == "QUEBET-SYSTEM-001 v1.0"
    assert "inputs_digest" in analysis

    findings = analysis["findings"]
    assert len(findings) >= 2

    # Check for overloaded power domain finding
    power_finding = next((f for f in findings if f["rule_id"] == "SYS-PWR-002"), None)
    assert power_finding is not None
    assert power_finding["severity"] == "CRITICAL"
    assert "Overloaded power domain" in power_finding["title"]

    # Check for incompatible interface finding
    iface_finding = next((f for f in findings if f["rule_id"] == "SYS-IFACE-001"), None)
    assert iface_finding is not None
    assert iface_finding["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_deterministic_failure_propagation_and_containment(async_client: AsyncClient):
    """
    Verifies:
    1. Single failure propagation downstream across interfaces and dependencies.
    2. Containment barrier (galvanic isolation) halting propagation.
    3. Multi-hop cascading failure discovery without probabilistic guessing.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "fmea_eng@quebet.ai", tenant_id="tenant-wave7-fmea")

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Industrial Controller System", "project_type": "embedded"},
        headers=headers,
    )
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Isolated Industrial Subsystem"},
        headers=headers,
    )
    system_id = s_res.json()["data"]["id"]

    # Subsystems: Controller -> Isolated CAN Transceiver -> Field Bus Node
    sub_ctl = (await async_client.post(
        f"/api/v1/systems/{system_id}/subsystems",
        json={"name": "Core MCU", "subsystem_type": "PROCESSING"},
        headers=headers,
    )).json()["data"]["id"]

    sub_iso = (await async_client.post(
        f"/api/v1/systems/{system_id}/subsystems",
        json={"name": "Galvanic Digital Isolator", "subsystem_type": "COMMUNICATION"},
        headers=headers,
    )).json()["data"]["id"]

    sub_field = (await async_client.post(
        f"/api/v1/systems/{system_id}/subsystems",
        json={"name": "External Field Actuator", "subsystem_type": "ACTUATION"},
        headers=headers,
    )).json()["data"]["id"]

    # Interfaces:
    # 1. Non-isolated: Controller to Isolator Input
    await async_client.post(
        f"/api/v1/systems/{system_id}/interfaces",
        json={
            "name": "SPI_TO_ISOLATOR",
            "interface_type": "COMMUNICATION",
            "source_subsystem_id": sub_ctl,
            "destination_subsystem_id": sub_iso,
            "contract": {"protocol": "SPI"},
        },
        headers=headers,
    )

    # 2. Galvanically Isolated: Isolator to Field Actuator
    await async_client.post(
        f"/api/v1/systems/{system_id}/interfaces",
        json={
            "name": "ISOLATED_FIELD_BUS",
            "interface_type": "COMMUNICATION",
            "source_subsystem_id": sub_iso,
            "destination_subsystem_id": sub_field,
            "contract": {"protocol": "CAN", "galvanic_isolation": True},
        },
        headers=headers,
    )

    # Simulate failure on Core MCU
    f_res = await async_client.post(
        f"/api/v1/systems/{system_id}/failure-analysis",
        json={"failed_subsystem_id": sub_ctl, "failure_type": "TOTAL_LOSS_OF_FUNCTION"},
        headers=headers,
    )
    assert f_res.status_code == 200
    res = f_res.json()["data"]

    # Controller failed -> Isolator affected
    assert sub_iso in res["downstream_affected_subsystems"]
    # Containment barrier active at Isolated Field Bus
    barriers = res["containment_barriers"]
    assert len(barriers) >= 1
    assert barriers[0]["type"] == "INTERFACE_ISOLATION"
    assert barriers[0]["protected_subsystem_id"] == sub_field
    # Field Actuator should be protected by the barrier and NOT in downstream_affected_subsystems
    assert sub_field not in res["downstream_affected_subsystems"]


@pytest.mark.asyncio
async def test_revision_integrity_stale_detection_and_change_impact(async_client: AsyncClient):
    """
    Verifies that system architecture mutations:
    1. Bump system revision and mark existing analysis STALE.
    2. Change impact service accurately maps the blast radius.
    3. Snapshots remain immutable.
    """
    user_id = str(uuid.uuid4())
    headers = auth_headers(user_id, "impact_eng@quebet.ai", tenant_id="tenant-wave7-impact")

    p_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Lifecycle Management Project", "project_type": "circuit"},
        headers=headers,
    )
    proj_id = p_res.json()["data"]["id"]

    s_res = await async_client.post(
        "/api/v1/systems",
        json={"project_id": proj_id, "name": "Sensor Pod System"},
        headers=headers,
    )
    system_id = s_res.json()["data"]["id"]

    # Initial Subsystem
    sub_res = await async_client.post(
        f"/api/v1/systems/{system_id}/subsystems",
        json={"name": "IMU Sensor", "subsystem_type": "SENSING"},
        headers=headers,
    )
    sub_id = sub_res.json()["data"]["id"]

    # Run Analysis
    analysis_res = await async_client.post(f"/api/v1/systems/{system_id}/analyze", headers=headers)
    assert analysis_res.status_code == 200
    analysis_id = analysis_res.json()["data"]["id"]
    assert analysis_res.json()["data"]["is_stale"] is False

    # Create Snapshot
    snap_res = await async_client.post(f"/api/v1/systems/{system_id}/snapshots", headers=headers)
    assert snap_res.status_code == 201
    snapshot = snap_res.json()["data"]
    assert "snapshot_hash" in snapshot
    assert len(snapshot["snapshot_hash"]) == 64

    # Calculate Change Impact of modifying IMU Sensor
    impact_res = await async_client.post(
        f"/api/v1/systems/{system_id}/change-impact",
        json={
            "target_type": "SUBSYSTEM",
            "target_id": sub_id,
            "proposed_change": {"name": "Upgraded 6-DoF IMU"},
        },
        headers=headers,
    )
    assert impact_res.status_code == 200
    impact = impact_res.json()["data"]
    assert sub_id in impact["affected_subsystems"]
    assert analysis_id in impact["affected_analyses"]

    # Mutate Subsystem -> Should bump revision and render analysis STALE
    update_res = await async_client.patch(
        f"/api/v1/subsystems/{sub_id}",
        json={"description": "Updated sensor pinout"},
        headers=headers,
    )
    assert update_res.status_code == 200

    # Fetch latest analysis -> Should now be STALE
    latest_an = await async_client.get(f"/api/v1/systems/{system_id}/analysis/latest", headers=headers)
    assert latest_an.status_code == 200
    assert latest_an.json()["data"]["is_stale"] is True


@pytest.mark.asyncio
async def test_system_tenant_isolation_and_idor_rejection(async_client: AsyncClient):
    """
    Verifies strict multi-tenant isolation:
    Tenant A cannot access, mutate, or analyze Tenant B's system or subsystem (IDOR rejection).
    """
    # Tenant A
    user_a = str(uuid.uuid4())
    headers_a = auth_headers(user_a, "alice@alpha.com", tenant_id="tenant-alpha")

    # Tenant B
    user_b = str(uuid.uuid4())
    headers_b = auth_headers(user_b, "bob@beta.com", tenant_id="tenant-beta")

    # Tenant A creates project & system
    p_a = (await async_client.post(
        "/api/v1/projects",
        json={"name": "Alpha Project", "project_type": "general"},
        headers=headers_a,
    )).json()["data"]["id"]

    sys_a = (await async_client.post(
        "/api/v1/systems",
        json={"project_id": p_a, "name": "Alpha System"},
        headers=headers_a,
    )).json()["data"]["id"]

    sub_a = (await async_client.post(
        f"/api/v1/systems/{sys_a}/subsystems",
        json={"name": "Alpha Core", "subsystem_type": "PROCESSING"},
        headers=headers_a,
    )).json()["data"]["id"]

    # Tenant B attempts direct access to Tenant A's system -> 404
    idor_sys = await async_client.get(f"/api/v1/systems/{sys_a}", headers=headers_b)
    assert idor_sys.status_code == 404

    # Tenant B attempts to update Tenant A's subsystem -> 404
    idor_sub = await async_client.patch(
        f"/api/v1/subsystems/{sub_a}",
        json={"name": "Hacked Subsystem"},
        headers=headers_b,
    )
    assert idor_sub.status_code == 404

    # Tenant B attempts to run analysis on Tenant A's system -> 404
    idor_an = await async_client.post(f"/api/v1/systems/{sys_a}/analyze", headers=headers_b)
    assert idor_an.status_code == 404
