"""
Cross-Domain Orchestration Engine for Phase 3 Wave 8: Advanced Engineering Validation, Cross-Domain Consistency & System-Level Verification.
Coordinates multi-domain consistency evaluations across Schematic, PCB, BOM, Simulation, DFM,
Operating Limits, Power, Thermal, Requirements, and Verification domains.
STRICT INVARIANTS:
- AI ENGINEERING AUTHORITY = NONE
- AI DECISION AUTHORITY = NONE
- UNKNOWN != PASS
- Zero synthetic engineering scoring.
"""
from typing import Any, Optional
from datetime import datetime, timezone

from app.models.db.cross_domain import (
    CrossDomainSeverity,
    CrossDomainStatus,
    CrossDomainValidationStatus,
)
from app.models.schemas.cross_domain import (
    CrossDomainFinding,
    CrossDomainValidationResponse,
    CrossDomainValidationSummary,
)
from app.services.ai.cross_domain.rule_registry import CROSS_DOMAIN_RULES
from app.services.ai.cross_domain.snapshot import CrossDomainSnapshotEngine
from app.services.ai.cross_domain.schematic_pcb_consistency import SchematicPCBConsistencyEngine
from app.services.ai.cross_domain.bom_consistency import BOMCrossDomainConsistencyEngine
from app.services.ai.cross_domain.operating_limits_consistency import OperatingLimitsConsistencyEngine
from app.services.ai.cross_domain.power_thermal_consistency import PowerThermalConsistencyEngine
from app.services.ai.cross_domain.simulation_consistency import SimulationConsistencyEngine
from app.services.ai.cross_domain.requirements_consistency import RequirementsConsistencyEngine
from app.services.ai.cross_domain.dfm_staleness_consistency import DFMStalenessConsistencyEngine
from app.services.ai.cross_domain.verification_consistency import VerificationConsistencyEngine
from app.services.ai.cross_domain.completeness_consistency import CompletenessConsistencyEngine


