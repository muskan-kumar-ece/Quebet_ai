import uuid
from typing import Any, Optional


def calculate_voltage_divider(
    v_in: float,
    r1: float,
    r2: float,
    component_ids: Optional[list[str]] = None,
    net_ids: Optional[list[str]] = None,
    context_name: str = "Voltage Divider Calculation",
) -> dict[str, Any]:
    """
    Deterministic Voltage Divider calculation:
    Vout = Vin * (R2 / (R1 + R2))
    Idivider = Vin / (R1 + R2)
    Rthevenin = (R1 * R2) / (R1 + R2)
    """
    comp_ids = component_ids or []
    n_ids = net_ids or []

    if r1 <= 0 or r2 <= 0:
        return {
            "id": str(uuid.uuid4()),
            "name": context_name,
            "category": "VOLTAGE_DIVIDER",
            "component_ids": comp_ids,
            "net_ids": n_ids,
            "formula": "Vout = Vin * (R2 / (R1 + R2))",
            "inputs": {"vin_v": v_in, "r1_ohms": r1, "r2_ohms": r2},
            "result": {"error": "Invalid resistor values: both R1 and R2 must be positive non-zero"},
            "unit": "V",
            "confidence": "LOW",
            "notes": "Non-physical or short-circuit resistor values.",
        }

    total_r = r1 + r2
    ratio = r2 / total_r
    v_out = v_in * ratio
    i_divider = v_in / total_r
    p_r1 = (i_divider * i_divider) * r1
    p_r2 = (i_divider * i_divider) * r2
    r_th = (r1 * r2) / total_r

    return {
        "id": str(uuid.uuid4()),
        "name": context_name,
        "category": "VOLTAGE_DIVIDER",
        "component_ids": comp_ids,
        "net_ids": n_ids,
        "formula": "Vout = Vin * (R2 / (R1 + R2))",
        "inputs": {
            "vin_v": round(v_in, 4),
            "r1_ohms": round(r1, 4),
            "r2_ohms": round(r2, 4),
        },
        "result": {
            "vout_v": round(v_out, 4),
            "divider_ratio": round(ratio, 4),
            "divider_current_ma": round(i_divider * 1000, 4),
            "power_r1_mw": round(p_r1 * 1000, 3),
            "power_r2_mw": round(p_r2 * 1000, 3),
            "thevenin_impedance_ohms": round(r_th, 3),
        },
        "unit": "V",
        "confidence": "HIGH",
        "notes": f"Division ratio: {ratio:.3f}. Output voltage: {v_out:.2f}V at Vin={v_in:.2f}V.",
    }
