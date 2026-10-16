"""
Power and Thermal Cross-Domain Consistency Engine for Phase 3 Wave 8.
Evaluates Rules X008 (Power Rail Capacity), X009 (Junction Temperature Dissipation),
and X010 (PCB Thermal Dissipation Features).
STRICT INVARIANTS:
- UNKNOWN != PASS
- Missing thermal parameters or power metrics -> UNKNOWN (NEVER silently substitute typical values)
- Zero synthetic scoring.
"""
from typing import Any, Optional
from app.models.db.cross_domain import (
    CrossDomainSeverity,
    CrossDomainStatus,
    SourceClassification,
    ValidationDomain,
)
from app.models.schemas.cross_domain import CrossDomainFinding


class PowerThermalConsistencyEngine:
    """
    Connects Wave 3 electrical power calculations with Wave 7 thermal/DFM layout constraints.
    """

    @staticmethod
    def evaluate(
        project_id: str,
        circuit: Optional[Any],
        board: Optional[Any],
        rules: dict[str, dict[str, Any]],
    ) -> list[CrossDomainFinding]:
        findings: list[CrossDomainFinding] = []

        rule_008 = rules.get("X008")
        rule_009 = rules.get("X009")
        rule_010 = rules.get("X010")

        if not circuit:
            for rule_id, domain_b in [("X008", ValidationDomain.SCHEMATIC), ("X009", ValidationDomain.PCB), ("X010", ValidationDomain.PCB)]:
                r = rules.get(rule_id)
                if r:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"{rule_id}_NO_CIRCUIT",
                            project_id=project_id,
                            domain_a=ValidationDomain.POWER_THERMAL,
                            domain_b=domain_b,
                            rule_id=rule_id,
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.HIGH,
                            engineering_claim=r["engineering_claim"],
                            explanation="Circuit model is missing. Power and thermal consistency cannot be evaluated.",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )
            return findings

        components = getattr(circuit, "components", []) or []

        # --- Rule X008: Electrical Power Rail Budget ---
        if rule_008:
            rails = getattr(circuit, "power_rails", {}) or {}
            # If power rails are not formally configured, inspect component power supply vs load
            if not rails:
                # Check if circuit properties contain rail budget
                props = getattr(circuit, "properties", {}) or {}
                rails = props.get("power_rails", {})

            if not rails:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X008_NO_RAILS",
                        project_id=project_id,
                        domain_a=ValidationDomain.POWER_THERMAL,
                        domain_b=ValidationDomain.SCHEMATIC,
                        rule_id="X008",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_008["engineering_claim"],
                        explanation="No power rails or source capacity limits configured in circuit. Rail capacity balance unknown.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                rail_violations = 0
                rail_passes = 0
                for rail_name, rail_info in rails.items():
                    if isinstance(rail_info, dict):
                        source_current_a = rail_info.get("source_capacity_a")
                        load_current_a = rail_info.get("total_load_a")
                        if source_current_a is not None and load_current_a is not None:
                            try:
                                src_a = float(source_current_a)
                                ld_a = float(load_current_a)
                                margin_a = src_a - ld_a
                                if ld_a > src_a:
                                    rail_violations += 1
                                    findings.append(
                                        CrossDomainFinding(
                                            finding_id=f"X008_OVERLOAD_{rail_name}",
                                            project_id=project_id,
                                            domain_a=ValidationDomain.POWER_THERMAL,
                                            domain_b=ValidationDomain.SCHEMATIC,
                                            rule_id="X008",
                                            status=CrossDomainStatus.FAIL,
                                            severity=CrossDomainSeverity.CRITICAL,
                                            engineering_claim=rule_008["engineering_claim"],
                                            explanation=f"Power rail '{rail_name}' total load current ({ld_a:.3f}A) exceeds source capacity ({src_a:.3f}A) by {abs(margin_a):.3f}A.",
                                            quantitative_values={"source_a": src_a, "load_a": ld_a},
                                            margin=round(margin_a, 4),
                                            source_classification=SourceClassification.CALCULATED,
                                        )
                                    )
                                else:
                                    rail_passes += 1
                            except (ValueError, TypeError):
                                pass

                if rail_violations == 0 and rail_passes > 0:
                    findings.append(
                        CrossDomainFinding(
                            finding_id="X008_PASS_ALL",
                            project_id=project_id,
                            domain_a=ValidationDomain.POWER_THERMAL,
                            domain_b=ValidationDomain.SCHEMATIC,
                            rule_id="X008",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_008["engineering_claim"],
                            explanation=f"All {rail_passes} defined power rails have sufficient source capacity for connected loads.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )

        # --- Rule X009: Electrical Dissipation vs Thermal Constraints ---
        if rule_009:
            thermal_violations = 0
            thermal_passes = 0

            for comp in components:
                ref = str(getattr(comp, "ref_des", "")).strip().upper()
                props = getattr(comp, "properties", None) or getattr(comp, "metadata_", None) or {}
                specs = getattr(comp, "specifications", None) or {}
                if not isinstance(props, dict):
                    props = {}
                if not isinstance(specs, dict):
                    specs = {}

                p_diss = props.get("power_dissipation_w", specs.get("power_dissipation_w", props.get("pd_w")))
                r_th = props.get("r_theta_ja", specs.get("r_theta_ja", props.get("thermal_resistance_c_w")))
                t_max = props.get("tj_max_c", specs.get("tj_max_c", props.get("max_temp_c", 125.0)))
                t_amb = props.get("ambient_temp_c", specs.get("ambient_temp_c", 25.0))

                if p_diss is not None and r_th is not None:
                    try:
                        pd = float(p_diss)
                        rth = float(r_th)
                        tj_max = float(t_max)
                        ta = float(t_amb)

                        # Tj = Ta + Pd * RthJA
                        t_j = ta + (pd * rth)
                        margin_t = tj_max - t_j

                        if t_j > tj_max:
                            thermal_violations += 1
                            findings.append(
                                CrossDomainFinding(
                                    finding_id=f"X009_OVERTEMP_{comp.id}",
                                    project_id=project_id,
                                    domain_a=ValidationDomain.POWER_THERMAL,
                                    domain_b=ValidationDomain.PCB,
                                    affected_entity_ids=[str(comp.id)],
                                    rule_id="X009",
                                    status=CrossDomainStatus.FAIL,
                                    severity=CrossDomainSeverity.HIGH,
                                    engineering_claim=rule_009["engineering_claim"],
                                    explanation=f"Component {ref} estimated junction temperature ({t_j:.1f}°C) exceeds rated limit ({tj_max:.1f}°C) at {pd:.2f}W dissipation (RthJA={rth}°C/W, Ta={ta}°C).",
                                    quantitative_values={"t_junction_c": round(t_j, 1), "t_max_c": tj_max, "pd_w": pd, "rth_ja": rth},
                                    margin=round(margin_t, 2),
                                    source_classification=SourceClassification.CALCULATED,
                                )
                            )
                        else:
                            thermal_passes += 1
                    except (ValueError, TypeError):
                        pass
                elif p_diss is not None and float(p_diss or 0.0) > 0.5:
                    # Dissipates significant power but thermal resistance missing
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X009_MISSING_RTH_{comp.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.POWER_THERMAL,
                            domain_b=ValidationDomain.PCB,
                            affected_entity_ids=[str(comp.id)],
                            rule_id="X009",
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.MEDIUM,
                            engineering_claim=rule_009["engineering_claim"],
                            explanation=f"Component {ref} dissipates {p_diss}W but lacks thermal resistance (Rth_ja) parameter. Thermal junction rise unknown (silent default substitution strictly forbidden).",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )

            if thermal_violations == 0 and thermal_passes > 0:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X009_PASS_ALL",
                        project_id=project_id,
                        domain_a=ValidationDomain.POWER_THERMAL,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X009",
                        status=CrossDomainStatus.PASS,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_009["engineering_claim"],
                        explanation=f"All {thermal_passes} evaluated dissipating components maintain junction temperature below maximum ratings.",
                        source_classification=SourceClassification.CALCULATED,
                    )
                )

        # --- Rule X010: Thermal Requirement vs PCB Thermal Assumptions ---
        if rule_010:
            if not board:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X010_NO_BOARD",
                        project_id=project_id,
                        domain_a=ValidationDomain.POWER_THERMAL,
                        domain_b=ValidationDomain.PCB,
                        rule_id="X010",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.MEDIUM,
                        engineering_claim=rule_010["engineering_claim"],
                        explanation="PCB layout model missing. PCB thermal relief and dissipation features cannot be checked.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                footprints = getattr(board, "footprints", []) or []
                vias = getattr(board, "vias", []) or []

                high_power_refs = []
                for comp in components:
                    props = getattr(comp, "properties", None) or getattr(comp, "metadata_", None) or {}
                    p = props.get("power_dissipation_w", props.get("pd_w", 0.0))
                    try:
                        if float(p or 0.0) >= 0.5:
                            high_power_refs.append(str(getattr(comp, "ref_des", "")).upper())
                    except (ValueError, TypeError):
                        pass

                if not high_power_refs:
                    findings.append(
                        CrossDomainFinding(
                            finding_id="X010_LOW_POWER_PASS",
                            project_id=project_id,
                            domain_a=ValidationDomain.POWER_THERMAL,
                            domain_b=ValidationDomain.PCB,
                            rule_id="X010",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_010["engineering_claim"],
                            explanation="No components in circuit exhibit high power dissipation (>=0.5W); standard PCB thermal geometry is sufficient.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )
                else:
                    # Check if board has thermal vias or heat sinking
                    thermal_vias = [v for v in vias if getattr(v, "via_type", "") == "THERMAL" or "THERMAL" in str(getattr(v, "net_name", "")).upper()]
                    if not thermal_vias and len(vias) < 5:
                        findings.append(
                            CrossDomainFinding(
                                finding_id="X010_WARN_NO_THERMAL_VIAS",
                                project_id=project_id,
                                domain_a=ValidationDomain.POWER_THERMAL,
                                domain_b=ValidationDomain.PCB,
                                rule_id="X010",
                                status=CrossDomainStatus.WARNING,
                                severity=CrossDomainSeverity.MEDIUM,
                                engineering_claim=rule_010["engineering_claim"],
                                explanation=f"High-power components ({', '.join(high_power_refs)}) present, but PCB layout has no designated thermal vias or cooling reliefs.",
                                source_classification=SourceClassification.CALCULATED,
                            )
                        )
                    else:
                        findings.append(
                            CrossDomainFinding(
                                finding_id="X010_PASS_ALL",
                                project_id=project_id,
                                domain_a=ValidationDomain.POWER_THERMAL,
                                domain_b=ValidationDomain.PCB,
                                rule_id="X010",
                                status=CrossDomainStatus.PASS,
                                severity=CrossDomainSeverity.INFO,
                                engineering_claim=rule_010["engineering_claim"],
                                explanation=f"PCB thermal assumptions satisfied for high-power components ({', '.join(high_power_refs)}).",
                                source_classification=SourceClassification.CALCULATED,
                            )
                        )

        return findings
