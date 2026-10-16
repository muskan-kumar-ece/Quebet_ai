from typing import Any, Dict, List, Optional, Set
from app.models.db.system import (
    EngineeringPowerDomain,
    EngineeringSubsystem,
    EngineeringSystemDependency,
    EngineeringSystemInterface,
)


class SystemFailurePropagationEngine:
    """
    Deterministic failure propagation analysis engine.
    Answers: 'If this subsystem or interface fails, what downstream functions are affected?'
    Evaluates physical containment barriers (isolation, fuses, domain separation).
    """
    ENGINE_VERSION = "1.0.0"

    @classmethod
    def simulate_failure(
        cls,
        subsystems: List[EngineeringSubsystem],
        interfaces: List[EngineeringSystemInterface],
        power_domains: List[EngineeringPowerDomain],
        dependencies: List[EngineeringSystemDependency],
        failed_subsystem_id: Optional[str] = None,
        failed_interface_id: Optional[str] = None,
        failure_type: str = "TOTAL_LOSS_OF_FUNCTION",
    ) -> Dict[str, Any]:
        sub_by_id = {s.id: s for s in subsystems}
        iface_by_id = {i.id: i for i in interfaces}
        domain_by_id = {d.id: d for d in power_domains}

        root_cause: Dict[str, Any] = {}
        downstream_affected: Set[str] = set()
        upstream_affected: Set[str] = set()
        affected_interfaces: Set[str] = set()
        affected_domains: Set[str] = set()
        containment_barriers: List[Dict[str, Any]] = []
        loss_of_functions: List[str] = []
        unknowns: List[str] = []

        # Identify starting point
        initial_subsystem_ids: Set[str] = set()
        if failed_subsystem_id:
            sub = sub_by_id.get(failed_subsystem_id)
            if not sub:
                return {
                    "root_cause": {"error": f"Subsystem {failed_subsystem_id} not found"},
                    "upstream_affected_subsystems": [],
                    "downstream_affected_subsystems": [],
                    "affected_interfaces": [],
                    "affected_power_domains": [],
                    "containment_barriers": [],
                    "loss_of_functions": [],
                    "unknowns": ["Target subsystem does not exist."],
                }
            root_cause = {
                "type": "SUBSYSTEM_FAILURE",
                "id": sub.id,
                "name": sub.name,
                "subsystem_type": sub.subsystem_type,
                "failure_type": failure_type,
            }
            initial_subsystem_ids.add(sub.id)
            loss_of_functions.append(f"Subsystem '{sub.name}' [{sub.subsystem_type}] inoperable.")

        elif failed_interface_id:
            iface = iface_by_id.get(failed_interface_id)
            if not iface:
                return {
                    "root_cause": {"error": f"Interface {failed_interface_id} not found"},
                    "upstream_affected_subsystems": [],
                    "downstream_affected_subsystems": [],
                    "affected_interfaces": [],
                    "affected_power_domains": [],
                    "containment_barriers": [],
                    "loss_of_functions": [],
                    "unknowns": ["Target interface does not exist."],
                }
            root_cause = {
                "type": "INTERFACE_FAILURE",
                "id": iface.id,
                "name": iface.name,
                "interface_type": iface.interface_type,
                "failure_type": failure_type,
            }
            affected_interfaces.add(iface.id)
            initial_subsystem_ids.add(iface.destination_subsystem_id)
            loss_of_functions.append(
                f"Interface '{iface.name}' [{iface.interface_type}] connection severed."
            )
        else:
            return {
                "root_cause": {"error": "Neither failed_subsystem_id nor failed_interface_id specified"},
                "upstream_affected_subsystems": [],
                "downstream_affected_subsystems": [],
                "affected_interfaces": [],
                "affected_power_domains": [],
                "containment_barriers": [],
                "loss_of_functions": [],
                "unknowns": ["No failure trigger provided."],
            }

        # 1. Downstream Propagation via Dependencies & Interfaces
        queue = list(initial_subsystem_ids)
        visited = set(initial_subsystem_ids)

        while queue:
            curr_id = queue.pop(0)

            # Check power domains sourced by this subsystem
            for d in power_domains:
                if d.source_subsystem_id == curr_id or d.regulator_subsystem_id == curr_id:
                    if d.id not in affected_domains:
                        affected_domains.add(d.id)
                        loss_of_functions.append(f"Power domain '{d.name}' ({d.nominal_voltage}V) collapsed.")

            # Traverse child subsystems (if parent fails, children fail)
            for s in subsystems:
                if s.parent_subsystem_id == curr_id and s.id not in visited:
                    visited.add(s.id)
                    downstream_affected.add(s.id)
                    loss_of_functions.append(f"Child subsystem '{s.name}' rendered inactive by parent.")
                    queue.append(s.id)

            # Check outgoing interfaces
            for iface in interfaces:
                if iface.source_subsystem_id == curr_id:
                    affected_interfaces.add(iface.id)
                    # Check containment barrier on interface contract
                    contract = iface.contract or {}
                    meta = iface.metadata_ or {}
                    is_isolated = (
                        contract.get("galvanic_isolation")
                        or contract.get("isolated")
                        or meta.get("protection_present")
                    )

                    if is_isolated:
                        containment_barriers.append({
                            "type": "INTERFACE_ISOLATION",
                            "interface_id": iface.id,
                            "interface_name": iface.name,
                            "barrier": "Galvanic or functional isolation prevented propagation",
                            "protected_subsystem_id": iface.destination_subsystem_id,
                            "protected_subsystem_name": sub_by_id.get(iface.destination_subsystem_id, iface).name if iface.destination_subsystem_id in sub_by_id else "UNKNOWN",
                        })
                    else:
                        dest_id = iface.destination_subsystem_id
                        if dest_id not in visited:
                            visited.add(dest_id)
                            downstream_affected.add(dest_id)
                            dest_sub = sub_by_id.get(dest_id)
                            loss_of_functions.append(
                                f"Subsystem '{dest_sub.name if dest_sub else dest_id}' disabled by lost interface '{iface.name}'."
                            )
                            queue.append(dest_id)

            # Check dependencies where target depends on curr_id
            for dep in dependencies:
                if dep.source_subsystem_id == curr_id:
                    target_id = dep.target_subsystem_id
                    if target_id not in visited:
                        visited.add(target_id)
                        downstream_affected.add(target_id)
                        target_sub = sub_by_id.get(target_id)
                        loss_of_functions.append(
                            f"Subsystem '{target_sub.name if target_sub else target_id}' disabled via dependency '{dep.dependency_type}'."
                        )
                        queue.append(target_id)

        # 2. Upstream Propagation (Power short-circuit or fault injection)
        if failure_type in ["SHORT_CIRCUIT", "OVERCURRENT_FAULT", "VOLTAGE_SPIKE"]:
            for initial_id in initial_subsystem_ids:
                for dep in dependencies:
                    if dep.dependency_type == "POWER_DEPENDS_ON" and dep.target_subsystem_id == initial_id:
                        src_id = dep.source_subsystem_id
                        src_sub = sub_by_id.get(src_id)
                        # Check protection on source
                        meta = (src_sub.metadata_ or {}) if src_sub else {}
                        has_fuse = meta.get("fuse_protection") or meta.get("overcurrent_protection")
                        if has_fuse:
                            containment_barriers.append({
                                "type": "UPSTREAM_PROTECTION",
                                "subsystem_id": src_id,
                                "subsystem_name": src_sub.name if src_sub else src_id,
                                "barrier": "Overcurrent/Fuse protection trips, isolating fault",
                            })
                        else:
                            upstream_affected.add(src_id)
                            loss_of_functions.append(
                                f"Upstream supply '{src_sub.name if src_sub else src_id}' subjected to reflected fault."
                            )

        return {
            "root_cause": root_cause,
            "upstream_affected_subsystems": list(upstream_affected),
            "downstream_affected_subsystems": list(downstream_affected),
            "affected_interfaces": list(affected_interfaces),
            "affected_power_domains": list(affected_domains),
            "containment_barriers": containment_barriers,
            "loss_of_functions": loss_of_functions,
            "unknowns": unknowns,
        }
