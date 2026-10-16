from typing import Any, Optional
from app.models.schemas.analysis import ExplainResponse


class EngineeringExplanationService:
    """
    AI Engineering Explanation boundary.
    Interprets verified deterministic calculation outputs, physical mechanisms, and rule findings.
    AI NEVER recalculates or overrides deterministic numbers.
    """

    def explain_analysis(
        self,
        circuit_id: str,
        analysis_data: dict[str, Any],
        finding_ids: Optional[list[str]] = None,
        component_ids: Optional[list[str]] = None,
        user_query: Optional[str] = None,
    ) -> ExplainResponse:
        calculations = analysis_data.get("calculations") or []
        findings = analysis_data.get("findings") or []
        unknowns = analysis_data.get("unknowns") or []

        # Filter relevant findings if specified
        relevant_findings = findings
        if finding_ids:
            relevant_findings = [f for f in findings if f.get("id") in finding_ids or f.get("rule_id") in finding_ids]
        elif component_ids:
            relevant_findings = [
                f for f in findings
                if any(cid in component_ids for cid in f.get("component_ids", []))
            ]

        # Collect verified calculation details
        calc_refs = []
        for c in calculations:
            name = c.get("name", "Calculation")
            formula = c.get("formula", "")
            res = c.get("result", {})
            calc_refs.append(f"{name} [{formula}] -> {res}")

        # Formulate physical mechanisms & tradeoffs
        mechanisms: list[str] = []
        tradeoffs: list[str] = []
        recommendations: list[str] = []

        explanation_lines = [
            f"Engineering Analysis Summary for Circuit {circuit_id}:",
            f"Deterministic evaluation status: {analysis_data.get('status')} (Confidence: {analysis_data.get('confidence')}).",
        ]

        if relevant_findings:
            explanation_lines.append(f"\nDetected {len(relevant_findings)} engineering issues requiring attention:")
            for f in relevant_findings:
                rule_id = f.get("rule_id", "RULE")
                title = f.get("title", "")
                desc = f.get("description", "")
                rec = f.get("recommended_action", "")
                explanation_lines.append(f"- [{rule_id}] {title}: {desc}")

                if rule_id == "R003":
                    mechanisms.append("Joule Heating / Resistor Over-dissipation: P = I^2 * R exceeds thermal rating.")
                    tradeoffs.append("Component Footprint vs Power Handling: Larger SMD (1206) or axial THT dissipates more power but consumes more PCB area.")
                elif rule_id in ["R004", "R005"]:
                    mechanisms.append("Linear Pass Element Overstress: Internal pass transistor exceeds breakdown voltage or safe operating area (SOA).")
                    tradeoffs.append("Linear LDO Simplicity vs Buck Converter Efficiency: Switching regulators offer >85% efficiency without heat sinking but introduce switching ripple.")
                elif rule_id == "R006":
                    mechanisms.append("Derating Violation: High utilization reduces component MTBF and thermal reliability.")
                    tradeoffs.append("Safety Factor Margin vs BOM Cost: 50% derating yields military/aerospace reliability at higher BOM cost.")
                elif rule_id == "R007":
                    mechanisms.append("High-Frequency Inductive Loop: Fast IC switching transients create power rail sag without local ceramic decoupling.")
                    tradeoffs.append("Decoupling Density: Adding 100nF X7R ceramic capacitor per VCC pin stabilizes rail but requires careful routing close to IC pins.")
                elif rule_id == "R008":
                    mechanisms.append("CMOS Gate Overvoltage: 5V signals on 3.3V logic gates cause ESD diode conduction and potential latch-up.")
                    tradeoffs.append("Level Shifting vs Dedicated Regulator: Direct level shifters protect logic without redesigning rail.")

                if rec and rec not in recommendations:
                    recommendations.append(rec)
        else:
            explanation_lines.append("\nNo critical engineering violations detected. Circuit conforms to standard derating and topological rules.")

        if unknowns:
            explanation_lines.append(f"\n{len(unknowns)} parameters remain unknown or partially specified:")
            for u in unknowns:
                explanation_lines.append(f"- {u.get('field')}: {u.get('reason')} (Impact: {u.get('impact')})")
            recommendations.append("Specify component values, package footprints, and load currents to enable full deterministic certification.")

        # Default trade-offs and mechanisms if empty
        if not mechanisms:
            mechanisms.append("DC steady-state operating point determined via Ohm's law and topological graph traversal.")
        if not tradeoffs:
            tradeoffs.append("Design simplicity vs operational safety margin.")
        if not recommendations:
            recommendations.append("Proceed with schematic layout or simulate dynamic response.")

        return ExplainResponse(
            circuit_id=circuit_id,
            explanation="\n".join(explanation_lines),
            identified_mechanisms=mechanisms,
            engineering_tradeoffs=tradeoffs,
            recommended_actions=recommendations,
            verified_calculations_used=calc_refs,
        )
