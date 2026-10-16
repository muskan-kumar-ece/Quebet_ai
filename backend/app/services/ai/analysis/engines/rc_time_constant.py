import math
import uuid
from typing import Any, Optional


def calculate_rc_time_constant(
    resistance_ohms: float,
    capacitance_farads: float,
    component_ids: Optional[list[str]] = None,
    net_ids: Optional[list[str]] = None,
    context_name: str = "RC Network Analysis",
) -> dict[str, Any]:
    """
    Deterministic RC time constant and frequency response:
    tau = R * C
    fc = 1 / (2 * pi * R * C)
    """
    comp_ids = component_ids or []
    n_ids = net_ids or []

    if resistance_ohms <= 0 or capacitance_farads <= 0:
        return {
            "id": str(uuid.uuid4()),
            "name": context_name,
            "category": "RC_TIME_CONSTANT",
            "component_ids": comp_ids,
            "net_ids": n_ids,
            "formula": "tau = R * C, fc = 1 / (2 * pi * R * C)",
            "inputs": {"resistance_ohms": resistance_ohms, "capacitance_f": capacitance_farads},
            "result": {"error": "Both resistance and capacitance must be positive non-zero values"},
            "unit": "s",
            "confidence": "LOW",
            "notes": "Non-physical RC parameter.",
        }

    tau = resistance_ohms * capacitance_farads
    fc = 1.0 / (2.0 * math.pi * tau)
    t_rise_10_90 = 2.197 * tau
    t_settle_99 = 4.605 * tau

    return {
        "id": str(uuid.uuid4()),
        "name": context_name,
        "category": "RC_TIME_CONSTANT",
        "component_ids": comp_ids,
        "net_ids": n_ids,
        "formula": "tau = R * C, fc = 1 / (2 * pi * R * C)",
        "inputs": {
            "resistance_ohms": round(resistance_ohms, 4),
            "capacitance_f": capacitance_farads,
        },
        "result": {
            "time_constant_seconds": tau,
            "time_constant_ms": round(tau * 1000, 4),
            "time_constant_us": round(tau * 1e6, 4),
            "cutoff_frequency_hz": round(fc, 2),
            "rise_time_10_90_ms": round(t_rise_10_90 * 1000, 4),
            "settling_time_99_ms": round(t_settle_99 * 1000, 4),
        },
        "unit": "s",
        "confidence": "HIGH",
        "notes": f"RC filter cutoff: {fc:.1f} Hz, tau: {tau*1000:.3f} ms.",
    }