class CrossDomainValidationEngine:
    """
    Orchestrates deterministic cross-domain validation evaluations across all engineering domains.
    """

    @staticmethod
    def run_cross_domain_validation(
        project_id: str,
        circuit: Optional[Any] = None,
        board: Optional[Any] = None,
        bom: Optional[Any] = None,
        simulation_job: Optional[Any] = None,
        simulation_result: Optional[Any] = None,
        dfm_analysis: Optional[Any] = None,
        current_board_digest: Optional[str] = None,
        analysis_results: Optional[list[Any]] = None,
        requirements: Optional[list[Any]] = None,
        verifications: Optional[list[Any]] = None,
        evidence_items: Optional[list[Any]] = None,
        sources: Optional[list[Any]] = None,
        dfm_rules: Optional[dict[str, Any]] = None,
    ) -> tuple[CrossDomainValidationSummary, list[CrossDomainFinding], str, dict[str, Any]]:
        all_findings: list[CrossDomainFinding] = []
        rules = CROSS_DOMAIN_RULES

        # 1. Schematic <-> PCB (X001, X002)
        all_findings.extend(SchematicPCBConsistencyEngine.evaluate(project_id, circuit, board, rules))

        # 2. BOM Cross-Domain (X003, X004, X005, X019)
        all_findings.extend(BOMCrossDomainConsistencyEngine.evaluate(project_id, circuit, board, bom, rules))

        # 3. Component Operating Limits & Absolute Maximum (X006, X007)
        all_findings.extend(OperatingLimitsConsistencyEngine.evaluate(project_id, circuit, analysis_results, rules))

        # 4. Power & Thermal Consistency (X008, X009, X010)
        all_findings.extend(PowerThermalConsistencyEngine.evaluate(project_id, circuit, board, rules))

        # 5. Simulation Staleness & Consistency (X011, X012)
        all_findings.extend(SimulationConsistencyEngine.evaluate(project_id, circuit, simulation_job, simulation_result, rules))

        # 6. Requirements & Design Constraints (X013, X014)
        all_findings.extend(RequirementsConsistencyEngine.evaluate(project_id, requirements, board, dfm_rules, rules))

        # 7. DFM Staleness & Revision Consistency (X015)
        all_findings.extend(DFMStalenessConsistencyEngine.evaluate(project_id, board, dfm_analysis, current_board_digest, rules))

        # 8. Verification & Authoritative Source Consistency (X016, X017, X018)
        all_findings.extend(VerificationConsistencyEngine.evaluate(project_id, circuit, verifications, evidence_items, sources, rules))

        # 9. Cross-Domain Completeness (X020)
        all_findings.extend(CompletenessConsistencyEngine.evaluate(
            project_id, circuit, board, bom, simulation_job, dfm_analysis, requirements, verifications, rules
        ))

        # Compute summary metrics (strictly categorical counts, NO composite scoring)
        pass_count = sum(1 for f in all_findings if f.status == CrossDomainStatus.PASS)
        fail_count = sum(1 for f in all_findings if f.status == CrossDomainStatus.FAIL)
        warning_count = sum(1 for f in all_findings if f.status == CrossDomainStatus.WARNING)
        unknown_count = sum(1 for f in all_findings if f.status == CrossDomainStatus.UNKNOWN)
        na_count = sum(1 for f in all_findings if f.status == CrossDomainStatus.NOT_APPLICABLE)

        severity_breakdown: dict[str, int] = {}
        for sev in CrossDomainSeverity:
            severity_breakdown[sev.value] = sum(1 for f in all_findings if f.severity == sev)

        domain_breakdown: dict[str, dict[str, int]] = {}
        for f in all_findings:
            key = f"{f.domain_a} <-> {f.domain_b}"
            if key not in domain_breakdown:
                domain_breakdown[key] = {"PASS": 0, "FAIL": 0, "WARNING": 0, "UNKNOWN": 0}
            if f.status.value in domain_breakdown[key]:
                domain_breakdown[key][f.status.value] += 1

        rule_results: dict[str, str] = {}
        # Priority order for aggregating multiple findings for same rule
        status_priority = {
            CrossDomainStatus.FAIL: 4,
            CrossDomainStatus.UNKNOWN: 3,
            CrossDomainStatus.WARNING: 2,
            CrossDomainStatus.PASS: 1,
            CrossDomainStatus.NOT_APPLICABLE: 0,
        }
        for f in all_findings:
            rid = f.rule_id
            curr_status = rule_results.get(rid)
            if not curr_status or status_priority.get(f.status, 0) > status_priority.get(CrossDomainStatus(curr_status), 0):
                rule_results[rid] = f.status.value

        summary = CrossDomainValidationSummary(
            total_findings=len(all_findings),
            pass_count=pass_count,
            fail_count=fail_count,
            warning_count=warning_count,
            unknown_count=unknown_count,
            not_applicable_count=na_count,
            severity_breakdown=severity_breakdown,
            domain_breakdown=domain_breakdown,
            rule_results=rule_results,
        )

        # Build canonical snapshot and compute digest
        snapshot_data = CrossDomainSnapshotEngine.serialize_domain_state(
            project_id=project_id,
            circuit=circuit,
            board=board,
            bom=bom,
            simulation_job=simulation_job,
            dfm_analysis=dfm_analysis,
            requirements=requirements,
            verifications=verifications,
            dfm_rules=dfm_rules,
        )
        digest = CrossDomainSnapshotEngine.compute_canonical_digest(snapshot_data)

        # Attach snapshot digest to findings
        now = datetime.now(timezone.utc)
        for f in all_findings:
            f.snapshot_digest = digest
            f.created_at = now

        domain_snapshots = {
            "circuit_version": getattr(circuit, "version", None) if circuit else None,
            "board_revision": getattr(board, "revision", None) if board else None,
            "bom_revision": getattr(bom, "revision", None) if bom else None,
            "simulation_id": getattr(simulation_job, "id", None) if simulation_job else None,
            "dfm_id": getattr(dfm_analysis, "id", None) if dfm_analysis else None,
        }

        return summary, all_findings, digest, domain_snapshots
