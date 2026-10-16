import hashlib
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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


class SystemRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_system(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
        load_relations: bool = False,
    ) -> Optional[EngineeringSystem]:
        stmt = select(EngineeringSystem).where(EngineeringSystem.id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystem.tenant_id == tenant_id)

        if load_relations:
            stmt = stmt.options(
                selectinload(EngineeringSystem.subsystems),
                selectinload(EngineeringSystem.interfaces),
                selectinload(EngineeringSystem.power_domains),
                selectinload(EngineeringSystem.dependencies),
                selectinload(EngineeringSystem.operating_modes),
                selectinload(EngineeringSystem.mode_transitions),
                selectinload(EngineeringSystem.requirements),
            )

        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_systems_for_project(
        self,
        project_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystem]:
        stmt = select(EngineeringSystem).where(EngineeringSystem.project_id == project_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystem.tenant_id == tenant_id)
        stmt = stmt.order_by(desc(EngineeringSystem.created_at))
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def create_system(
        self,
        project_id: str,
        name: str,
        created_by: str,
        description: Optional[str] = None,
        tenant_id: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> EngineeringSystem:
        system = EngineeringSystem(
            project_id=project_id,
            name=name,
            description=description,
            created_by=created_by,
            tenant_id=tenant_id,
            metadata_=metadata_ or {},
        )
        self.db.add(system)
        await self.db.commit()
        await self.db.refresh(system)
        return system

    async def update_system(
        self,
        system_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSystem]:
        system = await self.get_system(system_id, tenant_id=tenant_id)
        if not system:
            return None

        for k, v in updates.items():
            if v is not None:
                if k == "metadata":
                    system.metadata_ = v
                else:
                    setattr(system, k, v)

        system.revision += 1
        await self.mark_analyses_stale(system_id)
        await self.db.commit()
        await self.db.refresh(system)
        return system

    async def bump_system_revision(self, system_id: str) -> int:
        system = await self.get_system(system_id)
        if not system:
            raise ValueError(f"System {system_id} not found")
        system.revision += 1
        await self.mark_analyses_stale(system_id)
        await self.db.commit()
        return system.revision

    # Subsystems
    async def get_subsystem(
        self,
        subsystem_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSubsystem]:
        stmt = select(EngineeringSubsystem).where(EngineeringSubsystem.id == subsystem_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSubsystem.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_subsystems(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSubsystem]:
        stmt = select(EngineeringSubsystem).where(EngineeringSubsystem.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSubsystem.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def would_cause_subsystem_cycle(
        self,
        subsystem_id: str,
        proposed_parent_id: Optional[str],
    ) -> bool:
        if not proposed_parent_id:
            return False
        if subsystem_id == proposed_parent_id:
            return True

        curr_id = proposed_parent_id
        visited = {subsystem_id}
        while curr_id:
            if curr_id in visited:
                return True
            visited.add(curr_id)
            parent = await self.get_subsystem(curr_id)
            if not parent or not parent.parent_subsystem_id:
                break
            curr_id = parent.parent_subsystem_id
        return False

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
        if parent_subsystem_id:
            parent = await self.get_subsystem(parent_subsystem_id, tenant_id=tenant_id)
            if not parent or parent.system_id != system_id:
                raise ValueError("Parent subsystem does not belong to the same system")

        subsystem = EngineeringSubsystem(
            system_id=system_id,
            name=name,
            subsystem_type=subsystem_type,
            parent_subsystem_id=parent_subsystem_id,
            circuit_id=circuit_id,
            description=description,
            tenant_id=tenant_id,
            metadata_=metadata_ or {},
        )
        self.db.add(subsystem)
        await self.bump_system_revision(system_id)
        await self.db.commit()
        await self.db.refresh(subsystem)
        return subsystem

    async def update_subsystem(
        self,
        subsystem_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSubsystem]:
        subsystem = await self.get_subsystem(subsystem_id, tenant_id=tenant_id)
        if not subsystem:
            return None

        if "parent_subsystem_id" in updates:
            proposed_parent = updates["parent_subsystem_id"]
            if await self.would_cause_subsystem_cycle(subsystem_id, proposed_parent):
                raise ValueError("Cannot set parent: cycle detected in subsystem hierarchy")

        for k, v in updates.items():
            if v is not None:
                if k == "metadata":
                    subsystem.metadata_ = v
                else:
                    setattr(subsystem, k, v)

        subsystem.revision += 1
        await self.bump_system_revision(subsystem.system_id)
        await self.db.commit()
        await self.db.refresh(subsystem)
        return subsystem

    async def delete_subsystem(
        self,
        subsystem_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        subsystem = await self.get_subsystem(subsystem_id, tenant_id=tenant_id)
        if not subsystem:
            return False

        # Deletion protection: Check child subsystems
        child_stmt = select(EngineeringSubsystem).where(EngineeringSubsystem.parent_subsystem_id == subsystem_id)
        child_res = await self.db.execute(child_stmt)
        if child_res.scalars().first():
            raise ValueError("Cannot delete subsystem: child subsystems exist")

        # Deletion protection: Check interfaces
        iface_stmt = select(EngineeringSystemInterface).where(
            (EngineeringSystemInterface.source_subsystem_id == subsystem_id)
            | (EngineeringSystemInterface.destination_subsystem_id == subsystem_id)
        )
        iface_res = await self.db.execute(iface_stmt)
        if iface_res.scalars().first():
            raise ValueError("Cannot delete subsystem: active system interfaces exist")

        # Deletion protection: Check dependencies
        dep_stmt = select(EngineeringSystemDependency).where(
            (EngineeringSystemDependency.source_subsystem_id == subsystem_id)
            | (EngineeringSystemDependency.target_subsystem_id == subsystem_id)
        )
        dep_res = await self.db.execute(dep_stmt)
        if dep_res.scalars().first():
            raise ValueError("Cannot delete subsystem: system dependencies exist")

        system_id = subsystem.system_id
        await self.db.delete(subsystem)
        await self.bump_system_revision(system_id)
        await self.db.commit()
        return True

    # Interfaces
    async def get_interfaces(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemInterface]:
        stmt = select(EngineeringSystemInterface).where(EngineeringSystemInterface.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemInterface.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_interface(
        self,
        interface_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSystemInterface]:
        stmt = select(EngineeringSystemInterface).where(EngineeringSystemInterface.id == interface_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemInterface.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

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
        interface = EngineeringSystemInterface(
            system_id=system_id,
            name=name,
            source_subsystem_id=source_subsystem_id,
            destination_subsystem_id=destination_subsystem_id,
            interface_type=interface_type,
            contract=contract or {},
            description=description,
            tenant_id=tenant_id,
            metadata_=metadata_ or {},
        )
        self.db.add(interface)
        await self.bump_system_revision(system_id)
        await self.db.commit()
        await self.db.refresh(interface)
        return interface

    async def update_interface(
        self,
        interface_id: str,
        updates: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSystemInterface]:
        iface = await self.get_interface(interface_id, tenant_id=tenant_id)
        if not iface:
            return None

        for k, v in updates.items():
            if v is not None:
                if k == "metadata":
                    iface.metadata_ = v
                else:
                    setattr(iface, k, v)

        await self.bump_system_revision(iface.system_id)
        await self.db.commit()
        await self.db.refresh(iface)
        return iface

    async def delete_interface(
        self,
        interface_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        iface = await self.get_interface(interface_id, tenant_id=tenant_id)
        if not iface:
            return False
        system_id = iface.system_id
        await self.db.delete(iface)
        await self.bump_system_revision(system_id)
        await self.db.commit()
        return True

    # Power Domains
    async def get_power_domains(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringPowerDomain]:
        stmt = select(EngineeringPowerDomain).where(EngineeringPowerDomain.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringPowerDomain.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

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
        domain = EngineeringPowerDomain(
            system_id=system_id,
            name=name,
            nominal_voltage=nominal_voltage,
            min_voltage=min_voltage,
            max_voltage=max_voltage,
            source_subsystem_id=source_subsystem_id,
            regulator_subsystem_id=regulator_subsystem_id,
            current_capacity_a=current_capacity_a,
            tenant_id=tenant_id,
            metadata_=metadata_ or {},
        )
        self.db.add(domain)
        await self.bump_system_revision(system_id)
        await self.db.commit()
        await self.db.refresh(domain)
        return domain

    # Dependencies
    async def get_dependencies(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemDependency]:
        stmt = select(EngineeringSystemDependency).where(EngineeringSystemDependency.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemDependency.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

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
        dep = EngineeringSystemDependency(
            system_id=system_id,
            source_subsystem_id=source_subsystem_id,
            target_subsystem_id=target_subsystem_id,
            dependency_type=dependency_type,
            description=description,
            tenant_id=tenant_id,
            metadata_=metadata_ or {},
        )
        self.db.add(dep)
        await self.bump_system_revision(system_id)
        await self.db.commit()
        await self.db.refresh(dep)
        return dep

    # Operating Modes & Transitions
    async def get_operating_modes(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringOperatingMode]:
        stmt = select(EngineeringOperatingMode).where(EngineeringOperatingMode.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringOperatingMode.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

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
        mode = EngineeringOperatingMode(
            system_id=system_id,
            name=name,
            description=description,
            active_subsystem_ids=active_subsystem_ids or [],
            inactive_subsystem_ids=inactive_subsystem_ids or [],
            expected_power_domain_ids=expected_power_domain_ids or [],
            relevant_interface_ids=relevant_interface_ids or [],
            operating_conditions=operating_conditions or {},
            tenant_id=tenant_id,
            metadata_=metadata_ or {},
        )
        self.db.add(mode)
        await self.bump_system_revision(system_id)
        await self.db.commit()
        await self.db.refresh(mode)
        return mode

    async def get_mode_transitions(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringModeTransition]:
        stmt = select(EngineeringModeTransition).where(EngineeringModeTransition.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringModeTransition.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

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
        trans = EngineeringModeTransition(
            system_id=system_id,
            source_mode_id=source_mode_id,
            destination_mode_id=destination_mode_id,
            trigger=trigger,
            conditions=conditions or {},
            required_subsystems=required_subsystems or [],
            forbidden_conditions=forbidden_conditions or {},
            tenant_id=tenant_id,
            metadata_=metadata_ or {},
        )
        self.db.add(trans)
        await self.bump_system_revision(system_id)
        await self.db.commit()
        await self.db.refresh(trans)
        return trans

    # Requirements
    async def get_requirements(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemRequirement]:
        stmt = select(EngineeringSystemRequirement).where(EngineeringSystemRequirement.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemRequirement.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

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
        req = EngineeringSystemRequirement(
            system_id=system_id,
            code=code,
            title=title,
            description=description,
            requirement_type=requirement_type,
            source=source,
            status=status,
            constraints=constraints or {},
            tenant_id=tenant_id,
            metadata_=metadata_ or {},
        )
        self.db.add(req)
        await self.db.commit()
        await self.db.refresh(req)
        return req

    # Analyses and Findings
    async def get_latest_analysis(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EngineeringSystemAnalysis]:
        stmt = (
            select(EngineeringSystemAnalysis)
            .where(EngineeringSystemAnalysis.system_id == system_id)
            .order_by(desc(EngineeringSystemAnalysis.created_at))
            .options(selectinload(EngineeringSystemAnalysis.findings))
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemAnalysis.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def get_findings(
        self,
        system_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemFinding]:
        stmt = select(EngineeringSystemFinding).where(EngineeringSystemFinding.system_id == system_id)
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemFinding.tenant_id == tenant_id)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_analysis(
        self,
        system_id: str,
        system_revision: int,
        subsystem_revisions: Dict[str, int],
        circuit_revisions: Dict[str, int],
        engine_versions: Dict[str, str],
        rule_set_version: str,
        inputs_digest: str,
        findings_data: List[Dict[str, Any]],
        knowledge_snapshot_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> EngineeringSystemAnalysis:
        findings_objects = [
            EngineeringSystemFinding(
                system_id=system_id,
                tenant_id=tenant_id,
                rule_id=f.get("rule_id", "SYS-000"),
                category=f.get("category", "SYSTEM"),
                severity=f.get("severity", "WARNING"),
                title=f.get("title", ""),
                description=f.get("description", ""),
                affected_subsystems=f.get("affected_subsystems", []),
                affected_interfaces=f.get("affected_interfaces", []),
                affected_power_domains=f.get("affected_power_domains", []),
                inputs=f.get("inputs", {}),
                calculation=f.get("calculation", {}),
                provenance=f.get("provenance", {}),
                unknowns=f.get("unknowns", []),
                status="ACTIVE",
            )
            for f in findings_data
        ]

        analysis = EngineeringSystemAnalysis(
            system_id=system_id,
            tenant_id=tenant_id,
            system_revision=system_revision,
            subsystem_revisions=subsystem_revisions,
            circuit_revisions=circuit_revisions,
            engine_versions=engine_versions,
            rule_set_version=rule_set_version,
            knowledge_snapshot_id=knowledge_snapshot_id,
            inputs_digest=inputs_digest,
            status="ANALYSIS_COMPLETE",
            is_stale=False,
            findings=findings_objects,
        )
        self.db.add(analysis)
        await self.db.commit()
        return analysis

    async def mark_analyses_stale(self, system_id: str, tenant_id: Optional[str] = None) -> None:
        stmt = (
            update(EngineeringSystemAnalysis)
            .where(EngineeringSystemAnalysis.system_id == system_id)
        )
        if tenant_id is not None:
            stmt = stmt.where(EngineeringSystemAnalysis.tenant_id == tenant_id)
        stmt = stmt.values(is_stale=True, status="STALE")
        await self.db.execute(stmt)

    # Snapshots
    async def create_snapshot(
        self,
        system_id: str,
        content: Dict[str, Any],
        system_revision: int,
        tenant_id: Optional[str] = None,
    ) -> EngineeringSystemSnapshot:
        encoded = json.dumps(content, sort_keys=True).encode("utf-8")
        snapshot_hash = hashlib.sha256(encoded).hexdigest()

        snapshot = EngineeringSystemSnapshot(
            system_id=system_id,
            tenant_id=tenant_id,
            system_revision=system_revision,
            snapshot_hash=snapshot_hash,
            content=content,
        )
        self.db.add(snapshot)
        await self.db.commit()
        await self.db.refresh(snapshot)
        return snapshot
