import uuid
from typing import Any, Optional


def calculate_margin(
    actual: float,
    rated: float,
    parameter_name: str = "Rating",
    unit: str = "W",
    recommended_derating: float = 0.80,
    component_ids: Optional[list[str]] = None,
    net_ids: Optional[list[str]] = None,
    context_name: str = "Component Margin Evaluation",
) -> dict[str, Any]:
    """
    Deterministic Component Stress and Margin evaluation:
    Utilization = Actual / Rated
    Margin % = (1 - Utilization) * 100
    Safety Factor = Rated / Actual
    """
    comp_ids = component_ids or []
    n_ids = net_ids or []

    if rated <= 0:
        return {
            "id": str(uuid.uuid4()),
            "name": context_name,
            "category": "MARGIN",
            "component_ids": comp_ids,
            "net_ids": n_ids,
            "formula": "Utilization = Actual / Rated",
            "inputs": {"actual": actual, "rated": rated, "parameter": parameter_name},
            "result": {"error": f"Invalid rated {parameter_name}: must be positive non-zero"},
            "unit": "%",
            "confidence": "LOW",
            "notes": "Rated limit not specified or invalid.",
        }

    utilization = actual / rated
    margin_pct = (1.0 - utilization) * 100.0
    safety_factor = rated / actual if actual > 0 else 999.0

    is_overstressed = utilization > 1.0
    is_insufficient_margin = utilization > recommended_derating and not is_overstressed

    status = "ADEQUATE"
    if is_overstressed:
        status = "OVERSTRESSED"
    elif is_insufficient_margin:
        status = "INSUFFICIENT_MARGIN"

    return {
        "id": str(uuid.uuid4()),
        "name": context_name,
        "category": "MARGIN",
        "component_ids": comp_ids,
        "net_ids": n_ids,
        "formula": "Margin % = (1 - (Actual / Rated)) * 100",
        "inputs": {
            "actual": round(actual, 4),
            "rated": round(rated, 4),
            "parameter": parameter_name,
            "unit": unit,
            "derating_threshold": recommended_derating,
        },
        "result": {
            "utilization_pct": round(utilization * 100, 2),
            "margin_pct": round(margin_pct, 2),
            "safety_factor": round(safety_factor, 2),
            "status": status,
        },
        "unit": "%",
        "confidence": "HIGH",
        "notes": (
            f"{parameter_name} utilization is {utilization*100:.1f}%. "
            f"Margin is {margin_pct:.1f}%. Status: {status}."
        ),
    }
