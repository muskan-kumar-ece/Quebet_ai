import uuid
from typing import Any, Optional


def analyze_net_interface(
    net_id: str,
    net_name: str,
    connected_pins: list[dict[str, Any]],
    net_voltage: Optional[float] = None,
    context_name: str = "Interface Electrical Evaluation",
) -> dict[str, Any]:
    """
    Deterministic Interface & Net Compatibility Engine.
    Evaluates:
    - Direction contention (Multiple OUTPUT pins on same net)
    - Power/Ground short circuits (POWER pin connected directly to GROUND pin)
    - Voltage domain compatibility (Rail or driver exceeds receiver rating)
    - Open-drain requirements (Open-drain pins without pull-ups)

    INVARIANTS:
    - Zero synthetic scoring: strictly COMPATIBLE, INCOMPATIBLE, UNKNOWN, CONDITIONAL.
    - Verification status is CALCULATED (never PHYSICALLY VERIFIED).
    """
    issues = []
    status = "COMPATIBLE"

    output_pins = []
    power_pins = []
    ground_pins = []
    open_drain_pins = []
    input_pins = []
    has_resistor_pullup = False

    for pin in connected_pins:
        p_type = (pin.get("pin_type") or "").upper()
        p_role = (pin.get("electrical_role") or "").upper()
        p_dir = (pin.get("direction") or "").upper()
        comp_type = (pin.get("component_type") or "").upper()

        if comp_type in ["RESISTOR", "R"]:
            has_resistor_pullup = True

        if p_type in ["POWER_OUT", "OUTPUT"] or p_dir == "OUTPUT":
            output_pins.append(pin)
        elif p_type in ["POWER_IN", "POWER"] or p_role in ["VIN", "VCC", "VDD"]:
            power_pins.append(pin)
        elif p_type == "GROUND" or p_role in ["GND", "VSS", "GROUND"]:
            ground_pins.append(pin)
        elif p_type in ["OPEN_DRAIN", "OD"] or p_role in ["SDA", "SCL"]:
            open_drain_pins.append(pin)
        elif p_type in ["INPUT", "DIGITAL_IN", "ANALOG_IN"] or p_dir == "INPUT":
            input_pins.append(pin)

    # 1. Power / Ground Short Circuit Check
    if power_pins and ground_pins:
        status = "INCOMPATIBLE"
        issues.append({
            "type": "POWER_GROUND_SHORT",
            "severity": "CRITICAL",
            "message": f"Dead short detected on net '{net_name}': Power pin(s) directly connected to Ground pin(s).",
            "pins": [p.get("pin_id") or p.get("pin_name") for p in power_pins + ground_pins],
        })

    # 2. Driver Contention Check (Multiple push-pull outputs on same net)
    if len(output_pins) > 1:
        # Check if they are push-pull (not open-drain)
        non_od_outputs = [p for p in output_pins if (p.get("pin_type") or "").upper() not in ["OPEN_DRAIN", "OD"]]
        if len(non_od_outputs) > 1:
            status = "INCOMPATIBLE"
            issues.append({
                "type": "DRIVER_CONTENTION",
                "severity": "CRITICAL",
                "message": f"Bus contention on net '{net_name}': multiple output drivers driving net simultaneously.",
                "pins": [p.get("pin_id") or p.get("pin_name") for p in non_od_outputs],
            })

    # 3. Voltage Domain Overstress on Inputs
    if net_voltage is not None:
        for pin in input_pins:
            max_v = pin.get("max_voltage") or pin.get("v_in_max")
            is_5v_tolerant = pin.get("is_5v_tolerant", False)
            if max_v is not None and net_voltage > max_v:
                status = "INCOMPATIBLE"
                issues.append({
                    "type": "VOLTAGE_OVERSTRESS",
                    "severity": "CRITICAL",
                    "message": (
                        f"Pin '{pin.get('pin_name')}' on component '{pin.get('component_name')}' rated for max "
                        f"{max_v:.1f}V but connected to net '{net_name}' operating at {net_voltage:.1f}V."
                    ),
                    "pins": [pin.get("pin_id") or pin.get("pin_name")],
                })
            elif net_voltage > 3.6 and not is_5v_tolerant and pin.get("domain") in ["3.3V", "3V3"]:
                status = "INCOMPATIBLE"
                issues.append({
                    "type": "VOLTAGE_DOMAIN_MISMATCH",
                    "severity": "CRITICAL",
                    "message": (
                        f"3.3V pin '{pin.get('pin_name')}' on '{pin.get('component_name')}' is not 5V-tolerant "
                        f"but connected to net '{net_name}' operating at {net_voltage:.1f}V."
                    ),
                    "pins": [pin.get("pin_id") or pin.get("pin_name")],
                })

    # 4. Open-Drain Missing Pull-up
    if open_drain_pins and not has_resistor_pullup:
        # If open-drain net has no pull-up resistor, flag as CONDITIONAL
        if status != "INCOMPATIBLE":
            status = "CONDITIONAL"
        issues.append({
            "type": "MISSING_PULLUP",
            "severity": "WARNING",
            "message": f"Open-drain signal(s) on net '{net_name}' require an external pull-up resistor to function.",
            "pins": [p.get("pin_id") or p.get("pin_name") for p in open_drain_pins],
        })

    # Unknown check: if pin types are unspecified
    if not connected_pins or all(p.get("pin_type") in [None, "UNKNOWN", "PASSIVE"] for p in connected_pins):
        if not issues:
            status = "UNKNOWN"

    return {
        "id": str(uuid.uuid4()),
        "name": context_name,
        "category": "INTERFACE",
        "net_id": net_id,
        "net_name": net_name,
        "formula": "Driver Contention = Pin_Dir == OUTPUT; Rail Overstress = V_rail > V_pin_max",
        "inputs": {
            "net_name": net_name,
            "connected_pin_count": len(connected_pins),
            "net_voltage": net_voltage,
        },
        "result": {
            "status": status,
            "issues": issues,
            "issue_count": len(issues),
        },
        "unit": "status",
        "status": status,
        "issues": issues,
        "connected_pin_count": len(connected_pins),
        "verification_status": "CALCULATED",
        "confidence": "HIGH" if status != "UNKNOWN" else "LOW",
        "notes": f"Interface evaluated with status {status}. {len(issues)} issue(s) identified.",
    }
