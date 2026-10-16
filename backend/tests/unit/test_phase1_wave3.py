import time
import pytest
from httpx import AsyncClient
from app.core.security import create_access_token
from app.services.ai.analysis.circuit_analysis_service import CircuitAnalysisService
from app.services.ai.analysis.engines.margin_engine import calculate_margin
from app.services.ai.analysis.engines.ohms_law import calculate_ohms_law
from app.services.ai.analysis.engines.rc_time_constant import calculate_rc_time_constant
from app.services.ai.analysis.engines.regulator_analyzer import analyze_linear_regulator
from app.services.ai.analysis.engines.voltage_divider import calculate_voltage_divider
from app.services.ai.analysis.graph_analyzer import CircuitGraphAnalyzer
from app.services.ai.analysis.rule_engine import CircuitRuleEngine
from app.services.ai.analysis.spec_resolver import ComponentSpecificationResolver
from app.services.ai.analysis.units import (
    format_engineering,
    parse_capacitance,
    parse_current,
    parse_power,
    parse_resistance,
    parse_voltage,
)


@pytest.fixture
def auth_headers():
    token = create_access_token("wave3-eng-1", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-wave3-a"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_tenant_headers():
    token = create_access_token("wave3-eng-2", claims={"role": "user", "plan": "pro", "tenant_id": "tenant-wave3-b"})
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. UNIT & PARSER TESTS
# ==============================================================================
def test_unit_parsing():
    assert parse_resistance("10k") == 10000.0
    assert parse_resistance("4.7k") == 4700.0
    assert parse_resistance("4k7") == 4700.0
    assert parse_resistance("220R") == 220.0
    assert parse_resistance("1M") == 1000000.0
    assert parse_resistance("0.5") == 0.5
    assert parse_resistance(100) == 100.0
    assert parse_resistance("invalid") is None

    assert parse_capacitance("100nF") == pytest.approx(100e-9)
    assert parse_capacitance("0.1uF") == pytest.approx(0.1e-6)
    assert parse_capacitance("4u7") == pytest.approx(4.7e-6)
    assert parse_capacitance("22pF") == pytest.approx(22e-12)

    assert parse_voltage("3.3V") == 3.3
    assert parse_voltage("3V3") == 3.3
    assert parse_voltage("500mV") == 0.5
    assert parse_voltage("12V") == 12.0

    assert parse_current("500mA") == 0.5
    assert parse_current("1.5A") == 1.5

    assert parse_power("0.25W") == 0.25
    assert parse_power("1/4W") == 0.25
    assert parse_power("1/8W") == 0.125

    assert "10.00 kΩ" in format_engineering(10000, "Ω")
    assert "100.00 µF" in format_engineering(0.0001, "F")


# ==============================================================================
# 2. SPECIFICATION RESOLVER TESTS (ELECTRONICS-KB)
# ==============================================================================
def test_specification_resolver():
    resolver = ComponentSpecificationResolver()

    # Resistor with package footprint 0805
    res_spec = resolver.resolve_resistor_specs({
        "component_type": "resistor",
        "value": "10k",
        "footprint": "RES_0805",
    })
    assert res_spec["resistance_ohms"] == 10000.0
    assert res_spec["rated_power_w"] == 0.125
    assert res_spec["provenance"] == "ELECTRONICS_KB"

    # Resistor with explicit property rating
    res_spec_explicit = resolver.resolve_resistor_specs({
        "component_type": "resistor",
        "value": "220R",
        "properties": {"power_rating": "0.5W"},
    })
    assert res_spec_explicit["resistance_ohms"] == 220.0
    assert res_spec_explicit["rated_power_w"] == 0.5
    assert res_spec_explicit["provenance"] == "CIRCUIT_SPECIFIED"

    # IC Regulator LM7805
    reg_spec = resolver.resolve_regulator_specs({
        "component_type": "regulator",
        "part_number": "LM7805",
    })
    assert reg_spec["v_out"] == 5.0
    assert reg_spec["v_in_min"] == 7.0
    assert reg_spec["v_in_max"] == 25.0
    assert reg_spec["i_out_max_a"] == 1.5
    assert reg_spec["provenance"] == "ELECTRONICS_KB"

    # Unknown component
    unknown_spec = resolver.resolve_regulator_specs({
        "component_type": "regulator",
        "part_number": "UNKNOWN_IC_999",
    })
    assert unknown_spec["provenance"] == "SPECIFICATION_NOT_FOUND"


# ==============================================================================
# 3. DETERMINISTIC CALCULATION ENGINES
# ==============================================================================
def test_ohms_law_engine():
    # V=5V, R=1k -> I=5mA, P=25mW
    calc = calculate_ohms_law(voltage=5.0, resistance=1000.0)
    assert calc["result"]["current_ma"] == 5.0
    assert calc["result"]["power_mw"] == 25.0
    assert calc["confidence"] == "HIGH"

    # Zero resistance protection
    err_calc = calculate_ohms_law(voltage=5.0, resistance=0.0)
    assert "error" in err_calc["result"]
    assert err_calc["confidence"] == "LOW"


def test_voltage_divider_engine():
    # Vin=12V, R1=10k, R2=10k -> Vout=6V
    calc = calculate_voltage_divider(v_in=12.0, r1=10000.0, r2=10000.0)
    assert calc["result"]["vout_v"] == 6.0
    assert calc["result"]["divider_ratio"] == 0.5
    assert calc["result"]["divider_current_ma"] == 0.6
    assert calc["confidence"] == "HIGH"


def test_rc_time_constant_engine():
    # R=10k, C=100nF -> tau=1ms, fc ~ 159.15Hz
    calc = calculate_rc_time_constant(resistance_ohms=10000.0, capacitance_farads=100e-9)
    assert round(calc["result"]["time_constant_ms"], 1) == 1.0
    assert round(calc["result"]["cutoff_frequency_hz"], 1) == 159.2
    assert calc["confidence"] == "HIGH"


def test_regulator_analyzer_engine():
    specs = {
        "dropout_voltage_v": 2.0,
        "quiescent_current_ma": 5.0,
        "r_theta_ja": 54.0,
        "max_junction_temp_c": 125.0,
    }
    # Vin=12V, Vout=5V, Iload=0.5A -> Pd = 7V * 0.5A + 12V * 0.005A = 3.56W
    calc = analyze_linear_regulator(v_in=12.0, v_out=5.0, i_load_a=0.5, specs=specs)
    assert calc["result"]["has_adequate_headroom"] is True
    assert round(calc["result"]["power_dissipated_w"], 1) == 3.6
    assert calc["result"]["junction_temp_c"] > 100.0


def test_margin_engine():
    # 0.2W actual on 0.25W rated -> utilization 80% (adequate)
    calc1 = calculate_margin(actual=0.2, rated=0.25, parameter_name="Power")
    assert calc1["result"]["utilization_pct"] == 80.0
    assert calc1["result"]["status"] == "ADEQUATE"

    # 0.22W actual on 0.25W rated -> utilization 88% (insufficient margin)
    calc2 = calculate_margin(actual=0.22, rated=0.25, parameter_name="Power")
    assert calc2["result"]["status"] == "INSUFFICIENT_MARGIN"

    # 0.3W actual on 0.25W rated -> utilization 120% (overstressed)
    calc3 = calculate_margin(actual=0.3, rated=0.25, parameter_name="Power")
    assert calc3["result"]["status"] == "OVERSTRESSED"


# ==============================================================================
# 4. RULE ENGINE TESTS (R001 to R008)
# ==============================================================================
def test_rules_r001_to_r008():
    components = [
        {"id": "c1", "name": "R_BAD", "component_type": "RESISTOR", "value": "-10k"},
        {"id": "c2", "name": "ESP32_1", "component_type": "MICROCONTROLLER", "value": "ESP32-WROOM-32", "pins": [{"id": "p1", "name": "RESET", "number": "3"}]},
        {"id": "c3", "name": "U1", "component_type": "REGULATOR", "value": "LM7805", "pins": [{"id": "p_vin", "name": "VIN", "number": "1"}]},
        {"id": "c4", "name": "R_HOT", "component_type": "RESISTOR", "value": "100R", "footprint": "0402"},
    ]
    nets = [
        {"id": "n_high", "name": "30V"},
        {"id": "n_5v", "name": "+5V"},
        {"id": "n_gnd", "name": "GND"},
    ]
    connections = [
        {"id": "conn1", "component_id": "c3", "pin_id": "p_vin", "net_id": "n_high"},
        {"id": "conn2", "component_id": "c2", "pin_id": "p2", "net_id": "n_5v"},
    ]

    graph = CircuitGraphAnalyzer(components, nets, connections)
    specs = ComponentSpecificationResolver()

    # Calculations with overstressed resistor
    calcs = [
        {
            "category": "MARGIN",
            "component_ids": ["c4"],
            "inputs": {"actual": 0.25, "rated": 0.0625, "parameter": "Power Dissipation"},
            "result": {"status": "OVERSTRESSED", "utilization_pct": 400.0},
        }
    ]

    rule_engine = CircuitRuleEngine(graph, specs, calcs)
    findings = rule_engine.evaluate_all()

    rule_ids = {f["rule_id"] for f in findings}

    # Verify R001 (invalid value on R_BAD)
    assert "R001" in rule_ids
    # Verify R002 (floating pin on ESP32 RESET)
    assert "R002" in rule_ids
    # Verify R003 (excessive power on R_HOT)
    assert "R003" in rule_ids
    # Verify R004 (LM7805 input 30V > 25V max)
    assert "R004" in rule_ids
    # Verify R007 (missing decoupling capacitor on LM7805/ESP32)
    assert "R007" in rule_ids
    # Verify R008 (ESP32 directly connected to +5V)
    assert "R008" in rule_ids


# ==============================================================================
# 5. ORCHESTRATION & PERFORMANCE (< 500ms)
# ==============================================================================
def test_analysis_orchestration_and_latency():
    service = CircuitAnalysisService()

    circuit_data = {
        "components": [
            {"id": "c1", "name": "R1", "component_type": "RESISTOR", "value": "1k", "footprint": "0805"},
            {"id": "c2", "name": "R2", "component_type": "RESISTOR", "value": "1k", "footprint": "0805"},
        ],
        "nets": [
            {"id": "n1", "name": "+5V"},
            {"id": "n2", "name": "MID"},
            {"id": "n3", "name": "GND"},
        ],
        "connections": [
            {"component_id": "c1", "net_id": "n1"},
            {"component_id": "c1", "net_id": "n2"},
            {"component_id": "c2", "net_id": "n2"},
            {"component_id": "c2", "net_id": "n3"},
        ],
    }

    t0 = time.perf_counter()
    res = service.analyze_circuit(circuit_data)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 500.0, f"Analysis took {elapsed_ms}ms, exceeding 500ms threshold"
    assert res["status"] in ["COMPLETE", "PARTIAL", "BLOCKED"]
    assert res["confidence"] in ["HIGH", "MEDIUM", "LOW"]
    assert len(res["calculations"]) > 0


# ==============================================================================
# 6. END-TO-END API & TENANT ISOLATION TESTS
# ==============================================================================
@pytest.mark.asyncio
async def test_analysis_api_and_tenant_isolation(
    async_client: AsyncClient,
    auth_headers: dict,
    other_tenant_headers: dict,
):
    # 1. Create project and circuit for tenant A
    proj_res = await async_client.post(
        "/api/v1/projects",
        json={"name": "Analysis Project", "project_type": "power"},
        headers=auth_headers,
    )
    assert proj_res.status_code == 201
    project_id = proj_res.json()["data"]["id"]

    circ_res = await async_client.post(
        f"/api/v1/projects/{project_id}/circuits",
        json={"name": "Divider Circuit", "description": "12V to 5V Divider"},
        headers=auth_headers,
    )
    assert circ_res.status_code == 201
    circuit_id = circ_res.json()["data"]["id"]

    # 2. Add R1 and R2
    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R1", "component_type": "resistor", "value": "10k", "package": "0805"},
        headers=auth_headers,
    )
    await async_client.post(
        f"/api/v1/circuits/{circuit_id}/components",
        json={"ref_des": "R2", "component_type": "resistor", "value": "10k", "package": "0805"},
        headers=auth_headers,
    )

    # 3. Trigger analysis endpoint
    an_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/analyze",
        headers=auth_headers,
    )
    assert an_res.status_code == 200
    an_data = an_res.json()["data"]
    assert an_data["circuit_id"] == circuit_id
    assert an_data["status"] in ["COMPLETE", "PARTIAL", "BLOCKED"]
    assert an_data["confidence"] in ["HIGH", "MEDIUM", "LOW"]
    analysis_id = an_data["id"]

    # 4. Fetch latest analysis
    latest_res = await async_client.get(
        f"/api/v1/circuits/{circuit_id}/analysis/latest",
        headers=auth_headers,
    )
    assert latest_res.status_code == 200
    assert latest_res.json()["data"]["id"] == analysis_id

    # 5. Call AI explanation endpoint
    explain_res = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/explain",
        json={"user_query": "Explain power and stress margins for this circuit."},
        headers=auth_headers,
    )
    assert explain_res.status_code == 200
    exp_data = explain_res.json()["data"]
    assert len(exp_data["explanation"]) > 0
    assert len(exp_data["identified_mechanisms"]) > 0
    assert len(exp_data["engineering_tradeoffs"]) > 0

    # 6. Tenant isolation: Tenant B cannot access Tenant A's analysis
    other_get = await async_client.get(
        f"/api/v1/circuits/{circuit_id}/analysis/latest",
        headers=other_tenant_headers,
    )
    assert other_get.status_code == 404

    other_explain = await async_client.post(
        f"/api/v1/circuits/{circuit_id}/explain",
        json={},
        headers=other_tenant_headers,
    )
    assert other_explain.status_code == 404
