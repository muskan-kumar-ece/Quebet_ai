from typing import Any, Dict, List, Optional


class ScenarioComparisonService:
    """
    Computes transparent engineering deltas between a Baseline Scenario and an Alternative Scenario.
    Strictly prohibits composite health/risk scores or synthetic winner tags.
    """

    def compare_scenarios(
        self,
        baseline_result: Dict[str, Any],
        alternative_result: Dict[str, Any],
        baseline_name: str = "Baseline",
        alternative_name: str = "Alternative",
    ) -> Dict[str, Any]:
        # 1. Findings differential
        base_findings = baseline_result.get("findings", [])
        alt_findings = alternative_result.get("findings", [])
        base_titles = {f.get("title") for f in base_findings}
        alt_titles = {f.get("title") for f in alt_findings}

        introduced_findings = [f for f in alt_findings if f.get("title") not in base_titles]
        resolved_findings = [f for f in base_findings if f.get("title") not in alt_titles]

        # 2. Power & Current Deltas
        base_power = baseline_result.get("power_results", {})
        alt_power = alternative_result.get("power_results", {})
        base_domains = {d.get("name"): d for d in base_power.get("domains", [])}
        alt_domains = {d.get("name"): d for d in alt_power.get("domains", [])}

        power_deltas = {}
        for name, alt_d in alt_domains.items():
            base_d = base_domains.get(name)
            alt_load = alt_d.get("total_draw_a", 0.0)
            base_load = base_d.get("total_draw_a", 0.0) if base_d else 0.0
            power_deltas[name] = {
                "base_load_a": base_load,
                "alt_load_a": alt_load,
                "delta_a": round(alt_load - base_load, 4),
            }

        # 3. Failure Propagation Differential
        base_failures = baseline_result.get("failure_results", {})
        alt_failures = alternative_result.get("failure_results", {})

        base_affected_subs = set()
        for f in base_failures.values():
            base_affected_subs.update(f.get("downstream_affected_subsystems", []))

        alt_affected_subs = set()
        for f in alt_failures.values():
            alt_affected_subs.update(f.get("downstream_affected_subsystems", []))

        failure_changes = {
            "newly_affected_subsystems": list(alt_affected_subs - base_affected_subs),
            "isolated_or_protected_subsystems": list(base_affected_subs - alt_affected_subs),
        }

        # 4. Unknowns Differential
        base_unknowns = set(baseline_result.get("unknowns", []))
        alt_unknowns = set(alternative_result.get("unknowns", []))
        new_unknowns = list(alt_unknowns - base_unknowns)
        resolved_unknowns = list(base_unknowns - alt_unknowns)

        # 5. Requirement Changes
        base_reqs = {r.get("code"): r.get("scenario_status") for r in baseline_result.get("requirement_results", [])}
        alt_reqs = {r.get("code"): r.get("scenario_status") for r in alternative_result.get("requirement_results", [])}
        req_changes = []
        for code, alt_st in alt_reqs.items():
            base_st = base_reqs.get(code, "UNKNOWN")
            if base_st != alt_st:
                req_changes.append({"code": code, "from_status": base_st, "to_status": alt_st})

        summary = (
            f"Comparison of '{alternative_name}' against baseline '{baseline_name}': "
            f"{len(resolved_findings)} findings resolved, {len(introduced_findings)} findings introduced, "
            f"{len(failure_changes['isolated_or_protected_subsystems'])} subsystems protected from failure, "
            f"{len(new_unknowns)} new unknowns identified."
        )

        return {
            "baseline_scenario_id": baseline_result.get("scenario_id", ""),
            "alternative_scenario_id": alternative_result.get("scenario_id", ""),
            "power_delta": power_deltas,
            "current_delta": power_deltas,
            "constraint_changes": [],
            "finding_changes": {
                "introduced": introduced_findings,
                "resolved": resolved_findings,
            },
            "requirement_changes": req_changes,
            "failure_propagation_changes": failure_changes,
            "affected_subsystems": list(alt_affected_subs),
            "affected_interfaces": [],
            "affected_power_domains": list(power_deltas.keys()),
            "unknown_changes": new_unknowns,
            "summary": summary,
        }
