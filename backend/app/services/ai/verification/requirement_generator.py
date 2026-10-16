import uuid
from typing import Any
from app.models.db.verification import (
    EngineeringFailureMode,
    EngineeringTestPoint,
    EngineeringVerificationRequirement,
    OperatingCondition,
    VerificationMethod,
    VerificationStatus,
)


class VerificationRequirementGenerator:
    """
    Deterministic Verification Requirement & Test Point Generator.
    Grounds requirements in the VR001+ namespace and links them to failure modes,
    operating conditions, and laboratory measurement procedures.
    """

    def generate(
        self,
        circuit_dict: dict[str, Any],
        analysis_data: dict[str, Any],
        failure_modes: list[EngineeringFailureMode],
        review_id: str,
        tenant_id: str | None,
    ) -> tuple[list[EngineeringVerificationRequirement], list[EngineeringTestPoint]]:
        requirements: list[EngineeringVerificationRequirement] = []
        test_points: list[EngineeringTestPoint] = []

        components = circuit_dict.get("components", [])
        nets = circuit_dict.get("nets", [])
        findings = analysis_data.get("findings", [])
        calculations = analysis_data.get("calculations", [])
        unknowns = analysis_data.get("unknowns", [])

        req_counter = 1
        tp_counter = 1

        def next_req_code() -> str:
            nonlocal req_counter
            code = f"VR-{req_counter:03d}"
            req_counter += 1
            return code

        def next_tp_code() -> str:
            nonlocal tp_counter
            code = f"TP-{tp_counter:03d}"
            tp_counter += 1
            return code

        # Map failure modes by related rules
        fm_by_rule: dict[str, list[EngineeringFailureMode]] = {}
        for fm in failure_modes:
            for r in fm.related_rules:
                fm_by_rule.setdefault(r, []).append(fm)

        # ----------------------------------------------------------------------
        # VR001: Component Rating & Power Dissipation Verification
        # ----------------------------------------------------------------------
        resistors = [c for c in components if c.get("component_type", "").lower() == "resistor"]
        if resistors or "R003" in fm_by_rule:
            code = next_req_code()
            affected = [c["id"] for c in resistors]
            r003_fms = fm_by_rule.get("R003", [])
            req1 = EngineeringVerificationRequirement(
                id=str(uuid.uuid4()),
                review_id=review_id,
                tenant_id=tenant_id,
                code=code,
                title="Verify Passive Component Power Dissipation and Derating Margin",
                reason="Resistive components must not exceed 60-80% rated dissipation under maximum load conditions.",
                trigger="R003 Excessive Resistor Power / Passive derating checks",
                method=VerificationMethod.COMPONENT_RATING_CHECK.value,
                operating_condition=OperatingCondition.MAXIMUM_LOAD.value,
                required_evidence=["Calculated or measured continuous current", "Package power rating from datasheet"],
                status=VerificationStatus.NOT_STARTED.value if not r003_fms else VerificationStatus.BLOCKED.value,
                is_mandatory=True,
                affected_components=affected,
                affected_nets=[],
                related_rule_id="VR001",
                unknowns=[],
            )
            requirements.append(req1)
            for fm in r003_fms:
                fm.verification_requirement_ids.append(req1.id)

        # ----------------------------------------------------------------------
        # VR002: Thermal Verification (Regulators / Power ICs)
        # ----------------------------------------------------------------------
        regulators = [c for c in components if c.get("component_type", "").lower() == "regulator"]
        thermal_fms = [fm for fm in failure_modes if fm.category == "THERMAL_OVERSTRESS"]
        if regulators or thermal_fms:
            code = next_req_code()
            reg_ids = [r["id"] for r in regulators]
            req2 = EngineeringVerificationRequirement(
                id=str(uuid.uuid4()),
                review_id=review_id,
                tenant_id=tenant_id,
                code=code,
                title="Verify Silicon Junction Temperature and Thermal Dissipation Limit",
                reason="Linear regulators convert voltage differentials into heat; thermal calculations must confirm Tj < 125°C at peak ambient temperature.",
                trigger="Active voltage regulation under elevated input voltage or current load",
                method=VerificationMethod.THERMAL_CALCULATION.value,
                operating_condition=OperatingCondition.THERMAL_EXTREME.value,
                required_evidence=["Thermal resistance (Rth_ja or Rth_jc)", "Ambient operating temperature range", "Worst-case load current"],
                status=VerificationStatus.UNKNOWN.value if any("ambient" in str(u).lower() for u in unknowns) else VerificationStatus.NOT_STARTED.value,
                is_mandatory=True,
                affected_components=reg_ids,
                affected_nets=[],
                related_rule_id="VR002",
                unknowns=["Ambient temperature profile" if any("ambient" in str(u).lower() for u in unknowns) else None],
            )
            req2.unknowns = [u for u in req2.unknowns if u]
            requirements.append(req2)
            for fm in thermal_fms:
                fm.verification_requirement_ids.append(req2.id)

            # Add corresponding Laboratory Test Point
            test_points.append(
                EngineeringTestPoint(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    code=next_tp_code(),
                    target_component=regulators[0].get("ref_des", regulators[0].get("name", "REG1")) if regulators else "REG1",
                    measurement="Regulator Case / Tab Temperature at Max Load",
                    expected_basis="T_case + (P_diss * Rth_jc) < 125°C maximum junction rating",
                    instrumentation="Thermocouple / FLIR Thermal Imager",
                    operating_condition=OperatingCondition.MAXIMUM_LOAD.value,
                    related_requirement_id=req2.id,
                )
            )

        # ----------------------------------------------------------------------
        # VR003: Operating Voltage Range & Rail Regulation
        # ----------------------------------------------------------------------
        power_nets = [n for n in nets if any(s in n.get("name", "").upper() for s in ["VCC", "VDD", "3V3", "5V", "+"])]
        if power_nets or regulators:
            code = next_req_code()
            target_net = power_nets[0].get("name") if power_nets else "+3V3"
            req3 = EngineeringVerificationRequirement(
                id=str(uuid.uuid4()),
                review_id=review_id,
                tenant_id=tenant_id,
                code=code,
                title="Verify DC Supply Rail Regulation and Dropout Margin",
                reason="Output voltage must remain within +/- 3% tolerance across input voltage variations and transient load steps.",
                trigger="Regulated power rail stability verification",
                method=VerificationMethod.MEASUREMENT.value,
                operating_condition=OperatingCondition.MAXIMUM_INPUT.value,
                required_evidence=["Bench DMM measurement at nominal load", "Bench DMM measurement at maximum load"],
                status=VerificationStatus.NOT_STARTED.value,
                is_mandatory=True,
                affected_components=[r["id"] for r in regulators],
                affected_nets=[n["id"] for n in power_nets],
                related_rule_id="VR003",
                unknowns=[],
            )
            requirements.append(req3)

            test_points.append(
                EngineeringTestPoint(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    code=next_tp_code(),
                    target_net=target_net,
                    measurement=f"DC Steady-State Voltage on {target_net}",
                    expected_basis="Target voltage within nominal tolerance under load",
                    instrumentation="Digital Multimeter (6.5 digit precision)",
                    operating_condition=OperatingCondition.NOMINAL.value,
                    related_requirement_id=req3.id,
                )
            )

        # ----------------------------------------------------------------------
        # VR004: Decoupling Capacitor Verification (R007)
        # ----------------------------------------------------------------------
        r007_fms = fm_by_rule.get("R007", [])
        caps = [c for c in components if c.get("component_type", "").lower() == "capacitor"]
        if r007_fms or caps:
            code = next_req_code()
            req4 = EngineeringVerificationRequirement(
                id=str(uuid.uuid4()),
                review_id=review_id,
                tenant_id=tenant_id,
                code=code,
                title="Verify Local High-Frequency Decoupling Capacitance",
                reason="Ceramic capacitors (100nF) must be physically positioned adjacent to power pins to minimize parasitic inductance.",
                trigger="R007 Missing Decoupling / High di/dt switching noise",
                method=VerificationMethod.SCHEMATIC_REVIEW.value,
                operating_condition=OperatingCondition.STARTUP.value,
                required_evidence=["Schematic symbol confirmation", "100nF ceramic cap presence with low ESR"],
                status=VerificationStatus.FAILED.value if r007_fms else VerificationStatus.SATISFIED.value,
                is_mandatory=True,
                affected_components=[c["id"] for c in caps],
                affected_nets=[],
                related_rule_id="VR004",
                unknowns=[],
            )
            requirements.append(req4)
            for fm in r007_fms:
                fm.verification_requirement_ids.append(req4.id)

            test_points.append(
                EngineeringTestPoint(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    code=next_tp_code(),
                    target_net=power_nets[0].get("name") if power_nets else "VCC",
                    measurement="Power Rail AC Ripple & Switching Transients",
                    expected_basis="Peak-to-peak ripple < 50mVpp across operating frequency band",
                    instrumentation="Oscilloscope (AC coupling, 20MHz bandwidth limit)",
                    operating_condition=OperatingCondition.TRANSIENT.value,
                    related_requirement_id=req4.id,
                )
            )

        # ----------------------------------------------------------------------
        # VR005: Voltage Domain Isolation Verification (R008)
        # ----------------------------------------------------------------------
        r008_fms = fm_by_rule.get("R008", [])
        if r008_fms:
            code = next_req_code()
            req5 = EngineeringVerificationRequirement(
                id=str(uuid.uuid4()),
                review_id=review_id,
                tenant_id=tenant_id,
                code=code,
                title="Verify Logic Level Voltage Domain Compatibility",
                reason="Direct connection between divergent voltage rails (e.g. 5V into 3.3V) induces latchup and ESD diode burnout.",
                trigger="R008 Voltage Domain Conflict",
                method=VerificationMethod.SCHEMATIC_REVIEW.value,
                operating_condition=OperatingCondition.NOMINAL.value,
                required_evidence=["Level shifter or separate power rail step-down topology verified"],
                status=VerificationStatus.BLOCKED.value,
                is_mandatory=True,
                affected_components=[],
                affected_nets=[],
                related_rule_id="VR005",
                unknowns=[],
            )
            requirements.append(req5)
            for fm in r008_fms:
                fm.verification_requirement_ids.append(req5.id)

        # ----------------------------------------------------------------------
        # VR006: Component Specification & Datasheet Verification
        # ----------------------------------------------------------------------
        if unknowns:
            code = next_req_code()
            unk_strs = [u.get("variable", str(u)) if isinstance(u, dict) else str(u) for u in unknowns]
            req6 = EngineeringVerificationRequirement(
                id=str(uuid.uuid4()),
                review_id=review_id,
                tenant_id=tenant_id,
                code=code,
                title="Verify Unresolved Component Specifications in Manufacturer Datasheets",
                reason="Calculations depend on unresolved assumptions or missing component datasheet parameters.",
                trigger="Presence of EngineeringUnknown entries",
                method=VerificationMethod.DATASHEET_REVIEW.value,
                operating_condition=OperatingCondition.NOMINAL.value,
                required_evidence=["Official manufacturer datasheet matching full orderable part number"],
                status=VerificationStatus.UNKNOWN.value,
                is_mandatory=True,
                affected_components=[],
                affected_nets=[],
                related_rule_id="VR006",
                unknowns=unk_strs,
            )
            requirements.append(req6)

        # ----------------------------------------------------------------------
        # VR007: Critical Findings Resolution Verification
        # ----------------------------------------------------------------------
        critical_findings = [f for f in findings if f.get("severity") == "CRITICAL"]
        if critical_findings:
            code = next_req_code()
            c_titles = [f.get("title", "Critical Finding") for f in critical_findings]
            req7 = EngineeringVerificationRequirement(
                id=str(uuid.uuid4()),
                review_id=review_id,
                tenant_id=tenant_id,
                code=code,
                title=f"Resolve {len(critical_findings)} Critical Engineering Analysis Findings",
                reason="Design review cannot be verified while known critical deterministic engineering rule violations persist.",
                trigger="Active critical findings in baseline analysis",
                method=VerificationMethod.DETERMINISTIC_CALCULATION.value,
                operating_condition=OperatingCondition.NOMINAL.value,
                required_evidence=["Engineering proposal applied to eliminate critical violations", "Clean deterministic re-analysis"],
                status=VerificationStatus.BLOCKED.value,
                is_mandatory=True,
                affected_components=[],
                affected_nets=[],
                related_rule_id="VR007",
                unknowns=[],
            )
            requirements.append(req7)

        return requirements, test_points


verification_requirement_generator = VerificationRequirementGenerator()
