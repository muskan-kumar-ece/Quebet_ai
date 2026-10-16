from typing import Any, Dict, List, Optional


class VerificationImpactService:
    """
    Determines how an architectural candidate affects Wave 5 verification obligations.
    Outcomes: UNCHANGED, NEW_VERIFICATION_REQUIRED, VERIFICATION_INVALIDATED, VERIFICATION_REDUCED, UNKNOWN.
    A modified architecture never retains old verification automatically.
    """

    def evaluate_verification_impact(
        self,
        candidate_operations: List[Dict[str, Any]],
        candidate_strategy: str,
        existing_subsystems: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        impacts: List[Dict[str, Any]] = []

        for op in candidate_operations:
            op_type = op.get("op_type")
            payload = op.get("payload", {})

            if op_type in ["ADD_SUBSYSTEM", "ADD_INTERFACE", "ADD_POWER_DOMAIN"]:
                name = payload.get("name", "New Item")
                impacts.append({
                    "target_type": op_type.replace("ADD_", ""),
                    "target_name": name,
                    "impact": "NEW_VERIFICATION_REQUIRED",
                    "reason": f"New architectural element '{name}' requires physical bench test points and functional evidence.",
                })

            elif op_type in ["REPLACE_SUBSYSTEM", "UPDATE_SUBSYSTEM", "UPDATE_POWER_DOMAIN", "UPDATE_INTERFACE"]:
                target_id = payload.get("subsystem_id") or payload.get("domain_id") or payload.get("interface_id") or payload.get("id")
                impacts.append({
                    "target_type": op_type.replace("UPDATE_", "").replace("REPLACE_", ""),
                    "target_id": target_id,
                    "impact": "VERIFICATION_INVALIDATED",
                    "reason": f"Modification of {target_id} invalidates prior calibration and test point measurements.",
                })

            elif op_type in ["REMOVE_SUBSYSTEM", "REMOVE_INTERFACE"]:
                target_id = payload.get("subsystem_id") or payload.get("interface_id") or payload.get("id")
                impacts.append({
                    "target_type": op_type.replace("REMOVE_", ""),
                    "target_id": target_id,
                    "impact": "VERIFICATION_REDUCED",
                    "reason": f"Removed element {target_id} no longer requires active verification requirements.",
                })

        if not impacts:
            impacts.append({
                "target_type": "SYSTEM",
                "impact": "UNCHANGED",
                "reason": "Candidate operations do not modify active test points or verified boundaries.",
            })

        return impacts
