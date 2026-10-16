"""
Verification & Authoritative Source Consistency Engine for Phase 3 Wave 8.
Evaluates Rules X016 (Verification Evidence Currency), X017 (Historical vs Current Verification),
and X018 (Authoritative Source Currency).
STRICT INVARIANTS:
- HISTORICAL_VERIFICATION != CURRENT_VERIFICATION.
- A historical record does NOT automatically verify current design revision.
- ANALYSIS != PHYSICAL EVIDENCE.
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


class VerificationConsistencyEngine:
    """
    Evaluates verification evidence currency and authoritative source validity across design revisions.
    """

    @staticmethod
    def evaluate(
        project_id: str,
        circuit: Optional[Any],
        verifications: Optional[list[Any]],
        evidence_items: Optional[list[Any]],
        sources: Optional[list[Any]],
        rules: dict[str, dict[str, Any]],
    ) -> list[CrossDomainFinding]:
        findings: list[CrossDomainFinding] = []

        rule_016 = rules.get("X016")
        rule_017 = rules.get("X017")
        rule_018 = rules.get("X018")

        circuit_rev = int(getattr(circuit, "version", 1)) if circuit else 1

        # --- Rule X016: Verification Evidence vs Current Engineering Revision ---
        if rule_016:
            if not evidence_items:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X016_NO_EVIDENCE",
                        project_id=project_id,
                        domain_a=ValidationDomain.VERIFICATION,
                        domain_b=ValidationDomain.SCHEMATIC,
                        rule_id="X016",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_016["engineering_claim"],
                        explanation="No verification evidence records exist for this project. Physical/analytical evidence state unknown.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                stale_evidence = 0
                current_evidence = 0
                for ev in evidence_items:
                    ev_rev = getattr(ev, "design_revision", None) or getattr(ev, "circuit_version", None) or getattr(ev, "circuit_revision", None)
                    if ev_rev is not None and int(ev_rev) != circuit_rev:
                        stale_evidence += 1
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X016_STALE_EVIDENCE_{ev.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.VERIFICATION,
                                domain_b=ValidationDomain.SCHEMATIC,
                                affected_entity_ids=[str(ev.id)],
                                rule_id="X016",
                                status=CrossDomainStatus.WARNING,
                                severity=CrossDomainSeverity.HIGH,
                                engineering_claim=rule_016["engineering_claim"],
                                explanation=f"Evidence item '{getattr(ev, 'title', ev.id)}' corresponds to revision {ev_rev}, but current circuit is revision {circuit_rev}.",
                                source_classification=SourceClassification.HISTORICAL,
                            )
                        )
                    else:
                        current_evidence += 1

                if stale_evidence == 0 and current_evidence > 0:
                    findings.append(
                        CrossDomainFinding(
                            finding_id="X016_PASS_ALL",
                            project_id=project_id,
                            domain_a=ValidationDomain.VERIFICATION,
                            domain_b=ValidationDomain.SCHEMATIC,
                            rule_id="X016",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_016["engineering_claim"],
                            explanation=f"All {current_evidence} verification evidence items reference the active design revision {circuit_rev}.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )

        # --- Rule X017: Historical Verification vs Current Design Revision ---
        if rule_017:
            if not verifications:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X017_NO_VERIFICATIONS",
                        project_id=project_id,
                        domain_a=ValidationDomain.VERIFICATION,
                        domain_b=ValidationDomain.SCHEMATIC,
                        rule_id="X017",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_017["engineering_claim"],
                        explanation="No formal verification closure items exist. Verification currency unknown.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                historical_mismatches = 0
                active_verifications = 0
                for v in verifications:
                    v_rev = getattr(v, "design_revision", None) or getattr(v, "circuit_version", None) or getattr(v, "circuit_revision", None)
                    v_status = str(getattr(v, "status", "")).upper()
                    if v_rev is not None and int(v_rev) != circuit_rev and v_status in ("SATISFIED", "VERIFIED"):
                        historical_mismatches += 1
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X017_HISTORICAL_OVERCLAIM_{v.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.VERIFICATION,
                                domain_b=ValidationDomain.SCHEMATIC,
                                affected_entity_ids=[str(v.id)],
                                rule_id="X017",
                                status=CrossDomainStatus.UNKNOWN,
                                severity=CrossDomainSeverity.HIGH,
                                engineering_claim=rule_017["engineering_claim"],
                                explanation=f"HISTORICAL RECORD: Verification item '{getattr(v, 'title', v.id)}' passed on revision {v_rev}. (HISTORICAL_VERIFICATION != CURRENT_VERIFICATION; re-verification required for rev {circuit_rev}).",
                                source_classification=SourceClassification.HISTORICAL,
                            )
                        )
                    else:
                        active_verifications += 1

                if historical_mismatches == 0 and active_verifications > 0:
                    findings.append(
                        CrossDomainFinding(
                            finding_id="X017_PASS_ALL",
                            project_id=project_id,
                            domain_a=ValidationDomain.VERIFICATION,
                            domain_b=ValidationDomain.SCHEMATIC,
                            rule_id="X017",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_017["engineering_claim"],
                            explanation=f"All active verification records are aligned with current design revision {circuit_rev}.",
                            source_classification=SourceClassification.CALCULATED,
                        )
                    )

        # --- Rule X018: Current Authoritative Source vs Stale Source ---
        if rule_018:
            if not sources:
                findings.append(
                    CrossDomainFinding(
                        finding_id="X018_NO_SOURCES",
                        project_id=project_id,
                        domain_a=ValidationDomain.DATASHEET,
                        domain_b=ValidationDomain.BOM,
                        rule_id="X018",
                        status=CrossDomainStatus.UNKNOWN,
                        severity=CrossDomainSeverity.INFO,
                        engineering_claim=rule_018["engineering_claim"],
                        explanation="No external engineering sources or datasheets tracked for project.",
                        source_classification=SourceClassification.UNKNOWN,
                    )
                )
            else:
                stale_sources = 0
                valid_sources = 0
                for s in sources:
                    s_status = str(getattr(s, "status", "ACTIVE")).upper()
                    if s_status in ("SUPERSEDED", "OBSOLETE", "DEPRECATED", "STALE"):
                        stale_sources += 1
                        findings.append(
                            CrossDomainFinding(
                                finding_id=f"X018_SUPERSEDED_SOURCE_{s.id}",
                                project_id=project_id,
                                domain_a=ValidationDomain.DATASHEET,
                                domain_b=ValidationDomain.BOM,
                                affected_entity_ids=[str(s.id)],
                                rule_id="X018",
                                status=CrossDomainStatus.WARNING,
                                severity=CrossDomainSeverity.MEDIUM,
                                engineering_claim=rule_018["engineering_claim"],
                                explanation=f"Engineering source '{getattr(s, 'title', getattr(s, 'name', s.id))}' has status '{s_status}'. May contain obsolete technical ratings.",
                                source_classification=SourceClassification.HISTORICAL,
                            )
                        )
                    else:
                        valid_sources += 1

                if stale_sources == 0 and valid_sources > 0:
                    findings.append(
                        CrossDomainFinding(
                            finding_id="X018_PASS_ALL",
                            project_id=project_id,
                            domain_a=ValidationDomain.DATASHEET,
                            domain_b=ValidationDomain.BOM,
                            rule_id="X018",
                            status=CrossDomainStatus.PASS,
                            severity=CrossDomainSeverity.INFO,
                            engineering_claim=rule_018["engineering_claim"],
                            explanation=f"All {valid_sources} tracked engineering sources are active and authoritative.",
                            source_classification=SourceClassification.MANUFACTURER_CONFIRMED,
                        )
                    )

        return findings
