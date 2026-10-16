from typing import Any, Dict, List, Optional, Set
from app.models.db.system import (
    EngineeringPowerDomain,
    EngineeringSubsystem,
    EngineeringSystemDependency,
)


class PowerTreeEngine:
    """
    Deterministic power distribution tree analysis and current aggregation engine.
    Zero synthetic health scores.
    """
    ENGINE_VERSION = "1.0.0"

    @classmethod
    def analyze_power_tree(
        cls,
        subsystems: List[EngineeringSubsystem],
        power_domains: List[EngineeringPowerDomain],
        dependencies: List[EngineeringSystemDependency],
    ) -> Dict[str, Any]:
        subsystem_by_id = {s.id: s for s in subsystems}
        domains_by_id = {d.id: d for d in power_domains}
        findings: List[Dict[str, Any]] = []

        # 1. Map power dependencies
        # Target depends on Source for POWER
        power_deps = [d for d in dependencies if d.dependency_type == "POWER_DEPENDS_ON"]
        
        # Build adjacency
        downstream_map: Dict[str, List[str]] = {s.id: [] for s in subsystems}
        upstream_map: Dict[str, List[str]] = {s.id: [] for s in subsystems}

        for dep in power_deps:
            if dep.source_subsystem_id in downstream_map and dep.target_subsystem_id in upstream_map:
                downstream_map[dep.source_subsystem_id].append(dep.target_subsystem_id)
                upstream_map[dep.target_subsystem_id].append(dep.source_subsystem_id)

        # 2. Check for circular power paths
        for sub_id in subsystems:
            visited: Set[str] = set()
            stack = [sub_id.id]
            while stack:
                curr = stack.pop()
                if curr in visited:
                    findings.append({
                        "rule_id": "SYS-PWR-004",
                        "category": "POWER",
                        "severity": "CRITICAL",
                        "title": f"Circular power distribution detected involving subsystem '{subsystem_by_id.get(curr, curr).name}'",
                        "description": "A closed loop exists in the power dependency tree, creating potential latch-up or uncontrolled feedback.",
                        "affected_subsystems": [curr],
                        "affected_interfaces": [],
                        "affected_power_domains": [],
                        "inputs": {"subsystem_id": curr},
                        "calculation": {"loop_detected": True},
                        "provenance": {"engine": "PowerTreeEngine", "version": cls.ENGINE_VERSION},
                        "unknowns": [],
                    })
                    break
                visited.add(curr)
                stack.extend(downstream_map.get(curr, []))

        # 3. Check domain sourcing and capacity
        domain_loads: Dict[str, float] = {}
        for domain in power_domains:
            domain_loads[domain.id] = 0.0

            # Find source subsystem
            source_sub = subsystem_by_id.get(domain.source_subsystem_id)
            if not source_sub:
                findings.append({
                    "rule_id": "SYS-PWR-001",
                    "category": "POWER",
                    "severity": "CRITICAL",
                    "title": f"Power domain '{domain.name}' has invalid or missing source subsystem",
                    "description": f"Domain references source subsystem ID '{domain.source_subsystem_id}' which does not exist.",
                    "affected_subsystems": [],
                    "affected_interfaces": [],
                    "affected_power_domains": [domain.id],
                    "inputs": {"power_domain_id": domain.id},
                    "calculation": {},
                    "provenance": {"engine": "PowerTreeEngine", "version": cls.ENGINE_VERSION},
                    "unknowns": [],
                })

            # Check metadata for consumer loads
            meta = domain.metadata_ or {}
            load_current_a = meta.get("estimated_load_a", 0.0)
            domain_loads[domain.id] = load_current_a

            if domain.current_capacity_a is not None and load_current_a > domain.current_capacity_a:
                findings.append({
                    "rule_id": "SYS-PWR-002",
                    "category": "POWER",
                    "severity": "CRITICAL",
                    "title": f"Overloaded power domain '{domain.name}'",
                    "description": (
                        f"Aggregate downstream load ({load_current_a}A) exceeds domain rated capacity ({domain.current_capacity_a}A)."
                    ),
                    "affected_subsystems": [domain.source_subsystem_id],
                    "affected_interfaces": [],
                    "affected_power_domains": [domain.id],
                    "inputs": {
                        "nominal_voltage": domain.nominal_voltage,
                        "capacity_a": domain.current_capacity_a,
                        "load_a": load_current_a,
                    },
                    "calculation": {
                        "margin_a": round(domain.current_capacity_a - load_current_a, 4),
                        "overload_ratio": round(load_current_a / domain.current_capacity_a, 2),
                    },
                    "provenance": {"engine": "PowerTreeEngine", "version": cls.ENGINE_VERSION},
                    "unknowns": [],
                })

        # 4. Check for orphan subsystems requiring power
        for sub in subsystems:
            if sub.subsystem_type in ["PROCESSING", "SENSING", "COMMUNICATION", "ACTUATION", "USER_INTERFACE"]:
                # Should have at least one upstream power source or associated domain
                has_power = bool(upstream_map.get(sub.id))
                # Check if it has a domain assignment in metadata
                meta = sub.metadata_ or {}
                if meta.get("power_domain_id"):
                    has_power = True

                if not has_power:
                    findings.append({
                        "rule_id": "SYS-PWR-003",
                        "category": "POWER",
                        "severity": "WARNING",
                        "title": f"Subsystem '{sub.name}' has no defined power supply path",
                        "description": (
                            f"Active subsystem of type '{sub.subsystem_type}' is missing upstream POWER_DEPENDS_ON relationship or power domain assignment."
                        ),
                        "affected_subsystems": [sub.id],
                        "affected_interfaces": [],
                        "affected_power_domains": [],
                        "inputs": {"subsystem_id": sub.id, "subsystem_type": sub.subsystem_type},
                        "calculation": {},
                        "provenance": {"engine": "PowerTreeEngine", "version": cls.ENGINE_VERSION},
                        "unknowns": ["Supply rail and operating voltage are uncharacterized."],
                    })

        # Tree summary
        tree_summary = {
            "total_domains": len(power_domains),
            "domains": [
                {
                    "id": d.id,
                    "name": d.name,
                    "nominal_voltage": d.nominal_voltage,
                    "capacity_a": d.current_capacity_a,
                    "aggregated_load_a": domain_loads.get(d.id, 0.0),
                    "source_subsystem_name": subsystem_by_id.get(d.source_subsystem_id, d).name if d.source_subsystem_id in subsystem_by_id else "UNKNOWN",
                }
                for d in power_domains
            ],
            "total_power_dependencies": len(power_deps),
        }

        return {
            "summary": tree_summary,
            "findings": findings,
        }
