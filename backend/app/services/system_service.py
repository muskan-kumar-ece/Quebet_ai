from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.system import (
    EngineeringModeTransition,
    EngineeringOperatingMode,
    EngineeringPowerDomain,
    EngineeringSubsystem,
    EngineeringSystem,
    EngineeringSystemAnalysis,
    EngineeringSystemDependency,
    EngineeringSystemFinding,
    EngineeringSystemInterface,
    EngineeringSystemRequirement,
    EngineeringSystemSnapshot,
)
from app.repositories.circuit_repo import CircuitRepository
from app.repositories.system_repo import SystemRepository
from app.services.ai.system.failure_propagation_engine import SystemFailurePropagationEngine
from app.services.ai.system.system_analysis_service import SystemAnalysisService
from app.services.ai.system.system_change_impact_service import SystemChangeImpactService


class SystemService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SystemRepository(db)
        self.circuit_repo = CircuitRepository()

    async def get_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
        load_relations: bool = False,
    ) -> Optional[EngineeringSystem]:
        return await self.repo.get_system(system_id, tenant_id=tenant_id, load_relations=load_relations)

    async def get_systems_for_project(
        self,
        project_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystem]:
        return await self.repo.get_systems_for_project(project_id, tenant_id=tenant_id)

    async def create_system(
        self,
        project_id: str,
        name: str,
        created_by: str,
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringSystem:
        return await self.repo.create_system(
            project_id=project_id,
            name=name,
            created_by=created_by,
            description=description,
            tenant_id=tenant_id,
            metadata_=metadata_,
        )

    async def update_system(
        self,
        system_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSystem]:
        return await self.repo.update_system(system_id, updates, tenant_id=tenant_id)

    # Subsystem management
    async def create_subsystem(
        self,
        system_id: str,
        name: str,
        subsystem_type: str = "OTHER",
        parent_subsystem_id: Optional[str] = None,
        circuit_id: Optional[str] = None,
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringSubsystem:
        # Verify circuit ownership if provided
        if circuit_id:
            circuit = await self.circuit_repo.get_by_id(self.db, circuit_id, tenant_id=tenant_id)
            if not circuit:
                raise ValueError(f"Circuit {circuit_id} not found or inaccessible")

        return await self.repo.create_subsystem(
            system_id=system_id,
            name=name,
            subsystem_type=subsystem_type,
            parent_subsystem_id=parent_subsystem_id,
            circuit_id=circuit_id,
            description=description,
            tenant_id=tenant_id,
            metadata_=metadata_,
        )

    async def get_subsystems(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSubsystem]:
        return await self.repo.get_subsystems(system_id, tenant_id=tenant_id)

    async def update_subsystem(
        self,
        subsystem_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSubsystem]:
        return await self.repo.update_subsystem(subsystem_id, updates, tenant_id=tenant_id)

    async def delete_subsystem(
        self,
        subsystem_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        return await self.repo.delete_subsystem(subsystem_id, tenant_id=tenant_id)

    # Interfaces
    async def get_interfaces(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemInterface]:
        return await self.repo.get_interfaces(system_id, tenant_id=tenant_id)

    async def create_interface(
        self,
        system_id: str,
        name: str,
        source_subsystem_id: str,
        destination_subsystem_id: str,
        interface_type: str = "OTHER",
        contract: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringSystemInterface:
        return await self.repo.create_interface(
            system_id=system_id,
            name=name,
            source_subsystem_id=source_subsystem_id,
            destination_subsystem_id=destination_subsystem_id,
            interface_type=interface_type,
            contract=contract,
            description=description,
            tenant_id=tenant_id,
            metadata_=metadata_,
        )

    async def update_interface(
        self,
        interface_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSystemInterface]:
        return await self.repo.update_interface(interface_id, updates, tenant_id=tenant_id)

    async def delete_interface(
        self,
        interface_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        return await self.repo.delete_interface(interface_id, tenant_id=tenant_id)

    # Power Domains
    async def get_power_domains(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringPowerDomain]:
        return await self.repo.get_power_domains(system_id, tenant_id=tenant_id)

    async def create_power_domain(
        self,
        system_id: str,
        name: str,
        nominal_voltage: float,
        source_subsystem_id: str,
        min_voltage: Optional[float] = None,
        max_voltage: Optional[float] = None,
        regulator_subsystem_id: Optional[str] = None,
        current_capacity_a: Optional[float] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringPowerDomain:
        return await self.repo.create_power_domain(
            system_id=system_id,
            name=name,
            nominal_voltage=nominal_voltage,
            source_subsystem_id=source_subsystem_id,
            min_voltage=min_voltage,
            max_voltage=max_voltage,
            regulator_subsystem_id=regulator_subsystem_id,
            current_capacity_a=current_capacity_a,
            tenant_id=tenant_id,
            metadata_=metadata_,
        )

    # Dependencies
    async def get_dependencies(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemDependency]:
        return await self.repo.get_dependencies(system_id, tenant_id=tenant_id)

    async def create_dependency(
        self,
        system_id: str,
        source_subsystem_id: str,
        target_subsystem_id: str,
        dependency_type: str,
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringSystemDependency:
        return await self.repo.create_dependency(
            system_id=system_id,
            source_subsystem_id=source_subsystem_id,
            target_subsystem_id=target_subsystem_id,
            dependency_type=dependency_type,
            description=description,
            tenant_id=tenant_id,
            metadata_=metadata_,
        )

    # Operating Modes & Transitions
    async def get_operating_modes(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringOperatingMode]:
        return await self.repo.get_operating_modes(system_id, tenant_id=tenant_id)

    async def create_operating_mode(
        self,
        system_id: str,
        name: str,
        description: Optional[str] = None,
        active_subsystem_ids: Optional[List[str]] = None,
        inactive_subsystem_ids: Optional[List[str]] = None,
        expected_power_domain_ids: Optional[List[str]] = None,
        relevant_interface_ids: Optional[List[str]] = None,
        operating_conditions: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringOperatingMode:
        return await self.repo.create_operating_mode(
            system_id=system_id,
            name=name,
            description=description,
            active_subsystem_ids=active_subsystem_ids,
            inactive_subsystem_ids=inactive_subsystem_ids,
            expected_power_domain_ids=expected_power_domain_ids,
            relevant_interface_ids=relevant_interface_ids,
            operating_conditions=operating_conditions,
            tenant_id=tenant_id,
            metadata_=metadata_,
        )

    async def get_mode_transitions(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringModeTransition]:
        return await self.repo.get_mode_transitions(system_id, tenant_id=tenant_id)

    async def create_mode_transition(
        self,
        system_id: str,
        source_mode_id: str,
        destination_mode_id: str,
        trigger: str,
        conditions: Optional[Dict[str, Any]] = None,
        required_subsystems: Optional[List[str]] = None,
        forbidden_conditions: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringModeTransition:
        return await self.repo.create_mode_transition(
            system_id=system_id,
            source_mode_id=source_mode_id,
            destination_mode_id=destination_mode_id,
            trigger=trigger,
            conditions=conditions,
            required_subsystems=required_subsystems,
            forbidden_conditions=forbidden_conditions,
            tenant_id=tenant_id,
            metadata_=metadata_,
        )

    # Requirements
    async def get_requirements(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemRequirement]:
        return await self.repo.get_requirements(system_id, tenant_id=tenant_id)

    async def create_requirement(
        self,
        system_id: str,
        code: str,
        title: str,
        description: str,
        requirement_type: str = "FUNCTIONAL",
        source: Optional[str] = None,
        status: str = "UNKNOWN",
        constraints: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringSystemRequirement:
        return await self.repo.create_requirement(
            system_id=system_id,
            code=code,
            title=title,
            description=description,
            requirement_type=requirement_type,
            source=source,
            status=status,
            constraints=constraints,
            tenant_id=tenant_id,
            metadata_=metadata_,
        )

    # Master System Analysis
    async def run_system_analysis(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> EngineeringSystemAnalysis:
        system = await self.get_system(system_id, tenant_id=tenant_id)
        if not system:
            raise ValueError(f"System {system_id} not found")

        subsystems = await self.repo.get_subsystems(system_id, tenant_id=tenant_id)
        interfaces = await self.repo.get_interfaces(system_id, tenant_id=tenant_id)
        power_domains = await self.repo.get_power_domains(system_id, tenant_id=tenant_id)
        dependencies = await self.repo.get_dependencies(system_id, tenant_id=tenant_id)
        operating_modes = await self.repo.get_operating_modes(system_id, tenant_id=tenant_id)
        mode_transitions = await self.repo.get_mode_transitions(system_id, tenant_id=tenant_id)
        requirements = await self.repo.get_requirements(system_id, tenant_id=tenant_id)

        # Collect circuit revisions
        circuit_revisions: Dict[str, int] = {}
        for s in subsystems:
            if s.circuit_id:
                circ = await self.circuit_repo.get_by_id(self.db, s.circuit_id, tenant_id=tenant_id)
                if circ:
                    circuit_revisions[s.circuit_id] = circ.version

        analysis_data = SystemAnalysisService.analyze_system(
            system=system,
            subsystems=subsystems,
            interfaces=interfaces,
            power_domains=power_domains,
            dependencies=dependencies,
            operating_modes=operating_modes,
            mode_transitions=mode_transitions,
            requirements=requirements,
            circuit_revisions=circuit_revisions,
        )

        analysis = await self.repo.save_analysis(
            system_id=system.id,
            system_revision=system.revision,
            subsystem_revisions=analysis_data["subsystem_revisions"],
            circuit_revisions=circuit_revisions,
            engine_versions=analysis_data["engine_versions"],
            rule_set_version=analysis_data["rule_set_version"],
            inputs_digest=analysis_data["inputs_digest"],
            findings_data=analysis_data["findings"],
            tenant_id=tenant_id,
        )
        return analysis

    async def get_latest_analysis(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSystemAnalysis]:
        return await self.repo.get_latest_analysis(system_id, tenant_id=tenant_id)

    async def get_findings(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemFinding]:
        return await self.repo.get_findings(system_id, tenant_id=tenant_id)

    # Failure Propagation
    async def simulate_failure(
        self,
        system_id: str,
        failed_subsystem_id: Optional[str] = None,
        failed_interface_id: Optional[str] = None,
        failure_type: str = "TOTAL_LOSS_OF_FUNCTION",
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        system = await self.get_system(system_id, tenant_id=tenant_id)
        if not system:
            raise ValueError(f"System {system_id} not found")

        subsystems = await self.repo.get_subsystems(system_id, tenant_id=tenant_id)
        interfaces = await self.repo.get_interfaces(system_id, tenant_id=tenant_id)
        power_domains = await self.repo.get_power_domains(system_id, tenant_id=tenant_id)
        dependencies = await self.repo.get_dependencies(system_id, tenant_id=tenant_id)

        return SystemFailurePropagationEngine.simulate_failure(
            subsystems=subsystems,
            interfaces=interfaces,
            power_domains=power_domains,
            dependencies=dependencies,
            failed_subsystem_id=failed_subsystem_id,
            failed_interface_id=failed_interface_id,
            failure_type=failure_type,
        )

    # Change Impact
    async def calculate_change_impact(
        self,
        system_id: str,
        target_type: str,
        target_id: str,
        proposed_change: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        system = await self.get_system(system_id, tenant_id=tenant_id)
        if not system:
            raise ValueError(f"System {system_id} not found")

        subsystems = await self.repo.get_subsystems(system_id, tenant_id=tenant_id)
        interfaces = await self.repo.get_interfaces(system_id, tenant_id=tenant_id)
        power_domains = await self.repo.get_power_domains(system_id, tenant_id=tenant_id)
        dependencies = await self.repo.get_dependencies(system_id, tenant_id=tenant_id)
        requirements = await self.repo.get_requirements(system_id, tenant_id=tenant_id)

        from sqlalchemy import select
        stmt = select(EngineeringSystemAnalysis).where(EngineeringSystemAnalysis.system_id == system_id)
        res = await self.db.execute(stmt)
        analyses = list(res.scalars().all())

        return SystemChangeImpactService.calculate_impact(
            target_type=target_type,
            target_id=target_id,
            proposed_change=proposed_change,
            subsystems=subsystems,
            interfaces=interfaces,
            power_domains=power_domains,
            dependencies=dependencies,
            analyses=analyses,
            requirements=requirements,
        )

    # Snapshots
    async def create_snapshot(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> EngineeringSystemSnapshot:
        system = await self.get_system(system_id, tenant_id=tenant_id)
        if not system:
            raise ValueError(f"System {system_id} not found")

        subsystems = await self.repo.get_subsystems(system_id, tenant_id=tenant_id)
        interfaces = await self.repo.get_interfaces(system_id, tenant_id=tenant_id)
        power_domains = await self.repo.get_power_domains(system_id, tenant_id=tenant_id)
        dependencies = await self.repo.get_dependencies(system_id, tenant_id=tenant_id)
        operating_modes = await self.repo.get_operating_modes(system_id, tenant_id=tenant_id)
        requirements = await self.repo.get_requirements(system_id, tenant_id=tenant_id)

        content = {
            "system_id": system.id,
            "revision": system.revision,
            "name": system.name,
            "status": system.status,
            "subsystems": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.subsystem_type,
                    "parent_id": s.parent_subsystem_id,
                    "circuit_id": s.circuit_id,
                    "revision": s.revision,
                }
                for s in subsystems
            ],
            "interfaces": [
                {
                    "id": i.id,
                    "name": i.name,
                    "type": i.interface_type,
                    "source_id": i.source_subsystem_id,
                    "dest_id": i.destination_subsystem_id,
                    "contract": i.contract,
                }
                for i in interfaces
            ],
            "power_domains": [
                {
                    "id": d.id,
                    "name": d.name,
                    "nominal_voltage": d.nominal_voltage,
                    "source_id": d.source_subsystem_id,
                    "capacity_a": d.current_capacity_a,
                }
                for d in power_domains
            ],
            "dependencies": [
                {
                    "id": dep.id,
                    "type": dep.dependency_type,
                    "source_id": dep.source_subsystem_id,
                    "target_id": dep.target_subsystem_id,
                }
                for dep in dependencies
            ],
            "operating_modes": [
                {"id": m.id, "name": m.name, "active_subs": m.active_subsystem_ids}
                for m in operating_modes
            ],
            "requirements": [
                {"id": r.id, "code": r.code, "title": r.title, "type": r.requirement_type}
                for r in requirements
            ],
        }

        return await self.repo.create_snapshot(
            system_id=system.id,
            content=content,
            system_revision=system.revision,
            tenant_id=tenant_id,
        )

    # Traceability
    async def get_system_traceability(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        system = await self.get_system(system_id, tenant_id=tenant_id)
        if not system:
            raise ValueError(f"System {system_id} not found")

        subsystems = await self.repo.get_subsystems(system_id, tenant_id=tenant_id)
        interfaces = await self.repo.get_interfaces(system_id, tenant_id=tenant_id)
        power_domains = await self.repo.get_power_domains(system_id, tenant_id=tenant_id)
        requirements = await self.repo.get_requirements(system_id, tenant_id=tenant_id)

        latest_analysis = await self.repo.get_latest_analysis(system_id, tenant_id=tenant_id)
        findings = await self.repo.get_findings(system_id, tenant_id=tenant_id)

        return {
            "root_type": "SYSTEM",
            "root_id": system.id,
            "system_name": system.name,
            "revision": system.revision,
            "subsystems_count": len(subsystems),
            "interfaces_count": len(interfaces),
            "power_domains_count": len(power_domains),
            "latest_analysis_id": latest_analysis.id if latest_analysis else None,
            "is_analysis_stale": latest_analysis.is_stale if latest_analysis else False,
            "rule_set_version": latest_analysis.rule_set_version if latest_analysis else "QUEBET-SYSTEM-001 v1.0",
            "findings_count": len(findings),
            "findings": [
                {
                    "id": f.id,
                    "rule_id": f.rule_id,
                    "category": f.category,
                    "severity": f.severity,
                    "title": f.title,
                    "affected_subsystems": f.affected_subsystems,
                }
                for f in findings
            ],
            "requirements": [
                {
                    "id": r.id,
                    "code": r.code,
                    "title": r.title,
                    "status": r.status,
                    "source": r.source,
                }
                for r in requirements
            ],
        }
