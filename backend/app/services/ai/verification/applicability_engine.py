from typing import Any
from app.models.db.provenance import KnowledgeApplicability


class KnowledgeApplicabilityEngine:
    """
    Deterministic Knowledge Applicability Evaluator.
    Determines whether an Engineering Knowledge Record applies to a given operating context.
    Strictly adheres to:
      - If conditions match context -> APPLICABLE
      - If conditions contradict context -> NOT_APPLICABLE
      - If conditions indicate boundary/derating constraints -> CONDITIONALLY_APPLICABLE
      - If required context parameters are missing -> UNKNOWN (Never assume applicability)
    """

    @classmethod
    def evaluate(
        cls,
        conditions: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluates conditions against context.
        Returns:
            {
                "applicability": KnowledgeApplicability,
                "reasons": list[str],
                "evaluated_conditions": dict,
                "missing_conditions": list[str]
            }
        """
        if not conditions:
            # Unconditional standard specification
            return {
                "applicability": KnowledgeApplicability.APPLICABLE.value,
                "reasons": ["No operational constraints specified on knowledge record (unconditional)."],
                "evaluated_conditions": {},
                "missing_conditions": [],
            }

        reasons: list[str] = []
        missing_conditions: list[str] = []
        evaluated_conditions: dict[str, Any] = {}
        is_conditional_edge = False

        for cond_key, cond_val in conditions.items():
            # 1. Package Matching
            if cond_key in ["package", "footprint"]:
                ctx_pkg = context.get("package") or context.get("footprint")
                if not ctx_pkg:
                    missing_conditions.append(cond_key)
                    reasons.append(f"Required package '{cond_val}' cannot be verified: context lacks package.")
                elif str(ctx_pkg).upper().strip() != str(cond_val).upper().strip():
                    return {
                        "applicability": KnowledgeApplicability.NOT_APPLICABLE.value,
                        "reasons": [f"Package mismatch: record specifies '{cond_val}' but component uses '{ctx_pkg}'."],
                        "evaluated_conditions": {cond_key: {"expected": cond_val, "actual": ctx_pkg}},
                        "missing_conditions": [],
                    }
                else:
                    evaluated_conditions[cond_key] = {"expected": cond_val, "actual": ctx_pkg, "match": True}

            # 2. Temperature Bounds
            elif cond_key in ["temp_max_c", "ta_max_c", "max_temp_c"]:
                ctx_temp = context.get("temp_c") or context.get("ambient_temp_c") or context.get("ta_c")
                if ctx_temp is None:
                    missing_conditions.append(cond_key)
                    reasons.append(f"Temperature limit ({cond_val}°C) cannot be verified: ambient temperature unknown.")
                else:
                    try:
                        c_val = float(cond_val)
                        t_val = float(ctx_temp)
                        if t_val > c_val:
                            return {
                                "applicability": KnowledgeApplicability.NOT_APPLICABLE.value,
                                "reasons": [f"Temperature overstress: operating temp {t_val}°C exceeds rating limit {c_val}°C."],
                                "evaluated_conditions": {cond_key: {"max": c_val, "actual": t_val}},
                                "missing_conditions": [],
                            }
                        elif t_val >= c_val - 10.0:
                            is_conditional_edge = True
                            reasons.append(f"Operating temperature ({t_val}°C) is within 10°C of rating maximum ({c_val}°C); derating applies.")
                        evaluated_conditions[cond_key] = {"max": c_val, "actual": t_val, "within_bounds": True}
                    except (ValueError, TypeError):
                        missing_conditions.append(cond_key)

            elif cond_key in ["temp_min_c", "ta_min_c"]:
                ctx_temp = context.get("temp_c") or context.get("ambient_temp_c")
                if ctx_temp is None:
                    missing_conditions.append(cond_key)
                    reasons.append(f"Minimum temperature limit ({cond_val}°C) cannot be verified: ambient temp unknown.")
                else:
                    try:
                        c_val = float(cond_val)
                        t_val = float(ctx_temp)
                        if t_val < c_val:
                            return {
                                "applicability": KnowledgeApplicability.NOT_APPLICABLE.value,
                                "reasons": [f"Low-temperature violation: operating temp {t_val}°C is below minimum {c_val}°C."],
                                "evaluated_conditions": {cond_key: {"min": c_val, "actual": t_val}},
                                "missing_conditions": [],
                            }
                        evaluated_conditions[cond_key] = {"min": c_val, "actual": t_val, "within_bounds": True}
                    except (ValueError, TypeError):
                        missing_conditions.append(cond_key)

            # 3. Voltage Bounds
            elif cond_key in ["vin_max_v", "max_voltage_v"]:
                ctx_vin = context.get("vin_v") or context.get("voltage_v")
                if ctx_vin is None:
                    missing_conditions.append(cond_key)
                    reasons.append(f"Voltage rating ({cond_val}V) cannot be verified: input voltage unknown.")
                else:
                    try:
                        c_val = float(cond_val)
                        v_val = float(ctx_vin)
                        if v_val > c_val:
                            return {
                                "applicability": KnowledgeApplicability.NOT_APPLICABLE.value,
                                "reasons": [f"Voltage limit exceeded: input voltage {v_val}V exceeds rating limit {c_val}V."],
                                "evaluated_conditions": {cond_key: {"max": c_val, "actual": v_val}},
                                "missing_conditions": [],
                            }
                        evaluated_conditions[cond_key] = {"max": c_val, "actual": v_val, "within_bounds": True}
                    except (ValueError, TypeError):
                        missing_conditions.append(cond_key)

            # 4. Airflow / Environment
            elif cond_key in ["airflow_lfm", "cooling"]:
                ctx_air = context.get("airflow_lfm")
                if ctx_air is None and cond_val != 0:
                    missing_conditions.append(cond_key)
                    reasons.append(f"Airflow requirement ({cond_val} LFM) unknown in operating context.")
                else:
                    evaluated_conditions[cond_key] = {"expected": cond_val, "actual": ctx_air}

            # 5. Generic exact match
            else:
                ctx_val = context.get(cond_key)
                if ctx_val is None:
                    missing_conditions.append(cond_key)
                    reasons.append(f"Condition '{cond_key}' ({cond_val}) not specified in operating context.")
                elif str(ctx_val).lower().strip() != str(cond_val).lower().strip():
                    return {
                        "applicability": KnowledgeApplicability.NOT_APPLICABLE.value,
                        "reasons": [f"Condition mismatch for '{cond_key}': expected '{cond_val}', got '{ctx_val}'."],
                        "evaluated_conditions": {cond_key: {"expected": cond_val, "actual": ctx_val}},
                        "missing_conditions": [],
                    }
                else:
                    evaluated_conditions[cond_key] = {"expected": cond_val, "actual": ctx_val, "match": True}

        # If any required conditions were missing -> UNKNOWN (Never assume applicability)
        if missing_conditions:
            return {
                "applicability": KnowledgeApplicability.UNKNOWN.value,
                "reasons": reasons,
                "evaluated_conditions": evaluated_conditions,
                "missing_conditions": missing_conditions,
            }

        # If boundary condition reached
        if is_conditional_edge:
            return {
                "applicability": KnowledgeApplicability.CONDITIONALLY_APPLICABLE.value,
                "reasons": reasons or ["Boundary derating condition active."],
                "evaluated_conditions": evaluated_conditions,
                "missing_conditions": [],
            }

        return {
            "applicability": KnowledgeApplicability.APPLICABLE.value,
            "reasons": ["All operating conditions and package constraints verified."],
            "evaluated_conditions": evaluated_conditions,
            "missing_conditions": [],
        }
