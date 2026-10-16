from typing import Any, Dict, List, Optional
from app.models.db.cognitive import ReasoningFindingType, ReasoningFindingSeverity


class RequirementReflectionService:
    """
    Evaluates system and circuit requirements under the 4-state model:
    SATISFIED, NOT_SATISFIED, UNKNOWN, NOT_EVALUATED.
    Strictly preserves the non-negotiable invariant: UNKNOWN != SATISFIED.
    """

    @classmethod
    def evaluate_requirements(
        cls,
        requirements: List[Dict[str, Any]],
        execution_results: List[Dict[str, Any]],
        traceability_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        # Map execution results by target requirement or property
        evaluated_props = set()
        violated_props = set()

        for res in execution_results:
            details = res.get("details", {})
            if isinstance(details, dict):
                evaluated_props.update(k.lower() for k in details.keys())
            violations = res.get("violations", [])
            for v in violations:
                if isinstance(v, dict):
                    violated_props.add(str(v.get("rule", "")).lower())
                    violated_props.add(str(v.get("property", "")).lower())

        for req in requirements:
            req_id = req.get("id") or req.get("name") or "REQ"
            req_name = req.get("name") or req.get("description") or str(req_id)
            target = str(req.get("target_property") or req.get("property") or req.get("name", "")).lower()

            # If requirement status is explicitly marked
            status = req.get("status")

            if status == "UNKNOWN" or (target and target not in evaluated_props and not status):
                findings.append({
                    "finding_type": ReasoningFindingType.REQUIREMENT_GAP.value,
                    "severity": ReasoningFindingSeverity.CRITICAL.value,
                    "title": f"Requirement Unverified / Unknown: {req_name}",
                    "description": (
                        f"Requirement '{req_name}' (ID: {req_id}) cannot be evaluated from available "
                        f"deterministic results. UNKNOWN != SATISFIED: explicit evaluation is mandatory."
                    ),
                    "affected_entity_type": "REQUIREMENT",
                    "affected_entity_id": str(req_id),
                    "evidence_references": [str(req_id)],
                    "deterministic_facts": {
                        "requirement_id": req_id,
                        "state": "UNKNOWN",
                        "target_property": target,
                    },
                    "recommended_remedy": f"Execute requirement coverage analysis targeting {req_name}.",
                    "follow_up_capability": "requirement_coverage_check",
                })
            elif status == "NOT_SATISFIED" or any(target in v for v in violated_props if target):
                findings.append({
                    "finding_type": ReasoningFindingType.REQUIREMENT_GAP.value,
                    "severity": ReasoningFindingSeverity.CRITICAL.value,
                    "title": f"Requirement NOT_SATISFIED: {req_name}",
                    "description": (
                        f"Deterministic execution verified that requirement '{req_name}' (ID: {req_id}) "
                        f"is NOT satisfied by the current circuit/system configuration."
                    ),
                    "affected_entity_type": "REQUIREMENT",
                    "affected_entity_id": str(req_id),
                    "evidence_references": [str(req_id)],
                    "deterministic_facts": {
                        "requirement_id": req_id,
                        "state": "NOT_SATISFIED",
                        "violations": list(violated_props),
                    },
                    "recommended_remedy": "Adjust system architecture or component selection to meet specification.",
                    "follow_up_capability": "operating_point_recalculation",
                })

        # Check Traceability Gaps
        if traceability_records is not None:
            untraced_reqs = [
                r for r in requirements
                if not any(t.get("requirement_id") == (r.get("id") or r.get("name")) for t in traceability_records)
            ]
            for r in untraced_reqs:
                r_id = r.get("id") or r.get("name")
                findings.append({
                    "finding_type": ReasoningFindingType.TRACEABILITY_GAP.value,
                    "severity": ReasoningFindingSeverity.WARNING.value,
                    "title": f"Traceability Gap: Requirement {r_id} lacks implementation link",
                    "description": f"Requirement {r_id} is not linked to any circuit component, system interface, or verification item.",
                    "affected_entity_type": "REQUIREMENT",
                    "affected_entity_id": str(r_id),
                    "evidence_references": [str(r_id)],
                    "deterministic_facts": {"requirement_id": r_id},
                    "recommended_remedy": "Establish formal requirement traceability link to architecture object.",
                    "follow_up_capability": "requirement_coverage_check",
                })

        return findings
