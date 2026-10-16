"""
Requirements & Design Constraint Consistency Engine for Phase 3 Wave 8.
Evaluates Rules X013 (Requirement vs Implementation) and X014 (Design vs Manufacturing Constraints).
STRICT INVARIANTS:
- A requirement lacks evidence -> UNKNOWN (Do NOT infer satisfaction from AI explanation).
- SATISFIED requires verifiable engineering state and evidence.
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


class RequirementsConsistencyEngine:
    """
    Evaluates coverage and evidence for engineering requirements against current design implementation.
    """

    @staticmethod
    def evaluate(
        project_id: str,
        requirements: Optional[list[Any]],
        board: Optional[Any],
        dfm_rules: Optional[dict[str, Any]],
        rules: dict[str, dict[str, Any]],
    ) -> list[CrossDomainFinding]:
        findings: list[CrossDomainFinding] = []

        rule_013 = rules.get("X013")
        rule_014 = rules.get("X014")

        # --- Rule X013: Requirement vs Implementation Consistency ---
        if rule_013:
            if not requirements:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X013_NO_REQUIREMENTS",
                        project_id=project_id,
                        domain_a=ValidationDomain.REQUIREMENTS,
                        domain_b=ValidationDomain.SCHEMATIC,
                        rule_id="X013",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_013["engineering_claim"],
                        explanation="No formal engineering requirements defined for project. Requirement coverage unknown.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                satisfied_count = 0
                violated_count = 0
                unknown_count = 0

                for req in requirements:
                    req_id = str(getattr(req, "id", ""))
                    title = str(getattr(req, "title", getattr(req, "name", "Requirement")))
                    status = str(getattr(req, "status", "UNKNOWN")).upper()
                    evidence_links = getattr(req, "evidence_ids", []) or getattr(req, "evidence", []) or []

                    if status == "VIOLATED":
                        violated_count += 1
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X013_VIOLATED_{req_id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.REQUIREMENTS,
                                domain_b=ValidationDomain.SCHEMATIC,
                                affected_entity_ids=[req_id],
                                rule_id="X013",
                                status=CrossDomainStatus.FAIL,
                                severity=CrossDomainSeverity.HIGH,
                                engineering_claim=rule_013["engineering_claim"],
                                explanation=f"Engineering requirement '{title}' is explicitly flagged as VIOLATED.",
                                source_classification=SourceClassification.USER_ASSERTED,
                            )
                        )
                    elif status == "SATISFIED":
                        # Check if substantiated by evidence
                        if not evidence_links:
                            unknown_count += 1
                            findings.append(
                                CrossDomainFinding(
                                    finding_id=f"X013_UNSUBSTANTIATED_{req_id}",
                                    project_id=project_id,
                                    domain_a=ValidationDomain.REQUIREMENTS,
                                    domain_b=ValidationDomain.SCHEMATIC,
                                    affected_entity_ids=[req_id],
                                    rule_id="X013",
                                    status=CrossDomainStatus.UNKNOWN,
                                    severity=CrossDomainSeverity.MEDIUM,
                                    engineering_claim=rule_013["engineering_claim"],
                                    explanation=f"Requirement '{title}' is marked SATISFIED but lacks substantiated verification evidence items. (UNKNOWN != SATISFIED; AI explanation cannot substantiate compliance).",
                                    source_classification=SourceClassification.UNKNOWN,
                                )
                            )
                        else:
                            satisfied_count += 1
                    else:
                        unknown_count += 1
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X013_UNVERIFIED_{req_id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.REQUIREMENTS,
                                domain_b=ValidationDomain.SCHEMATIC,
                                affected_entity_ids=[req_id],
                                rule_id="X013",
                                status=CrossDomainStatus.UNKNOWN,
                                severity=CrossDomainSeverity.INFO,
                                engineering_claim=rule_013["engineering_claim"],
                                explanation=f"Requirement '{title}' status is '{status}'. Verification evidence required.",
                                source_classification=SourceClassification.UNKNOWN,
                            )
                        )

                if violated_count == 0 and unknown_count == 0 and satisfied_count > 0:
                    findings.append(
                        CrossDomainFinding(
                            finding_id="X013_PASS_ALL",
                            project_id=project_id,
                            domain_a=ValidationDomain.REQUIREMENTS,
                            domain_b=ValidationDomain.SCHEMATIC,
                            rule_id="X013",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_013["engineering_claim"],
                            explanation=f"All {satisfied_count} engineering requirements are linked to substantiated verification evidence.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )

        # --- Rule X014: Design Constraint vs Manufacturing Constraint ---
        if rule_014:
            if not board:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X014_NO_BOARD",
                        project_id=project_id,
                        domain_a=ValidationDomain.REQUIREMENTS,
                        domain_b=ValidationDomain.DFM,
                        rule_id="X014",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.HIGH,
                        engineering_claim=rule_014["engineering_claim"],
                        explanation="PCB board model is missing. Design constraint vs manufacturing capability compatibility unknown.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                traces = getattr(board, "traces", []) or []
                min_fab_width = 0.15  # default 0.15 mm
                if dfm_rules and "MFG001" in dfm_rules:
                    min_fab_width = float(dfm_rules["MFG001"].get("parameters", {}).get("min_trace_width_mm", 0.15))

                conflict_count = 0
                for t in traces:
                    w = float(getattr(t, "width", 0.0) or 0.0)
                    if 0 < w < min_fab_width:
                        conflict_count += 1
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X014_CONSTRAINT_CONFLICT_{t.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.REQUIREMENTS,
                                domain_b=ValidationDomain.DFM,
                                affected_entity_ids=[str(t.id)],
                                rule_id="X014",
                                status=CrossDomainStatus.FAIL,
                                severity=CrossDomainSeverity.HIGH,
                                engineering_claim=rule_014["engineering_claim"],
                                explanation=f"PCB trace width design constraint ({w} mm) conflicts with minimum fabrication capability ({min_fab_width} mm).",
                                quantitative_values={"design_width": w, "fab_capability_min": min_fab_width},
                                margin=round(w - min_fab_width, 4),
                                source_classification=SourceClassification.CALCULATED,
                            )
                        )

                if conflict_count == 0 and len(traces) > 0:
                    findings.append(
                        CrossDomainFinding(
                            finding_id="X014_PASS_ALL",
                            project_id=project_id,
                            domain_a=ValidationDomain.REQUIREMENTS,
                            domain_b=ValidationDomain.DFM,
                            rule_id="X014",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_014["engineering_claim"],
                            explanation=f"All evaluated physical layout design constraints satisfy manufacturing capability limits.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )

        return findings
