from typing import Any, Dict, List, Optional


class EngineeringTradeoffService:
    """
    Identifies and articulates explicit engineering trade-offs between design alternatives.
    CRITICAL SAFETY PRINCIPLE:
    The service exposes trade-offs objectively along physical and engineering dimensions.
    It does NOT resolve trade-offs, does NOT score them, and does NOT declare a winning choice.
    """

    @classmethod
    def analyze_tradeoffs(
        cls,
        alternatives: List[Dict[str, Any]],
        comparison_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tradeoffs_by_alternative: Dict[str, Dict[str, List[str]]] = {}
        pairwise_tradeoffs: List[Dict[str, Any]] = []

        # 1. Extract advantages & disadvantages per alternative
        for alt in alternatives:
            alt_id = str(alt.get("id") or alt.get("alternative_id") or "ALT")
            eng_eff = alt.get("engineering_effects", {})
            req_eff = alt.get("requirement_evaluations", {})
            findings = alt.get("engineering_findings", [])
            unknowns = alt.get("unknowns", [])
            ver_gaps = alt.get("verification_gaps", [])

            advantages: List[str] = []
            disadvantages: List[str] = []

            # Pre-populated tradeoffs if available
            explicit_tradeoffs = alt.get("tradeoffs", {})
            if isinstance(explicit_tradeoffs, dict):
                advantages.extend(explicit_tradeoffs.get("advantages", []))
                disadvantages.extend(explicit_tradeoffs.get("disadvantages", []))

            # Derived from engineering facts
            if alt.get("affected_components"):
                if len(alt.get("affected_components")) == 0:
                    advantages.append("No component substitutions or BOM modifications required.")
                else:
                    disadvantages.append(
                        f"Requires modification to {len(alt.get('affected_components'))} component(s): {', '.join(alt.get('affected_components')[:3])}."
                    )

            if alt.get("affected_interfaces"):
                disadvantages.append(
                    f"Modifies {len(alt.get('affected_interfaces'))} system interface contract(s)."
                )

            if len(unknowns) > 0:
                disadvantages.append(f"Carries {len(unknowns)} unresolved engineering unknown(s).")
            else:
                advantages.append("No unresolved component unknowns or uncharacterized parameters.")

            if len(ver_gaps) > 0:
                disadvantages.append(f"Requires execution of {len(ver_gaps)} additional physical verification obligation(s).")

            if len(findings) > 0:
                critical_count = sum(1 for f in findings if isinstance(f, dict) and f.get("severity") == "CRITICAL")
                if critical_count > 0:
                    disadvantages.append(f"Contains {critical_count} critical engineering finding(s) or constraint violation(s).")

            # Deduplicate
            tradeoffs_by_alternative[alt_id] = {
                "advantages": list(dict.fromkeys(advantages)),
                "disadvantages": list(dict.fromkeys(disadvantages)),
            }

        # 2. Pairwise dimension comparison (e.g. Alt A vs Alt B)
        if len(alternatives) >= 2:
            alt_a = alternatives[0]
            alt_b = alternatives[1]
            alt_a_id = str(alt_a.get("id") or alt_a.get("alternative_id") or "ALT-A")
            alt_b_id = str(alt_b.get("id") or alt_b.get("alternative_id") or "ALT-B")

            pairwise_tradeoffs.append({
                "dimension": "Topological & BOM Complexity",
                "alternative_a_id": alt_a_id,
                "alternative_b_id": alt_b_id,
                "comparison": (
                    f"{alt_a.get('name', alt_a_id)} impacts {len(alt_a.get('affected_components', []))} component(s) vs "
                    f"{alt_b.get('name', alt_b_id)} impacting {len(alt_b.get('affected_components', []))} component(s)."
                ),
            })
            pairwise_tradeoffs.append({
                "dimension": "Verification & Epistemic Uncertainty",
                "alternative_a_id": alt_a_id,
                "alternative_b_id": alt_b_id,
                "comparison": (
                    f"{alt_a.get('name', alt_a_id)} has {len(alt_a.get('unknowns', []))} unknown(s) and {len(alt_a.get('verification_gaps', []))} verification gap(s) vs "
                    f"{alt_b.get('name', alt_b_id)} with {len(alt_b.get('unknowns', []))} unknown(s) and {len(alt_b.get('verification_gaps', []))} verification gap(s)."
                ),
            })

        return {
            "tradeoffs_by_alternative": tradeoffs_by_alternative,
            "pairwise_tradeoffs": pairwise_tradeoffs,
        }
