from typing import Any, Dict, List, Optional
from app.models.db.cognitive import ReasoningFindingType, ReasoningFindingSeverity


class VerificationReflectionService:
    """
    Audits verification plans, physical test obligations, and empirical evidence.
    Strictly preserves the non-negotiable invariants:
    - CALCULATED != PHYSICALLY VERIFIED
    - ANALYSIS != PHYSICAL EVIDENCE
    - AI REFLECTION != ENGINEERING VERIFICATION
    """

    @classmethod
    def audit_verification(
        cls,
        verification_impacts: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
        evidence_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        # 1. Audit verification items claimed from simulation vs physical
        for v in verification_impacts or []:
            v_id = v.get("verification_id") or v.get("id") or "V-REQ"
            name = v.get("name") or v.get("title") or str(v_id)
            method = str(v.get("method", "")).upper()
            status = str(v.get("status", "")).upper()

            # Invariant check: If simulation claims to satisfy a PHYSICAL_TEST requirement
            if method in ("SIMULATION", "CALCULATION", "ANALYSIS") and status in ("VERIFIED", "PASSED", "SATISFIED"):
                # Check if requirement specifically demands physical / laboratory evidence
                target_req_type = str(v.get("requirement_type", "")).upper()
                if "PHYSICAL" in target_req_type or "ENVIRONMENTAL" in target_req_type or "EMC" in target_req_type or "HARDWARE" in target_req_type:
                    findings.append({
                        "finding_type": ReasoningFindingType.VERIFICATION_GAP.value,
                        "severity": ReasoningFindingSeverity.CRITICAL.value,
                        "title": f"Invalid Verification Claim: {name} (CALCULATED != PHYSICALLY VERIFIED)",
                        "description": (
                            f"Verification obligation '{name}' requires physical hardware measurement, but has only "
                            f"been evaluated via {method}. Under QUEBET engineering invariants, calculated or simulated "
                            f"results cannot substitute for physical verification evidence."
                        ),
                        "affected_entity_type": "VERIFICATION",
                        "affected_entity_id": str(v_id),
                        "evidence_references": [str(v_id)],
                        "deterministic_facts": {
                            "verification_id": v_id,
                            "claimed_method": method,
                            "required_type": target_req_type,
                        },
                        "recommended_remedy": "Schedule physical bench test and upload calibrated measurement evidence.",
                        "follow_up_capability": "verification_planning",
                    })

            # Missing or unexecuted test points
            if status in ("PENDING", "UNEXECUTED", "BLOCKED"):
                findings.append({
                    "finding_type": ReasoningFindingType.VERIFICATION_GAP.value,
                    "severity": ReasoningFindingSeverity.WARNING.value,
                    "title": f"Unexecuted Verification Obligation: {name}",
                    "description": f"Verification requirement '{name}' has not been executed (Status: {status}).",
                    "affected_entity_type": "VERIFICATION",
                    "affected_entity_id": str(v_id),
                    "evidence_references": [str(v_id)],
                    "deterministic_facts": {"verification_id": v_id, "status": status},
                    "recommended_remedy": "Execute verification test procedure prior to design sign-off.",
                    "follow_up_capability": "verification_planning",
                })

        # 2. Check for critical requirements missing any verification mapping
        verified_req_ids = {
            str(v.get("requirement_id") or v.get("req_id"))
            for v in (verification_impacts or [])
            if v.get("requirement_id") or v.get("req_id")
        }

        for r in requirements:
            r_id = str(r.get("id") or r.get("name"))
            is_critical = str(r.get("criticality", "")).upper() == "CRITICAL" or str(r.get("level", "")).upper() == "HIGH"
            if is_critical and r_id not in verified_req_ids:
                findings.append({
                    "finding_type": ReasoningFindingType.VERIFICATION_GAP.value,
                    "severity": ReasoningFindingSeverity.CRITICAL.value,
                    "title": f"Missing Verification Plan for Critical Requirement: {r_id}",
                    "description": (
                        f"Critical requirement '{r.get('name', r_id)}' lacks an associated verification requirement "
                        f"or test procedure."
                    ),
                    "affected_entity_type": "REQUIREMENT",
                    "affected_entity_id": r_id,
                    "evidence_references": [r_id],
                    "deterministic_facts": {"requirement_id": r_id, "criticality": "CRITICAL"},
                    "recommended_remedy": f"Create formal verification plan for requirement {r_id}.",
                    "follow_up_capability": "verification_planning",
                })

        return findings
