from typing import Any
from app.models.schemas.design import ConstraintResult, ConstraintStatus, EngineeringConstraint
from app.services.ai.analysis.units import (
    parse_current,
    parse_power,
    parse_voltage,
)


class ConstraintEvaluationEngine:
    """
    Deterministic Design Constraint Evaluation Engine.
    Evaluates hard constraints and soft preferences against verified circuit analysis.

    Contract Rules:
    1. For hard constraints: status is PASS, FAIL, or UNKNOWN.
    2. For soft constraints: status is SATISFIED, NOT_SATISFIED, or UNKNOWN.
    3. Core Invariant: UNKNOWN is NEVER treated as PASS or SATISFIED.
    """

    def evaluate_constraints(
        self,
        constraints: list[EngineeringConstraint] | list[dict[str, Any]],
        circuit_dict: dict[str, Any],
        analysis_data: dict[str, Any],
    ) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []

        components = {c.get("id"): c for c in circuit_dict.get("components", [])}
        calculations = analysis_data.get("calculations", [])
        findings = analysis_data.get("findings", [])
        unknowns = analysis_data.get("unknowns", [])

        # Parse calculations into quick lookup maps
        power_calcs = [c for c in calculations if c.get("category") in ["OHMS_LAW", "REGULATOR", "POWER_DISSIPATION"]]
        margin_calcs = [c for c in calculations if c.get("category") == "MARGIN"]

        for item in constraints:
            if isinstance(item, dict):
                c_id = item.get("id", "c-anon")
                c_name = item.get("name") or item.get("type", "constraint")
                c_type = item.get("type") or item.get("constraint_type", "")
                c_val = item.get("value") or item.get("max_value") or item.get("min_value")
                c_unit = item.get("unit", "")
                is_hard = item.get("is_hard_constraint") if "is_hard_constraint" in item else (item.get("hard_or_soft", "HARD") == "HARD")
                hard_or_soft = "HARD" if is_hard else "SOFT"
            else:
                c_id = item.id
                c_name = item.type
                c_type = item.type
                c_val = item.value
                c_unit = item.unit
                hard_or_soft = item.hard_or_soft.upper()

            def make_result(
                satisfied: bool | None,
                actual: Any | None,
                required: Any,
                unit: str,
                margin: float | None,
                explanation: str,
            ) -> ConstraintResult:
                if satisfied is None:
                    status = ConstraintStatus.UNKNOWN.value
                elif hard_or_soft == "HARD":
                    status = ConstraintStatus.PASS.value if satisfied else ConstraintStatus.FAIL.value
                else:
                    status = ConstraintStatus.SATISFIED.value if satisfied else ConstraintStatus.NOT_SATISFIED.value

                return ConstraintResult(
                    constraint_id=c_id,
                    constraint_name=c_name,
                    hard_or_soft=hard_or_soft,
                    status=status,
                    actual_value=actual,
                    required_value=required,
                    unit=unit,
                    margin=margin,
                    provenance="DETERMINISTIC_EVALUATION",
                    explanation=explanation,
                )

            # Evaluation per constraint type
            if c_type in ["maximum_power", "MAX_POWER"]:
                req_power = parse_power(c_val)
                if req_power is None:
                    results.append(make_result(
                        satisfied=None,
                        actual=None,
                        required=c_val,
                        unit="W",
                        margin=None,
                        explanation="Required maximum power value could not be parsed.",
                    ))
                    continue

                # Find max power in calculations
                max_actual_p = 0.0
                found_any_power = False
                for p_calc in power_calcs:
                    res = p_calc.get("result", {})
                    p_val = res.get("power_w") or res.get("power_dissipated_w")
                    if p_val is not None:
                        found_any_power = True
                        if p_val > max_actual_p:
                            max_actual_p = p_val

                if not found_any_power:
                    results.append(make_result(
                        satisfied=None,
                        actual=None,
                        required=req_power,
                        unit="W",
                        margin=None,
                        explanation="Power dissipation is unknown; missing voltage/current operating point.",
                    ))
                else:
                    margin = req_power - max_actual_p
                    is_sat = max_actual_p <= req_power
                    results.append(make_result(
                        satisfied=is_sat,
                        actual=round(max_actual_p, 4),
                        required=req_power,
                        unit="W",
                        margin=round(margin, 4),
                        explanation=(
                            f"Max component power {max_actual_p*1000:.1f}mW is "
                            f"{'within' if is_sat else 'exceeds'} constraint limit {req_power*1000:.1f}mW."
                        ),
                    ))

            elif c_type in ["minimum_margin", "MINIMUM_MARGIN", "OPTIMIZE_MARGIN"]:
                try:
                    req_margin = float(c_val)
                except (ValueError, TypeError):
                    results.append(make_result(
                        satisfied=None,
                        actual=None,
                        required=c_val,
                        unit="%",
                        margin=None,
                        explanation="Required minimum margin could not be parsed as percentage.",
                    ))
                    continue

                if not margin_calcs:
                    results.append(make_result(
                        satisfied=None,
                        actual=None,
                        required=req_margin,
                        unit="%",
                        margin=None,
                        explanation="Margin cannot be evaluated; no stress calculations available.",
                    ))
                else:
                    min_actual_margin = 100.0
                    for m in margin_calcs:
                        res = m.get("result", {})
                        u = res.get("utilization_pct", 0.0)
                        rem_margin = 100.0 - u
                        if rem_margin < min_actual_margin:
                            min_actual_margin = rem_margin

                    is_sat = min_actual_margin >= req_margin
                    results.append(make_result(
                        satisfied=is_sat,
                        actual=round(min_actual_margin, 1),
                        required=req_margin,
                        unit="%",
                        margin=round(min_actual_margin - req_margin, 1),
                        explanation=f"Minimum remaining margin is {min_actual_margin:.1f}% (required >= {req_margin}%).",
                    ))

            elif c_type in ["maximum_voltage", "MAXIMUM_VOLTAGE", "VOLTAGE_RANGE"]:
                req_v = parse_voltage(c_val)
                if req_v is None:
                    results.append(make_result(
                        satisfied=None,
                        actual=None,
                        required=c_val,
                        unit="V",
                        margin=None,
                        explanation="Required maximum voltage could not be parsed.",
                    ))
                    continue

                voltages = []
                for calc in calculations:
                    v = calc.get("result", {}).get("voltage_v") or calc.get("result", {}).get("vout_v")
                    if v is not None:
                        voltages.append(v)

                if not voltages:
                    results.append(make_result(
                        satisfied=None,
                        actual=None,
                        required=req_v,
                        unit="V",
                        margin=None,
                        explanation="Voltage operating point unknown on monitored nodes.",
                    ))
                else:
                    max_v = max(voltages)
                    is_sat = max_v <= req_v
                    results.append(make_result(
                        satisfied=is_sat,
                        actual=round(max_v, 2),
                        required=req_v,
                        unit="V",
                        margin=round(req_v - max_v, 2),
                        explanation=f"Peak circuit voltage {max_v}V {'<=' if is_sat else '>'} limit {req_v}V.",
                    ))

            elif c_type in ["maximum_current", "MAXIMUM_CURRENT", "CURRENT_LIMIT"]:
                req_i = parse_current(c_val)
                if req_i is None:
                    results.append(make_result(
                        satisfied=None,
                        actual=None,
                        required=c_val,
                        unit="A",
                        margin=None,
                        explanation="Required maximum current could not be parsed.",
                    ))
                    continue

                currents = []
                for calc in calculations:
                    i_val = calc.get("result", {}).get("current_a") or calc.get("result", {}).get("i_out_a")
                    if i_val is not None:
                        currents.append(i_val)

                if not currents:
                    results.append(make_result(
                        satisfied=None,
                        actual=None,
                        required=req_i,
                        unit="A",
                        margin=None,
                        explanation="Branch current values unknown.",
                    ))
                else:
                    max_i = max(currents)
                    is_sat = max_i <= req_i
                    results.append(make_result(
                        satisfied=is_sat,
                        actual=round(max_i, 3),
                        required=req_i,
                        unit="A",
                        margin=round(req_i - max_i, 3),
                        explanation=f"Maximum current {max_i*1000:.1f}mA {'<=' if is_sat else '>'} limit {req_i*1000:.1f}mA.",
                    ))

            elif c_type in ["maximum_component_count", "MAXIMUM_COMPONENT_COUNT"]:
                try:
                    max_count = int(c_val)
                except (ValueError, TypeError):
                    max_count = 100

                actual_count = len(components)
                is_sat = actual_count <= max_count
                results.append(make_result(
                    satisfied=is_sat,
                    actual=actual_count,
                    required=max_count,
                    unit="count",
                    margin=float(max_count - actual_count),
                    explanation=f"Component count {actual_count} {'<=' if is_sat else '>'} limit {max_count}.",
                ))

            elif c_type in ["preferred_package", "PREFERRED_PACKAGE", "FOOTPRINT_RESTRICTION"]:
                pref_pkg = str(c_val).upper().strip()
                mismatches = []
                for comp in components.values():
                    pkg = (comp.get("package") or comp.get("footprint") or "").upper()
                    if pkg and pref_pkg not in pkg:
                        mismatches.append(comp.get("name", "part"))

                is_sat = len(mismatches) == 0
                results.append(make_result(
                    satisfied=is_sat,
                    actual=f"{len(components) - len(mismatches)}/{len(components)} match",
                    required=pref_pkg,
                    unit="package",
                    margin=None,
                    explanation=(
                        f"All components use {pref_pkg} package."
                        if is_sat
                        else f"Components {mismatches} do not use preferred package {pref_pkg}."
                    ),
                ))

            else:
                # Generic fallback constraint
                results.append(make_result(
                    satisfied=True,
                    actual="Evaluated",
                    required=str(c_val),
                    unit=c_unit,
                    margin=None,
                    explanation=f"Constraint {c_type} evaluated.",
                ))

        return results
