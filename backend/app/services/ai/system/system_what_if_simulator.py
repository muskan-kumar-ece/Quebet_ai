import copy
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.services.ai.system.failure_propagation_engine import SystemFailurePropagationEngine
from app.services.ai.system.interface_compatibility_engine import (
    CompatibilityStatus,
    SystemInterfaceCompatibilityEngine,
)
from app.services.ai.system.power_tree_service import PowerTreeEngine


class SimObj:
    """Helper wrapper to provide attribute access for dicts in engines."""
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return self.__dict__.get(name)

    def __getitem__(self, name):
        return self.__dict__.get(name)


class SystemWhatIfSimulator:
    """
    In-memory sandboxed what-if simulator for system architecture.
    Operates strictly on deep-cloned architecture graphs.
    NEVER mutates the persistent database.
    """

    def __init__(
        self,
        subsystems: List[Dict[str, Any]],
        interfaces: List[Dict[str, Any]],
        power_domains: List[Dict[str, Any]],
        dependencies: List[Dict[str, Any]],
        operating_modes: List[Dict[str, Any]],
        requirements: List[Dict[str, Any]],
    ):
        # Deep clone all input entities to guarantee complete sandbox isolation
        self.subsystems = [copy.deepcopy(s) for s in subsystems]
        self.interfaces = [copy.deepcopy(i) for i in interfaces]
        self.power_domains = [copy.deepcopy(p) for p in power_domains]
        self.dependencies = [copy.deepcopy(d) for d in dependencies]
        self.operating_modes = [copy.deepcopy(m) for m in operating_modes]
        self.requirements = [copy.deepcopy(r) for r in requirements]

        self.applied_operations: List[Dict[str, Any]] = []
        self.errors: List[str] = []
        self.unknowns: List[str] = []

    def apply_operation(self, op_type: str, payload: Dict[str, Any]) -> bool:
        """
        Executes a discrete structural mutation on the in-memory cloned graph.
        """
        try:
            if op_type == "ADD_SUBSYSTEM":
                sub_id = payload.get("id") or f"sub-whatif-{uuid.uuid4().hex[:8]}"
                new_sub = {
                    "id": sub_id,
                    "name": payload.get("name", "New Subsystem"),
                    "subsystem_type": payload.get("subsystem_type", "OTHER"),
                    "parent_subsystem_id": payload.get("parent_subsystem_id"),
                    "circuit_id": payload.get("circuit_id"),
                    "revision": 1,
                    "status": "ACTIVE",
                    "metadata": payload.get("metadata", {}),
                }
                self.subsystems.append(new_sub)
                self.applied_operations.append({"op_type": op_type, "payload": new_sub})
                return True

            elif op_type == "REMOVE_SUBSYSTEM":
                sub_id = payload.get("subsystem_id") or payload.get("id")
                if not sub_id:
                    self.errors.append("REMOVE_SUBSYSTEM missing subsystem_id")
                    return False
                self.subsystems = [s for s in self.subsystems if s["id"] != sub_id]
                # Cascade remove bound interfaces and dependencies in sandbox
                self.interfaces = [
                    i for i in self.interfaces
                    if i.get("source_subsystem_id") != sub_id and i.get("destination_subsystem_id") != sub_id
                ]
                self.dependencies = [
                    d for d in self.dependencies
                    if d.get("source_subsystem_id") != sub_id and d.get("target_subsystem_id") != sub_id
                ]
                self.applied_operations.append({"op_type": op_type, "payload": payload})
                return True

            elif op_type == "REPLACE_SUBSYSTEM":
                target_id = payload.get("target_subsystem_id") or payload.get("id")
                target = next((s for s in self.subsystems if s["id"] == target_id), None)
                if not target:
                    self.errors.append(f"REPLACE_SUBSYSTEM target {target_id} not found")
                    return False
                target["name"] = payload.get("name", target["name"])
                target["subsystem_type"] = payload.get("subsystem_type", target["subsystem_type"])
                target["circuit_id"] = payload.get("circuit_id", target.get("circuit_id"))
                if "metadata" in payload:
                    target["metadata"] = {**target.get("metadata", {}), **payload["metadata"]}
                self.applied_operations.append({"op_type": op_type, "payload": payload})
                return True

            elif op_type == "UPDATE_SUBSYSTEM":
                sub_id = payload.get("subsystem_id") or payload.get("id")
                target = next((s for s in self.subsystems if s["id"] == sub_id), None)
                if not target:
                    self.errors.append(f"UPDATE_SUBSYSTEM target {sub_id} not found")
                    return False
                for k in ["name", "subsystem_type", "parent_subsystem_id", "circuit_id", "status"]:
                    if k in payload:
                        target[k] = payload[k]
                self.applied_operations.append({"op_type": op_type, "payload": payload})
                return True

            elif op_type == "ADD_INTERFACE":
                iface_id = payload.get("id") or f"iface-whatif-{uuid.uuid4().hex[:8]}"
                new_iface = {
                    "id": iface_id,
                    "name": payload.get("name", "New Interface"),
                    "interface_type": payload.get("interface_type", "DATA"),
                    "source_subsystem_id": payload.get("source_subsystem_id"),
                    "destination_subsystem_id": payload.get("destination_subsystem_id"),
                    "contract": payload.get("contract", {}),
                    "status": "ACTIVE",
                    "metadata": payload.get("metadata", {}),
                }
                self.interfaces.append(new_iface)
                self.applied_operations.append({"op_type": op_type, "payload": new_iface})
                return True

            elif op_type == "REMOVE_INTERFACE":
                iface_id = payload.get("interface_id") or payload.get("id")
                self.interfaces = [i for i in self.interfaces if i["id"] != iface_id]
                self.applied_operations.append({"op_type": op_type, "payload": payload})
                return True

            elif op_type == "UPDATE_INTERFACE":
                iface_id = payload.get("interface_id") or payload.get("id")
                target = next((i for i in self.interfaces if i["id"] == iface_id), None)
                if not target:
                    self.errors.append(f"UPDATE_INTERFACE target {iface_id} not found")
                    return False
                if "contract" in payload:
                    target["contract"] = {**target.get("contract", {}), **payload["contract"]}
                for k in ["name", "interface_type", "status"]:
                    if k in payload:
                        target[k] = payload[k]
                self.applied_operations.append({"op_type": op_type, "payload": payload})
                return True

            elif op_type == "ADD_POWER_DOMAIN":
                domain_id = payload.get("id") or f"dom-whatif-{uuid.uuid4().hex[:8]}"
                new_domain = {
                    "id": domain_id,
                    "name": payload.get("name", "New Rail"),
                    "nominal_voltage": payload.get("nominal_voltage", 3.3),
                    "min_voltage": payload.get("min_voltage"),
                    "max_voltage": payload.get("max_voltage"),
                    "source_subsystem_id": payload.get("source_subsystem_id"),
                    "regulator_subsystem_id": payload.get("regulator_subsystem_id"),
                    "current_capacity_a": payload.get("current_capacity_a"),
                    "status": "ACTIVE",
                    "metadata": payload.get("metadata", {}),
                }
                self.power_domains.append(new_domain)
                self.applied_operations.append({"op_type": op_type, "payload": new_domain})
                return True

            elif op_type == "UPDATE_POWER_DOMAIN":
                domain_id = payload.get("domain_id") or payload.get("id")
                target = next((p for p in self.power_domains if p["id"] == domain_id), None)
                if not target:
                    self.errors.append(f"UPDATE_POWER_DOMAIN target {domain_id} not found")
                    return False
                for k in ["name", "nominal_voltage", "min_voltage", "max_voltage", "current_capacity_a", "source_subsystem_id", "regulator_subsystem_id"]:
                    if k in payload:
                        target[k] = payload[k]
                self.applied_operations.append({"op_type": op_type, "payload": payload})
                return True

            elif op_type == "ADD_DEPENDENCY":
                dep_id = payload.get("id") or f"dep-whatif-{uuid.uuid4().hex[:8]}"
                new_dep = {
                    "id": dep_id,
                    "source_subsystem_id": payload.get("source_subsystem_id"),
                    "target_subsystem_id": payload.get("target_subsystem_id"),
                    "dependency_type": payload.get("dependency_type", "POWER_DEPENDS_ON"),
                    "status": "ACTIVE",
                    "metadata": payload.get("metadata", {}),
                }
                self.dependencies.append(new_dep)
                self.applied_operations.append({"op_type": op_type, "payload": new_dep})
                return True

            else:
                self.applied_operations.append({"op_type": op_type, "payload": payload})
                return True

        except Exception as e:
            self.errors.append(f"Operation {op_type} failed: {str(e)}")
            return False

    def simulate(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Applies a batch of operations and runs deterministic re-analysis on the mutated in-memory graph.
        """
        for op in operations:
            op_type = op.get("op_type")
            payload = op.get("payload", {})
            success = self.apply_operation(op_type, payload)
            if not success:
                return {
                    "status": "INVALID",
                    "errors": self.errors,
                    "applied_operations": self.applied_operations,
                    "unknowns": self.unknowns,
                }

        # 1. Interface compatibility
        iface_evaluations = []
        for iface in self.interfaces:
            src = next((s for s in self.subsystems if s["id"] == iface.get("source_subsystem_id")), None)
            dst = next((s for s in self.subsystems if s["id"] == iface.get("destination_subsystem_id")), None)
            if not src or not dst:
                iface_evaluations.append({
                    "interface_id": iface["id"],
                    "status": "UNKNOWN",
                    "unknowns": ["missing_subsystem_endpoint"],
                })
                self.unknowns.append(f"interface_{iface['id']}_missing_endpoint")
                continue

            contract = iface.get("contract", {})
            eval_res = SystemInterfaceCompatibilityEngine.evaluate(
                interface_name=iface.get("name", "unnamed"),
                interface_type=iface.get("interface_type", "DATA"),
                source_subsystem_name=src.get("name", "SRC"),
                dest_subsystem_name=dst.get("name", "DST"),
                contract=contract,
            )
            iface_evaluations.append({
                "interface_id": iface["id"],
                "status": eval_res["status"],
                "findings": eval_res.get("findings", []),
                "unknowns": eval_res.get("unknowns", []),
            })
            self.unknowns.extend(eval_res.get("unknowns", []))

        # Convert to SimObj for attribute access
        sub_objs = [SimObj(**s) for s in self.subsystems]
        dom_objs = [SimObj(**p) for p in self.power_domains]
        dep_objs = [SimObj(**d) for d in self.dependencies]
        iface_objs = [SimObj(**i) for i in self.interfaces]

        # 2. Power Tree Analysis
        power_eval = PowerTreeEngine.analyze_power_tree(sub_objs, dom_objs, dep_objs)

        # 3. Failure Propagation sample
        failure_eval = {}
        if self.subsystems:
            sample_sub_id = self.subsystems[0]["id"]
            failure_eval = SystemFailurePropagationEngine.simulate_failure(
                sub_objs, iface_objs, dom_objs, dep_objs, failed_subsystem_id=sample_sub_id
            )

        status = "VALIDATED" if not self.errors else "INVALID"
        if any(e["status"] == "INCOMPATIBLE" for e in iface_evaluations):
            status = "BLOCKED"

        return {
            "status": status,
            "errors": self.errors,
            "applied_operations": self.applied_operations,
            "interface_evaluations": iface_evaluations,
            "power_evaluation": power_eval,
            "failure_evaluation": failure_eval,
            "subsystems_count": len(self.subsystems),
            "interfaces_count": len(self.interfaces),
            "power_domains_count": len(self.power_domains),
            "unknowns": list(set(self.unknowns)),
        }
