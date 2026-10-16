from typing import Any, Dict, List, Optional, Set
from app.models.db.cognitive import ReasoningFindingType, ReasoningFindingSeverity


class UnknownAnalysisService:
    """
    Consolidates, deduplicates, and classifies explicit engineering unknowns,
    missing datasheet parameters, and unverified assumptions.
    Strictly preserves the invariant: UNKNOWN != PASS, UNKNOWN != SATISFIED.
    """

    @classmethod
    def analyze_unknowns(
        cls,
        execution_unknowns: List[Dict[str, Any]],
        context_payload: Optional[Dict[str, Any]] = None,
        intent_missing_info: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        # 1. Unknowns reported by execution tasks
        for item in execution_unknowns or []:
            unknown_text = item.get("unknown") or item.get("description") or str(item)
            source = item.get("source") or "Deterministic Execution"
            ref_des = item.get("ref_des") or item.get("component")

            dedup_key = f"{source}:{unknown_text}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            # Classify severity: critical if it impacts electrical calculation
            is_critical = any(k in str(unknown_text).lower() for k in ["esr", "inductance", "thermal", "voltage", "current"])
            severity = ReasoningFindingSeverity.WARNING.value if not is_critical else ReasoningFindingSeverity.CRITICAL.value

            findings.append({
                "finding_type": ReasoningFindingType.UNRESOLVED_UNKNOWN.value,
                "severity": severity,
                "title": f"Unresolved Engineering Unknown: {unknown_text[:60]}",
                "description": (
                    f"Deterministic analysis encountered an uncharacterized parameter: '{unknown_text}'. "
                    f"This parameter cannot be assumed or fabricated; explicit measurement or datasheet data is required."
                ),
                "affected_entity_type": "CIRCUIT" if ref_des else "ANALYSIS",
                "affected_entity_id": ref_des,
                "evidence_references": [source],
                "deterministic_facts": {"raw_unknown": item, "source": source},
                "recommended_remedy": "Retrieve manufacturer datasheet or perform parameter characterization measurement.",
                "follow_up_capability": "knowledge_lookup",
            })

        # 2. Missing information recorded during intent resolution
        for item in intent_missing_info or []:
            field = item.get("field") or item.get("target") or "Parameter"
            reason = item.get("reason") or "Required for rigorous deterministic evaluation"
            dedup_key = f"intent_missing:{field}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            findings.append({
                "finding_type": ReasoningFindingType.MISSING_INFORMATION.value,
                "severity": ReasoningFindingSeverity.WARNING.value,
                "title": f"Missing Engineering Parameter: {field}",
                "description": f"Design analysis lacks parameter '{field}': {reason}.",
                "affected_entity_type": "REQUIREMENT",
                "affected_entity_id": None,
                "evidence_references": ["intent_packet"],
                "deterministic_facts": item,
                "recommended_remedy": f"Specify explicit engineering tolerance or boundary value for {field}.",
                "follow_up_capability": "knowledge_lookup",
            })

        # 3. Component level missing parameters in context payload
        if context_payload:
            components = context_payload.get("components", [])
            for c in components:
                ref_des = c.get("ref_des")
                if not ref_des:
                    continue

                # Check for uncharacterized capacitors/inductors (e.g. missing ESR)
                c_type = str(c.get("type", "")).upper()
                if "CAPACITOR" in c_type or ref_des.startswith("C"):
                    if not c.get("esr") and not c.get("parameters", {}).get("esr"):
                        key = f"esr:{ref_des}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            findings.append({
                                "finding_type": ReasoningFindingType.UNRESOLVED_UNKNOWN.value,
                                "severity": ReasoningFindingSeverity.WARNING.value,
                                "title": f"Missing Capacitor ESR: {ref_des}",
                                "description": (
                                    f"Capacitor {ref_des} lacks Equivalent Series Resistance (ESR) characterization. "
                                    f"Ripple voltage and transient stability calculations will be approximate."
                                ),
                                "affected_entity_type": "CIRCUIT",
                                "affected_entity_id": ref_des,
                                "evidence_references": [ref_des],
                                "deterministic_facts": {"ref_des": ref_des, "missing_parameter": "ESR"},
                                "recommended_remedy": f"Extract ESR vs Frequency curve from {ref_des} manufacturer datasheet.",
                                "follow_up_capability": "knowledge_lookup",
                            })

        return findings
