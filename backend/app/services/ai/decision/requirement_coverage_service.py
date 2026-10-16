from typing import Any, Dict, List, Optional
from app.models.db.decision import EngineeringRequirement, EngineeringDecisionRecord


class RequirementCoverageService:
    """
    Deterministically computes requirement coverage across systems, subsystems,
    analyses, verification requirements, evidence, and decisions.

    Strict boundary: UNKNOWN != COVERED.
    Mere mention or link without verified evidence or decided status evaluates to PARTIALLY_COVERED or UNKNOWN.
    """

    @classmethod
    def evaluate_requirement_coverage(
        cls,
        requirements: List[EngineeringRequirement],
        decisions: List[EngineeringDecisionRecord],
        verification_requirements: Optional[List[Any]] = None,
        evidence_records: Optional[List[Any]] = None,
        analyses: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        verification_requirements = verification_requirements or []
        evidence_records = evidence_records or []
        analyses = analyses or []

        coverage_by_req: Dict[str, Dict[str, Any]] = {}
        counts = {
            "COVERED": 0,
            "PARTIALLY_COVERED": 0,
            "NOT_COVERED": 0,
            "UNKNOWN": 0,
        }

        # Index verification requirements by requirement_id / code
        v_req_map = {}
        for vr in verification_requirements:
            req_id = getattr(vr, "requirement_id", None) or getattr(vr, "system_requirement_id", None)
            if req_id:
                v_req_map.setdefault(req_id, []).append(vr)

        # Index evidence by requirement / verification
        ev_map = {}
        for ev in evidence_records:
            v_id = getattr(ev, "verification_requirement_id", None)
            if v_id:
                ev_map.setdefault(v_id, []).append(ev)

        # Index decisions by requirement references
        dec_map = {}
        for dec in decisions:
            ctx = getattr(dec, "decision_context", {}) or {}
            ref_reqs = ctx.get("requirements", [])
            for r_ref in ref_reqs:
                if isinstance(r_ref, str):
                    dec_map.setdefault(r_ref, []).append(dec)
                elif isinstance(r_ref, dict) and "id" in r_ref:
                    dec_map.setdefault(r_ref["id"], []).append(dec)

        for req in requirements:
            req_v_reqs = v_req_map.get(req.id, []) + v_req_map.get(req.requirement_key, [])
            req_decs = dec_map.get(req.id, []) + dec_map.get(req.requirement_key, [])

            # Check if any associated verification requirement is VERIFIED with physical evidence
            has_verified_evidence = False
            for vr in req_v_reqs:
                vr_id = getattr(vr, "id", None)
                v_evs = ev_map.get(vr_id, [])
                if any(getattr(e, "status", "") == "VERIFIED" for e in v_evs):
                    has_verified_evidence = True
                    break

            # Check decision status
            has_decided_decision = any(
                getattr(d, "status", "") in ["DECIDED", "IMPLEMENTED", "CLOSED"]
                for d in req_decs
            )

            # Determine status
            if req.status == "SATISFIED" and has_verified_evidence:
                status = "COVERED"
            elif has_verified_evidence or (has_decided_decision and len(req_v_reqs) > 0):
                status = "COVERED"
            elif len(req_v_reqs) > 0 or len(req_decs) > 0:
                status = "PARTIALLY_COVERED"
            elif req.status == "UNKNOWN":
                status = "UNKNOWN"
            else:
                status = "NOT_COVERED"

            counts[status] += 1
            coverage_by_req[req.id] = {
                "requirement_id": req.id,
                "requirement_key": req.requirement_key,
                "title": req.title,
                "category": req.category,
                "priority": req.priority,
                "coverage_status": status,
                "linked_verifications_count": len(req_v_reqs),
                "has_verified_evidence": has_verified_evidence,
                "linked_decisions_count": len(req_decs),
            }

        return {
            "total_requirements": len(requirements),
            "counts": counts,
            "requirements": coverage_by_req,
        }
