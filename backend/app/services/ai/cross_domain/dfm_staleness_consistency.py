"""
DFM Staleness & Revision Consistency Engine for Phase 3 Wave 8.
Evaluates Rule X015 (DFM Finding vs Current PCB Revision).
STRICT INVARIANTS:
- A previous DFM analysis MUST NOT be represented as current if the PCB has changed.
- DFM snapshot digest != current PCB snapshot digest -> STATUS = UNKNOWN / STALE.
- DFM_ANALYSIS != MANUFACTURER_ACCEPTANCE.
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


class DFMStalenessConsistencyEngine:
    """
    Verifies that DFM fabrication and assembly analyses correspond to the active PCB revision.
    """

    @staticmethod
    def evaluate(
        project_id: str,
        board: Optional[Any],
        dfm_analysis: Optional[Any],
        current_board_digest: Optional[str],
        rules: dict[str, dict[str, Any]],
    ) -> list[CrossDomainFinding]:
        findings: list[CrossDomainFinding] = []

        rule_015 = rules.get("X015")
        if not rule_015:
            return findings

        if not dfm_analysis:
            findings.append(
                CrossDomainFinding(
                    finding_id="X015_NO_DFM_ANALYSIS",
                    project_id=project_id,
                    domain_a=ValidationDomain.DFM,
                    domain_b=ValidationDomain.PCB,
                    rule_id="X015",
                    status=CrossDomainStatus.UNKNOWN,
                    severity=CrossDomainSeverity.INFO,
                    engineering_claim=rule_015["engineering_claim"],
                    explanation="No DFM manufacturing analysis has been executed for this board. DFM readiness status unknown.",
                    source_classification=SourceClassification.UNKNOWN,
                )
            )
            return findings

        if not board:
            findings.append(
                CrossDomainFinding(
                    finding_id="X015_NO_BOARD",
                    project_id=project_id,
                    domain_a=ValidationDomain.DFM,
                    domain_b=ValidationDomain.PCB,
                    rule_id="X015",
                    status=CrossDomainStatus.UNKNOWN,
                    severity=CrossDomainSeverity.HIGH,
                    engineering_claim=rule_015["engineering_claim"],
                    explanation="PCB board model is missing. DFM revision consistency cannot be verified.",
                    source_classification=SourceClassification.UNKNOWN,
                )
            )
            return findings

        board_rev = int(getattr(board, "revision", getattr(board, "version", 1)))
        dfm_board_rev = int(getattr(dfm_analysis, "board_revision", 1))
        dfm_digest = str(getattr(dfm_analysis, "board_snapshot_digest", "") or "")

        # Check revision or digest mismatch
        is_stale = (board_rev != dfm_board_rev) or (current_board_digest and dfm_digest and dfm_digest != current_board_digest)

        if is_stale:
            findings.append(
                CrossDomainFinding(
                    finding_id=f"X015_STALE_DFM_{dfm_analysis.id}",
                    project_id=project_id,
                    domain_a=ValidationDomain.DFM,
                    domain_b=ValidationDomain.PCB,
                    affected_entity_ids=[str(dfm_analysis.id), str(board.id)],
                    rule_id="X015",
                    status=CrossDomainStatus.UNKNOWN,
                    severity=CrossDomainSeverity.HIGH,
                    engineering_claim=rule_015["engineering_claim"],
                    explanation=f"STALE DFM: Manufacturing analysis was performed on PCB revision {dfm_board_rev}, but current PCB is revision {board_rev}. New DFM analysis required.",
                    quantitative_values={"dfm_board_revision": dfm_board_rev, "current_board_revision": board_rev},
                    source_classification=SourceClassification.CALCULATED,
                )
            )
        else:
            findings.append(
                CrossDomainFinding(
                    finding_id=f"X015_PASS_{dfm_analysis.id}",
                    project_id=project_id,
                    domain_a=ValidationDomain.DFM,
                    domain_b=ValidationDomain.PCB,
                    affected_entity_ids=[str(dfm_analysis.id)],
                    rule_id="X015",
                    status=CrossDomainStatus.PASS,
                    severity=CrossDomainSeverity.INFO,
                    engineering_claim=rule_015["engineering_claim"],
                    explanation=f"DFM manufacturing analysis matches current PCB layout revision {board_rev}. (DFM_ANALYSIS != MANUFACTURER_ACCEPTANCE).",
                    source_classification=SourceClassification.CALCULATED,
                )
            )

        return findings
