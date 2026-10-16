import uuid
from typing import Any, Optional


def calculate_thermal_dissipation(
    power_w: Optional[float],
    theta_ja: Optional[float],
    ambient_temp_c: Optional[float] = 25.0,
    tj_max: Optional[float] = None,
    component_ids: Optional[list[str]] = None,
    net_ids: Optional[list[str]] = None,
    context_name: str = "Thermal Dissipation Analysis",
    source_id: Optional[str] = None,
    revision: Optional[str] = None,
) -> dict[str, Any]:
    """
    Deterministic Thermal Dissipation & Junction Temperature Engine.
    Formula: Delta_T = Pd * Theta_JA; Tj = Ta + Delta_T
    
    INVARIANTS:
    1. CALCULATED != PHYSICALLY VERIFIED.
    2. UNKNOWN != SATISFIED. If Theta_JA or Ta is not documented, emit UNKNOWN.
       NEVER guess, extrapolate, or use synthetic industry averages.
    3. ZERO SYNTHETIC SCORING: Strict categorical evaluation (ADEQUATE, INSUFFICIENT_MARGIN, OVERSTRESSED, UNKNOWN).
    """
    comp_ids = component_ids or []
    n_ids = net_ids or []

    # Check for missing parameters
    missing = []
    if power_w is None:
        missing.append("power_w")
    if theta_ja is None:
        missing.append("theta_ja")
    if ambient_temp_c is None:
        missing.append("ambient_temp_c")

    if missing:
        return {
            "id": str(uuid.uuid4()),
            "name": context_name,
            "category": "THERMAL",
            "component_ids": comp_ids,
            "net_ids": n_ids,
            "formula": "Tj = Ta + (Pd * Theta_JA)",
            "inputs": {
                "power_w": power_w,
                "theta_ja": theta_ja,
                "ambient_temp_c": ambient_temp_c,
                "tj_max_c": tj_max,
            },
            "result": {
                "status": "UNKNOWN",
                "missing_parameters": missing,
                "reason": f"Missing required thermal parameter(s): {', '.join(missing)}. Industry averages will not be assumed.",
            },
            "unit": "°C",
            "verification_status": "UNVERIFIED",
            "confidence": "LOW",
            "source_id": source_id,
            "revision": revision,
            "notes": "Thermal analysis requires documented Theta_JA and operating temperature.",
        }

    # Deterministic physical calculation
    delta_t = power_w * theta_ja
    tj = ambient_temp_c + delta_t

    thermal_margin = None
    stress_status = "ADEQUATE"

    if tj_max is not None and tj_max > 0:
        thermal_margin = tj_max - tj
        if tj > tj_max:
            stress_status = "OVERSTRESSED"
        elif tj > (0.80 * tj_max):
            stress_status = "INSUFFICIENT_MARGIN"
        else:
            stress_status = "ADEQUATE"
    else:
        stress_status = "CALCULATED_NO_LIMIT"

    notes = []
    if stress_status == "OVERSTRESSED":
        notes.append(f"Silicon destruction risk: junction temperature {tj:.1f}°C exceeds rated absolute maximum {tj_max:.1f}°C.")
    elif stress_status == "INSUFFICIENT_MARGIN":
        notes.append(f"Elevated junction temperature {tj:.1f}°C exceeds 80% thermal derating threshold.")
    else:
        notes.append(f"Junction temperature {tj:.1f}°C within safe operating limits.")

    return {
        "id": str(uuid.uuid4()),
        "name": context_name,
        "category": "THERMAL",
        "component_ids": comp_ids,
        "net_ids": n_ids,
        "formula": "Tj = Ta + (Pd * Theta_JA)",
        "inputs": {
            "power_w": round(power_w, 4),
            "theta_ja": round(theta_ja, 2),
            "ambient_temp_c": round(ambient_temp_c, 2),
            "tj_max_c": round(tj_max, 2) if tj_max is not None else None,
        },
        "result": {
            "status": stress_status,
            "delta_t_c": round(delta_t, 2),
            "junction_temp_c": round(tj, 2),
            "thermal_margin_c": round(thermal_margin, 2) if thermal_margin is not None else None,
            "tj_max_c": tj_max,
        },
        "unit": "°C",
        "verification_status": "CALCULATED",
        "confidence": "HIGH",
        "source_id": source_id,
        "revision": revision,
        "notes": "; ".join(notes),
    }
