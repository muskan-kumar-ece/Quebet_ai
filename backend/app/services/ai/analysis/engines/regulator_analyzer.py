import uuid
from typing import Any, Optional


def analyze_linear_regulator(
    v_in: float,
    v_out: float,
    i_load_a: float,
    specs: dict[str, Any],
    ambient_temp_c: float = 25.0,
    component_ids: Optional[list[str]] = None,
    net_ids: Optional[list[str]] = None,
    context_name: str = "Linear Regulator Thermal & Dissipation",
) -> dict[str, Any]:
    """
    Deterministic Linear Regulator analysis:
    Pd = (Vin - Vout) * Iload + Vin * Iq
    Delta_T = Pd * R_theta_ja
    Tj = Tambient + Delta_T
    """
    comp_ids = component_ids or []
    n_ids = net_ids or []

    v_dropout = specs.get("dropout_voltage_v", 1.5)
    iq_ma = specs.get("quiescent_current_ma") or 5.0
    iq_a = iq_ma / 1000.0
    r_theta = specs.get("r_theta_ja") or 65.0
    tj_max = specs.get("max_junction_temp_c") or 125.0

    delta_v = v_in - v_out
    has_dropout_headroom = delta_v >= v_dropout

    # Power dissipation in watts
    p_dissipated = (delta_v * i_load_a) + (v_in * iq_a)
    delta_t = p_dissipated * r_theta
    est_tj = ambient_temp_c + delta_t
    thermal_margin = tj_max - est_tj

    notes_list = []
    if not has_dropout_headroom:
        notes_list.append(
            f"Insufficient dropout headroom: Vin-Vout={delta_v:.2f}V is less than required dropout {v_dropout:.2f}V."
        )
    if est_tj > tj_max:
        notes_list.append(
            f"Overheating hazard: junction temperature {est_tj:.1f}°C exceeds rated {tj_max:.1f}°C."
        )
    elif est_tj > 85.0:
        notes_list.append(
            f"High thermal dissipation: junction temperature is {est_tj:.1f}°C; heatsink recommended."
        )

    return {
        "id": str(uuid.uuid4()),
        "name": context_name,
        "category": "REGULATOR",
        "component_ids": comp_ids,
        "net_ids": n_ids,
        "formula": "Pd = (Vin - Vout) * Iload; Tj = Ta + Pd * R_theta_ja",
        "inputs": {
            "vin_v": round(v_in, 2),
            "vout_v": round(v_out, 2),
            "iload_a": round(i_load_a, 4),
            "dropout_v": round(v_dropout, 2),
            "r_theta_ja": round(r_theta, 1),
            "ambient_temp_c": round(ambient_temp_c, 1),
        },
        "result": {
            "headroom_v": round(delta_v, 3),
            "has_adequate_headroom": has_dropout_headroom,
            "power_dissipated_w": round(p_dissipated, 3),
            "temp_rise_c": round(delta_t, 1),
            "junction_temp_c": round(est_tj, 1),
            "thermal_margin_c": round(thermal_margin, 1),
            "max_junction_temp_c": tj_max,
        },
        "unit": "W",
        "confidence": "HIGH",
        "notes": "; ".join(notes_list) if notes_list else "Regulator operating within thermal and dropout bounds.",
    }
