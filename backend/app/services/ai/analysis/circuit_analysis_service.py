import time
from typing import Any, Optional
from app.services.ai.analysis.engines.interface_analyzer import analyze_net_interface
from app.services.ai.analysis.engines.margin_engine import calculate_margin
from app.services.ai.analysis.engines.ohms_law import calculate_ohms_law
from app.services.ai.analysis.engines.rc_time_constant import calculate_rc_time_constant
from app.services.ai.analysis.engines.regulator_analyzer import analyze_linear_regulator
from app.services.ai.analysis.engines.thermal_analyzer import calculate_thermal_dissipation
from app.services.ai.analysis.engines.voltage_divider import calculate_voltage_divider
from app.services.ai.analysis.graph_analyzer import CircuitGraphAnalyzer
from app.services.ai.analysis.rule_engine import CircuitRuleEngine
from app.services.ai.analysis.spec_resolver import ComponentSpecificationResolver
from app.services.ai.analysis.units import (
    parse_capacitance,
    parse_current,
    parse_resistance,
    parse_voltage,
)


class CircuitAnalysisService:
    """
    Deterministic Engineering Circuit Analysis Orchestrator (Phase 3 Wave 3).
    Executes graph topology analysis, physical equations, spec resolution,
    thermal analysis, interface checks, and rule evaluation (R001 - R016).

    INVARIANTS:
    - AI ENGINEERING AUTHORITY = NONE
    - UNKNOWN != SATISFIED
    - CALCULATED != PHYSICALLY VERIFIED
    - ZERO SYNTHETIC ENGINEERING SCORING
    """

    ENGINE_VERSIONS = {
        "OhmsLawEngine": "1.2.0",
        "VoltageDividerEngine": "1.1.0",
        "RegulatorAnalyzerEngine": "1.2.0",
        "RCTimeConstantEngine": "1.0.0",
        "MarginEngine": "1.2.0",
        "ThermalAnalyzerEngine": "1.0.0",
        "InterfaceAnalyzerEngine": "1.0.0",
        "ConstraintEvaluatorEngine": "1.0.0",
        "CircuitRuleEngine": "2.0.0",
        "CircuitGraphAnalyzer": "1.2.0",
    }
    RULE_SET_VERSION = "QUEBET-ELECTRICAL-001 v2.0"

    def __init__(self, spec_resolver: Optional[ComponentSpecificationResolver] = None):
        self.spec_resolver = spec_resolver or ComponentSpecificationResolver()

    def analyze_circuit(
        self,
        circuit_dict: dict[str, Any],
        user_assumptions: Optional[list[dict[str, Any]]] = None,
        component_profiles: Optional[dict[str, Any]] = None,
        operating_mode: Optional[str] = "NORMAL",
        requirements: Optional[list[dict[str, Any]]] = None,
        constraints: Optional[list[dict[str, Any]]] = None,
        ambient_temp_c: Optional[float] = 25.0,
    ) -> dict[str, Any]:
        start_time = time.perf_counter()

        # Register component intelligence profiles if provided
        if component_profiles:
            self.spec_resolver.set_component_profiles(component_profiles)

        components = circuit_dict.get("components") or []
        nets = circuit_dict.get("nets") or []
        connections = circuit_dict.get("connections") or []
        assumptions = list(user_assumptions or circuit_dict.get("assumptions") or [])
        reqs = list(requirements or circuit_dict.get("requirements") or [])
        consts = list(constraints or circuit_dict.get("constraints") or [])
        circuit_rev = circuit_dict.get("version") or circuit_dict.get("revision") or 1

        graph = CircuitGraphAnalyzer(components, nets, connections)
        calculations: list[dict[str, Any]] = []
        unknowns: list[dict[str, Any]] = []

        # 1. Identify Unknowns on Components
        for comp in components:
            comp_id = comp.get("id")
            comp_name = comp.get("name", "Unknown")
            comp_type = comp.get("component_type", "").upper()
            val = comp.get("value")

            if not val:
                unknowns.append({
                    "id": f"unk-{comp_id}-val",
                    "component_id": comp_id,
                    "field": "value",
                    "reason": f"Value not specified for {comp_name}.",
                    "impact": "Cannot calculate exact electrical operating point or power dissipation.",
                })

            if comp_type in ["RESISTOR", "R"]:
                specs = self.spec_resolver.resolve_resistor_specs(comp)
                if specs.get("rated_power_w") is None:
                    unknowns.append({
                        "id": f"unk-{comp_id}-pwr",
                        "component_id": comp_id,
                        "field": "rated_power_w",
                        "reason": f"Rated power not specified in properties and package/footprint '{comp.get('footprint')}' not in KB.",
                        "impact": "Resistor power derating and stress margin cannot be certified.",
                    })

        # 2. Resistor Electrical Calculations, Power Analysis & Margins
        for comp in components:
            comp_id = comp.get("id")
            comp_name = comp.get("name", "R")
            comp_type = comp.get("component_type", "").upper()
            if comp_type in ["RESISTOR", "R"]:
                specs = self.spec_resolver.resolve_resistor_specs(comp)
                res_ohms = specs.get("resistance_ohms")
                p_rated = specs.get("rated_power_w")

                conn_nets = list(graph.component_nets.get(comp_id, set()))
                voltages = [graph.infer_net_voltage(graph.nets[nid].get("name", "")) for nid in conn_nets if nid in graph.nets]
                valid_voltages = [v for v in voltages if v is not None]

                v_drop = None
                if len(valid_voltages) >= 2:
                    v_drop = abs(valid_voltages[0] - valid_voltages[1])
                elif len(valid_voltages) == 1 and any(graph.is_ground_net(graph.nets[nid].get("name", "")) for nid in conn_nets if nid in graph.nets):
                    v_drop = valid_voltages[0]

                if res_ohms is not None and v_drop is not None:
                    ohm_calc = calculate_ohms_law(
                        voltage=v_drop,
                        resistance=res_ohms,
                        component_ids=[comp_id],
                        net_ids=conn_nets,
                        context_name=f"Ohm's Law: {comp_name} ({v_drop:.1f}V drop)",
                    )
                    # Explicit current classification & verification tagging
                    calc_current = ohm_calc.get("result", {}).get("current_a")
                    ohm_calc["current_classification"] = "CALCULATED_CURRENT"
                    ohm_calc["verification_status"] = "CALCULATED"
                    calculations.append(ohm_calc)

                    # Power calculation: P = V*I = I^2 * R = V^2 / R
                    p_dissipated = (v_drop * calc_current) if calc_current is not None else (v_drop**2 / res_ohms)
                    p_calc = {
                        "id": f"pwr-{comp_id}",
                        "name": f"Resistor Power Dissipation: {comp_name}",
                        "category": "POWER",
                        "component_ids": [comp_id],
                        "net_ids": conn_nets,
                        "formula": "P = V * I = I^2 * R = V^2 / R",
                        "inputs": {
                            "voltage_v": round(v_drop, 4),
                            "current_a": round(calc_current, 6) if calc_current else None,
                            "resistance_ohms": round(res_ohms, 2),
                        },
                        "result": {
                            "power_w": round(p_dissipated, 6),
                            "power_mw": round(p_dissipated * 1000.0, 3),
                        },
                        "unit": "W",
                        "verification_status": "CALCULATED",
                        "confidence": "HIGH",
                    }
                    calculations.append(p_calc)

                    # Margin evaluation
                    if p_rated is not None:
                        margin_calc = calculate_margin(
                            actual=p_dissipated,
                            rated=p_rated,
                            parameter_name="Power Dissipation",
                            unit="W",
                            component_ids=[comp_id],
                            net_ids=conn_nets,
                            context_name=f"Power Margin: {comp_name} ({p_rated*1000:.0f}mW rated)",
                        )
                        margin_calc["verification_status"] = "CALCULATED"
                        calculations.append(margin_calc)

        # 3. Voltage Divider Detection
        for net_id, conns in graph.net_pins.items():
            resistor_conns = [
                c for c in conns
                if graph.components.get(c.get("component_id"), {}).get("component_type", "").upper() in ["RESISTOR", "R"]
            ]
            if len(resistor_conns) == 2:
                c1_id = resistor_conns[0].get("component_id")
                c2_id = resistor_conns[1].get("component_id")
                c1 = graph.components.get(c1_id, {})
                c2 = graph.components.get(c2_id, {})

                r1_val = parse_resistance(c1.get("value"))
                r2_val = parse_resistance(c2.get("value"))

                c1_nets = graph.component_nets.get(c1_id, set()) - {net_id}
                c2_nets = graph.component_nets.get(c2_id, set()) - {net_id}

                top_net_id = next(iter(c1_nets), None)
                bottom_net_id = next(iter(c2_nets), None)

                top_v = graph.infer_net_voltage(graph.nets[top_net_id].get("name", "")) if top_net_id else None
                bot_v = graph.infer_net_voltage(graph.nets[bottom_net_id].get("name", "")) if bottom_net_id else None

                if top_v is not None and bot_v == 0.0 and r1_val and r2_val:
                    div_calc = calculate_voltage_divider(
                        v_in=top_v,
                        r1=r1_val,
                        r2=r2_val,
                        component_ids=[c1_id, c2_id],
                        net_ids=[top_net_id, net_id, bottom_net_id],
                        context_name=f"Voltage Divider: {c1.get('name')}/{c2.get('name')}",
                    )
                    div_calc["verification_status"] = "CALCULATED"
                    calculations.append(div_calc)

        # 4. Regulator & IC Electrical, Power, and Thermal Analysis
        for comp in components:
            comp_id = comp.get("id")
            comp_type = comp.get("component_type", "").upper()
            if comp_type in ["REGULATOR", "LDO"] or (comp_type in ["IC"] and ((comp.get("properties") or {}).get("v_out") or "REGULATOR" in (comp.get("part_number") or "").upper())):
                reg_specs = self.spec_resolver.resolve_regulator_specs(comp)
                thermal_specs = self.spec_resolver.resolve_thermal_specs(comp)

                if reg_specs.get("provenance") != "SPECIFICATION_NOT_FOUND":
                    conn_nets = list(graph.component_nets.get(comp_id, set()))
                    net_voltages = [
                        (nid, graph.infer_net_voltage(graph.nets[nid].get("name", "")))
                        for nid in conn_nets if nid in graph.nets
                    ]
                    v_ins = [v for nid, v in net_voltages if v is not None and v > (reg_specs.get("v_out") or 0)]
                    vin_val = max(v_ins) if v_ins else reg_specs.get("v_in_min", 5.0)
                    vout_val = reg_specs.get("v_out") or 3.3

                    props = comp.get("properties") or {}
                    base_load = (
                        parse_current(props.get("load_current"))
                        or parse_current(props.get("i_load"))
                        or 0.35
                    )

                    # Operating mode load scaling
                    mode_str = (operating_mode or "NORMAL").upper()
                    if mode_str in ["PEAK_LOAD", "MAXIMUM_LOAD"]:
                        load_current = base_load * float(props.get("peak_load_factor", 1.5))
                    elif mode_str in ["STARTUP"]:
                        load_current = base_load * float(props.get("startup_load_factor", 1.8))
                    elif mode_str in ["SLEEP", "LOW_POWER"]:
                        load_current = float(props.get("sleep_current", 0.005))
                    else:
                        load_current = base_load

                    reg_calc = analyze_linear_regulator(
                        v_in=vin_val,
                        v_out=vout_val,
                        i_load_a=load_current,
                        specs=reg_specs,
                        ambient_temp_c=ambient_temp_c or 25.0,
                        component_ids=[comp_id],
                        net_ids=conn_nets,
                        context_name=f"Linear Regulator Analysis: {comp.get('name')} [{mode_str}]",
                    )
                    reg_calc["current_classification"] = "CALCULATED_CURRENT"
                    reg_calc["verification_status"] = "CALCULATED"
                    calculations.append(reg_calc)

                    # Output current margin check
                    if reg_specs.get("i_out_max_a"):
                        i_margin = calculate_margin(
                            actual=load_current,
                            rated=reg_specs.get("i_out_max_a"),
                            parameter_name="Regulator Output Current",
                            unit="A",
                            component_ids=[comp_id],
                            net_ids=conn_nets,
                            context_name=f"Current Margin: {comp.get('name')}",
                        )
                        i_margin["verification_status"] = "CALCULATED"
                        calculations.append(i_margin)

                    # Dedicated Thermal Dissipation & Junction Temperature Engine
                    power_dissipated = reg_calc.get("result", {}).get("power_dissipated_w")
                    theta_ja = thermal_specs.get("theta_ja")
                    tj_max = thermal_specs.get("tj_max_c")

                    thermal_calc = calculate_thermal_dissipation(
                        power_w=power_dissipated,
                        theta_ja=theta_ja,
                        ambient_temp_c=ambient_temp_c or 25.0,
                        tj_max=tj_max,
                        component_ids=[comp_id],
                        net_ids=conn_nets,
                        context_name=f"Thermal Analysis: {comp.get('name')} [{mode_str}]",
                        source_id=thermal_specs.get("source_id"),
                        revision=thermal_specs.get("revision"),
                    )
                    calculations.append(thermal_calc)

        # 5. RC Filter / Timing Network Detection
        for net_id, conns in graph.net_pins.items():
            rc_r = [c for c in conns if graph.components.get(c.get("component_id"), {}).get("component_type", "").upper() in ["RESISTOR", "R"]]
            rc_c = [c for c in conns if graph.components.get(c.get("component_id"), {}).get("component_type", "").upper() in ["CAPACITOR", "C"]]

            if rc_r and rc_c:
                r_comp = graph.components.get(rc_r[0].get("component_id"), {})
                c_comp = graph.components.get(rc_c[0].get("component_id"), {})
                r_val = parse_resistance(r_comp.get("value"))
                c_val = parse_capacitance(c_comp.get("value"))

                if r_val and c_val:
                    rc_calc = calculate_rc_time_constant(
                        resistance_ohms=r_val,
                        capacitance_farads=c_val,
                        component_ids=[r_comp.get("id"), c_comp.get("id")],
                        net_ids=[net_id],
                        context_name=f"RC Filter: {r_comp.get('name')}-{c_comp.get('name')}",
                    )
                    rc_calc["verification_status"] = "CALCULATED"
                    calculations.append(rc_calc)

        # 6. Interface & Net Compatibility Engine
        for net_id, conns in graph.net_pins.items():
            net = graph.nets.get(net_id, {})
            net_name = net.get("name", net_id)
            net_v = graph.infer_net_voltage(net_name)

            connected_pins_info = []
            for c in conns:
                comp = graph.components.get(c.get("component_id"), {})
                comp_pins = comp.get("pins") or []
                c_pin_id = c.get("pin_id") or c.get("pin_number")
                target_pin = next((p for p in comp_pins if (p.get("id") or p.get("number")) == c_pin_id), {})

                connected_pins_info.append({
                    "component_id": comp.get("id"),
                    "component_name": comp.get("name"),
                    "component_type": comp.get("component_type"),
                    "pin_id": c_pin_id,
                    "pin_name": target_pin.get("name", str(c_pin_id)),
                    "pin_type": target_pin.get("type") or target_pin.get("pin_type"),
                    "electrical_role": target_pin.get("role") or target_pin.get("electrical_role"),
                    "direction": target_pin.get("direction"),
                    "max_voltage": parse_voltage(target_pin.get("max_voltage")),
                    "is_5v_tolerant": target_pin.get("is_5v_tolerant", False),
                    "domain": target_pin.get("domain"),
                })

            if len(connected_pins_info) >= 2:
                if_calc = analyze_net_interface(
                    net_id=net_id,
                    net_name=net_name,
                    connected_pins=connected_pins_info,
                    net_voltage=net_v,
                    context_name=f"Net Interface: {net_name}",
                )
                calculations.append(if_calc)

        # 7. Rule Evaluation (R001 to R016)
        rule_engine = CircuitRuleEngine(
            graph_analyzer=graph,
            spec_resolver=self.spec_resolver,
            calculations=calculations,
            requirements=reqs,
            constraints=consts,
            circuit_revision=circuit_rev,
        )
        findings = rule_engine.evaluate_all()

        # 8. Status & Confidence Determination
        has_critical = any(f.get("severity") == "CRITICAL" for f in findings)
        status = "COMPLETE"
        confidence = "HIGH"

        if has_critical:
            status = "BLOCKED"
            confidence = "HIGH"
        elif unknowns or any(f.get("status") == "UNKNOWN" for f in findings):
            status = "PARTIAL"
            confidence = "MEDIUM" if len(unknowns) <= 2 else "LOW"

        graph_summary = graph.get_summary()
        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return {
            "status": status,
            "confidence": confidence,
            "operating_mode": operating_mode,
            "graph_summary": graph_summary,
            "calculations": calculations,
            "findings": findings,
            "unknowns": unknowns,
            "assumptions": assumptions,
            "requirements": reqs,
            "constraints": consts,
            "execution_time_ms": execution_time_ms,
            "engine_versions": self.ENGINE_VERSIONS,
            "rule_set_version": self.RULE_SET_VERSION,
            "calculation_methods": [
                "NODAL_VOLTAGE",
                "OHMS_LAW",
                "VOLTAGE_DIVIDER",
                "RC_TIME_CONSTANT",
                "REGULATOR_POWER",
                "MARGIN_DERATING",
                "THERMAL_DISSIPATION",
                "INTERFACE_COMPATIBILITY",
                "REQUIREMENT_EVALUATION",
                "CONSTRAINT_CHECK",
            ],
        }
