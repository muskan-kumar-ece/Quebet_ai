import uuid
from typing import Any
from app.models.db.verification import (
    EngineeringFailureMode,
    FailureModeCategory,
)


class FailureAnalysisEngine:
    """
    Deterministic Failure Analysis Engine.
    Derives engineering failure modes from:
    1. Circuit topology and component roles
    2. Deterministic analysis findings (R001 - R008)
    3. Physics calculations (Ohm's law, junction temperatures, derating margins)
    4. Explicit engineering unknowns
    """

    def analyze_circuit(
        self,
        circuit_dict: dict[str, Any],
        analysis_data: dict[str, Any],
        review_id: str,
        tenant_id: str | None,
    ) -> list[EngineeringFailureMode]:
        failure_modes: list[EngineeringFailureMode] = []
        components = circuit_dict.get("components", [])
        nets = circuit_dict.get("nets", [])
        connections = circuit_dict.get("connections", [])
        findings = analysis_data.get("findings", [])
        calculations = analysis_data.get("calculations", [])
        unknowns = analysis_data.get("unknowns", [])

        comp_by_id = {c["id"]: c for c in components}
        comp_by_ref = {c.get("ref_des", c.get("name", "")).upper(): c for c in components}

        # ----------------------------------------------------------------------
        # 1. OVERPOWER & COMPONENT_RATING_MARGIN (R003, R006)
        # ----------------------------------------------------------------------
        r003_findings = [f for f in findings if f.get("rule_id") == "R003"]
        for f in r003_findings:
            comp_refs = f.get("component_refs", [])
            comp_ids = f.get("component_ids", [comp_by_ref.get(r, {}).get("id") for r in comp_refs if r in comp_by_ref])
            comp_ids = [cid for cid in comp_ids if cid]
            failure_modes.append(
                EngineeringFailureMode(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    category=FailureModeCategory.OVERPOWER.value,
                    trigger=f"R003: {f.get('title')}",
                    mechanism="Electrical power dissipation exceeds continuous package rating; Joule heating causes dielectric breakdown or permanent resistive drift.",
                    consequence="Thermal damage to resistor element, localized PCB discoloration, fire hazard, or open-circuit failure.",
                    likelihood="HIGH",
                    severity="CRITICAL",
                    affected_components=comp_ids,
                    affected_nets=[],
                    evidence=["DETERMINISTIC_ANALYSIS", "OHMS_LAW_CALCULATION", "ENGINEERING_RULE_R003"],
                    unknowns=[],
                    related_findings=[f.get("id")] if f.get("id") else [],
                    related_rules=["R003"],
                    verification_requirement_ids=[],
                )
            )

        r006_findings = [f for f in findings if f.get("rule_id") == "R006"]
        for f in r006_findings:
            comp_refs = f.get("component_refs", [])
            comp_ids = [comp_by_ref.get(r, {}).get("id") for r in comp_refs if r in comp_by_ref]
            failure_modes.append(
                EngineeringFailureMode(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    category=FailureModeCategory.COMPONENT_RATING_MARGIN.value,
                    trigger=f"R006: {f.get('title')}",
                    mechanism="Component operates at or near absolute maximum rating with less than 20% safety margin.",
                    consequence="Premature fatigue, reduced MTBF, accelerated failure during elevated ambient temperature conditions.",
                    likelihood="MEDIUM",
                    severity="WARNING",
                    affected_components=[cid for cid in comp_ids if cid],
                    affected_nets=[],
                    evidence=["DETERMINISTIC_ANALYSIS", "DERATING_MARGIN_CALCULATION"],
                    unknowns=[],
                    related_findings=[f.get("id")] if f.get("id") else [],
                    related_rules=["R006"],
                    verification_requirement_ids=[],
                )
            )

        # ----------------------------------------------------------------------
        # 2. OVERVOLTAGE & VOLTAGE_DOMAIN_CONFLICT (R004, R008)
        # ----------------------------------------------------------------------
        r004_findings = [f for f in findings if f.get("rule_id") == "R004"]
        for f in r004_findings:
            failure_modes.append(
                EngineeringFailureMode(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    category=FailureModeCategory.OVERVOLTAGE.value,
                    trigger=f"R004: {f.get('title')}",
                    mechanism="Input rail voltage exceeds regulator maximum rated input breakdown voltage.",
                    consequence="Immediate pass-element punch-through, uncontrolled rail pass-through to downstream low-voltage silicon.",
                    likelihood="HIGH",
                    severity="CRITICAL",
                    affected_components=f.get("component_ids", []),
                    affected_nets=f.get("net_ids", []),
                    evidence=["DETERMINISTIC_ANALYSIS", "MAX_VOLTAGE_RATING", "ENGINEERING_RULE_R004"],
                    unknowns=[],
                    related_findings=[f.get("id")] if f.get("id") else [],
                    related_rules=["R004"],
                    verification_requirement_ids=[],
                )
            )

        r008_findings = [f for f in findings if f.get("rule_id") == "R008"]
        for f in r008_findings:
            failure_modes.append(
                EngineeringFailureMode(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    category=FailureModeCategory.VOLTAGE_DOMAIN_CONFLICT.value,
                    trigger=f"R008: {f.get('title')}",
                    mechanism="5V domain driving directly into low-voltage (3.3V/1.8V) CMOS I/O or power pin without level translation.",
                    consequence="Forward-biasing of internal ESD protection diodes, parasitic latch-up, high clamp currents, and silicon destruction.",
                    likelihood="HIGH",
                    severity="CRITICAL",
                    affected_components=f.get("component_ids", []),
                    affected_nets=f.get("net_ids", []),
                    evidence=["DETERMINISTIC_ANALYSIS", "LOGIC_FAMILY_STANDARDS", "ENGINEERING_RULE_R008"],
                    unknowns=[],
                    related_findings=[f.get("id")] if f.get("id") else [],
                    related_rules=["R008"],
                    verification_requirement_ids=[],
                )
            )

        # ----------------------------------------------------------------------
        # 3. OVERCURRENT & THERMAL_OVERSTRESS (R005, Thermal Calculations)
        # ----------------------------------------------------------------------
        r005_findings = [f for f in findings if f.get("rule_id") == "R005"]
        for f in r005_findings:
            failure_modes.append(
                EngineeringFailureMode(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    category=FailureModeCategory.OVERCURRENT.value,
                    trigger=f"R005: {f.get('title')}",
                    mechanism="Output current draw exceeds continuous limit of linear regulator pass transistor.",
                    consequence="Thermal limiting shutdown, excessive output voltage droop, or thermal thermal-runaway destruction.",
                    likelihood="HIGH",
                    severity="CRITICAL",
                    affected_components=f.get("component_ids", []),
                    affected_nets=f.get("net_ids", []),
                    evidence=["DETERMINISTIC_ANALYSIS", "REGULATOR_CURRENT_CALCULATION", "ENGINEERING_RULE_R005"],
                    unknowns=[],
                    related_findings=[f.get("id")] if f.get("id") else [],
                    related_rules=["R005"],
                    verification_requirement_ids=[],
                )
            )

        # Inspect thermal calculations
        reg_calcs = [c for c in calculations if c.get("category") == "REGULATOR"]
        for rc in reg_calcs:
            res = rc.get("result", {})
            tj = res.get("junction_temp_c")
            dissipation = res.get("power_dissipation_w")
            if (tj is not None and tj > 100.0) or (dissipation is not None and dissipation > 1.0):
                failure_modes.append(
                    EngineeringFailureMode(
                        id=str(uuid.uuid4()),
                        review_id=review_id,
                        tenant_id=tenant_id,
                        category=FailureModeCategory.THERMAL_OVERSTRESS.value,
                        trigger=f"Elevated Junction Temperature: {tj}°C (Dissipation: {dissipation}W)",
                        mechanism="Linear power dissipation in package creates excessive internal silicon junction temperature without active heatsinking.",
                        consequence="Thermal cycling fatigue, solder joint creep, sporadic reset due to thermal protection tripping.",
                        likelihood="HIGH" if tj and tj > 125.0 else "MEDIUM",
                        severity="CRITICAL" if tj and tj > 125.0 else "WARNING",
                        affected_components=res.get("component_id", []),
                        affected_nets=[],
                        evidence=["DETERMINISTIC_ANALYSIS", "THERMAL_DISSIPATION_EQUATION"],
                        unknowns=["Ambient temperature profile unknown" if not any("ambient" in str(u).lower() for u in unknowns) else "Ambient profile unverified"],
                        related_findings=[],
                        related_rules=["R005"],
                        verification_requirement_ids=[],
                    )
                )

        # ----------------------------------------------------------------------
        # 4. MISSING_DECOUPLING & POWER_INTEGRITY (R007)
        # ----------------------------------------------------------------------
        r007_findings = [f for f in findings if f.get("rule_id") == "R007"]
        for f in r007_findings:
            failure_modes.append(
                EngineeringFailureMode(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    category=FailureModeCategory.MISSING_DECOUPLING.value,
                    trigger=f"R007: {f.get('title')}",
                    mechanism="Lack of localized high-frequency bypass capacitance allows switching current transients (di/dt) to develop voltage bounce on supply rails.",
                    consequence="Microcontroller brownouts, spurious watchdog resets, degraded ADC SNR, and high radiated RF emissions.",
                    likelihood="HIGH",
                    severity="WARNING",
                    affected_components=f.get("component_ids", []),
                    affected_nets=f.get("net_ids", []),
                    evidence=["DETERMINISTIC_ANALYSIS", "TOPOLOGICAL_INSPECTION", "ENGINEERING_RULE_R007"],
                    unknowns=[],
                    related_findings=[f.get("id")] if f.get("id") else [],
                    related_rules=["R007"],
                    verification_requirement_ids=[],
                )
            )

        # ----------------------------------------------------------------------
        # 5. FLOATING_NODE & SIGNAL_INTEGRITY (R002)
        # ----------------------------------------------------------------------
        r002_findings = [f for f in findings if f.get("rule_id") == "R002"]
        for f in r002_findings:
            failure_modes.append(
                EngineeringFailureMode(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    category=FailureModeCategory.FLOATING_NODE.value,
                    trigger=f"R002: {f.get('title')}",
                    mechanism="High-impedance gate or required control pin left unconnected picks up electrostatic or capacitive noise.",
                    consequence="Unpredictable logic states, high shoot-through supply currents, spontaneous chip reset or bus contention.",
                    likelihood="HIGH",
                    severity="CRITICAL",
                    affected_components=f.get("component_ids", []),
                    affected_nets=[],
                    evidence=["DETERMINISTIC_ANALYSIS", "CIRCUIT_TOPOLOGY_INSPECTION", "ENGINEERING_RULE_R002"],
                    unknowns=[],
                    related_findings=[f.get("id")] if f.get("id") else [],
                    related_rules=["R002"],
                    verification_requirement_ids=[],
                )
            )

        # ----------------------------------------------------------------------
        # 6. UNKNOWN_COMPONENT_BEHAVIOR (Unresolved Unknowns)
        # ----------------------------------------------------------------------
        for u in unknowns:
            var_name = u.get("variable", "UNSPECIFIED_PARAMETER") if isinstance(u, dict) else str(u)
            failure_modes.append(
                EngineeringFailureMode(
                    id=str(uuid.uuid4()),
                    review_id=review_id,
                    tenant_id=tenant_id,
                    category=FailureModeCategory.UNKNOWN_COMPONENT_BEHAVIOR.value,
                    trigger=f"Missing Engineering Specification: {var_name}",
                    mechanism="Absence of verified datasheet limits precludes closed-form safety verification.",
                    consequence="Operational hazard during extreme environmental conditions; impossible to guarantee product longevity.",
                    likelihood="LOW",
                    severity="WARNING",
                    affected_components=u.get("affected_components", []) if isinstance(u, dict) else [],
                    affected_nets=[],
                    evidence=["ENGINEERING_UNKNOWN_TRACKER"],
                    unknowns=[var_name],
                    related_findings=[],
                    related_rules=[],
                    verification_requirement_ids=[],
                )
            )

        return failure_modes


failure_analysis_engine = FailureAnalysisEngine()
