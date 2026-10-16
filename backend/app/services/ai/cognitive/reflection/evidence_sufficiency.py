from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from app.models.db.cognitive import ReasoningFindingType, ReasoningFindingSeverity


class EvidenceSufficiencyEngine:
    """
    Evaluates currency, calibration, and environmental relevance of empirical evidence.
    Strictly preserves the non-negotiable invariant:
    - ANALYSIS != PHYSICAL EVIDENCE
    - Stale evidence from prior hardware revisions must not be silently accepted.
    """

    @classmethod
    def evaluate_evidence(
        cls,
        evidence_items: List[Dict[str, Any]],
        current_revision: int,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        for ev in evidence_items or []:
            ev_id = ev.get("id") or ev.get("evidence_id") or "EV"
            name = ev.get("name") or ev.get("title") or str(ev_id)
            ev_rev = ev.get("revision") or ev.get("base_revision")

            # 1. Revision Staleness Check
            if ev_rev is not None and int(ev_rev) < int(current_revision):
                findings.append({
                    "finding_type": ReasoningFindingType.INSUFFICIENT_EVIDENCE.value,
                    "severity": ReasoningFindingSeverity.WARNING.value,
                    "title": f"Stale Evidence Record: {name} (Rev {ev_rev} vs Current {current_revision})",
                    "description": (
                        f"Evidence '{name}' was collected on hardware revision {ev_rev}, but the current "
                        f"system baseline is at revision {current_revision}. Circuit topology or component "
                        f"changes may invalidate this evidence."
                    ),
                    "affected_entity_type": "EVIDENCE",
                    "affected_entity_id": str(ev_id),
                    "evidence_references": [str(ev_id)],
                    "deterministic_facts": {
                        "evidence_id": ev_id,
                        "evidence_revision": ev_rev,
                        "current_revision": current_revision,
                    },
                    "recommended_remedy": f"Re-run verification test on current revision {current_revision} hardware.",
                    "follow_up_capability": "verification_planning",
                })

            # 2. Calibration Validity Check
            cal_status = str(ev.get("instrument_calibration_status", "")).upper()
            cal_expiry = ev.get("instrument_calibration_expiry")
            is_expired = False
            if cal_expiry:
                try:
                    exp_dt = datetime.fromisoformat(str(cal_expiry).replace("Z", "+00:00"))
                    if exp_dt < datetime.now(timezone.utc):
                        is_expired = True
                except Exception:
                    pass

            if cal_status in ("EXPIRED", "UNCALIBRATED") or is_expired:
                findings.append({
                    "finding_type": ReasoningFindingType.INSUFFICIENT_EVIDENCE.value,
                    "severity": ReasoningFindingSeverity.CRITICAL.value,
                    "title": f"Uncalibrated Test Equipment Evidence: {name}",
                    "description": (
                        f"Evidence '{name}' was captured using test instrumentation whose calibration status is "
                        f"'{cal_status or 'EXPIRED'}'. Measurements are not admissible for certified design sign-off."
                    ),
                    "affected_entity_type": "EVIDENCE",
                    "affected_entity_id": str(ev_id),
                    "evidence_references": [str(ev_id)],
                    "deterministic_facts": {
                        "evidence_id": ev_id,
                        "instrument": ev.get("instrument"),
                        "calibration_expiry": cal_expiry,
                    },
                    "recommended_remedy": "Recalibrate test bench instrumentation and repeat verification measurement.",
                    "follow_up_capability": "verification_planning",
                })

            # 3. Simulated Data Misrepresented as Physical Evidence
            is_sim = ev.get("is_simulation", False) or str(ev.get("evidence_type", "")).upper() in ("SIMULATION", "SPICE")
            is_claimed_physical = str(ev.get("category", "")).upper() == "PHYSICAL_LAB_MEASUREMENT"
            if is_sim and is_claimed_physical:
                findings.append({
                    "finding_type": ReasoningFindingType.INSUFFICIENT_EVIDENCE.value,
                    "severity": ReasoningFindingSeverity.CRITICAL.value,
                    "title": f"Evidence Type Contradiction: {name} (ANALYSIS != PHYSICAL EVIDENCE)",
                    "description": (
                        f"Evidence '{name}' is marked as physical lab measurement but source is simulation/SPICE data. "
                        f"Under QUEBET engineering invariants, simulated data cannot be classified as physical empirical evidence."
                    ),
                    "affected_entity_type": "EVIDENCE",
                    "affected_entity_id": str(ev_id),
                    "evidence_references": [str(ev_id)],
                    "deterministic_facts": {"evidence_id": ev_id, "evidence_type": ev.get("evidence_type")},
                    "recommended_remedy": "Reclassify evidence as SIMULATION and capture actual lab measurements.",
                    "follow_up_capability": "verification_planning",
                })

        return findings
