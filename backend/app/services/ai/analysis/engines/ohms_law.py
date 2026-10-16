import uuid
from typing import Any, Optional


def calculate_ohms_law(
    voltage: Optional[float] = None,
    resistance: Optional[float] = None,
    current: Optional[float] = None,
    component_ids: Optional[list[str]] = None,
    net_ids: Optional[list[str]] = None,
    context_name: str = "Ohm's Law Calculation",
) -> dict[str, Any]:
    """
    Deterministic Ohm's law and power calculation:
    V = I * R
    P = V * I = I^2 * R = V^2 / R
    Protects against zero-division and invalid inputs.
    """
    comp_ids = component_ids or []
    n_ids = net_ids or []

    # Case 1: Given V and R -> find I, P
    if voltage is not None and resistance is not None:
        if resistance <= 0:
            return {
                "id": str(uuid.uuid4()),
                "name": context_name,
                "category": "OHMS_LAW",
                "component_ids": comp_ids,
                "net_ids": n_ids,
                "formula": "I = V / R",
                "inputs": {"voltage_v": voltage, "resistance_ohms": resistance},
                "result": {"error": "Invalid resistance: resistance must be greater than 0"},
                "unit": "A",
                "confidence": "LOW",
                "notes": "Non-physical or short-circuit resistance value.",
            }

        calc_current = voltage / resistance
        calc_power = (voltage * voltage) / resistance
        return {
            "id": str(uuid.uuid4()),
            "name": context_name,
            "category": "OHMS_LAW",
            "component_ids": comp_ids,
            "net_ids": n_ids,
            "formula": "I = V / R, P = V * I",
            "inputs": {"voltage_v": round(voltage, 4), "resistance_ohms": round(resistance, 4)},
            "result": {
                "current_a": round(calc_current, 6),
                "current_ma": round(calc_current * 1000, 3),
                "power_w": round(calc_power, 6),
                "power_mw": round(calc_power * 1000, 3),
            },
            "unit": "A",
            "confidence": "HIGH",
            "notes": None,
        }

    # Case 2: Given I and R -> find V, P
    if current is not None and resistance is not None:
        if resistance < 0:
            return {
                "id": str(uuid.uuid4()),
                "name": context_name,
                "category": "OHMS_LAW",
                "component_ids": comp_ids,
                "net_ids": n_ids,
                "formula": "V = I * R",
                "inputs": {"current_a": current, "resistance_ohms": resistance},
                "result": {"error": "Invalid resistance: resistance cannot be negative"},
                "unit": "V",
                "confidence": "LOW",
                "notes": "Non-physical resistance value.",
            }

        calc_voltage = current * resistance
        calc_power = (current * current) * resistance
        return {
            "id": str(uuid.uuid4()),
            "name": context_name,
            "category": "OHMS_LAW",
            "component_ids": comp_ids,
            "net_ids": n_ids,
            "formula": "V = I * R, P = I^2 * R",
            "inputs": {"current_a": round(current, 6), "resistance_ohms": round(resistance, 4)},
            "result": {
                "voltage_v": round(calc_voltage, 4),
                "power_w": round(calc_power, 6),
                "power_mw": round(calc_power * 1000, 3),
            },
            "unit": "V",
            "confidence": "HIGH",
            "notes": None,
        }

    # Case 3: Given V and I -> find R, P
    if voltage is not None and current is not None:
        if abs(current) < 1e-12:
            return {
                "id": str(uuid.uuid4()),
                "name": context_name,
                "category": "OHMS_LAW",
                "component_ids": comp_ids,
                "net_ids": n_ids,
                "formula": "R = V / I",
                "inputs": {"voltage_v": voltage, "current_a": current},
                "result": {"error": "Division by zero current"},
                "unit": "Ω",
                "confidence": "LOW",
                "notes": "Current is zero, open circuit.",
            }

        calc_r = voltage / current
        calc_power = voltage * current
        return {
            "id": str(uuid.uuid4()),
            "name": context_name,
            "category": "OHMS_LAW",
            "component_ids": comp_ids,
            "net_ids": n_ids,
            "formula": "R = V / I, P = V * I",
            "inputs": {"voltage_v": round(voltage, 4), "current_a": round(current, 6)},
            "result": {
                "resistance_ohms": round(calc_r, 4),
                "power_w": round(calc_power, 6),
                "power_mw": round(calc_power * 1000, 3),
            },
            "unit": "Ω",
            "confidence": "HIGH",
            "notes": None,
        }

    return {
        "id": str(uuid.uuid4()),
        "name": context_name,
        "category": "OHMS_LAW",
        "component_ids": comp_ids,
        "net_ids": n_ids,
        "formula": "V = I * R",
        "inputs": {},
        "result": {"error": "Insufficient parameters for Ohm's law (need 2 of V, I, R)"},
        "unit": "N/A",
        "confidence": "LOW",
        "notes": "Missing boundary parameters.",
    }
