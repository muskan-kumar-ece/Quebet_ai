import uuid
from typing import Any, Optional


def evaluate_engineering_requirement(
    requirement: dict[str, Any],
    circuit_state: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic Evaluation of EngineeringRequirement expressions against circuit state.
    Expressions format:
    {
        "parameter": "v_out" | "power" | "efficiency" | "frequency",
        "operator": "EQ" | "LTE" | "GTE" | "LT" | "GT" | "RANGE",
        "value": float | list[float],
        "unit": "V" | "W" | "Hz" | "A",
        "tolerance": Optional[float] (fractional, e.g. 0.05 for +/- 5%)
    }
    
    INVARIANTS:
    - Status is strictly: SATISFIED, VIOLATED, UNKNOWN.
    - UNKNOWN != SATISFIED. If parameter is not computed or available, emit UNKNOWN.
    - Zero synthetic scoring: No partial percentage or confidence grading.
    """
    req_id = requirement.get("id") or requirement.get("requirement_key") or str(uuid.uuid4())
    title = requirement.get("title") or requirement.get("requirement_key") or "Engineering Requirement"
    expr = requirement.get("expression") or {}

    parameter = expr.get("parameter") or requirement.get("parameter")
    operator = (expr.get("operator") or requirement.get("operator") or "LTE").upper()
    target_val = expr.get("value") if expr.get("value") is not None else requirement.get("value")
    tolerance = expr.get("tolerance", 0.0)
    unit = expr.get("unit") or requirement.get("unit") or ""

    if not parameter or target_val is None:
        return {
            "requirement_id": req_id,
            "title": title,
            "parameter": parameter or "UNSPECIFIED",
            "target": target_val,
            "actual": None,
            "unit": unit,
            "status": "UNKNOWN",
            "reason": "Requirement expression lacks parameter or target value definition.",
            "verification_status": "UNVERIFIED",
        }

    # Extract actual parameter from circuit state
    actual_val = circuit_state.get(parameter)
    if actual_val is None:
        # Check in nested dictionaries if present
        for k, v in circuit_state.items():
            if isinstance(v, dict) and parameter in v:
                actual_val = v[parameter]
                break

    if actual_val is None:
        return {
            "requirement_id": req_id,
            "title": title,
            "parameter": parameter,
            "target": target_val,
            "actual": None,
            "unit": unit,
            "status": "UNKNOWN",
            "reason": f"Parameter '{parameter}' was not determined in circuit analysis.",
            "verification_status": "UNVERIFIED",
        }

    # Deterministic comparison
    status = "VIOLATED"
    reason = ""

    try:
        val = float(actual_val)
        if operator == "EQ":
            tol_val = abs(float(target_val) * float(tolerance)) if tolerance else 0.001
            if abs(val - float(target_val)) <= tol_val:
                status = "SATISFIED"
                reason = f"Actual value {val}{unit} matches required target {target_val}{unit} (tolerance +/- {tol_val})."
            else:
                status = "VIOLATED"
                reason = f"Actual value {val}{unit} deviates from required {target_val}{unit} beyond tolerance."
        elif operator == "LTE" or operator == "LT":
            limit = float(target_val) * (1.0 + float(tolerance))
            if val <= limit:
                status = "SATISFIED"
                reason = f"Actual value {val}{unit} satisfies <= {target_val}{unit} limit."
            else:
                status = "VIOLATED"
                reason = f"Actual value {val}{unit} exceeds required maximum {target_val}{unit}."
        elif operator == "GTE" or operator == "GT":
            limit = float(target_val) * (1.0 - float(tolerance))
            if val >= limit:
                status = "SATISFIED"
                reason = f"Actual value {val}{unit} satisfies >= {target_val}{unit} minimum."
            else:
                status = "VIOLATED"
                reason = f"Actual value {val}{unit} is below required minimum {target_val}{unit}."
        elif operator == "RANGE":
            if isinstance(target_val, (list, tuple)) and len(target_val) == 2:
                low, high = float(target_val[0]), float(target_val[1])
                if low <= val <= high:
                    status = "SATISFIED"
                    reason = f"Actual value {val}{unit} is within specified range [{low}, {high}]{unit}."
                else:
                    status = "VIOLATED"
                    reason = f"Actual value {val}{unit} is outside specified range [{low}, {high}]{unit}."
            else:
                status = "UNKNOWN"
                reason = "RANGE operator requires a [min, max] list."
        else:
            status = "UNKNOWN"
            reason = f"Unsupported operator '{operator}'."
    except Exception as e:
        status = "UNKNOWN"
        reason = f"Evaluation error: {e}"

    return {
        "requirement_id": req_id,
        "title": title,
        "parameter": parameter,
        "target": target_val,
        "actual": actual_val,
        "unit": unit,
        "status": status,
        "reason": reason,
        "verification_status": "CALCULATED",
    }


def evaluate_system_design_constraint(
    constraint: dict[str, Any],
    circuit_state: dict[str, Any],
) -> dict[str, Any]:
    """
    Deterministic Evaluation of EngineeringSystemDesignConstraint.
    HARD constraint: PASS / FAIL / UNKNOWN.
    SOFT constraint: SATISFIED / NOT_SATISFIED / UNKNOWN.
    """
    c_id = constraint.get("id") or str(uuid.uuid4())
    c_type = (constraint.get("constraint_type") or "HARD").upper()
    parameter = constraint.get("parameter")
    operator = (constraint.get("operator") or "LTE").upper()
    val_spec = constraint.get("value")
    unit = constraint.get("unit") or ""

    # Value in EngineeringSystemDesignConstraint is stored as a JSON dict (e.g. {"val": 5.0} or 5.0)
    target_val = val_spec.get("val") if isinstance(val_spec, dict) else val_spec

    # Reuse core evaluation logic
    req_dict = {
        "id": c_id,
        "title": f"Constraint: {parameter}",
        "expression": {
            "parameter": parameter,
            "operator": operator,
            "value": target_val,
            "unit": unit,
        },
    }
    raw_eval = evaluate_engineering_requirement(req_dict, circuit_state)

    raw_status = raw_eval.get("status")
    if c_type == "HARD":
        if raw_status == "SATISFIED":
            final_status = "PASS"
        elif raw_status == "VIOLATED":
            final_status = "FAIL"
        else:
            final_status = "UNKNOWN"
    else:  # SOFT
        if raw_status == "SATISFIED":
            final_status = "SATISFIED"
        elif raw_status == "VIOLATED":
            final_status = "NOT_SATISFIED"
        else:
            final_status = "UNKNOWN"

    return {
        "constraint_id": c_id,
        "constraint_type": c_type,
        "parameter": parameter,
        "operator": operator,
        "target": target_val,
        "actual": raw_eval.get("actual"),
        "unit": unit,
        "status": final_status,
        "reason": raw_eval.get("reason"),
        "verification_status": raw_eval.get("verification_status"),
    }
