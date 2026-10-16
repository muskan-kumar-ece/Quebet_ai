import hashlib
import json
from typing import Any, Dict, List, Set
from app.models.db.system import (
    EngineeringModeTransition,
    EngineeringOperatingMode,
    EngineeringPowerDomain,
    EngineeringSubsystem,
    EngineeringSystem,
    EngineeringSystemDependency,
    EngineeringSystemInterface,
    EngineeringSystemRequirement,
)
from app.services.ai.system.interface_compatibility_engine import (
    CompatibilityStatus,
    SystemInterfaceCompatibilityEngine,
)
from app.services.ai.system.power_tree_service import PowerTreeEngine


class SystemAnalysisService:
    """
    Comprehensive deterministic system-level analysis service.
    Orchestrates power trees, interface contracts, dependency graphs, operating modes, and requirements.
    Zero arbitrary health/risk scores.
    """
    ENGINE_VERSIONS = {
        "SystemAnalysisEngine": "1.0.0",
        "SystemInterfaceCompatibilityEngine": SystemInterfaceCompatibilityEngine.ENGINE_VERSION,
        "PowerTreeEngine": PowerTreeEngine.ENGINE_VERSION,
    }
    RULE_SET_VERSION = "QUEBET-SYSTEM-001 v1.0"

    @classmethod
    def analyze_system(
        cls,
        system: EngineeringSystem,
        subsystems: List[EngineeringSubsystem],
        interfaces: List[EngineeringSystemInterface],
        power_domains: List[EngineeringPowerDomain],
        dependencies: List[EngineeringSystemDependency],
        operating_modes: List[EngineeringOperatingMode],
        mode_transitions: List[EngineeringModeTransition],
        requirements: List[EngineeringSystemRequirement],
        circuit_revisions: Dict[str, int],
    ) -> Dict[str, Any]:
        sub_by_id = {s.id: s for s in subsystems}
        all_findings: List[Dict[str, Any]] = []

        # 1. Interface Compatibility Analysis
        for iface in interfaces:
            src_name = sub_by_id.get(iface.source_subsystem_id, iface).name if iface.source_subsystem_id in sub_by_id else "UNKNOWN"
            dst_name = sub_by_id.get(iface.destination_subsystem_id, iface).name if iface.destination_subsystem_id in sub_by_id else "UNKNOWN"

            eval_res = SystemInterfaceCompatibilityEngine.evaluate(
                interface_name=iface.name,
                interface_type=iface.interface_type,
                source_subsystem_name=src_name,
                dest_subsystem_name=dst_name,
                contract=iface.contract,
            )

            if eval_res["status"] == CompatibilityStatus.INCOMPATIBLE.value:
                all_findings.append({
                    "rule_id": "SYS-IFACE-001",
                    "category": "INTERFACE",
                    "severity": "CRITICAL",
                    "title": f"Incompatible interface boundary '{iface.name}'",
                    "description": eval_res["conclusion"],
                    "affected_subsystems": [iface.source_subsystem_id, iface.destination_subsystem_id],
                    "affected_interfaces": [iface.id],
                    "affected_power_domains": [],
                    "inputs": eval_res["inputs"],
                    "calculation": eval_res["calculation"],
                    "provenance": eval_res["provenance"],
                    "unknowns": eval_res["unknowns"],
                })
            elif eval_res["status"] == CompatibilityStatus.UNKNOWN.value:
                all_findings.append({
                    "rule_id": "SYS-IFACE-002",
                    "category": "INTERFACE",
                    "severity": "WARNING",
                    "title": f"Uncharacterized interface boundary '{iface.name}'",
                    "description": eval_res["conclusion"],
                    "affected_subsystems": [iface.source_subsystem_id, iface.destination_subsystem_id],
                    "affected_interfaces": [iface.id],
                    "affected_power_domains": [],
                    "inputs": eval_res["inputs"],
                    "calculation": eval_res["calculation"],
                    "provenance": eval_res["provenance"],
                    "unknowns": eval_res["unknowns"],
                })
            elif eval_res["status"] == CompatibilityStatus.PARTIALLY_COMPATIBLE.value:
                all_findings.append({
                    "rule_id": "SYS-IFACE-003",
                    "category": "INTERFACE",
                    "severity": "WARNING",
                    "title": f"Marginal or partially compatible interface '{iface.name}'",
                    "description": eval_res["conclusion"],
                    "affected_subsystems": [iface.source_subsystem_id, iface.destination_subsystem_id],
                    "affected_interfaces": [iface.id],
                    "affected_power_domains": [],
                    "inputs": eval_res["inputs"],
                    "calculation": eval_res["calculation"],
                    "provenance": eval_res["provenance"],
                    "unknowns": eval_res["unknowns"],
                })

        # 2. Power Tree Analysis
        power_tree_res = PowerTreeEngine.analyze_power_tree(
            subsystems=subsystems,
            power_domains=power_domains,
            dependencies=dependencies,
        )
        all_findings.extend(power_tree_res["findings"])

        # 3. Dependency Graph & Cycle Detection
        adj: Dict[str, List[str]] = {s.id: [] for s in subsystems}
        for dep in dependencies:
            if dep.source_subsystem_id in adj and dep.target_subsystem_id in adj:
                adj[dep.source_subsystem_id].append(dep.target_subsystem_id)

        # Detect circular dependencies across all types
        for s in subsystems:
            visited: Set[str] = set()
            stack = [s.id]
            while stack:
                curr = stack.pop()
                if curr in visited:
                    all_findings.append({
                        "rule_id": "SYS-DEP-001",
                        "category": "DEPENDENCY",
                        "severity": "CRITICAL",
                        "title": f"Circular system dependency involving '{sub_by_id[curr].name}'",
                        "description": "Cyclic functional or electrical dependency chain detected.",
                        "affected_subsystems": [curr],
                        "affected_interfaces": [],
                        "affected_power_domains": [],
                        "inputs": {"subsystem_id": curr},
                        "calculation": {"cycle_detected": True},
                        "provenance": {"engine": "SystemAnalysisEngine", "version": "1.0.0"},
                        "unknowns": [],
                    })
                    break
                visited.add(curr)
                stack.extend(adj.get(curr, []))

        # 4. Operating Modes & Transitions Analysis
        mode_by_id = {m.id: m for m in operating_modes}
        for mode in operating_modes:
            # Check if active subsystems exist
            for sub_id in mode.active_subsystem_ids:
                if sub_id not in sub_by_id:
                    all_findings.append({
                        "rule_id": "SYS-MODE-001",
                        "category": "OPERATING_MODE",
                        "severity": "CRITICAL",
                        "title": f"Mode '{mode.name}' references non-existent active subsystem",
                        "description": f"Subsystem ID '{sub_id}' configured as active in mode '{mode.name}' does not exist.",
                        "affected_subsystems": [],
                        "affected_interfaces": [],
                        "affected_power_domains": [],
                        "inputs": {"mode_id": mode.id, "subsystem_id": sub_id},
                        "calculation": {},
                        "provenance": {"engine": "SystemAnalysisEngine", "version": "1.0.0"},
                        "unknowns": [],
                    })

        for trans in mode_transitions:
            if trans.source_mode_id not in mode_by_id or trans.destination_mode_id not in mode_by_id:
                all_findings.append({
                    "rule_id": "SYS-MODE-002",
                    "category": "OPERATING_MODE",
                    "severity": "CRITICAL",
                    "title": f"Invalid mode transition trigger '{trans.trigger}'",
                    "description": "Transition references non-existent source or destination operating mode.",
                    "affected_subsystems": [],
                    "affected_interfaces": [],
                    "affected_power_domains": [],
                    "inputs": {
                        "source_mode_id": trans.source_mode_id,
                        "destination_mode_id": trans.destination_mode_id,
                    },
                    "calculation": {},
                    "provenance": {"engine": "SystemAnalysisEngine", "version": "1.0.0"},
                    "unknowns": [],
                })

        # 5. System Requirements Evaluation
        for req in requirements:
            constraints = req.constraints or {}
            # E.g. max system power consumption
            if "max_system_power_w" in constraints:
                max_w = constraints["max_system_power_w"]
                # Sum from domains or metadata
                total_power = sum(
                    d.nominal_voltage * (d.metadata_.get("estimated_load_a", 0.0) if d.metadata_ else 0.0)
                    for d in power_domains
                )
                if total_power > max_w:
                    all_findings.append({
                        "rule_id": "SYS-REQ-001",
                        "category": "RELIABILITY",
                        "severity": "CRITICAL",
                        "title": f"System requirement '{req.code}' violated: Power limit exceeded",
                        "description": f"Calculated system power ({round(total_power, 2)}W) exceeds specified ceiling ({max_w}W).",
                        "affected_subsystems": [],
                        "affected_interfaces": [],
                        "affected_power_domains": [d.id for d in power_domains],
                        "inputs": {"power_limit_w": max_w, "total_power_w": total_power},
                        "calculation": {"over_budget_w": round(total_power - max_w, 2)},
                        "provenance": {"engine": "SystemAnalysisEngine", "version": "1.0.0"},
                        "unknowns": [],
                    })

        # Calculate immutable inputs digest
        canonical_state = {
            "system_id": system.id,
            "revision": system.revision,
            "subsystems": [{"id": s.id, "revision": s.revision} for s in sorted(subsystems, key=lambda x: x.id)],
            "interfaces": [{"id": i.id, "contract": i.contract} for i in sorted(interfaces, key=lambda x: x.id)],
            "power_domains": [{"id": d.id, "v": d.nominal_voltage} for d in sorted(power_domains, key=lambda x: x.id)],
            "circuit_revisions": circuit_revisions,
        }
        encoded = json.dumps(canonical_state, sort_keys=True).encode("utf-8")
        inputs_digest = hashlib.sha256(encoded).hexdigest()

        subsystem_revisions = {s.id: s.revision for s in subsystems}

        return {
            "inputs_digest": inputs_digest,
            "engine_versions": cls.ENGINE_VERSIONS,
            "rule_set_version": cls.RULE_SET_VERSION,
            "subsystem_revisions": subsystem_revisions,
            "circuit_revisions": circuit_revisions,
            "power_tree_summary": power_tree_res["summary"],
            "findings": all_findings,
        }
