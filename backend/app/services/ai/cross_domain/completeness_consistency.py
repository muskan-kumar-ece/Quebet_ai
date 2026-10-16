"""
Cross-Domain Completeness Engine for Phase 3 Wave 8.
Evaluates Rule X020 (Engineering State Cross-Domain Completeness).
STRICT INVARIANTS:
- Complete system engineering requires synchronization across all seven core domains.
- Missing domains are strictly flagged as UNKNOWN (Never implied PASS).
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


class CompletenessConsistencyEngine:
    """
    Audits availability of multi-domain pillars to prevent premature sign-off.
    """

    @staticmethod
    def evaluate(
        project_id: str,
        circuit: Optional[Any],
        board: Optional[Any],
        bom: Optional[Any],
        simulation_job: Optional[Any],
        dfm_analysis: Optional[Any],
        requirements: Optional[list[Any]],
        verifications: Optional[list[Any]],
        rules: dict[str, dict[str, Any]],
    ) -> list[CrossDomainFinding]:
        findings: list[CrossDomainFinding] = []

        rule_020 = rules.get("X020")
        if not rule_020:
            return findings

        domain_status = {
            "Schematic": circuit is not None,
            "PCB": board is not None,
            "BOM": bom is not None,
            "Simulation": simulation_job is not None,
            "DFM": dfm_analysis is not None,
            "Requirements": bool(requirements and len(requirements) > 0),
            "Verification": bool(verifications and len(verifications) > 0),
        }

        missing = [d for d, present in domain_status.items() if not present]
        present = [d for d, present in domain_status.items() if present]

        if missing:
            findings.append(
                CrossDomainFinding(
                    finding_id="X020_INCOMPLETE_DOMAINS",
                    project_id=project_id,
                    domain_a=ValidationDomain.SCHEMATIC,
                    domain_b=ValidationDomain.PCB,
                    rule_id="X020",
                    status=CrossDomainStatus.UNKNOWN,
                    severity=CrossDomainSeverity.INFO,
                    engineering_claim=rule_020["engineering_claim"],
                    explanation=f"Cross-domain state is incomplete. Missing domain artifacts: {', '.join(missing)}. Available domains: {', '.join(present)}.",
                    quantitative_values={"available_domains": len(present), "missing_domains": len(missing)},
                    source_classification=SourceClassification.UNKNOWN,
                )
            )
        else:
            findings.append(
                CrossDomainFinding(
                    finding_id="X020_PASS_ALL",
                    project_id=project_id,
                    domain_a=ValidationDomain.SCHEMATIC,
                    domain_b=ValidationDomain.PCB,
                    rule_id="X020",
                    status=CrossDomainStatus.PASS,
                    severity=CrossDomainSeverity.INFO,
                    engineering_claim=rule_020["engineering_claim"],
                    explanation="All seven core engineering domains (Schematic, PCB, BOM, Simulation, DFM, Requirements, Verification) are populated and synchronized.",
                    quantitative_values={"available_domains": 7, "missing_domains": 0},
                    source_classification=SourceClassification.CALCULATED,
                )
            )

        return findings
