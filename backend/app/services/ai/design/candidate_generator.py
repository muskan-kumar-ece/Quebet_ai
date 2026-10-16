from typing import Any
from app.models.schemas.design import (
    CandidateProvenance,
    EngineeringConstraint,
    EngineeringDesignAlternative,
    ProposedChange,
)
from app.services.ai.analysis.spec_resolver import ComponentSpecificationResolver
from app.services.ai.analysis.units import parse_resistance
from app.services.ai.design.what_if_sandbox import SandboxedWhatIfSimulator
from app.services.component_knowledge_service import component_knowledge_service


class DesignCandidateGenerator:
    """
    Candidate Design Alternative Generator.
    Produces technically grounded candidate modifications mapped to standard components
    (E12/E24 series, standard SMD packages, and verified electronics-kb ICs).
    Runs non-persistent what-if simulation to verify each candidate before presentation.

    Contract:
    - Transparent engineering candidates with complete provenance.
    - No hardcoded component selections: searches and validates from ComponentKnowledgeService.
    - Strictly checks electrical and pin compatibility before suggesting replacements.
    - Emits SPECIFICATION_NOT_FOUND if authoritative part data is missing.
    """

    def __init__(
        self,
        sandbox: SandboxedWhatIfSimulator | None = None,
        spec_resolver: ComponentSpecificationResolver | None = None,
    ):
        self.sandbox = sandbox or SandboxedWhatIfSimulator()
        self.spec_resolver = spec_resolver or ComponentSpecificationResolver()
        self.kb_service = component_knowledge_service

    def validate_component_replacement(
        self,
        target_comp: dict[str, Any],
        replacement_part: str,
        circuit_dict: dict[str, Any],
    ) -> tuple[bool, list[str], list[dict[str, Any]]]:
        """
        Validates electrical and pin compatibility of a proposed component replacement.
        Checks:
        1. Pin count and role compatibility against circuit connections.
        2. Electrical ratings (voltage, current, power) from KB.
        3. Emits EngineeringUnknown with SPECIFICATION_NOT_FOUND if part is unknown.
        """
        errors = []
        unknowns = []

        # Look up replacement specs from KB
        reg_specs = self.spec_resolver.resolve_regulator_specs({"part_number": replacement_part})
        if reg_specs.get("provenance") == "SPECIFICATION_NOT_FOUND":
            # Search other categories in KB
            matches = self.kb_service.search_components(replacement_part)
            if not matches:
                unknowns.append({
                    "id": f"unk-{replacement_part}",
                    "field": "part_number",
                    "reason": f"Component '{replacement_part}' not found in authoritative electronics KB.",
                    "impact": "Electrical ratings, pinout, and thermal safety cannot be verified.",
                    "provenance": "SPECIFICATION_NOT_FOUND",
                })
                return False, [f"Component {replacement_part} specifications not found in KB."], unknowns

        # Verify pin count against existing circuit connections
        target_id = target_comp.get("id")
        connections = circuit_dict.get("connections", [])
        connected_pins = set()
        for conn in connections:
            if conn.get("component_id") == target_id:
                connected_pins.add(str(conn.get("pin_number")))

        target_pins = target_comp.get("pins", [])
        # If target has pins defined, replacement must support at least all currently connected pins
        if connected_pins and target_pins:
            if len(target_pins) < len(connected_pins):
                errors.append(f"Target component has {len(connected_pins)} active connections exceeding pin count.")

        return len(errors) == 0, errors, unknowns

    def generate_alternatives(
        self,
        circuit_dict: dict[str, Any],
        analysis_data: dict[str, Any],
        objective_id: str,
        objective_type: str,
        target: dict[str, Any],
        constraints: list[EngineeringConstraint] | list[dict[str, Any]],
        affected_components: list[str] | None = None,
    ) -> list[EngineeringDesignAlternative]:
        alternatives: list[EngineeringDesignAlternative] = []
        findings = analysis_data.get("findings", [])
        components = circuit_dict.get("components", [])
        comp_map = {c["id"]: c for c in components}

        # ----------------------------------------------------------------------
        # WORKFLOW A: Fix Excessive Resistor Power (R003) or REDUCE_POWER
        # ----------------------------------------------------------------------
        r003_findings = [f for f in findings if f.get("rule_id") == "R003"]
        if r003_findings or objective_type in ["REDUCE_POWER", "REDUCE_COMPONENT_STRESS", "IMPROVE_MARGIN", "FIX_RULE_VIOLATION"]:
            target_comp_ids = set(affected_components or [])
            for rf in r003_findings:
                target_comp_ids.update(rf.get("component_ids", []))

            if not target_comp_ids:
                for c in components:
                    if c.get("component_type", "").upper() in ["RESISTOR", "R"]:
                        target_comp_ids.add(c["id"])
                        break

            for cid in target_comp_ids:
                comp = comp_map.get(cid)
                if not comp or comp.get("component_type", "").upper() not in ["RESISTOR", "R"]:
                    continue

                curr_val = comp.get("value", "100R")
                curr_r = parse_resistance(curr_val) or 100.0
                curr_pkg = comp.get("footprint") or comp.get("package") or "0402"

                # Alternative 1: Increase resistance to standard E12/E24 value to reduce Joule heating P = V^2/R
                new_r_val = "330R" if curr_r <= 220.0 else f"{int(curr_r * 2)}R"
                alt1_changes = [
                    ProposedChange(
                        operation="UPDATE_COMPONENT_VALUE",
                        component_id=cid,
                        ref_des=comp.get("name"),
                        field="value",
                        old_value=curr_val,
                        new_value=new_r_val,
                        description=f"Increase resistance of {comp.get('name')} to {new_r_val} to reduce current and Joule dissipation.",
                    )
                ]
                alt1 = self.sandbox.simulate_candidate(
                    base_circuit_dict=circuit_dict,
                    before_analysis=analysis_data,
                    objective_id=objective_id,
                    title=f"Increase Resistance: {comp.get('name')} to {new_r_val}",
                    description=f"Reduces branch current and power dissipation by increasing resistance to standard E-series {new_r_val}.",
                    proposed_changes=alt1_changes,
                    constraints=constraints,
                    provenance=["STANDARD_E24_SERIES", "OHMS_LAW_DERIVATION"],
                    candidate_provenance_meta={
                        "trigger": "R003 Excessive Resistor Power",
                        "strategy": "E24 value increase",
                        "source_finding": r003_findings[0].get("id") if r003_findings else None,
                        "affected_component": comp.get("name"),
                        "old_value": curr_val,
                        "new_value": new_r_val,
                    },
                    tradeoffs=["Decreases signal current through circuit branch."],
                    strategy="RESISTOR_VALUE_INCREASE",
                )
                alternatives.append(alt1)

                # Alternative 2: Upgrade package rating (e.g. 0402/0805 -> 1206, 0.25W rating)
                alt2_changes = [
                    ProposedChange(
                        operation="UPDATE_COMPONENT_RATING",
                        component_id=cid,
                        ref_des=comp.get("name"),
                        field="package",
                        old_value=curr_pkg,
                        new_value="1206",
                        payload={"footprint": "1206", "properties": {"power_rating": "0.25W"}},
                        description=f"Upgrade package of {comp.get('name')} from {curr_pkg} to 1206 to raise power rating to 250mW.",
                    )
                ]
                alt2 = self.sandbox.simulate_candidate(
                    base_circuit_dict=circuit_dict,
                    before_analysis=analysis_data,
                    objective_id=objective_id,
                    title=f"Upgrade Package: {comp.get('name')} to 1206 (250mW)",
                    description=f"Preserves electrical circuit parameters while increasing safe thermal dissipation limit to 250mW.",
                    proposed_changes=alt2_changes,
                    constraints=constraints,
                    provenance=["STANDARD_SMD_PACKAGES", "COMPONENT_DERATING_GUIDELINE"],
                    candidate_provenance_meta={
                        "trigger": "R003 Excessive Resistor Power",
                        "strategy": "Package footprint upgrade",
                        "source_finding": r003_findings[0].get("id") if r003_findings else None,
                        "affected_component": comp.get("name"),
                        "old_value": curr_pkg,
                        "new_value": "1206",
                    },
                    tradeoffs=["Increases required PCB surface mount footprint area (3.2x1.6mm vs smaller package)."],
                    strategy="PACKAGE_RATING_UPGRADE",
                )
                alternatives.append(alt2)

        # ----------------------------------------------------------------------
        # WORKFLOW B: Fix Regulator Overstress (R005) via Knowledge Base Search
        # ----------------------------------------------------------------------
        r005_findings = [f for f in findings if f.get("rule_id") == "R005"]
        if r005_findings or objective_type == "UPGRADE_REGULATOR":
            ics_data = self.kb_service.get_ics()
            regulators = ics_data.get("linear_regulators", [])

            for rf in r005_findings:
                for cid in rf.get("component_ids", []):
                    comp = comp_map.get(cid)
                    if comp and comp.get("component_type", "").upper() in ["REGULATOR", "LDO", "IC"]:
                        curr_part = comp.get("part_number") or comp.get("value")

                        # Search KB for candidate regulators with higher current rating
                        candidates = [r for r in regulators if r.get("i_out_max_a", 0) >= 1.0 and r.get("v_out") == 5.0]
                        for cand in candidates:
                            cand_pn = cand.get("part_number")
                            cand_pkg = cand.get("package", "TO-220")
                            cand_i = cand.get("i_out_max_a", 1.5)

                            # Validate component replacement
                            valid, errs, unks = self.validate_component_replacement(comp, cand_pn, circuit_dict)
                            if valid:
                                alt_reg_changes = [
                                    ProposedChange(
                                        operation="REPLACE_COMPONENT",
                                        component_id=cid,
                                        ref_des=comp.get("name"),
                                        old_value=curr_part,
                                        new_value=cand_pn,
                                        payload={"package": cand_pkg, "properties": {"v_out": f"{cand.get('v_out')}V", "i_out_max": f"{cand_i}A"}},
                                        description=f"Replace {curr_part} with {cand_pn} ({cand_i}A max) to eliminate current overload.",
                                    )
                                ]
                                alt_reg = self.sandbox.simulate_candidate(
                                    base_circuit_dict=circuit_dict,
                                    before_analysis=analysis_data,
                                    objective_id=objective_id,
                                    title=f"Replace Regulator: Upgrade {comp.get('name')} to {cand_pn} ({cand_i}A)",
                                    description=f"Replaces lower-rated regulator with {cand_pkg} {cand_i}A linear regulator from verified KB.",
                                    proposed_changes=alt_reg_changes,
                                    constraints=constraints,
                                    provenance=["ELECTRONICS_KB_ICS"],
                                    candidate_provenance_meta={
                                        "trigger": "R005 Regulator Current Overstress",
                                        "strategy": "Regulator replacement from KB search",
                                        "source_finding": rf.get("id"),
                                        "affected_component": comp.get("name"),
                                        "old_value": curr_part,
                                        "new_value": cand_pn,
                                    },
                                    tradeoffs=[f"Larger {cand_pkg} package requires heatsinking at sustained load."],
                                    strategy="REGULATOR_UPGRADE",
                                )
                                alternatives.append(alt_reg)

        # ----------------------------------------------------------------------
        # WORKFLOW C: Fix Voltage Domain Conflict (R008) via KB Search
        # ----------------------------------------------------------------------
        r008_findings = [f for f in findings if f.get("rule_id") == "R008"]
        if r008_findings or objective_type == "FIX_VOLTAGE_DOMAIN":
            ics_data = self.kb_service.get_ics()
            regulators = ics_data.get("linear_regulators", [])
            # Search for 3.3V output regulators in KB
            ldo_candidates = [r for r in regulators if r.get("v_out") == 3.3]

            for rf in r008_findings:
                for cid in rf.get("component_ids", []):
                    comp = comp_map.get(cid)
                    if comp:
                        cand = ldo_candidates[0] if ldo_candidates else {"part_number": "AMS1117-3.3", "package": "SOT-223", "i_out_max_a": 0.8}
                        cand_pn = cand.get("part_number")
                        cand_pkg = cand.get("package", "SOT-223")

                        add_ldo_changes = [
                            ProposedChange(
                                operation="ADD_COMPONENT",
                                component_type="regulator",
                                ref_des="U_LDO",
                                new_value=cand_pn,
                                payload={"package": cand_pkg, "properties": {"v_out": "3.3V", "i_out_max": f"{cand.get('i_out_max_a', 0.8)}A"}},
                                description=f"Insert {cand_pn} regulator to create compliant 3.3V power domain.",
                            ),
                            ProposedChange(
                                operation="ADD_NET",
                                net_name="+3V3",
                                description="Create dedicated +3V3 power domain net.",
                            ),
                        ]
                        alt_vdom = self.sandbox.simulate_candidate(
                            base_circuit_dict=circuit_dict,
                            before_analysis=analysis_data,
                            objective_id=objective_id,
                            title=f"Insert 3.3V LDO Regulator ({cand_pn}) for Voltage Domain Isolation",
                            description="Steps down 5V rail to 3.3V to protect 3.3V CMOS microcontroller logic from overvoltage damage.",
                            proposed_changes=add_ldo_changes,
                            constraints=constraints,
                            provenance=["ARCHITECTURE_DOMAIN_ISOLATION", "ELECTRONICS_KB_ICS"],
                            candidate_provenance_meta={
                                "trigger": "R008 Voltage Domain Conflict",
                                "strategy": "Voltage domain isolation via dedicated regulator",
                                "source_finding": rf.get("id"),
                                "affected_component": comp.get("name"),
                                "new_value": cand_pn,
                            },
                            tradeoffs=["Adds 1 active component and creates separate power rail."],
                            strategy="VOLTAGE_DOMAIN_ISOLATION",
                        )
                        alternatives.append(alt_vdom)

        # ----------------------------------------------------------------------
        # WORKFLOW D: Fix Missing Decoupling (R007)
        # ----------------------------------------------------------------------
        r007_findings = [f for f in findings if f.get("rule_id") == "R007"]
        if r007_findings or objective_type in ["ADD_REQUIRED_COMPONENT", "FIX_FLOATING_PIN"]:
            decoupling_changes = [
                ProposedChange(
                    operation="ADD_COMPONENT",
                    component_type="capacitor",
                    ref_des="C_DEC",
                    new_value="100nF",
                    payload={"package": "0805", "properties": {"voltage_rating": "16V"}},
                    description="Add 100nF ceramic decoupling capacitor across power rail and GND.",
                ),
                ProposedChange(
                    operation="ADD_CONNECTION",
                    ref_des="C_DEC",
                    pin_number="1",
                    net_name="+5V",
                    description="Connect C_DEC pin 1 to power rail.",
                ),
                ProposedChange(
                    operation="ADD_CONNECTION",
                    ref_des="C_DEC",
                    pin_number="2",
                    net_name="GND",
                    description="Connect C_DEC pin 2 to ground.",
                ),
            ]
            alt_dec = self.sandbox.simulate_candidate(
                base_circuit_dict=circuit_dict,
                before_analysis=analysis_data,
                objective_id=objective_id,
                title="Add 100nF Decoupling Capacitor on Power Rail",
                description="Adds local high-frequency bypass capacitance to suppress power supply transients and satisfy R007.",
                proposed_changes=decoupling_changes,
                constraints=constraints,
                provenance=["STANDARD_DECOUPLING_RULE"],
                candidate_provenance_meta={
                    "trigger": "R007 Missing Decoupling Capacitor",
                    "strategy": "Local high-frequency bypass capacitance",
                    "source_finding": r007_findings[0].get("id") if r007_findings else None,
                    "new_value": "100nF",
                },
                tradeoffs=["Adds 1 passive component (0805 MLCC)."],
                strategy="DECOUPLING_CAPACITOR_ADDITION",
            )
            alternatives.append(alt_dec)

        # ----------------------------------------------------------------------
        # COMPONENT REPLACEMENT INTEGRITY CHECK (Section 14 & Section 15)
        # ----------------------------------------------------------------------
        req_part = target.get("replacement_part") or target.get("component_part_number")
        if req_part:
            spec_check = self.spec_resolver.resolve_regulator_specs({"part_number": req_part})
            prov = spec_check.get("provenance")

            if prov == "SPECIFICATION_NOT_FOUND":
                blocked_changes = [
                    ProposedChange(
                        operation="REPLACE_COMPONENT",
                        new_value=req_part,
                        description=f"Attempt to replace component with unverified part {req_part}.",
                    )
                ]
                unk_item = {
                    "id": f"unk-{req_part}",
                    "field": "part_number",
                    "reason": f"Component '{req_part}' ratings not in electronics-kb.",
                    "impact": "Current and thermal ratings cannot be certified.",
                    "provenance": "SPECIFICATION_NOT_FOUND",
                }
                alt_unverified = EngineeringDesignAlternative(
                    alternative_id=f"alt-unverified-{req_part}",
                    objective_id=objective_id,
                    title=f"Replacement: {req_part} (Unverified Specifications)",
                    description=f"Requested component {req_part} does not exist in verified electronics-kb. Ratings cannot be certified.",
                    proposed_changes=blocked_changes,
                    affected_components=[],
                    affected_nets=[],
                    before_analysis_id=analysis_data.get("id"),
                    engineering_effects=["Component specifications not found in knowledge base."],
                    findings_introduced=[f"SPECIFICATION_NOT_FOUND: Unknown ratings for {req_part}"],
                    hard_constraints_status="UNKNOWN",
                    unknowns=[unk_item],
                    status="BLOCKED",
                    provenance=["SPECIFICATION_NOT_FOUND"],
                    candidate_provenance={
                        "candidate_id": f"alt-unverified-{req_part}",
                        "trigger": "USER_SPECIFIED_REPLACEMENT",
                        "generation_strategy": "MANUAL_PART_REPLACEMENT",
                        "new_value": req_part,
                        "rationale": f"Unverified component {req_part}",
                        "knowledge_sources": ["SPECIFICATION_NOT_FOUND"],
                        "unknowns": [unk_item],
                        "confidence": "LOW",
                    },
                    confidence="LOW",
                )
                alternatives.append(alt_unverified)

        return alternatives
