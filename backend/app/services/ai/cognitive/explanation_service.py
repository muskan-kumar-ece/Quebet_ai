from typing import Any, Dict, List, Optional
from app.models.db.cognitive import EngineeringTaskPlan


class EngineeringExplanationService:
    """
    Synthesizes natural language explanations strictly from authoritative deterministic results.
    Never alters, overrides, or recalculates engineering numbers.
    Explicitly labels AI interpretations and links them to underlying engine provenance.
    """

    @classmethod
    def generate_explanation(
        cls,
        plan: EngineeringTaskPlan,
        results: List[Dict[str, Any]],
        findings: List[Dict[str, Any]],
        unknowns: List[Dict[str, Any]],
        human_actions: List[str],
    ) -> str:
        lines: List[str] = [
            "### AI Engineering Interpretation (Informational Only)",
            f"Orchestrated plan execution for **{plan.project_id}** at **Base Revision {plan.base_revision}**.",
            "",
            "#### Deterministic Capabilities Executed:",
        ]

        for r in results:
            cap = r.get("capability", "unknown")
            task_desc = r.get("task", "")
            lines.append(f"- **{cap}**: {task_desc}")

        if findings:
            lines.append(f"\n#### Engineering Findings ({len(findings)}):")
            for f in findings:
                rule_id = f.get("rule_id", "FINDING")
                title = f.get("title", f.get("description", "Issue"))
                sev = f.get("severity", "MEDIUM")
                lines.append(f"- `[{sev}]` **{rule_id}**: {title}")
        else:
            lines.append("\n#### Engineering Findings:\n- No critical anomalies identified in the deterministic pass.")

        if unknowns:
            lines.append(f"\n#### Epistemological Boundary & Unknowns ({len(unknowns)}):")
            for u in unknowns:
                source = u.get("source", "analysis")
                desc = u.get("unknown", u.get("requirement_id", "Parameter unknown"))
                lines.append(f"- `[UNKNOWN != PASS]` ({source}): {desc}")
            lines.append("> *Note: UNKNOWN parameters are never assumed to be satisfied. Physical verification or explicit assumptions are required.*")

        if human_actions:
            lines.append("\n#### Human Engineering Actions Required:")
            for a in human_actions:
                lines.append(f"- ⚠️ {a}")
        else:
            lines.append("\n#### Human Engineering Actions:\n- Proceed with standard peer review.")

        lines.append(
            "\n---\n*Disclaimer: AI interpretations do not constitute physical verification, regulatory approval, or authoritative decisions. Decision authority belongs solely to the authorized human engineer.*"
        )
        return "\n".join(lines)
