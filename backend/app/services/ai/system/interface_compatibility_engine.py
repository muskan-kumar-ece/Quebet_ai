from typing import Any, Dict, List, Optional
from enum import Enum


class CompatibilityStatus(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    PARTIALLY_COMPATIBLE = "PARTIALLY_COMPATIBLE"
    UNKNOWN = "UNKNOWN"


class SystemInterfaceCompatibilityEngine:
    """
    Deterministic evaluation of engineering boundary compatibility between subsystems.
    Strictly adheres to: UNKNOWN != COMPATIBLE / PASS.
    """
    ENGINE_VERSION = "1.0.0"

    @classmethod
    def evaluate(
        cls,
        interface_name: str,
        interface_type: str,
        source_subsystem_name: str,
        dest_subsystem_name: str,
        contract: Dict[str, Any],
    ) -> Dict[str, Any]:
        unknowns: List[str] = []
        violations: List[str] = []
        cautions: List[str] = []
        calculation: Dict[str, Any] = {}

        if not contract:
            return {
                "rule_id": "SYS-IFACE-000",
                "status": CompatibilityStatus.UNKNOWN.value,
                "conclusion": f"Interface '{interface_name}' contract is empty. Specifications are unknown.",
                "inputs": {"contract": contract},
                "calculation": {},
                "provenance": {"engine": "SystemInterfaceCompatibilityEngine", "version": cls.ENGINE_VERSION},
                "unknowns": ["No contract specifications defined for boundary."],
            }

        # 1. Electrical Evaluation
        src_v_max = contract.get("voltage_max") or contract.get("source_voltage_max")
        src_v_min = contract.get("voltage_min") or contract.get("source_voltage_min")
        dst_v_max = contract.get("destination_voltage_max") or contract.get("voltage_max_tolerance")
        dst_v_min = contract.get("destination_voltage_min") or contract.get("voltage_min_tolerance")

        if src_v_max is not None and dst_v_max is not None:
            calculation["voltage_max_check"] = {
                "source_max": src_v_max,
                "dest_max_rating": dst_v_max,
                "margin_v": round(dst_v_max - src_v_max, 3),
            }
            if src_v_max > dst_v_max:
                violations.append(
                    f"Overvoltage hazard: Source max ({src_v_max}V) exceeds destination max rating ({dst_v_max}V)."
                )

        if src_v_min is not None and dst_v_min is not None:
            calculation["voltage_min_check"] = {
                "source_min": src_v_min,
                "dest_min_threshold": dst_v_min,
            }
            if src_v_min < dst_v_min:
                violations.append(
                    f"Undervoltage fault: Source min ({src_v_min}V) is below destination operating minimum ({dst_v_min}V)."
                )

        # Current capacity vs load check
        src_current_max = contract.get("current_max") or contract.get("source_current_capacity_a")
        dst_current_load = contract.get("load_current_max") or contract.get("destination_current_draw_a")

        if src_current_max is not None and dst_current_load is not None:
            calculation["current_check"] = {
                "source_capacity_a": src_current_max,
                "dest_load_a": dst_current_load,
                "margin_a": round(src_current_max - dst_current_load, 4),
            }
            if src_current_max < dst_current_load:
                violations.append(
                    f"Current capacity exceeded: Source capacity ({src_current_max}A) below load requirement ({dst_current_load}A)."
                )

        # 2. Communication Evaluation
        if interface_type in ["COMMUNICATION", "DATA"]:
            src_protocol = contract.get("protocol") or contract.get("source_protocol")
            dst_protocol = contract.get("destination_protocol") or contract.get("protocol")

            if not src_protocol or not dst_protocol:
                unknowns.append("Communication protocol unspecified for interface.")
            elif str(src_protocol).upper() != str(dst_protocol).upper():
                violations.append(
                    f"Protocol mismatch: Source operates on '{src_protocol}' while destination expects '{dst_protocol}'."
                )

            src_baud = contract.get("baud_rate") or contract.get("source_baud_rate")
            dst_baud = contract.get("destination_baud_rate") or contract.get("baud_rate")
            if src_baud is not None and dst_baud is not None and src_baud != dst_baud:
                violations.append(
                    f"Baud rate mismatch: Source configured at {src_baud} baud, destination at {dst_baud} baud."
                )

        # 3. Logic Level Evaluation
        logic_level_src = contract.get("logic_level_v") or contract.get("source_logic_v")
        logic_level_dst = contract.get("destination_logic_v") or contract.get("destination_logic_level_v")
        if logic_level_src is not None and logic_level_dst is not None:
            calculation["logic_level_check"] = {
                "source_v": logic_level_src,
                "dest_v": logic_level_dst,
            }
            if logic_level_src != logic_level_dst:
                if logic_level_src > logic_level_dst:
                    violations.append(
                        f"Logic level conflict: {logic_level_src}V source connected to {logic_level_dst}V destination without level shifter."
                    )
                else:
                    cautions.append(
                        f"Logic level warning: {logic_level_src}V source may not meet high threshold for {logic_level_dst}V destination."
                    )

        # Required fields check
        required_fields = contract.get("required_parameters", [])
        for req in required_fields:
            if req not in contract:
                unknowns.append(f"Mandatory contract parameter '{req}' is unspecified.")

        # Outcome determination
        if violations:
            status = CompatibilityStatus.INCOMPATIBLE.value
            conclusion = f"Interface incompatible: {'; '.join(violations)}"
        elif unknowns:
            status = CompatibilityStatus.UNKNOWN.value
            conclusion = f"Interface compatibility unknown: {'; '.join(unknowns)}"
        elif cautions:
            status = CompatibilityStatus.PARTIALLY_COMPATIBLE.value
            conclusion = f"Interface partially compatible with warnings: {'; '.join(cautions)}"
        else:
            status = CompatibilityStatus.COMPATIBLE.value
            conclusion = f"Interface fully compatible between {source_subsystem_name} and {dest_subsystem_name}."

        return {
            "rule_id": "SYS-IFACE-001",
            "status": status,
            "conclusion": conclusion,
            "inputs": {
                "interface_name": interface_name,
                "interface_type": interface_type,
                "source_subsystem": source_subsystem_name,
                "destination_subsystem": dest_subsystem_name,
                "contract": contract,
            },
            "calculation": calculation,
            "provenance": {
                "engine": "SystemInterfaceCompatibilityEngine",
                "version": cls.ENGINE_VERSION,
            },
            "unknowns": unknowns,
            "violations": violations,
            "cautions": cautions,
        }
