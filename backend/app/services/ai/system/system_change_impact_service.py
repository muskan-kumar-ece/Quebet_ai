from typing import Any, Dict, List, Set
from app.models.db.system import (
    EngineeringPowerDomain,
    EngineeringSubsystem,
    EngineeringSystemAnalysis,
    EngineeringSystemDependency,
    EngineeringSystemInterface,
    EngineeringSystemRequirement,
)


class SystemChangeImpactService:
    """
    Deterministic blast-radius calculation for subsystem and interface mutations.
    Preserves historical analysis immutability while identifying affected dependencies.
    """

    @classmethod
    def calculate_impact(
        cls,
        target_type: str,
        target_id: str,
        proposed_change: Dict[str, Any],
        subsystems: List[EngineeringSubsystem],
        interfaces: List[EngineeringSystemInterface],
        power_domains: List[EngineeringPowerDomain],
        dependencies: List[EngineeringSystemDependency],
        analyses: List[EngineeringSystemAnalysis],
        requirements: List[EngineeringSystemRequirement],
    ) -> Dict[str, Any]:
        sub_by_id = {s.id: s for s in subsystems}
        affected_subsystems: Set[str] = set()
        affected_interfaces: Set[str] = set()
        affected_domains: Set[str] = set()
        affected_reqs: Set[str] = set()

        if target_type.upper() == "SUBSYSTEM":
            affected_subsystems.add(target_id)
            # Find interfaces where target_id is source or destination
            for iface in interfaces:
                if iface.source_subsystem_id == target_id or iface.destination_subsystem_id == target_id:
                    affected_interfaces.add(iface.id)
                    affected_subsystems.add(iface.source_subsystem_id)
                    affected_subsystems.add(iface.destination_subsystem_id)

            # Find dependencies
            for dep in dependencies:
                if dep.source_subsystem_id == target_id or dep.target_subsystem_id == target_id:
                    affected_subsystems.add(dep.source_subsystem_id)
                    affected_subsystems.add(dep.target_subsystem_id)

            # Find power domains
            for d in power_domains:
                if d.source_subsystem_id == target_id or d.regulator_subsystem_id == target_id:
                    affected_domains.add(d.id)

        elif target_type.upper() == "INTERFACE":
            affected_interfaces.add(target_id)
            iface = next((i for i in interfaces if i.id == target_id), None)
            if iface:
                affected_subsystems.add(iface.source_subsystem_id)
                affected_subsystems.add(iface.destination_subsystem_id)

        elif target_type.upper() == "POWER_DOMAIN":
            affected_domains.add(target_id)
            domain = next((d for d in power_domains if d.id == target_id), None)
            if domain:
                affected_subsystems.add(domain.source_subsystem_id)
                if domain.regulator_subsystem_id:
                    affected_subsystems.add(domain.regulator_subsystem_id)

        # Check requirements related to affected subsystems/domains
        for req in requirements:
            req_constraints = req.constraints or {}
            target_subs = req_constraints.get("subsystems", [])
            target_doms = req_constraints.get("power_domains", [])
            if any(s in affected_subsystems for s in target_subs) or any(d in affected_domains for d in target_doms):
                affected_reqs.add(req.id)

        # All existing analyses for the system will become STALE when changes are committed
        affected_analyses = [a.id for a in analyses]

        target_name = (
            sub_by_id.get(target_id).name
            if target_id in sub_by_id
            else target_id
        )

        blast_summary = (
            f"Modifying {target_type} '{target_name}' affects {len(affected_subsystems)} subsystems, "
            f"{len(affected_interfaces)} boundary interfaces, {len(affected_domains)} power domains, "
            f"and renders {len(affected_analyses)} historical system analyses STALE."
        )

        return {
            "target_id": target_id,
            "target_type": target_type,
            "affected_subsystems": list(affected_subsystems),
            "affected_interfaces": list(affected_interfaces),
            "affected_power_domains": list(affected_domains),
            "affected_analyses": affected_analyses,
            "affected_verification_requirements": list(affected_reqs),
            "stale_analyses_count": len(affected_analyses),
            "blast_radius_summary": blast_summary,
        }
