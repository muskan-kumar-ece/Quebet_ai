from typing import Any, Dict, List, Optional


class RequirementChangeImpactService:
    """
    Evaluates cascading change impact across subsystems, interfaces, analyses,
    scenarios, candidates, proposals, verification requirements, and decisions
    when an engineering requirement is modified or superseded.
    """

    @classmethod
    def calculate_impact(
        cls,
        changed_requirement_id: str,
        system_id: str,
        subsystems: List[Any],
        interfaces: List[Any],
        analyses: List[Any],
        decisions: List[Any],
        candidates: Optional[List[Any]] = None,
        verification_requirements: Optional[List[Any]] = None,
    ) -> Dict[str, Any]:
        candidates = candidates or []
        verification_requirements = verification_requirements or []

        affected_subsystems = []
        affected_interfaces = []
        affected_analyses = []
        affected_decisions = []
        affected_candidates = []
        affected_verifications = []

        # 1. Subsystems affected (matching category or explicitly referenced)
        for sub in subsystems:
            sub_id = getattr(sub, "id", None)
            meta = getattr(sub, "metadata_", {}) or {}
            ref_reqs = meta.get("linked_requirements", [])
            if changed_requirement_id in ref_reqs:
                affected_subsystems.append(sub_id)

        # 2. Interfaces affected
        for iface in interfaces:
            iface_id = getattr(iface, "id", None)
            meta = getattr(iface, "metadata_", {}) or {}
            ref_reqs = meta.get("linked_requirements", [])
            if changed_requirement_id in ref_reqs:
                affected_interfaces.append(iface_id)

        # 3. Decisions referencing this requirement
        for dec in decisions:
            dec_id = getattr(dec, "id", None)
            ctx = getattr(dec, "decision_context", {}) or {}
            ref_reqs = ctx.get("requirements", [])
            matched = False
            for r_ref in ref_reqs:
                if (isinstance(r_ref, str) and r_ref == changed_requirement_id) or (
                    isinstance(r_ref, dict) and r_ref.get("id") == changed_requirement_id
                ):
                    matched = True
                    break
            if matched:
                affected_decisions.append({
                    "decision_id": dec_id,
                    "title": getattr(dec, "title", "Untitled Decision"),
                    "impact": "STALE",
                    "action_required": "Review and re-evaluate alternatives against updated requirement",
                })

        # 4. Candidates affected
        for cand in candidates:
            cand_id = getattr(cand, "id", None)
            affected_candidates.append({
                "candidate_id": cand_id,
                "impact": "REVIEW_REQUIRED",
            })

        # 5. Analyses invalidated
        for an in analyses:
            an_id = getattr(an, "id", None)
            affected_analyses.append(an_id)

        # 6. Verification requirements affected
        for vr in verification_requirements:
            vr_id = getattr(vr, "id", None)
            req_id = getattr(vr, "requirement_id", None) or getattr(vr, "system_requirement_id", None)
            if req_id == changed_requirement_id:
                affected_verifications.append({
                    "verification_requirement_id": vr_id,
                    "impact": "SUPERSEDED_OR_STALE",
                })

        return {
            "changed_requirement_id": changed_requirement_id,
            "system_id": system_id,
            "affected_subsystems": affected_subsystems,
            "affected_interfaces": affected_interfaces,
            "affected_analyses_count": len(affected_analyses),
            "affected_analyses": affected_analyses,
            "affected_decisions_count": len(affected_decisions),
            "affected_decisions": affected_decisions,
            "affected_candidates_count": len(affected_candidates),
            "affected_candidates": affected_candidates,
            "affected_verifications_count": len(affected_verifications),
            "affected_verifications": affected_verifications,
            "summary": (
                f"Requirement change directly affects {len(affected_decisions)} decisions, "
                f"{len(affected_verifications)} verifications, and invalidates {len(affected_analyses)} system analyses."
            ),
        }
