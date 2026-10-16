from typing import Any
from app.models.schemas.design import (
    ComparisonMatrixRow,
    ConstraintStatus,
    DesignComparisonResponse,
    EngineeringDesignAlternative,
)


class DesignComparisonService:
    """
    Deterministic Engineering Design Comparison Engine.
    Evaluates baseline circuit metrics against candidate alternatives across measurable dimensions.
    Produces transparent engineering evidence without composite scores, top candidates, or automatic ranking.
    """

    def compare_alternatives(
        self,
        circuit_dict: dict[str, Any],
        baseline_analysis: dict[str, Any],
        alternatives: list[EngineeringDesignAlternative] | list[dict[str, Any]],
    ) -> DesignComparisonResponse:
        base_components = circuit_dict.get("components", [])
        base_findings = baseline_analysis.get("findings", [])
        base_calculations = baseline_analysis.get("calculations", [])
        base_unknowns = baseline_analysis.get("unknowns", [])

        # Extract baseline metrics
        base_critical = len([f for f in base_findings if f.get("severity") == "CRITICAL"])
        base_warnings = len([f for f in base_findings if f.get("severity") == "WARNING"])
        base_total_p = sum(
            c.get("result", {}).get("power_w", 0.0) or c.get("result", {}).get("power_dissipated_w", 0.0)
            for c in base_calculations
            if c.get("category") in ["OHMS_LAW", "REGULATOR", "POWER_DISSIPATION"]
        )

        base_worst_util = 0.0
        for c in base_calculations:
            if c.get("category") == "MARGIN":
                u = c.get("result", {}).get("utilization_pct", 0.0)
                if u > base_worst_util:
                    base_worst_util = u

        baseline_metrics = {
            "critical_findings": base_critical,
            "warning_findings": base_warnings,
            "total_findings": len(base_findings),
            "unknowns_count": len(base_unknowns),
            "total_power_w": round(base_total_p, 4) if base_total_p else None,
            "worst_utilization_pct": round(base_worst_util, 1),
            "component_count": len(base_components),
        }

        comparison_matrix: list[ComparisonMatrixRow] = []
        comparison_table: list[dict[str, Any]] = []
        alt_dicts: list[dict[str, Any]] = []

        for alt in alternatives:
            if isinstance(alt, EngineeringDesignAlternative):
                alt_data = alt.model_dump()
            else:
                alt_data = alt

            after_an = alt_data.get("after_analysis") or {}
            after_findings = after_an.get("findings", [])
            after_calcs = after_an.get("calculations", [])
            after_unknowns = after_an.get("unknowns", [])

            after_critical = len([f for f in after_findings if f.get("severity") == "CRITICAL"])
            after_warnings = len([f for f in after_findings if f.get("severity") == "WARNING"])
            after_total_p = sum(
                c.get("result", {}).get("power_w", 0.0) or c.get("result", {}).get("power_dissipated_w", 0.0)
                for c in after_calcs
                if c.get("category") in ["OHMS_LAW", "REGULATOR", "POWER_DISSIPATION"]
            )

            after_worst_util = 0.0
            for c in after_calcs:
                if c.get("category") == "MARGIN":
                    u = c.get("result", {}).get("utilization_pct", 0.0)
                    if u > after_worst_util:
                        after_worst_util = u

            constraints = alt_data.get("constraint_results", [])
            hard_constraints = [c for c in constraints if c.get("hard_or_soft") == "HARD"]
            soft_constraints = [c for c in constraints if c.get("hard_or_soft") == "SOFT"]

            if any(c.get("status") == ConstraintStatus.FAIL.value for c in hard_constraints):
                hard_status = ConstraintStatus.FAIL.value
            elif any(c.get("status") == ConstraintStatus.UNKNOWN.value for c in hard_constraints):
                hard_status = ConstraintStatus.UNKNOWN.value
            else:
                hard_status = ConstraintStatus.PASS.value

            soft_sat = sum(1 for c in soft_constraints if c.get("status") == ConstraintStatus.SATISFIED.value)
            soft_total = len(soft_constraints)
            soft_summary_str = f"{soft_sat}/{soft_total} SATISFIED" if soft_total > 0 else "N/A"

            power_delta = round(after_total_p - base_total_p, 4) if (base_total_p or after_total_p) else None
            worst_margin = round(100.0 - after_worst_util, 1) if after_worst_util else None

            resolved = alt_data.get("findings_resolved", [])
            introduced = alt_data.get("findings_introduced", [])
            remaining = alt_data.get("remaining_findings", [])

            struct_fx = alt_data.get("structural_effects") or {}
            comp_delta = struct_fx.get("component_count_delta", 0)

            # Determine strategy from candidate_provenance or title
            meta = alt_data.get("candidate_provenance") or {}
            strategy = meta.get("generation_strategy") or "ENGINEERING_MODIFICATION"

            matrix_row = ComparisonMatrixRow(
                alternative_id=alt_data.get("alternative_id", ""),
                title=alt_data.get("title", ""),
                strategy=strategy,
                hard_constraints=hard_status,
                soft_constraints=soft_summary_str,
                findings_resolved_count=len(resolved),
                findings_introduced_count=len(introduced),
                remaining_findings_count=len(remaining),
                resolved_finding_ids=resolved,
                introduced_finding_ids=introduced,
                power_delta_w=power_delta,
                worst_margin=worst_margin,
                component_count_delta=comp_delta,
                footprint=alt_data.get("footprint", "UNKNOWN"),
                cost=alt_data.get("cost", "UNKNOWN"),
                confidence=alt_data.get("confidence", "HIGH"),
                tradeoffs=alt_data.get("tradeoffs", []),
            )
            comparison_matrix.append(matrix_row)

            # Legacy table representation without scores
            row_dict = {
                "alternative_id": alt_data.get("alternative_id"),
                "title": alt_data.get("title"),
                "status": alt_data.get("status"),
                "confidence": alt_data.get("confidence"),
                "critical_delta": after_critical - base_critical,
                "warnings_delta": after_warnings - base_warnings,
                "unknowns_delta": len(after_unknowns) - len(base_unknowns),
                "power_delta_w": power_delta,
                "worst_utilization_pct": round(after_worst_util, 1),
                "hard_constraints": hard_status,
                "soft_constraints": soft_summary_str,
                "findings_resolved": resolved,
                "findings_introduced": introduced,
                "remaining_findings": remaining,
                "component_count_delta": comp_delta,
                "footprint": alt_data.get("footprint", "UNKNOWN"),
                "cost": alt_data.get("cost", "UNKNOWN"),
            }
            comparison_table.append(row_dict)
            alt_dicts.append(alt_data)

        return DesignComparisonResponse(
            circuit_id=circuit_dict.get("id", ""),
            base_revision=circuit_dict.get("version", 1),
            baseline_metrics=baseline_metrics,
            alternatives=alt_dicts,
            comparison_table=comparison_table,
            comparison_matrix=comparison_matrix,
        )
