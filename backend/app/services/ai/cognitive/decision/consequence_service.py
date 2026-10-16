from typing import Any, Dict, List, Optional


class DecisionConsequenceService:
    """
    Identifies deterministic consequences of adopting candidate engineering alternatives.
    Surfaces downstream impacts across architecture, power trees, interfaces,
    verification obligations, and evidence validity.
    """

    CONSEQUENCE_TYPES = [
        "COMPONENT_CHANGE",
        "POWER_CHANGE",
        "THERMAL_CHANGE",
        "INTERFACE_CHANGE",
        "DEPENDENCY_CHANGE",
        "REQUIREMENT_IMPACT",
        "VERIFICATION_IMPACT",
        "EVIDENCE_INVALIDATION",
        "TRACEABILITY_IMPACT",
        "SYSTEM_REVISION_IMPACT",
    ]

    @classmethod
    def evaluate_consequences(
        cls,
        alternatives: List[Dict[str, Any]],
        current_revision: int = 1,
    ) -> Dict[str, List[Dict[str, Any]]]:
        consequences_by_alt: Dict[str, List[Dict[str, Any]]] = {}

        for alt in alternatives:
            alt_id = str(alt.get("id") or alt.get("alternative_id") or "ALT")
            consequences: List[Dict[str, Any]] = []

            # 1. Component Changes & BOM Impact
            comps = alt.get("affected_components", [])
            if comps:
                consequences.append({
                    "type": "COMPONENT_CHANGE",
                    "severity": "MEDIUM",
                    "description": f"Modifies or substitutes {len(comps)} component(s): {', '.join(comps)}.",
                    "affected_entities": comps,
                })
                consequences.append({
                    "type": "SYSTEM_REVISION_IMPACT",
                    "severity": "HIGH",
                    "description": f"Adoption will increment baseline revision from {current_revision} to {current_revision + 1}.",
                    "affected_entities": [f"Rev {current_revision + 1}"],
                })
                consequences.append({
                    "type": "EVIDENCE_INVALIDATION",
                    "severity": "HIGH",
                    "description": f"Hardware measurements collected on revision {current_revision} will be marked STALE.",
                    "affected_entities": comps,
                })

            # 2. Interface Changes
            interfaces = alt.get("affected_interfaces", [])
            if interfaces:
                consequences.append({
                    "type": "INTERFACE_CHANGE",
                    "severity": "HIGH",
                    "description": f"Modifies interface contract across {len(interfaces)} boundary interface(s).",
                    "affected_entities": interfaces,
                })

            # 3. Power & Thermal Changes
            eng_eff = alt.get("engineering_effects", {})
            if "power_change_w" in eng_eff or "power_dissipation_w" in eng_eff:
                pwr = eng_eff.get("power_change_w") or eng_eff.get("power_dissipation_w")
                consequences.append({
                    "type": "POWER_CHANGE",
                    "severity": "MEDIUM",
                    "description": f"Power budget change: {pwr}.",
                    "affected_entities": ["power_domain"],
                })

            if "thermal_change_c" in eng_eff or "operating_temp" in eng_eff:
                thm = eng_eff.get("thermal_change_c") or eng_eff.get("operating_temp")
                consequences.append({
                    "type": "THERMAL_CHANGE",
                    "severity": "MEDIUM",
                    "description": f"Thermal profile impact: {thm}.",
                    "affected_entities": ["thermal_domain"],
                })

            # 4. Verification Impact
            ver_gaps = alt.get("verification_gaps", [])
            if ver_gaps:
                consequences.append({
                    "type": "VERIFICATION_IMPACT",
                    "severity": "HIGH",
                    "description": f"Creates {len(ver_gaps)} new verification obligation(s) requiring physical test evidence.",
                    "affected_entities": ver_gaps,
                })

            consequences_by_alt[alt_id] = consequences

        return consequences_by_alt
