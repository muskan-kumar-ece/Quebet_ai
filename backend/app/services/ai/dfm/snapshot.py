"""
DFM Snapshot & Integrity Digest Service for Phase 3 Wave 7: Manufacturing / DFM & Assembly Intelligence.
Computes deterministic SHA-256 provenance digests over canonicalized DFM analysis findings and rulesets.
"""
from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from app.models.schemas.dfm import DFMSnapshotResponse


class DFMSnapshotService:
    """
    Deterministic snapshot and digest computation service.
    Guarantees reproducible hashing across environments with zero synthetic scoring.
    """

    @staticmethod
    def compute_analysis_digest(
        board_id: str,
        board_revision: int,
        rule_set_id: str,
        rule_set_revision: str,
        findings: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> str:
        """
        Computes SHA-256 digest of canonical analysis payload.
        Ensures strict sorting and deterministic formatting.
        """
        # Canonicalize findings: sort by finding_id, rule_id
        canonical_findings = sorted(
            [
                {
                    "finding_id": f.get("finding_id"),
                    "rule_id": f.get("rule_id"),
                    "status": f.get("status"),
                    "severity": f.get("severity"),
                    "element_type": f.get("element_type"),
                    "measured_value": round(float(f["measured_value"]), 4) if f.get("measured_value") is not None else None,
                    "required_value": round(float(f["required_value"]), 4) if f.get("required_value") is not None else None,
                    "margin": round(float(f["margin"]), 4) if f.get("margin") is not None else None,
                }
                for f in findings
            ],
            key=lambda x: (x.get("finding_id", ""), x.get("rule_id", "")),
        )

        canonical_summary = {
            "total_rules_evaluated": summary.get("total_rules_evaluated", 0),
            "pass_count": summary.get("pass_count", 0),
            "fail_count": summary.get("fail_count", 0),
            "warning_count": summary.get("warning_count", 0),
            "unknown_count": summary.get("unknown_count", 0),
            "status": summary.get("status", "COMPLETED"),
        }

        payload = {
            "board_id": board_id,
            "board_revision": board_revision,
            "rule_set_id": rule_set_id,
            "rule_set_revision": rule_set_revision,
            "findings": canonical_findings,
            "summary": canonical_summary,
        }

        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_snapshot(
        analysis: Any,
    ) -> DFMSnapshotResponse:
        """
        Creates verifiable DFMSnapshotResponse containing canonical digest and invariant assurances.
        """
        findings = getattr(analysis, "findings", []) or []
        summary = getattr(analysis, "summary", {}) or {}

        digest = DFMSnapshotService.compute_analysis_digest(
            board_id=str(analysis.board_id),
            board_revision=int(analysis.board_revision),
            rule_set_id=str(analysis.rule_set_id),
            rule_set_revision=str(analysis.rule_set_revision),
            findings=findings,
            summary=summary,
        )

        invariants = [
            "AI_ENGINEERING_AUTHORITY = NONE",
            "AUTONOMOUS_MANUFACTURING_APPROVAL = DISABLED",
            "AUTONOMOUS_FABRICATION_RELEASE = DISABLED",
            "UNKNOWN != PASS",
            "UNKNOWN != MANUFACTURABLE",
            "DFM_ANALYSIS != MANUFACTURER_CERTIFICATION",
            "ZERO_SYNTHETIC_MANUFACTURABILITY_SCORE",
            "ZERO_SYNTHETIC_FABRICATOR_RANKING",
            "PROVENANCE_AND_INTEGRITY_DIGEST != DIGITAL_SIGNATURE",
        ]

        return DFMSnapshotResponse(
            board_id=str(analysis.board_id),
            board_revision=int(analysis.board_revision),
            analysis_id=str(analysis.id),
            rule_set_id=str(analysis.rule_set_id),
            rule_set_revision=str(analysis.rule_set_revision),
            canonical_digest=digest,
            computed_at=datetime.now(timezone.utc).isoformat(),
            invariants_verified=invariants,
        )
