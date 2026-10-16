import uuid
from typing import Any, Optional
from app.services.ai.analysis.engines.constraint_evaluator import (
    evaluate_engineering_requirement,
    evaluate_system_design_constraint,
)
from app.services.ai.analysis.graph_analyzer import CircuitGraphAnalyzer
from app.services.ai.analysis.spec_resolver import ComponentSpecificationResolver
from app.services.ai.analysis.units import (
    parse_capacitance,
    parse_frequency,
    parse_resistance,
    parse_voltage,
)


class CircuitRuleEngine:
    """
    Deterministic Circuit Rule Engine evaluating rules R001 through R016.
    Never hallucinates issues; each finding points directly to circuit objects,
    engineering physics, documented component profiles, or formal constraints.

    INVARIANTS:
    - AI ENGINEERING AUTHORITY = NONE
    - UNKNOWN != SATISFIED
    - CALCULATED != PHYSICALLY VERIFIED
    - ZERO SYNTHETIC ENGINEERING SCORING
    - Operating Limits != Absolute Maximum Ratings
    """

    def __init__(
        self,
        graph_analyzer: CircuitGraphAnalyzer,
        spec_resolver: ComponentSpecificationResolver,
        calculations: list[dict[str, Any]],
        requirements: Optional[list[dict[str, Any]]] = None,
        constraints: Optional[list[dict[str, Any]]] = None,
        circuit_revision: Optional[int] = 1,
    ):
        self.graph = graph_analyzer
        self.specs = spec_resolver
        self.calculations = calculations
        self.requirements = requirements or []
        self.constraints = constraints or []
        self.circuit_revision = circuit_revision

    def evaluate_all(self) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []

        # Foundational rules R001 - R008
        findings.extend(self.check_r001_invalid_component_values())
        findings.extend(self.check_r002_floating_pins())
        findings.extend(self.check_r003_excessive_resistor_power())
        findings.extend(self.check_r004_regulator_input_exceeds_rating())
        findings.extend(self.check_r005_regulator_current_exceeds_rating())
        findings.extend(self.check_r006_insufficient_margin())
        findings.extend(self.check_r007_missing_decoupling_capacitors())
        findings.extend(self.check_r008_voltage_domain_conflict())

        # Wave 3 Advanced Engineering & Constraint Rules R009 - R016
        findings.extend(self.check_r009_operating_limit_exceeded())
        findings.extend(self.check_r010_absolute_maximum_exceeded())
        findings.extend(self.check_r011_thermal_limit_exceeded())
        findings.extend(self.check_r012_application_constraint_violation())
        findings.extend(self.check_r013_interface_incompatibility())
        findings.extend(self.check_r014_frequency_timing_limit_exceeded())
        findings.extend(self.check_r015_requirement_violation())
        findings.extend(self.check_r016_design_constraint_violation())

        return findings

    # -------------------------------------------------------------------------
    # R001: Invalid Component Values
    # -------------------------------------------------------------------------
    def check_r001_invalid_component_values(self) -> list[dict[str, Any]]:
        """R001: Component has unparseable or non-physical value (<= 0 or malformed)."""
        findings = []
        for comp_id, comp in self.graph.components.items():
            comp_type = comp.get("component_type", "").upper()
            val = comp.get("value")
            name = comp.get("name", comp_id)

            if not val or str(val).strip() in ["?", "TBD", "UNKNOWN", "NONE", "NAN"]:
                findings.append({
                    "id": str(uuid.uuid4()),
                    "rule_id": "R001",
                    "title": f"Unspecified component value for {name}",
                    "description": f"Component '{name}' ({comp_type}) has no valid value assigned.",
                    "severity": "WARNING",
                    "status": "UNKNOWN",
                    "component_ids": [comp_id],
                    "net_ids": [],
                    "pin_ids": [],
                    "recommended_action": "Assign an explicit engineering value with standard metric unit.",
                    "provenance": "DETERMINISTIC_RULE",
                    "verification_status": "UNVERIFIED",
                })
                continue

            if comp_type in ["RESISTOR", "R"]:
                parsed = parse_resistance(val)
                if parsed is None or parsed <= 0:
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "rule_id": "R001",
                        "title": f"Invalid resistance value on {name}",
                        "description": f"Resistor '{name}' value '{val}' cannot be parsed or is non-physical (<= 0).",
                        "severity": "CRITICAL",
                        "status": "VIOLATED",
                        "component_ids": [comp_id],
                        "net_ids": [],
                        "pin_ids": [],
                        "recommended_action": "Specify a positive resistance in ohms (e.g., 10k, 220R).",
                        "provenance": "DETERMINISTIC_RULE",
                        "verification_status": "CALCULATED",
                    })
            elif comp_type in ["CAPACITOR", "C"]:
                parsed = parse_capacitance(val)
                if parsed is None or parsed <= 0:
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "rule_id": "R001",
                        "title": f"Invalid capacitance value on {name}",
                        "description": f"Capacitor '{name}' value '{val}' cannot be parsed or is non-physical (<= 0).",
                        "severity": "CRITICAL",
                        "status": "VIOLATED",
                        "component_ids": [comp_id],
                        "net_ids": [],
                        "pin_ids": [],
                        "recommended_action": "Specify a positive capacitance in farads (e.g., 100nF, 10uF).",
                        "provenance": "DETERMINISTIC_RULE",
                        "verification_status": "CALCULATED",
                    })

        return findings

    # -------------------------------------------------------------------------
    # R002: Floating Pins
    # -------------------------------------------------------------------------
    def check_r002_floating_pins(self) -> list[dict[str, Any]]:
        """R002: Detect floating or unrouted pins, especially on ICs and critical nodes."""
        findings = []
        for comp_id, comp in self.graph.components.items():
            comp_type = comp.get("component_type", "").upper()
            pins = comp.get("pins") or []
            if not pins:
                continue

            connected_pins = set()
            for net_id, conns in self.graph.net_pins.items():
                for conn in conns:
                    if conn.get("component_id") == comp_id:
                        connected_pins.add(conn.get("pin_id") or conn.get("pin_number"))

            for pin in pins:
                pin_id = pin.get("id") or pin.get("number")
                pin_name = pin.get("name") or str(pin_id)
                pin_type = (pin.get("type") or "").upper()
                is_nc = "NC" in pin_name.upper() or pin_type == "NC"

                if pin_id not in connected_pins and not is_nc:
                    severity = "CRITICAL" if comp_type in ["IC", "REGULATOR", "MICROCONTROLLER", "MCU"] and pin_type in ["POWER", "INPUT", "RESET"] else "WARNING"
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "rule_id": "R002",
                        "title": f"Unconnected pin {pin_name} on {comp.get('name')}",
                        "description": f"Pin '{pin_name}' (type: {pin_type or 'General'}) of {comp.get('name')} is floating with no net attached.",
                        "severity": severity,
                        "status": "VIOLATED",
                        "component_ids": [comp_id],
                        "net_ids": [],
                        "pin_ids": [pin_id] if pin_id else [],
                        "recommended_action": f"Route pin {pin_name} to its target net or explicitly mark it as Not Connected (NC).",
                        "provenance": "DETERMINISTIC_RULE",
                        "verification_status": "CALCULATED",
                    })
        return findings

    # -------------------------------------------------------------------------
    # R003: Excessive Resistor Power
    # -------------------------------------------------------------------------
    def check_r003_excessive_resistor_power(self) -> list[dict[str, Any]]:
        """R003: Resistor power dissipation exceeds its rated wattage (P > P_rated)."""
        findings = []
        for calc in self.calculations:
            if calc.get("category") == "MARGIN":
                inputs = calc.get("inputs", {})
                result = calc.get("result", {})
                if inputs.get("parameter") == "Power Dissipation" and result.get("status") == "OVERSTRESSED":
                    actual = inputs.get("actual")
                    rated = inputs.get("rated")
                    comp_ids = calc.get("component_ids", [])
                    comp_name = self.graph.components.get(comp_ids[0], {}).get("name", "Resistor") if comp_ids else "Resistor"

                    findings.append({
                        "id": str(uuid.uuid4()),
                        "rule_id": "R003",
                        "title": f"Excessive power dissipation on {comp_name}",
                        "description": (
                            f"Resistor '{comp_name}' dissipates {actual*1000:.1f} mW, exceeding its "
                            f"rated limit of {rated*1000:.1f} mW by {result.get('margin_pct', 0):.1f}%."
                        ),
                        "severity": "CRITICAL",
                        "status": "OVERSTRESSED",
                        "actual_value": actual,
                        "limit_value": rated,
                        "unit": "W",
                        "component_ids": comp_ids,
                        "net_ids": calc.get("net_ids", []),
                        "pin_ids": [],
                        "recommended_action": f"Upgrade {comp_name} to a larger footprint or increase resistance.",
                        "provenance": "DETERMINISTIC_RULE",
                        "verification_status": "CALCULATED",
                    })
        return findings

    # -------------------------------------------------------------------------
    # R004: Regulator Input Exceeds Rating
    # -------------------------------------------------------------------------
    def check_r004_regulator_input_exceeds_rating(self) -> list[dict[str, Any]]:
        """R004: Regulator input voltage exceeds maximum rating (Vin > Vin_max)."""
        findings = []
        for comp_id, comp in self.graph.components.items():
            comp_type = comp.get("component_type", "").upper()
            if comp_type in ["REGULATOR", "LDO", "IC"]:
                reg_specs = self.specs.resolve_regulator_specs(comp)
                v_in_max = reg_specs.get("v_in_max")
                if v_in_max is None:
                    continue

                for net_id in self.graph.component_nets.get(comp_id, set()):
                    net = self.graph.nets.get(net_id, {})
                    net_v = self.graph.infer_net_voltage(net.get("name", ""))
                    if net_v is not None and net_v > v_in_max:
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "rule_id": "R004",
                            "title": f"Input voltage exceeds rating on {comp.get('name')}",
                            "description": (
                                f"Input voltage on net '{net.get('name')}' ({net_v:.1f}V) exceeds "
                                f"maximum rated input voltage ({v_in_max:.1f}V) for {reg_specs.get('part_number')}."
                            ),
                            "severity": "CRITICAL",
                            "status": "VIOLATED",
                            "actual_value": net_v,
                            "limit_value": v_in_max,
                            "unit": "V",
                            "component_ids": [comp_id],
                            "net_ids": [net_id],
                            "pin_ids": [],
                            "recommended_action": f"Reduce input voltage below {v_in_max:.1f}V or use a pre-regulator/buck converter.",
                            "provenance": "DETERMINISTIC_RULE",
                            "verification_status": "CALCULATED",
                        })
        return findings

    # -------------------------------------------------------------------------
    # R005: Regulator Current Exceeds Rating
    # -------------------------------------------------------------------------
    def check_r005_regulator_current_exceeds_rating(self) -> list[dict[str, Any]]:
        """R005: Regulator load current exceeds maximum rated current (I_out > I_out_max)."""
        findings = []
        for calc in self.calculations:
            if calc.get("category") == "MARGIN":
                inputs = calc.get("inputs", {})
                result = calc.get("result", {})
                if inputs.get("parameter") == "Regulator Output Current" and result.get("status") == "OVERSTRESSED":
                    actual = inputs.get("actual")
                    rated = inputs.get("rated")
                    comp_ids = calc.get("component_ids", [])
                    comp_name = self.graph.components.get(comp_ids[0], {}).get("name", "Regulator") if comp_ids else "Regulator"

                    findings.append({
                        "id": str(uuid.uuid4()),
                        "rule_id": "R005",
                        "title": f"Output current exceeds maximum rating on {comp_name}",
                        "description": (
                            f"Total load current ({actual*1000:.1f} mA) exceeds rated maximum "
                            f"output current ({rated*1000:.1f} mA)."
                        ),
                        "severity": "CRITICAL",
                        "status": "OVERSTRESSED",
                        "actual_value": actual,
                        "limit_value": rated,
                        "unit": "A",
                        "component_ids": comp_ids,
                        "net_ids": calc.get("net_ids", []),
                        "pin_ids": [],
                        "recommended_action": f"Select higher-current regulator or reduce downstream circuit load.",
                        "provenance": "DETERMINISTIC_RULE",
                        "verification_status": "CALCULATED",
                    })
        return findings

    # -------------------------------------------------------------------------
    # R006: Insufficient Margin
    # -------------------------------------------------------------------------
    def check_r006_insufficient_margin(self) -> list[dict[str, Any]]:
        """R006: Component operating with insufficient margin (utilization > 80% but <= 100%)."""
        findings = []
        for calc in self.calculations:
            if calc.get("category") == "MARGIN":
                inputs = calc.get("inputs", {})
                result = calc.get("result", {})
                if result.get("status") == "INSUFFICIENT_MARGIN":
                    actual = inputs.get("actual")
                    rated = inputs.get("rated")
                    param = inputs.get("parameter", "Stress")
                    unit = inputs.get("unit", "")
                    comp_ids = calc.get("component_ids", [])
                    comp_name = self.graph.components.get(comp_ids[0], {}).get("name", "Component") if comp_ids else "Component"

                    findings.append({
                        "id": str(uuid.uuid4()),
                        "rule_id": "R006",
                        "title": f"Insufficient {param.lower()} margin on {comp_name}",
                        "description": (
                            f"{comp_name} operates at {result.get('utilization_pct', 0):.1f}% of rated {param.lower()} "
                            f"({actual} {unit} / {rated} {unit}), exceeding recommended 80% derating threshold."
                        ),
                        "severity": "WARNING",
                        "status": "INSUFFICIENT_MARGIN",
                        "actual_value": actual,
                        "limit_value": rated,
                        "unit": unit,
                        "component_ids": comp_ids,
                        "net_ids": calc.get("net_ids", []),
                        "pin_ids": [],
                        "recommended_action": f"Derate {comp_name} by increasing its rating or reducing load for long-term reliability.",
                        "provenance": "DETERMINISTIC_RULE",
                        "verification_status": "CALCULATED",
                    })
        return findings

    # -------------------------------------------------------------------------
    # R007: Missing Decoupling Capacitors
    # -------------------------------------------------------------------------
    def check_r007_missing_decoupling_capacitors(self) -> list[dict[str, Any]]:
        """R007: IC or regulator power pins lack decoupling capacitors."""
        findings = []
        for comp_id, comp in self.graph.components.items():
            comp_type = comp.get("component_type", "").upper()
            if comp_type in ["IC", "MICROCONTROLLER", "MCU", "REGULATOR", "LDO"]:
                comp_power_nets = [
                    nid for nid in self.graph.component_nets.get(comp_id, set())
                    if self.graph.is_power_net(self.graph.nets[nid].get("name", ""))
                ]

                for pnet_id in comp_power_nets:
                    pnet = self.graph.nets[pnet_id]
                    has_cap = False
                    for conn in self.graph.net_pins.get(pnet_id, []):
                        c_id = conn.get("component_id")
                        connected_comp = self.graph.components.get(c_id, {})
                        if connected_comp.get("component_type", "").upper() in ["CAPACITOR", "C"]:
                            has_cap = True
                            break

                    if not has_cap:
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "rule_id": "R007",
                            "title": f"Missing decoupling capacitor for {comp.get('name')}",
                            "description": (
                                f"Power rail '{pnet.get('name')}' supplying {comp.get('name')} "
                                f"({comp_type}) does not have a local decoupling or bypass capacitor."
                            ),
                            "severity": "WARNING",
                            "status": "VIOLATED",
                            "component_ids": [comp_id],
                            "net_ids": [pnet_id],
                            "pin_ids": [],
                            "recommended_action": f"Add a 100nF ceramic capacitor between '{pnet.get('name')}' and GND close to {comp.get('name')}.",
                            "provenance": "DETERMINISTIC_RULE",
                            "verification_status": "CALCULATED",
                        })
        return findings

    # -------------------------------------------------------------------------
    # R008: Voltage Domain Conflict
    # -------------------------------------------------------------------------
    def check_r008_voltage_domain_conflict(self) -> list[dict[str, Any]]:
        """R008: Voltage domain or net naming conflict."""
        findings = []
        for comp_id, comp in self.graph.components.items():
            comp_type = comp.get("component_type", "").upper()
            pn = (comp.get("part_number") or comp.get("value") or "").upper()
            if "ESP32" in pn or comp_type == "MICROCONTROLLER":
                for net_id in self.graph.component_nets.get(comp_id, set()):
                    net = self.graph.nets.get(net_id, {})
                    net_name = net.get("name", "")
                    inferred_v = self.graph.infer_net_voltage(net_name)

                    if self.graph.is_power_net(net_name) and inferred_v is not None and inferred_v > 3.6:
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "rule_id": "R008",
                            "title": f"Voltage domain conflict on {comp.get('name')}",
                            "description": (
                                f"3.3V nominal component '{comp.get('name')}' ({pn}) is directly connected "
                                f"to {inferred_v:.1f}V net '{net_name}', violating maximum operating limit (3.6V)."
                            ),
                            "severity": "CRITICAL",
                            "status": "VIOLATED",
                            "actual_value": inferred_v,
                            "limit_value": 3.6,
                            "unit": "V",
                            "component_ids": [comp_id],
                            "net_ids": [net_id],
                            "pin_ids": [],
                            "recommended_action": "Power the microcontroller through a 3.3V voltage regulator (e.g., AMS1117-3.3).",
                            "provenance": "DETERMINISTIC_RULE",
                            "verification_status": "CALCULATED",
                        })
        return findings

    # -------------------------------------------------------------------------
    # R009: Operating Limit Exceeded
    # -------------------------------------------------------------------------
    def check_r009_operating_limit_exceeded(self) -> list[dict[str, Any]]:
        """
        R009: Operating parameter exceeds recommended operating limits documented in component profile.
        INVARIANT: Recommended operating limits != Absolute Maximum Ratings.
        """
        findings = []
        for comp_id, comp in self.graph.components.items():
            limits = self.specs.resolve_operating_limits(comp)
            abs_max = self.specs.resolve_absolute_maximums(comp)
            name = comp.get("name", comp_id)

            # Check operating voltage against recommended limits
            v_max = limits.get("v_in_max")
            abs_v_max = abs_max.get("v_in_abs_max")

            if v_max is not None:
                for net_id in self.graph.component_nets.get(comp_id, set()):
                    net = self.graph.nets.get(net_id, {})
                    net_v = self.graph.infer_net_voltage(net.get("name", ""))
                    # Trigger R009 if net_v > recommended operating limit
                    if net_v is not None and net_v > v_max:
                        # If net_v also exceeds absolute maximum, R010 handles the destruction risk;
                        # here we log the operating limit exceedance
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "rule_id": "R009",
                            "title": f"Operating limit exceeded on {name}",
                            "description": (
                                f"Operating voltage {net_v:.2f}V on net '{net.get('name')}' exceeds "
                                f"recommended operating limit ({v_max:.2f}V) for {name}."
                            ),
                            "severity": "WARNING",
                            "status": "OPERATING_LIMIT_EXCEEDED",
                            "actual_value": net_v,
                            "limit_value": v_max,
                            "unit": "V",
                            "condition": "Recommended Operating Limit",
                            "component_ids": [comp_id],
                            "net_ids": [net_id],
                            "pin_ids": [],
                            "source_id": limits.get("source_id"),
                            "revision": limits.get("revision"),
                            "recommended_action": f"Operate {name} within recommended operating voltage <= {v_max:.2f}V.",
                            "provenance": "DETERMINISTIC_RULE",
                            "verification_status": "CALCULATED",
                        })

        return findings

    # -------------------------------------------------------------------------
    # R010: Absolute Maximum Rating Exceeded (Destruction Hazard)
    # -------------------------------------------------------------------------
    def check_r010_absolute_maximum_exceeded(self) -> list[dict[str, Any]]:
        """
        R010: Parameter exceeds documented Absolute Maximum Rating.
        CRITICAL SAFETY INVARIANT: Silicon destruction hazard.
        """
        findings = []
        for comp_id, comp in self.graph.components.items():
            abs_max = self.specs.resolve_absolute_maximums(comp)
            name = comp.get("name", comp_id)

            abs_v_max = abs_max.get("v_in_abs_max")
            if abs_v_max is not None:
                for net_id in self.graph.component_nets.get(comp_id, set()):
                    net = self.graph.nets.get(net_id, {})
                    net_v = self.graph.infer_net_voltage(net.get("name", ""))
                    if net_v is not None and net_v > abs_v_max:
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "rule_id": "R010",
                            "title": f"Absolute maximum rating exceeded on {name} (Destruction Hazard)",
                            "description": (
                                f"Input voltage {net_v:.2f}V on net '{net.get('name')}' exceeds "
                                f"Absolute Maximum Rating ({abs_v_max:.2f}V) for {name}. Silicon destruction hazard!"
                            ),
                            "severity": "CRITICAL",
                            "status": "ABSOLUTE_MAXIMUM_EXCEEDED",
                            "actual_value": net_v,
                            "limit_value": abs_v_max,
                            "unit": "V",
                            "condition": "Absolute Maximum Rating",
                            "component_ids": [comp_id],
                            "net_ids": [net_id],
                            "pin_ids": [],
                            "source_id": abs_max.get("source_id"),
                            "revision": abs_max.get("revision"),
                            "recommended_action": f"Immediately reduce voltage below absolute maximum {abs_v_max:.2f}V to prevent physical destruction.",
                            "provenance": "DETERMINISTIC_RULE",
                            "verification_status": "CALCULATED",
                        })

        return findings

    # -------------------------------------------------------------------------
    # R011: Thermal Limit Exceeded & Unknown Thermal
    # -------------------------------------------------------------------------
    def check_r011_thermal_limit_exceeded(self) -> list[dict[str, Any]]:
        """
        R011: Thermal dissipation and junction temperature verification.
        Handles both calculated thermal overstress and explicit UNKNOWN thermal state.
        """
        findings = []
        for calc in self.calculations:
            if calc.get("category") == "THERMAL":
                res = calc.get("result", {})
                status = res.get("status")
                comp_ids = calc.get("component_ids", [])
                comp_name = self.graph.components.get(comp_ids[0], {}).get("name", "Component") if comp_ids else "Component"

                if status == "UNKNOWN":
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "rule_id": "R011",
                        "title": f"Unknown thermal dissipation or parameter for {comp_name}",
                        "description": res.get("reason", "Thermal parameters missing."),
                        "severity": "WARNING",
                        "status": "UNKNOWN",
                        "component_ids": comp_ids,
                        "net_ids": calc.get("net_ids", []),
                        "pin_ids": [],
                        "recommended_action": "Specify documented Theta_JA and operating temperature for component.",
                        "provenance": "DETERMINISTIC_RULE",
                        "verification_status": "UNVERIFIED",
                    })
                elif status == "OVERSTRESSED":
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "rule_id": "R011",
                        "title": f"Thermal limit exceeded on {comp_name}",
                        "description": (
                            f"Calculated junction temperature {res.get('junction_temp_c')}°C exceeds "
                            f"rated maximum junction temperature {res.get('tj_max_c')}°C. Overheating hazard!"
                        ),
                        "severity": "CRITICAL",
                        "status": "THERMAL_LIMIT_EXCEEDED",
                        "actual_value": res.get("junction_temp_c"),
                        "limit_value": res.get("tj_max_c"),
                        "unit": "°C",
                        "component_ids": comp_ids,
                        "net_ids": calc.get("net_ids", []),
                        "pin_ids": [],
                        "recommended_action": "Add heatsink, improve airflow, or select component with lower thermal resistance.",
                        "provenance": "DETERMINISTIC_RULE",
                        "verification_status": "CALCULATED",
                    })
                elif status == "INSUFFICIENT_MARGIN":
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "rule_id": "R011",
                        "title": f"Insufficient thermal derating margin on {comp_name}",
                        "description": (
                            f"Calculated junction temperature {res.get('junction_temp_c')}°C exceeds "
                            f"80% derating threshold of {res.get('tj_max_c')}°C."
                        ),
                        "severity": "WARNING",
                        "status": "INSUFFICIENT_MARGIN",
                        "actual_value": res.get("junction_temp_c"),
                        "limit_value": res.get("tj_max_c"),
                        "unit": "°C",
                        "component_ids": comp_ids,
                        "net_ids": calc.get("net_ids", []),
                        "pin_ids": [],
                        "recommended_action": "Improve thermal dissipation to operate comfortably below 80% maximum junction temperature.",
                        "provenance": "DETERMINISTIC_RULE",
                        "verification_status": "CALCULATED",
                    })

        return findings

    # -------------------------------------------------------------------------
    # R012: Application Constraint Violation (Cin, Cout, ESR, Pull-up)
    # -------------------------------------------------------------------------
    def check_r012_application_constraint_violation(self) -> list[dict[str, Any]]:
        """
        R012: Evaluates component application constraints (Cin, Cout, ESR, Pull-ups).
        """
        findings = []
        for comp_id, comp in self.graph.components.items():
            app_constraints = self.specs.resolve_application_constraints(comp)
            name = comp.get("name", comp_id)
            comp_nets = self.graph.component_nets.get(comp_id, set())

            for c in app_constraints:
                c_type = (c.get("constraint_type") or "").upper()
                req_val = c.get("requirement_value")
                desc = c.get("description")

                # Check Output Capacitance Requirement
                if "OUTPUT_CAPACITANCE" in c_type or "COUT" in c_type or "OUTPUT CAPACITOR" in desc.upper():
                    # Identify output net (usually net with regulator Vout or downstream rail)
                    for net_id in comp_nets:
                        net = self.graph.nets.get(net_id, {})
                        net_name = net.get("name", "")
                        if "OUT" in net_name.upper() or "3V3" in net_name.upper():
                            # Sum capacitance on this net
                            total_cap = 0.0
                            for conn in self.graph.net_pins.get(net_id, []):
                                c_comp = self.graph.components.get(conn.get("component_id"), {})
                                if c_comp.get("component_type", "").upper() in ["CAPACITOR", "C"]:
                                    cap_specs = self.specs.resolve_capacitor_specs(c_comp)
                                    if cap_specs.get("capacitance_f"):
                                        total_cap += cap_specs["capacitance_f"]

                            req_f = parse_capacitance(req_val) or 10e-6
                            if total_cap < req_f:
                                findings.append({
                                    "id": str(uuid.uuid4()),
                                    "rule_id": "R012",
                                    "title": f"Application constraint violated: Output capacitance on {name}",
                                    "description": (
                                        f"Total output capacitance on net '{net_name}' ({total_cap*1e6:.1f}µF) "
                                        f"is less than manufacturer requirement ({req_f*1e6:.1f}µF). Loop instability risk!"
                                    ),
                                    "severity": "CRITICAL",
                                    "status": "VIOLATED",
                                    "actual_value": total_cap,
                                    "limit_value": req_f,
                                    "unit": "F",
                                    "component_ids": [comp_id],
                                    "net_ids": [net_id],
                                    "pin_ids": [],
                                    "recommended_action": f"Add minimum {req_f*1e6:.1f}µF output capacitor to net '{net_name}'.",
                                    "provenance": "DETERMINISTIC_RULE",
                                    "verification_status": "CALCULATED",
                                })

                # Check ESR constraint
                if "ESR" in c_type or "ESR" in desc.upper():
                    # Check capacitors connected to this component
                    for net_id in comp_nets:
                        for conn in self.graph.net_pins.get(net_id, []):
                            c_comp = self.graph.components.get(conn.get("component_id"), {})
                            if c_comp.get("component_type", "").upper() in ["CAPACITOR", "C"]:
                                cap_specs = self.specs.resolve_capacitor_specs(c_comp)
                                esr = cap_specs.get("esr_ohms")
                                if esr is not None and esr < 0.1 and "MINIMUM ESR" in desc.upper():
                                    findings.append({
                                        "id": str(uuid.uuid4()),
                                        "rule_id": "R012",
                                        "title": f"Application constraint violated: Capacitor ESR on {c_comp.get('name')}",
                                        "description": (
                                            f"Capacitor {c_comp.get('name')} ESR ({esr:.2f}Ω) is lower than "
                                            f"minimum stability requirement for {name}. Tantalum or series resistor required."
                                        ),
                                        "severity": "CRITICAL",
                                        "status": "VIOLATED",
                                        "actual_value": esr,
                                        "limit_value": 0.1,
                                        "unit": "Ω",
                                        "component_ids": [comp_id, c_comp.get("id")],
                                        "net_ids": [net_id],
                                        "pin_ids": [],
                                        "recommended_action": "Use capacitor with recommended ESR or add a small series resistor.",
                                        "provenance": "DETERMINISTIC_RULE",
                                        "verification_status": "CALCULATED",
                                    })

        return findings

    # -------------------------------------------------------------------------
    # R013: Interface Incompatibility
    # -------------------------------------------------------------------------
    def check_r013_interface_incompatibility(self) -> list[dict[str, Any]]:
        """
        R013: Evaluates interface compatibility (short circuit, contention, voltage mismatch).
        """
        findings = []
        for calc in self.calculations:
            if calc.get("category") == "INTERFACE":
                status = calc.get("status")
                issues = calc.get("issues", [])
                net_name = calc.get("net_name", "Net")
                net_id = calc.get("net_id")

                if status == "INCOMPATIBLE":
                    for issue in issues:
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "rule_id": "R013",
                            "title": f"Interface incompatibility on net '{net_name}': {issue.get('type')}",
                            "description": issue.get("message", "Interface incompatibility detected."),
                            "severity": issue.get("severity", "CRITICAL"),
                            "status": "INCOMPATIBLE",
                            "component_ids": [],
                            "net_ids": [net_id] if net_id else [],
                            "pin_ids": issue.get("pins", []),
                            "recommended_action": "Resolve pin direction contention or voltage mismatch.",
                            "provenance": "DETERMINISTIC_RULE",
                            "verification_status": "CALCULATED",
                        })
                elif status == "CONDITIONAL":
                    for issue in issues:
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "rule_id": "R013",
                            "title": f"Interface conditional on net '{net_name}': {issue.get('type')}",
                            "description": issue.get("message", "Missing required pull-up resistor."),
                            "severity": "WARNING",
                            "status": "CONDITIONAL",
                            "component_ids": [],
                            "net_ids": [net_id] if net_id else [],
                            "pin_ids": issue.get("pins", []),
                            "recommended_action": "Add appropriate pull-up resistor (e.g. 4.7kΩ for I2C).",
                            "provenance": "DETERMINISTIC_RULE",
                            "verification_status": "CALCULATED",
                        })

        return findings

    # -------------------------------------------------------------------------
    # R014: Frequency / Timing Limit Exceeded
    # -------------------------------------------------------------------------
    def check_r014_frequency_timing_limit_exceeded(self) -> list[dict[str, Any]]:
        """
        R014: Evaluates signal frequency against component maximum clock/switching ratings.
        """
        findings = []
        for comp_id, comp in self.graph.components.items():
            limits = self.specs.resolve_operating_limits(comp)
            f_max = limits.get("freq_max_hz")
            name = comp.get("name", comp_id)

            if f_max is not None:
                for net_id in self.graph.component_nets.get(comp_id, set()):
                    net = self.graph.nets.get(net_id, {})
                    net_props = net.get("properties") or {}
                    signal_freq = parse_frequency(net_props.get("frequency") or net_props.get("clock_freq"))

                    if signal_freq is not None and signal_freq > f_max:
                        findings.append({
                            "id": str(uuid.uuid4()),
                            "rule_id": "R014",
                            "title": f"Frequency limit exceeded on {name}",
                            "description": (
                                f"Signal frequency on net '{net.get('name')}' ({signal_freq/1e6:.2f} MHz) "
                                f"exceeds maximum rated operating frequency ({f_max/1e6:.2f} MHz) for {name}."
                            ),
                            "severity": "CRITICAL",
                            "status": "VIOLATED",
                            "actual_value": signal_freq,
                            "limit_value": f_max,
                            "unit": "Hz",
                            "component_ids": [comp_id],
                            "net_ids": [net_id],
                            "pin_ids": [],
                            "recommended_action": f"Reduce clock frequency or upgrade {name} to higher-speed variant.",
                            "provenance": "DETERMINISTIC_RULE",
                            "verification_status": "CALCULATED",
                        })

        return findings

    # -------------------------------------------------------------------------
    # R015: Requirement Violation
    # -------------------------------------------------------------------------
    def check_r015_requirement_violation(self) -> list[dict[str, Any]]:
        """
        R015: Evaluates user/system EngineeringRequirement expressions against circuit state.
        Produces categorical status: SATISFIED, VIOLATED, UNKNOWN.
        """
        findings = []
        if not self.requirements:
            return findings

        # Synthesize flat circuit state dictionary for requirement evaluation
        circuit_state = {}
        for comp in self.graph.components.values():
            name = comp.get("name")
            if name:
                circuit_state[name] = comp

        for net in self.graph.nets.values():
            net_name = net.get("name")
            if net_name:
                v = self.graph.infer_net_voltage(net_name)
                if v is not None:
                    circuit_state[net_name] = v
                    circuit_state[f"{net_name}_voltage"] = v

        for calc in self.calculations:
            cat = calc.get("category")
            res = calc.get("result", {})
            if cat == "REGULATOR":
                circuit_state["v_out"] = res.get("vout_v")
                circuit_state["power"] = res.get("power_dissipated_w")
            elif cat == "VOLTAGE_DIVIDER":
                circuit_state["v_out"] = res.get("v_out")
            elif cat == "THERMAL":
                circuit_state["junction_temp"] = res.get("junction_temp_c")

        for req in self.requirements:
            eval_res = evaluate_engineering_requirement(req, circuit_state)
            status = eval_res.get("status")

            if status == "VIOLATED":
                findings.append({
                    "id": str(uuid.uuid4()),
                    "rule_id": "R015",
                    "title": f"Requirement violated: {eval_res.get('title')}",
                    "description": eval_res.get("reason"),
                    "severity": "CRITICAL" if req.get("priority") == "CRITICAL" else "WARNING",
                    "status": "VIOLATED",
                    "actual_value": eval_res.get("actual"),
                    "limit_value": eval_res.get("target"),
                    "unit": eval_res.get("unit"),
                    "component_ids": [],
                    "net_ids": [],
                    "pin_ids": [],
                    "recommended_action": "Adjust circuit component values to meet requirement expression.",
                    "provenance": "DETERMINISTIC_RULE",
                    "verification_status": "CALCULATED",
                })
            elif status == "UNKNOWN":
                findings.append({
                    "id": str(uuid.uuid4()),
                    "rule_id": "R015",
                    "title": f"Requirement state unknown: {eval_res.get('title')}",
                    "description": eval_res.get("reason"),
                    "severity": "INFO",
                    "status": "UNKNOWN",
                    "actual_value": None,
                    "limit_value": eval_res.get("target"),
                    "unit": eval_res.get("unit"),
                    "component_ids": [],
                    "net_ids": [],
                    "pin_ids": [],
                    "recommended_action": "Ensure circuit parameters allow evaluation of requirement target.",
                    "provenance": "DETERMINISTIC_RULE",
                    "verification_status": "UNVERIFIED",
                })

        return findings

    # -------------------------------------------------------------------------
    # R016: System Design Constraint Violation
    # -------------------------------------------------------------------------
    def check_r016_design_constraint_violation(self) -> list[dict[str, Any]]:
        """
        R016: Evaluates EngineeringSystemDesignConstraint.
        HARD constraint: PASS / FAIL / UNKNOWN.
        SOFT constraint: SATISFIED / NOT_SATISFIED / UNKNOWN.
        """
        findings = []
        if not self.constraints:
            return findings

        circuit_state = {}
        for net in self.graph.nets.values():
            net_name = net.get("name")
            if net_name:
                v = self.graph.infer_net_voltage(net_name)
                if v is not None:
                    circuit_state[net_name] = v
                    circuit_state[f"{net_name}_voltage"] = v

        for calc in self.calculations:
            cat = calc.get("category")
            res = calc.get("result", {})
            if cat == "REGULATOR":
                circuit_state["v_out"] = res.get("vout_v")
                circuit_state["power"] = res.get("power_dissipated_w")
            elif cat == "THERMAL":
                circuit_state["junction_temp"] = res.get("junction_temp_c")

        for c in self.constraints:
            eval_res = evaluate_system_design_constraint(c, circuit_state)
            status = eval_res.get("status")

            if status in ["FAIL", "NOT_SATISFIED"]:
                c_type = eval_res.get("constraint_type")
                findings.append({
                    "id": str(uuid.uuid4()),
                    "rule_id": "R016",
                    "title": f"Design constraint violation: {eval_res.get('parameter')}",
                    "description": eval_res.get("reason"),
                    "severity": "CRITICAL" if c_type == "HARD" else "WARNING",
                    "status": status,
                    "actual_value": eval_res.get("actual"),
                    "limit_value": eval_res.get("target"),
                    "unit": eval_res.get("unit"),
                    "component_ids": [],
                    "net_ids": [],
                    "pin_ids": [],
                    "recommended_action": f"Adjust design to satisfy {c_type} constraint.",
                    "provenance": "DETERMINISTIC_RULE",
                    "verification_status": "CALCULATED",
                })
            elif status == "UNKNOWN":
                findings.append({
                    "id": str(uuid.uuid4()),
                    "rule_id": "R016",
                    "title": f"Design constraint unknown: {eval_res.get('parameter')}",
                    "description": eval_res.get("reason"),
                    "severity": "INFO",
                    "status": "UNKNOWN",
                    "component_ids": [],
                    "net_ids": [],
                    "pin_ids": [],
                    "recommended_action": "Verify missing parameters for constraint evaluation.",
                    "provenance": "DETERMINISTIC_RULE",
                    "verification_status": "UNVERIFIED",
                })

        return findings
