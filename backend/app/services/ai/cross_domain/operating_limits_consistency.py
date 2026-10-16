"""
Component Operating Limits & Absolute Maximum Consistency Engine for Phase 3 Wave 8.
Evaluates Rules X006 (Continuous Operating Limits) and X007 (Absolute Maximum Ratings).
STRICT INVARIANTS:
- UNKNOWN != PASS
- Missing operating condition or datasheet rating -> UNKNOWN
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


class OperatingLimitsConsistencyEngine:
    """
    Cross-checks component electrical ratings (Wave 2 / Datasheet) against circuit design conditions (Wave 3 / Wave 4).
    """

    @staticmethod
    def evaluate(
        project_id: str,
        circuit: Optional[Any],
        analysis_results: Optional[list[Any]],
        rules: dict[str, dict[str, Any]],
    ) -> list[CrossDomainFinding]:
        findings: list[CrossDomainFinding] = []

        rule_006 = rules.get("X006")
        rule_007 = rules.get("X007")

        if not circuit:
            for rule_id in ("X006", "X007"):
                r = rules.get(rule_id)
                if r:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"{rule_id}_NO_CIRCUIT",
                            project_id=project_id,
                            domain_a=ValidationDomain.DATASHEET,
                            domain_b=ValidationDomain.SCHEMATIC,
                            rule_id=rule_id,
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.HIGH,
                            engineering_claim=r["engineering_claim"],
                            explanation="Circuit model is missing. Component operating ratings cannot be evaluated against design conditions.",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )
            return findings

        components = getattr(circuit, "components", []) or []
        if not components:
            for rule_id in ("X006", "X007"):
                r = rules.get(rule_id)
                if r:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"{rule_id}_NO_COMPONENTS",
                            project_id=project_id,
                            domain_a=ValidationDomain.DATASHEET,
                            domain_b=ValidationDomain.SCHEMATIC,
                            rule_id=rule_id,
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=r["engineering_claim"],
                            explanation="No components present in circuit to evaluate operating limits.",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )
            return findings

        # Map operating conditions from analysis results or component attributes
        # Components can have `operating_voltage`, `voltage_rating`, `abs_max_voltage`, etc.
        # or extracted from `component.specifications` / `component.properties`.
        passes_006 = 0
        violations_006 = 0
        passes_007 = 0
        violations_007 = 0

        for comp in components:
            ref = str(getattr(comp, "ref_des", "")).strip().upper()
            props = getattr(comp, "properties", None) or getattr(comp, "metadata_", None) or {}
            specs = getattr(comp, "specifications", None) or {}
            if not isinstance(props, dict):
                props = {}
            if not isinstance(specs, dict):
                specs = {}

            # Operating conditions (from analysis, properties, or schematic specs)
            v_operating = props.get("operating_voltage", specs.get("operating_voltage", specs.get("v_in", props.get("v_in"))))
            v_rated = props.get("voltage_rating", specs.get("voltage_rating", specs.get("v_max_continuous", props.get("v_rated"))))
            v_abs_max = props.get("abs_max_voltage", specs.get("abs_max_voltage", specs.get("v_abs_max", props.get("v_abs_max"))))

            # Rule X006: Continuous Operating Limit
            if rule_006:
                if v_operating is None or v_rated is None:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X006_UNKNOWN_{comp.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.DATASHEET,
                            domain_b=ValidationDomain.SCHEMATIC,
                            affected_entity_ids=[str(comp.id)],
                            rule_id="X006",
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_006["engineering_claim"],
                            explanation=f"Component {ref} lacks specified operating voltage ({v_operating}) or rated voltage limit ({v_rated}). Conformance unknown.",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )
                else:
                    try:
                        v_op = float(v_operating)
                        v_rt = float(v_rated)
                        margin_v = v_rt - v_op
                        if v_op > v_rt:
                            violations_006 += 1
                            findings.append(
                                CrossDomainFinding(
                                    finding_id=f"X006_OVERRATED_{comp.id}",
                                    project_id=project_id,
                                    domain_a=ValidationDomain.DATASHEET,
                                    domain_b=ValidationDomain.SCHEMATIC,
                                    affected_entity_ids=[str(comp.id)],
                                    rule_id="X006",
                                    status=CrossDomainStatus.FAIL,
                                    severity=CrossDomainSeverity.HIGH,
                                    engineering_claim=rule_006["engineering_claim"],
                                    explanation=f"Component {ref} operating voltage ({v_op:.2f}V) exceeds continuous rating ({v_rt:.2f}V) by {abs(margin_v):.2f}V.",
                                    quantitative_values={"operating_v": v_op, "rated_v": v_rt},
                                    margin=round(margin_v, 4),
                                    source_classification=SourceClassification.CALCULATED,
                                )
                            )
                        else:
                            passes_006 += 1
                    except (ValueError, TypeError):
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X006_PARSE_ERR_{comp.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.DATASHEET,
                                domain_b=ValidationDomain.SCHEMATIC,
                                affected_entity_ids=[str(comp.id)],
                                rule_id="X006",
                                status=CrossDomainStatus.UNKNOWN,
                                severity=CrossDomainSeverity.LOW,
                                engineering_claim=rule_006["engineering_claim"],
                                explanation=f"Non-numeric voltage values on {ref}: operating={v_operating}, rated={v_rated}.",
                                source_classification=SourceClassification.UNKNOWN,
                            )
                        )

            # Rule X007: Absolute Maximum Limit
            if rule_007:
                if v_operating is None or v_abs_max is None:
                    findings.append(
                        CrossDomainFinding(
                            finding_id=f"X007_UNKNOWN_{comp.id}",
                            project_id=project_id,
                            domain_a=ValidationDomain.DATASHEET,
                            domain_b=ValidationDomain.SCHEMATIC,
                            affected_entity_ids=[str(comp.id)],
                            rule_id="X007",
                            status=CrossDomainStatus.UNKNOWN,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_007["engineering_claim"],
                            explanation=f"Component {ref} lacks specified operating voltage ({v_operating}) or absolute maximum limit ({v_abs_max}). Absolute max safety unknown.",
                            source_classification=SourceClassification.UNKNOWN,
                        )
                    )
                else:
                    try:
                        v_op = float(v_operating)
                        v_am = float(v_abs_max)
                        margin_am = v_am - v_op
                        if v_op >= v_am:
                            violations_007 += 1
                            findings.append(
                                CrossDomainFinding(
                                    finding_id=f"X007_ABS_MAX_VIOLATION_{comp.id}",
                                    project_id=project_id,
                                    domain_a=ValidationDomain.DATASHEET,
                                    domain_b=ValidationDomain.SCHEMATIC,
                                    affected_entity_ids=[str(comp.id)],
                                    rule_id="X007",
                                    status=CrossDomainStatus.FAIL,
                                    severity=CrossDomainSeverity.CRITICAL,
                                    engineering_claim=rule_007["engineering_claim"],
                                    explanation=f"CRITICAL: Component {ref} operating condition ({v_op:.2f}V) violates absolute maximum rating ({v_am:.2f}V). Permanent silicon damage risk.",
                                    quantitative_values={"operating_v": v_op, "abs_max_v": v_am},
                                    margin=round(margin_am, 4),
                                    source_classification=SourceClassification.CALCULATED,
                                )
                            )
                        else:
                            passes_007 += 1
                    except (ValueError, TypeError):
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X007_PARSE_ERR_{comp.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.DATASHEET,
                                domain_b=ValidationDomain.SCHEMATIC,
                                affected_entity_ids=[str(comp.id)],
                                rule_id="X007",
                                status=CrossDomainStatus.UNKNOWN,
                                severity=CrossDomainSeverity.LOW,
                                engineering_claim=rule_007["engineering_claim"],
                                explanation=f"Non-numeric voltage values on {ref}: operating={v_operating}, abs_max={v_abs_max}.",
                                source_classification=SourceClassification.UNKNOWN,
                            )
                        )

        if rule_006 and violations_006 == 0 and passes_006 > 0:
            findings.append(
                CrossDomainFinding(
                    finding_id="X006_PASS_ALL",
                    project_id=project_id,
                    domain_a=ValidationDomain.DATASHEET,
                    domain_b=ValidationDomain.SCHEMATIC,
                    rule_id="X006",
                    status=CrossDomainStatus.PASS,
                    severity=CrossDomainSeverity.INFO,
                    engineering_claim=rule_006["engineering_claim"],
                    explanation=f"All {passes_006} evaluated components operate within designated continuous operating limits.",
                    source_classification=SourceClassification.CALCULATED,
                )
            )

        if rule_007 and violations_007 == 0 and passes_007 > 0:
            findings.append(
                CrossDomainFinding(
                    finding_id="X007_PASS_ALL",
                    project_id=project_id,
                    domain_a=ValidationDomain.DATASHEET,
                    domain_b=ValidationDomain.SCHEMATIC,
                    rule_id="X007",
                    status=CrossDomainStatus.PASS,
                    severity=CrossDomainSeverity.INFO,
                    engineering_claim=rule_007["engineering_claim"],
                    explanation=f"All {passes_007} evaluated components maintain positive safety margin below absolute maximum ratings.",
                    source_classification=SourceClassification.CALCULATED,
                )
            )

        return findings
