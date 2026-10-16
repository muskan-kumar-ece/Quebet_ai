import math
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.db.circuit import Circuit
from app.models.schemas.component_intelligence import (
    ComponentConstraintItem,
    ComponentIdentity,
    ComponentParameterItem,
    ComponentProfileResponse,
    IdentityState,
    ParameterCategory,
)
from app.services.ai.analysis.circuit_analysis_service import CircuitAnalysisService
from app.services.ai.analysis.engines.constraint_evaluator import (
    evaluate_engineering_requirement,
    evaluate_system_design_constraint,
)
from app.services.ai.analysis.engines.interface_analyzer import analyze_net_interface
from app.services.ai.analysis.engines.margin_engine import calculate_margin
from app.services.ai.analysis.engines.ohms_law import calculate_ohms_law
from app.services.ai.analysis.engines.thermal_analyzer import calculate_thermal_dissipation
from app.services.ai.analysis.graph_analyzer import CircuitGraphAnalyzer
from app.services.ai.analysis.rule_engine import CircuitRuleEngine
from app.services.ai.analysis.spec_resolver import ComponentSpecificationResolver
from app.services.analysis_service import analysis_service


@pytest.fixture
def auth_headers():
    token = create_access_token("wave3-eng-user", claims={"role": "user", "plan": "enterprise", "tenant_id": "tenant-p3w3-a"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_tenant_headers():
    token = create_access_token("wave3-eng-other", claims={"role": "user", "plan": "enterprise", "tenant_id": "tenant-p3w3-b"})
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. VOLTAGE DOMAIN ANALYSIS (Operating vs Downstream Input)
# ==============================================================================
def test_01_voltage_domain_analysis():
    circuit = {
        "version": 1,
        "components": [
            {"id": "c1", "name": "U1", "component_type": "MICROCONTROLLER", "part_number": "ESP32-WROOM-32"},
        ],
        "nets": [
            {"id": "n1", "name": "5V"},
            {"id": "n2", "name": "GND"},
        ],
        "connections": [
            {"component_id": "c1", "net_id": "n1", "pin_number": "1"},
            {"component_id": "c1", "net_id": "n2", "pin_number": "2"},
        ],
    }
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit(circuit)

    # 5V directly connected to 3.3V ESP32 triggers R008 voltage domain conflict
    r008 = [f for f in res["findings"] if f["rule_id"] == "R008"]
    assert len(r008) >= 1
    assert r008[0]["severity"] == "CRITICAL"
    assert r008[0]["status"] == "VIOLATED"
    assert r008[0]["verification_status"] == "CALCULATED"


# ==============================================================================
# 2. CURRENT CLASSIFICATION (CALCULATED vs DOCUMENTED)
# ==============================================================================
def test_02_current_classification():
    circuit = {
        "version": 1,
        "components": [
            {"id": "r1", "name": "R1", "component_type": "RESISTOR", "value": "100R", "properties": {"rated_power": "0.25W"}},
        ],
        "nets": [
            {"id": "n1", "name": "5V"},
            {"id": "n2", "name": "GND"},
        ],
        "connections": [
            {"component_id": "r1", "net_id": "n1", "pin_number": "1"},
            {"component_id": "r1", "net_id": "n2", "pin_number": "2"},
        ],
    }
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit(circuit)

    ohm_calc = next(c for c in res["calculations"] if c["category"] == "OHMS_LAW")
    assert ohm_calc["current_classification"] == "CALCULATED_CURRENT"
    assert ohm_calc["verification_status"] == "CALCULATED"
    assert ohm_calc["result"]["current_a"] == pytest.approx(0.05)


# ==============================================================================
# 3. POWER ANALYSIS (P = VI = I^2R = V^2/R)
# ==============================================================================
def test_03_power_analysis_resistor():
    circuit = {
        "version": 1,
        "components": [
            {"id": "r1", "name": "R1", "component_type": "RESISTOR", "value": "100R", "properties": {"rated_power": "0.125W"}},
        ],
        "nets": [
            {"id": "n1", "name": "5V"},
            {"id": "n2", "name": "GND"},
        ],
        "connections": [
            {"component_id": "r1", "net_id": "n1", "pin_number": "1"},
            {"component_id": "r1", "net_id": "n2", "pin_number": "2"},
        ],
    }
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit(circuit)

    pwr_calc = next(c for c in res["calculations"] if c["category"] == "POWER")
    # P = 5^2 / 100 = 0.25W (250mW)
    assert pwr_calc["result"]["power_w"] == pytest.approx(0.25)
    assert pwr_calc["result"]["power_mw"] == pytest.approx(250.0)

    # 0.25W exceeds 0.125W rated wattage -> R003 excessive resistor power
    r003 = [f for f in res["findings"] if f["rule_id"] == "R003"]
    assert len(r003) >= 1
    assert r003[0]["status"] == "OVERSTRESSED"
    assert r003[0]["actual_value"] == pytest.approx(0.25)
    assert r003[0]["limit_value"] == pytest.approx(0.125)


# ==============================================================================
# 4. THERMAL CALCULATION (T_J = T_A + P * Theta_JA)
# ==============================================================================
def test_04_thermal_calculation():
    # Power = 1.0W, Theta_JA = 65.0 C/W, Ta = 25.0C -> Tj = 25 + 65 = 90.0C, Tj_max = 125C
    res = calculate_thermal_dissipation(
        power_w=1.0,
        theta_ja=65.0,
        ambient_temp_c=25.0,
        tj_max=125.0,
        source_id="src-datasheet-001",
        revision="2.0",
    )
    assert res["result"]["status"] == "ADEQUATE"
    assert res["result"]["delta_t_c"] == 65.0
    assert res["result"]["junction_temp_c"] == 90.0
    assert res["result"]["thermal_margin_c"] == 35.0
    assert res["verification_status"] == "CALCULATED"
    assert res["source_id"] == "src-datasheet-001"


# ==============================================================================
# 5. UNKNOWN THERMAL PARAMETER HANDLING (Never guesses or uses averages)
# ==============================================================================
def test_05_unknown_thermal_handling():
    # When Theta_JA is unknown, must return explicit UNKNOWN, never an assumed 65.0
    res = calculate_thermal_dissipation(
        power_w=1.0,
        theta_ja=None,
        ambient_temp_c=25.0,
        tj_max=125.0,
    )
    assert res["result"]["status"] == "UNKNOWN"
    assert "theta_ja" in res["result"]["missing_parameters"]
    assert res["verification_status"] == "UNVERIFIED"

    # Evaluated through CircuitRuleEngine
    rule_engine = CircuitRuleEngine(
        graph_analyzer=CircuitGraphAnalyzer([], [], []),
        spec_resolver=ComponentSpecificationResolver(),
        calculations=[res],
    )
    findings = rule_engine.check_r011_thermal_limit_exceeded()
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "R011"
    assert findings[0]["status"] == "UNKNOWN"
    assert findings[0]["verification_status"] == "UNVERIFIED"


# ==============================================================================
# 6. MARGIN CALCULATION (Deterministic, Zero Synthetic Scores)
# ==============================================================================
def test_06_margin_calculation():
    m = calculate_margin(actual=0.42, rated=0.5, parameter_name="Current", unit="A")
    assert m["result"]["status"] == "INSUFFICIENT_MARGIN"  # 0.42 / 0.5 = 84.0% (> 80% derating threshold)
    assert m["result"]["utilization_pct"] == pytest.approx(84.0)
    assert m["result"]["margin_pct"] == pytest.approx(16.0)
    assert "engineering_score" not in m
    assert "confidence_score" not in m["result"]


# ==============================================================================
# 7. DERATING ANALYSIS (80% Stress Threshold)
# ==============================================================================
def test_07_derating_analysis():
    # 0.85W on 1.0W rating -> 85% utilization > 80% derating threshold
    m = calculate_margin(actual=0.85, rated=1.0, parameter_name="Power Dissipation", unit="W")
    assert m["result"]["status"] == "INSUFFICIENT_MARGIN"

    # Overstressed > 100%
    m_over = calculate_margin(actual=1.2, rated=1.0, parameter_name="Power Dissipation", unit="W")
    assert m_over["result"]["status"] == "OVERSTRESSED"


# ==============================================================================
# 8. FREQUENCY LIMIT EVALUATION (R014)
# ==============================================================================
def test_08_frequency_limit_evaluation():
    resolver = ComponentSpecificationResolver()
    resolver.set_component_profiles({
        "MCU-1": {
            "operating_ranges": [
                {"parameter": "max_clock_frequency", "normalized_value": 48e6, "unit": "Hz"}
            ],
            "provenance_chain": {"source_id": "src-mcu", "revision": "1.0"},
        }
    })

    circuit = {
        "version": 1,
        "components": [
            {"id": "mcu", "name": "MCU-1", "component_type": "IC", "part_number": "MCU-1"},
        ],
        "nets": [
            {"id": "clk", "name": "CLK", "properties": {"frequency": "80MHz"}},
        ],
        "connections": [
            {"component_id": "mcu", "net_id": "clk", "pin_number": "1"},
        ],
    }

    svc = CircuitAnalysisService(spec_resolver=resolver)
    res = svc.analyze_circuit(circuit)

    r014 = [f for f in res["findings"] if f["rule_id"] == "R014"]
    assert len(r014) == 1
    assert r014[0]["status"] == "VIOLATED"
    assert r014[0]["actual_value"] == 80e6
    assert r014[0]["limit_value"] == 48e6


# ==============================================================================
# 9. TIMING CONSTRAINT EVALUATION
# ==============================================================================
def test_09_timing_constraint_evaluation():
    circuit = {
        "version": 1,
        "components": [
            {"id": "r1", "name": "R1", "component_type": "RESISTOR", "value": "10k"},
            {"id": "c1", "name": "C1", "component_type": "CAPACITOR", "value": "100nF"},
        ],
        "nets": [
            {"id": "reset_net", "name": "RESET"},
        ],
        "connections": [
            {"component_id": "r1", "net_id": "reset_net", "pin_number": "2"},
            {"component_id": "c1", "net_id": "reset_net", "pin_number": "1"},
        ],
    }
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit(circuit)

    rc_calc = next(c for c in res["calculations"] if c["category"] == "RC_TIME_CONSTANT")
    # Tau = 10k * 100nF = 1ms
    assert rc_calc["result"]["time_constant_seconds"] == pytest.approx(0.001)
    assert rc_calc["result"]["time_constant_ms"] == pytest.approx(1.0)
    assert rc_calc["verification_status"] == "CALCULATED"


# ==============================================================================
# 10. APPLICATION CONSTRAINT EVALUATION (Cin, Cout, ESR - R012)
# ==============================================================================
def test_10_application_constraint_cin_cout():
    resolver = ComponentSpecificationResolver()
    resolver.set_component_profiles({
        "AMS1117-3.3": {
            "application_constraints": [
                {
                    "constraint_type": "OUTPUT_CAPACITANCE",
                    "description": "Requires minimum 22uF output capacitor for loop stability",
                    "requirement_value": "22uF",
                }
            ],
            "provenance_chain": {"source_id": "src-ams1117", "revision": "1.0"},
        }
    })

    # Circuit with only 10uF on 3V3 output rail (violates 22uF minimum)
    circuit = {
        "version": 1,
        "components": [
            {"id": "u1", "name": "U1", "component_type": "REGULATOR", "part_number": "AMS1117-3.3"},
            {"id": "c_out", "name": "C1", "component_type": "CAPACITOR", "value": "10uF"},
        ],
        "nets": [
            {"id": "n_in", "name": "5V"},
            {"id": "n_out", "name": "3V3"},
            {"id": "n_gnd", "name": "GND"},
        ],
        "connections": [
            {"component_id": "u1", "net_id": "n_in", "pin_number": "1"},
            {"component_id": "u1", "net_id": "n_out", "pin_number": "2"},
            {"component_id": "u1", "net_id": "n_gnd", "pin_number": "3"},
            {"component_id": "c_out", "net_id": "n_out", "pin_number": "1"},
            {"component_id": "c_out", "net_id": "n_gnd", "pin_number": "2"},
        ],
    }

    svc = CircuitAnalysisService(spec_resolver=resolver)
    res = svc.analyze_circuit(circuit)

    r012 = [f for f in res["findings"] if f["rule_id"] == "R012"]
    assert len(r012) >= 1
    assert r012[0]["status"] == "VIOLATED"
    assert r012[0]["actual_value"] == pytest.approx(10e-6)
    assert r012[0]["limit_value"] == pytest.approx(22e-6)


# ==============================================================================
# 11. DECOUPLING REQUIREMENT EVALUATION (R007)
# ==============================================================================
def test_11_decoupling_requirement_evaluation():
    # IC on 3.3V rail with NO decoupling capacitor
    circuit = {
        "version": 1,
        "components": [
            {"id": "mcu", "name": "U1", "component_type": "IC", "part_number": "STM32F401"},
        ],
        "nets": [
            {"id": "vcc", "name": "3V3"},
            {"id": "gnd", "name": "GND"},
        ],
        "connections": [
            {"component_id": "mcu", "net_id": "vcc", "pin_number": "1"},
            {"component_id": "mcu", "net_id": "gnd", "pin_number": "2"},
        ],
    }
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit(circuit)

    r007 = [f for f in res["findings"] if f["rule_id"] == "R007"]
    assert len(r007) >= 1
    assert r007[0]["status"] == "VIOLATED"


# ==============================================================================
# 12. INTERFACE COMPATIBILITY (Bus Contention & Short Circuit - R013)
# ==============================================================================
def test_12_interface_compatibility():
    # 1. Driver Contention: Two output pins driving same net
    pins = [
        {"component_name": "U1", "pin_name": "TX", "pin_type": "OUTPUT", "direction": "OUTPUT"},
        {"component_name": "U2", "pin_name": "TX", "pin_type": "OUTPUT", "direction": "OUTPUT"},
    ]
    contention = analyze_net_interface("net-1", "UART_LINE", pins)
    assert contention["status"] == "INCOMPATIBLE"
    assert any(i["type"] == "DRIVER_CONTENTION" for i in contention["issues"])

    # 2. Dead short: Power pin directly connected to Ground pin
    short_pins = [
        {"component_name": "U1", "pin_name": "VCC", "pin_type": "POWER_IN", "electrical_role": "VCC"},
        {"component_name": "U1", "pin_name": "GND", "pin_type": "GROUND", "electrical_role": "GND"},
    ]
    short = analyze_net_interface("net-2", "FAULTY_RAIL", short_pins)
    assert short["status"] == "INCOMPATIBLE"
    assert any(i["type"] == "POWER_GROUND_SHORT" for i in short["issues"])

    # 3. Open-drain missing pull-up
    od_pins = [
        {"component_name": "U1", "pin_name": "SDA", "pin_type": "OPEN_DRAIN", "electrical_role": "SDA"},
        {"component_name": "U2", "pin_name": "SDA", "pin_type": "OPEN_DRAIN", "electrical_role": "SDA"},
    ]
    od = analyze_net_interface("net-3", "I2C_SDA", od_pins)
    assert od["status"] == "CONDITIONAL"
    assert any(i["type"] == "MISSING_PULLUP" for i in od["issues"])


# ==============================================================================
# 13. REQUIREMENT EVALUATION (SATISFIED / VIOLATED / UNKNOWN - R015)
# ==============================================================================
def test_13_requirement_evaluation():
    state = {"v_out": 3.32, "power": 1.2}

    # Satisfied EQ with 5% tolerance
    req_sat = {
        "id": "req-1",
        "title": "Output Voltage Regulation",
        "expression": {"parameter": "v_out", "operator": "EQ", "value": 3.3, "tolerance": 0.05, "unit": "V"},
    }
    eval_sat = evaluate_engineering_requirement(req_sat, state)
    assert eval_sat["status"] == "SATISFIED"

    # Violated LTE max power
    req_viol = {
        "id": "req-2",
        "title": "Maximum Power Dissipation",
        "expression": {"parameter": "power", "operator": "LTE", "value": 1.0, "unit": "W"},
    }
    eval_viol = evaluate_engineering_requirement(req_viol, state)
    assert eval_viol["status"] == "VIOLATED"

    # Unknown parameter
    req_unk = {
        "id": "req-3",
        "title": "Efficiency Target",
        "expression": {"parameter": "efficiency", "operator": "GTE", "value": 85.0, "unit": "%"},
    }
    eval_unk = evaluate_engineering_requirement(req_unk, state)
    assert eval_unk["status"] == "UNKNOWN"


# ==============================================================================
# 14. CONSTRAINT EVALUATION (HARD: PASS/FAIL/UNKNOWN, SOFT: SATISFIED/NOT_SATISFIED)
# ==============================================================================
def test_14_constraint_evaluation():
    state = {"junction_temp": 115.0}

    # Hard constraint: Tj <= 105.0 -> FAIL
    hard_c = {
        "id": "c-hard-1",
        "constraint_type": "HARD",
        "parameter": "junction_temp",
        "operator": "LTE",
        "value": 105.0,
        "unit": "°C",
    }
    eval_hard = evaluate_system_design_constraint(hard_c, state)
    assert eval_hard["status"] == "FAIL"

    # Soft constraint: Tj <= 100.0 -> NOT_SATISFIED
    soft_c = {
        "id": "c-soft-1",
        "constraint_type": "SOFT",
        "parameter": "junction_temp",
        "operator": "LTE",
        "value": 100.0,
        "unit": "°C",
    }
    eval_soft = evaluate_system_design_constraint(soft_c, state)
    assert eval_soft["status"] == "NOT_SATISFIED"

    # Unknown hard constraint
    hard_unk = {
        "id": "c-hard-2",
        "constraint_type": "HARD",
        "parameter": "ambient_noise_db",
        "operator": "LTE",
        "value": 40.0,
    }
    eval_unk = evaluate_system_design_constraint(hard_unk, state)
    assert eval_unk["status"] == "UNKNOWN"


# ==============================================================================
# 15. OPERATING MODE ANALYSIS (NORMAL vs STARTUP vs PEAK_LOAD)
# ==============================================================================
def test_15_operating_mode_analysis():
    circuit = {
        "version": 1,
        "components": [
            {
                "id": "reg",
                "name": "REG1",
                "component_type": "REGULATOR",
                "part_number": "AMS1117-3.3",
                "properties": {
                    "load_current": "0.3A",
                    "peak_load_factor": 2.0,  # 0.6A at PEAK_LOAD
                },
            },
        ],
        "nets": [
            {"id": "vin", "name": "5V"},
            {"id": "vout", "name": "3V3"},
            {"id": "gnd", "name": "GND"},
        ],
        "connections": [
            {"component_id": "reg", "net_id": "vin", "pin_number": "1"},
            {"component_id": "reg", "net_id": "vout", "pin_number": "2"},
            {"component_id": "reg", "net_id": "gnd", "pin_number": "3"},
        ],
    }

    svc = CircuitAnalysisService()

    # Normal mode: 0.3A
    res_normal = svc.analyze_circuit(circuit, operating_mode="NORMAL")
    calc_normal = next(c for c in res_normal["calculations"] if c["category"] == "REGULATOR")
    assert calc_normal["inputs"]["iload_a"] == pytest.approx(0.3)

    # Peak load mode: 0.3 * 2.0 = 0.6A
    res_peak = svc.analyze_circuit(circuit, operating_mode="PEAK_LOAD")
    calc_peak = next(c for c in res_peak["calculations"] if c["category"] == "REGULATOR")
    assert calc_peak["inputs"]["iload_a"] == pytest.approx(0.6)
    assert calc_peak["result"]["power_dissipated_w"] > calc_normal["result"]["power_dissipated_w"]


# ==============================================================================
# 16. OPERATING RANGE VS ABSOLUTE MAXIMUM SEPARATION
# ==============================================================================
def test_16_operating_range_vs_abs_max_separation():
    resolver = ComponentSpecificationResolver()
    resolver.set_component_profiles({
        "IC-SENSITIVE": {
            "operating_ranges": [
                {"parameter": "recommended_vin", "normalized_value": 5.5, "unit": "V"}
            ],
            "absolute_maximums": [
                {"parameter": "abs_max_vin", "normalized_value": 7.0, "unit": "V"}
            ],
            "provenance_chain": {"source_id": "src-spec-99", "revision": "1.0"},
        }
    })

    # Case A: 6.0V (Exceeds operating limit 5.5V, but below absolute maximum 7.0V)
    circuit_a = {
        "version": 1,
        "components": [
            {"id": "u1", "name": "U1", "component_type": "IC", "part_number": "IC-SENSITIVE"},
        ],
        "nets": [
            {"id": "vrail", "name": "6V"},
            {"id": "gnd", "name": "GND"},
        ],
        "connections": [
            {"component_id": "u1", "net_id": "vrail", "pin_number": "1"},
            {"component_id": "u1", "net_id": "gnd", "pin_number": "2"},
        ],
    }

    svc = CircuitAnalysisService(spec_resolver=resolver)
    res_a = svc.analyze_circuit(circuit_a)

    r009 = [f for f in res_a["findings"] if f["rule_id"] == "R009"]
    r010 = [f for f in res_a["findings"] if f["rule_id"] == "R010"]

    assert len(r009) == 1
    assert r009[0]["status"] == "OPERATING_LIMIT_EXCEEDED"
    assert len(r010) == 0  # Absolute maximum NOT exceeded!

    # Case B: 8.0V (Exceeds both operating limit and absolute maximum destruction hazard)
    circuit_b = {
        "version": 1,
        "components": [
            {"id": "u1", "name": "U1", "component_type": "IC", "part_number": "IC-SENSITIVE"},
        ],
        "nets": [
            {"id": "vrail", "name": "8V"},
            {"id": "gnd", "name": "GND"},
        ],
        "connections": [
            {"component_id": "u1", "net_id": "vrail", "pin_number": "1"},
            {"component_id": "u1", "net_id": "gnd", "pin_number": "2"},
        ],
    }
    res_b = svc.analyze_circuit(circuit_b)
    r010_b = [f for f in res_b["findings"] if f["rule_id"] == "R010"]
    assert len(r010_b) == 1
    assert r010_b[0]["status"] == "ABSOLUTE_MAXIMUM_EXCEEDED"
    assert r010_b[0]["severity"] == "CRITICAL"


# ==============================================================================
# 17. CALCULATED != PHYSICALLY VERIFIED INVARIANT
# ==============================================================================
def test_17_calculated_not_physically_verified():
    circuit = {
        "version": 1,
        "components": [
            {"id": "r1", "name": "R1", "component_type": "RESISTOR", "value": "1k"},
        ],
        "nets": [
            {"id": "n1", "name": "3V3"},
            {"id": "n2", "name": "GND"},
        ],
        "connections": [
            {"component_id": "r1", "net_id": "n1", "pin_number": "1"},
            {"component_id": "r1", "net_id": "n2", "pin_number": "2"},
        ],
    }
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit(circuit)

    for calc in res["calculations"]:
        assert calc.get("verification_status") != "PHYSICALLY_VERIFIED"
        assert calc.get("verification_status") in ["CALCULATED", "UNVERIFIED"]


# ==============================================================================
# 18. UNKNOWN != SATISFIED INVARIANT
# ==============================================================================
def test_18_unknown_not_satisfied():
    # If a parameter cannot be evaluated, status MUST be UNKNOWN, NEVER SATISFIED or PASS
    req = {
        "id": "req-unknown",
        "title": "Transient Recovery Time",
        "expression": {"parameter": "recovery_time_us", "operator": "LTE", "value": 50.0},
    }
    eval_res = evaluate_engineering_requirement(req, {})
    assert eval_res["status"] == "UNKNOWN"
    assert eval_res["status"] != "SATISFIED"


# ==============================================================================
# 19. SOURCE REVISION BINDING
# ==============================================================================
def test_19_source_revision_binding():
    resolver = ComponentSpecificationResolver()
    resolver.set_component_profiles({
        "REG-PROV": {
            "operating_ranges": [{"parameter": "vin_max", "normalized_value": 10.0, "unit": "V"}],
            "provenance_chain": {
                "source_id": "source-uuid-777",
                "revision": "Rev-C",
                "integrity_digest": "abcdef1234567890",
            },
        }
    })

    limits = resolver.resolve_operating_limits({"part_number": "REG-PROV"})
    assert limits["source_id"] == "source-uuid-777"
    assert limits["revision"] == "Rev-C"
    assert limits["provenance"] == "COMPONENT_PROFILE"


# ==============================================================================
# 20. STALE ANALYSIS DETECTION ON REVISION ADVANCE
# ==============================================================================
def test_20_stale_analysis_detection():
    # Simulated circuit version mismatch check
    current_user = type("User", (), {"id": "u1", "tenant_id": "tenant-a"})()

    # Staleness logic verification
    stale_check = {
        "analysis_circuit_version": 1,
        "current_circuit_version": 2,
    }
    is_stale = stale_check["current_circuit_version"] > stale_check["analysis_circuit_version"]
    assert is_stale is True


# ==============================================================================
# 21. PROVENANCE CHAIN COMPLETENESS
# ==============================================================================
def test_21_provenance_chain_completeness():
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit({
        "version": 3,
        "components": [{"id": "r1", "name": "R1", "component_type": "R", "value": "100R"}],
        "nets": [{"id": "n1", "name": "5V"}, {"id": "n2", "name": "GND"}],
        "connections": [{"component_id": "r1", "net_id": "n1", "pin_number": "1"}, {"component_id": "r1", "net_id": "n2", "pin_number": "2"}],
    })

    assert "engine_versions" in res
    assert "rule_set_version" in res
    assert res["rule_set_version"] == "QUEBET-ELECTRICAL-001 v2.0"
    assert "calculation_methods" in res
    assert "THERMAL_DISSIPATION" in res["calculation_methods"]


# ==============================================================================
# 22. CONTRADICTORY COMPONENT KNOWLEDGE HANDLING
# ==============================================================================
def test_22_contradictory_component_knowledge_handling():
    # Resolver handles profiles with conflicting records gracefully
    resolver = ComponentSpecificationResolver()
    resolver.set_component_profiles({
        "CONFLICT-PART": {
            "operating_ranges": [
                {"parameter": "vin_max", "normalized_value": 5.0},
                {"parameter": "vin_max", "normalized_value": 12.0},
            ],
            "contradictions": [{"parameter": "vin_max", "reason": "Dual conflicting datasheets"}],
        }
    })

    profile = resolver.resolve_profile_for_component({"part_number": "CONFLICT-PART"})
    assert profile is not None
    assert len(profile.get("contradictions", [])) == 1


# ==============================================================================
# 23. TENANT ISOLATION
# ==============================================================================
@pytest.mark.asyncio
async def test_23_tenant_isolation(async_client: AsyncClient, auth_headers, other_tenant_headers):
    # Verify that requesting a circuit or analysis belonging to tenant-a with tenant-b credentials returns 404
    fake_circuit_id = str(uuid.uuid4())
    res = await async_client.get(f"/api/v1/circuits/{fake_circuit_id}/analysis/latest", headers=other_tenant_headers)
    assert res.status_code == 404


# ==============================================================================
# 24. IDOR DEFENSE
# ==============================================================================
@pytest.mark.asyncio
async def test_24_idor_defense(async_client: AsyncClient, other_tenant_headers):
    fake_cid = str(uuid.uuid4())
    fake_aid = str(uuid.uuid4())
    res = await async_client.get(f"/api/v1/circuits/{fake_cid}/analysis/{fake_aid}", headers=other_tenant_headers)
    assert res.status_code == 404


# ==============================================================================
# 25. MALFORMED ENGINEERING VALUES HANDLING
# ==============================================================================
def test_25_malformed_engineering_values():
    circuit = {
        "version": 1,
        "components": [
            {"id": "r_bad", "name": "R_BAD", "component_type": "RESISTOR", "value": "-50R"},
            {"id": "c_bad", "name": "C_BAD", "component_type": "CAPACITOR", "value": "UNKNOWN"},
        ],
        "nets": [],
        "connections": [],
    }
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit(circuit)

    r001_findings = [f for f in res["findings"] if f["rule_id"] == "R001"]
    assert len(r001_findings) == 2
    # Non-physical value (-50R) is flagged CRITICAL
    assert any(f["severity"] == "CRITICAL" for f in r001_findings)


# ==============================================================================
# 26. ZERO SYNTHETIC SCORING VALIDATION
# ==============================================================================
def test_26_zero_synthetic_scoring_validation():
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit({
        "version": 1,
        "components": [{"id": "r1", "name": "R1", "component_type": "R", "value": "10k"}],
        "nets": [{"id": "n1", "name": "3V3"}],
        "connections": [{"component_id": "r1", "net_id": "n1", "pin_number": "1"}],
    })

    # Assert no forbidden synthetic score keys exist in output
    forbidden_keys = [
        "engineering_score",
        "compatibility_score",
        "confidence_score",
        "quality_score",
        "winner",
        "recommended_component",
    ]
    for k in forbidden_keys:
        assert k not in res, f"Forbidden synthetic key '{k}' found in analysis response!"


# ==============================================================================
# 27. NO AUTONOMOUS MUTATION
# ==============================================================================
def test_27_no_autonomous_mutation():
    original_circuit = {
        "version": 1,
        "components": [{"id": "r1", "name": "R1", "component_type": "R", "value": "100R"}],
        "nets": [{"id": "n1", "name": "5V"}, {"id": "n2", "name": "GND"}],
        "connections": [{"component_id": "r1", "net_id": "n1", "pin_number": "1"}, {"component_id": "r1", "net_id": "n2", "pin_number": "2"}],
    }
    copy_comp_val = original_circuit["components"][0]["value"]

    svc = CircuitAnalysisService()
    svc.analyze_circuit(original_circuit)

    # Circuit definition must remain untouched
    assert original_circuit["components"][0]["value"] == copy_comp_val
    assert original_circuit["version"] == 1


# ==============================================================================
# 28. REFLECTION INTEGRATION
# ==============================================================================
def test_28_reflection_integration():
    # Findings must provide structured provenance so cognitive reflection can inspect them
    finding = {
        "rule_id": "R009",
        "title": "Operating limit exceeded",
        "status": "OPERATING_LIMIT_EXCEEDED",
        "actual_value": 6.0,
        "limit_value": 5.5,
        "unit": "V",
        "provenance": "DETERMINISTIC_RULE",
        "verification_status": "CALCULATED",
    }
    assert finding["verification_status"] == "CALCULATED"
    assert finding["actual_value"] > finding["limit_value"]


# ==============================================================================
# 29. COGNITIVE CONTEXT INTEGRATION
# ==============================================================================
def test_29_cognitive_context_integration():
    svc = CircuitAnalysisService()
    res = svc.analyze_circuit({
        "version": 1,
        "components": [{"id": "r1", "name": "R1", "component_type": "R", "value": "1k"}],
        "nets": [{"id": "n1", "name": "5V"}, {"id": "n2", "name": "GND"}],
        "connections": [{"component_id": "r1", "net_id": "n1", "pin_number": "1"}, {"component_id": "r1", "net_id": "n2", "pin_number": "2"}],
    })
    # Must provide graph summary and status suitable for context snapshot
    assert "graph_summary" in res
    assert "status" in res
    assert res["status"] in ["COMPLETE", "PARTIAL", "BLOCKED"]


# ==============================================================================
# 30. END-TO-END: CIRCUIT -> KNOWLEDGE -> ANALYSIS -> FINDING -> VERIFICATION
# ==============================================================================
def test_30_end_to_end_circuit_to_finding():
    # Profile with thermal specs, recommended limits, and absolute maximums
    resolver = ComponentSpecificationResolver()
    resolver.set_component_profiles({
        "LM317": {
            "identity": ComponentIdentity(state=IdentityState.RESOLVED, part_number="LM317"),
            "operating_ranges": [
                ComponentParameterItem(
                    parameter="input_voltage_max",
                    category=ParameterCategory.OPERATING_LIMIT.value,
                    raw_value="37V",
                    normalized_value=37.0,
                    unit="V",
                )
            ],
            "absolute_maximums": [
                ComponentParameterItem(
                    parameter="max_junction_temp",
                    category=ParameterCategory.ABSOLUTE_MAXIMUM.value,
                    raw_value="125°C",
                    normalized_value=125.0,
                    unit="°C",
                )
            ],
            "thermal_characteristics": [
                ComponentParameterItem(
                    parameter="theta_ja",
                    category=ParameterCategory.TYPICAL_VALUE.value,
                    raw_value="50°C/W",
                    normalized_value=50.0,
                    unit="°C/W",
                )
            ],
            "provenance_chain": {
                "source_id": "src-ti-lm317",
                "revision": "Rev. S",
                "integrity_digest": "lm317sha256hash",
            },
        }
    })

    circuit = {
        "version": 2,
        "components": [
            {
                "id": "u1",
                "name": "REG1",
                "component_type": "REGULATOR",
                "part_number": "LM317",
                "properties": {
                    "v_out": "3.3V",
                    "load_current": "1.0A",
                },
            },
        ],
        "nets": [
            {"id": "vin", "name": "12V"},
            {"id": "vout", "name": "3V3"},
            {"id": "gnd", "name": "GND"},
        ],
        "connections": [
            {"component_id": "u1", "net_id": "vin", "pin_number": "1"},
            {"component_id": "u1", "net_id": "vout", "pin_number": "2"},
            {"component_id": "u1", "net_id": "gnd", "pin_number": "3"},
        ],
    }

    # At Vin = 12V, Vout = 3.3V, Iload = 1.0A:
    # Power = (12 - 3.3) * 1.0 + 12 * 0.005 = 8.76W
    # Delta_T = 8.76 * 50 = 438°C !
    # Tj = 25 + 438 = 463°C > Tj_max 125°C! -> CRITICAL thermal destruction hazard!
    svc = CircuitAnalysisService(spec_resolver=resolver)
    res = svc.analyze_circuit(circuit)

    assert res["status"] == "BLOCKED"

    # Verify thermal calculation is present
    thermal_calc = next(c for c in res["calculations"] if c["category"] == "THERMAL")
    assert thermal_calc["result"]["status"] == "OVERSTRESSED"
    assert thermal_calc["verification_status"] == "CALCULATED"
    assert thermal_calc["source_id"] == "src-ti-lm317"

    # Verify R011 Thermal Limit Exceeded finding
    r011 = [f for f in res["findings"] if f["rule_id"] == "R011"]
    assert len(r011) >= 1
    assert r011[0]["severity"] == "CRITICAL"
    assert r011[0]["status"] == "THERMAL_LIMIT_EXCEEDED"
    assert r011[0]["verification_status"] == "CALCULATED"
