import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.system_synthesis import (
    CandidateStatus,
    EngineeringScenario,
    EngineeringScenarioCondition,
    EngineeringScenarioResult,
    EngineeringScenarioSnapshot,
    EngineeringSystemCandidate,
    EngineeringSystemDesignConstraint,
    EngineeringSystemDesignObjective,
    SystemObjectiveStatus,
)
from app.models.schemas.system_synthesis import (
    ScenarioCreate,
    ScenarioUpdate,
    SystemDesignObjectiveCreate,
    SystemDesignObjectiveUpdate,
)
from app.repositories.system_repo import SystemRepository
from app.repositories.system_synthesis_repo import SystemSynthesisRepository
from app.services.ai.system.scenario_comparison_service import ScenarioComparisonService
from app.services.ai.system.scenario_execution_service import ScenarioExecutionService
from app.services.ai.system.system_architecture_comparison_service import SystemArchitectureComparisonService
from app.services.ai.system.system_candidate_generator import SystemCandidateGenerator
from app.services.ai.system.system_what_if_simulator import SystemWhatIfSimulator


class SystemSynthesisService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.system_repo = SystemRepository(db)
        self.synthesis_repo = SystemSynthesisRepository(db)
        self.scenario_exec_service = ScenarioExecutionService()
        self.scenario_compare_service = ScenarioComparisonService()
        self.candidate_generator = SystemCandidateGenerator()
        self.arch_compare_service = SystemArchitectureComparisonService()

    # ---------------------------------------------------------
    # Objectives & Constraints
    # ---------------------------------------------------------

    async def create_objective(
        self,
        system_id: str,
        user_id: str,
        payload: SystemDesignObjectiveCreate,
        tenant_id: Optional[str] = None,
    ) -> EngineeringSystemDesignObjective:
        system = await self.system_repo.get_system(system_id, tenant_id=tenant_id)
        if not system:
            raise HTTPException(status_code=404, detail="System not found")

        obj_id = str(uuid.uuid4())
        obj = EngineeringSystemDesignObjective(
            id=obj_id,
            system_id=system_id,
            tenant_id=tenant_id,
            title=payload.title,
            description=payload.description,
            objective_type=payload.objective_type,
            priority=payload.priority,
            status=SystemObjectiveStatus.ACTIVE.value,
            target=payload.target,
            affected_subsystems=payload.affected_subsystems,
            relevant_modes=payload.relevant_modes,
            created_by=user_id,
            metadata_=payload.metadata or {},
        )
        await self.synthesis_repo.create_objective(obj)

        # Create constraints if provided
        for c_data in payload.constraints or []:
            const = EngineeringSystemDesignConstraint(
                id=str(uuid.uuid4()),
                objective_id=obj_id,
                system_id=system_id,
                tenant_id=tenant_id,
                constraint_type=c_data.constraint_type,
                parameter=c_data.parameter,
                operator=c_data.operator,
                value=c_data.value,
                unit=c_data.unit,
                weight=c_data.weight or 1.0,
                status=c_data.status,
                metadata_=c_data.metadata or {},
            )
            await self.synthesis_repo.create_constraint(const)

        await self.db.commit()
        return await self.synthesis_repo.get_objective(obj_id, tenant_id=tenant_id)

    async def get_objective(
        self, objective_id: str, tenant_id: Optional[str] = None
    ) -> EngineeringSystemDesignObjective:
        obj = await self.synthesis_repo.get_objective(objective_id, tenant_id=tenant_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Objective not found")
        return obj

    async def get_objectives_for_system(
        self, system_id: str, tenant_id: Optional[str] = None
    ) -> List[EngineeringSystemDesignObjective]:
        return await self.synthesis_repo.get_objectives_for_system(system_id, tenant_id=tenant_id)

    # ---------------------------------------------------------
    # Scenarios & Scenario Execution
    # ---------------------------------------------------------

    async def create_scenario(
        self,
        system_id: str,
        user_id: str,
        payload: ScenarioCreate,
        tenant_id: Optional[str] = None,
    ) -> EngineeringScenario:
        system = await self.system_repo.get_system(system_id, tenant_id=tenant_id)
        if not system:
            raise HTTPException(status_code=404, detail="System not found")

        scen_id = str(uuid.uuid4())
        scenario = EngineeringScenario(
            id=scen_id,
            system_id=system_id,
            tenant_id=tenant_id,
            name=payload.name,
            description=payload.description,
            scenario_type=payload.scenario_type,
            status="ACTIVE",
            system_revision=system.revision,
            created_by=user_id,
            metadata_=payload.metadata or {},
        )
        await self.synthesis_repo.create_scenario(scenario)

        for cond_data in payload.conditions or []:
            cond = EngineeringScenarioCondition(
                id=str(uuid.uuid4()),
                scenario_id=scen_id,
                tenant_id=tenant_id,
                condition_type=cond_data.condition_type,
                target_type=cond_data.target_type,
                target_id=cond_data.target_id,
                parameter=cond_data.parameter,
                value=cond_data.value,
                unit=cond_data.unit,
                source=cond_data.source,
                confidence=cond_data.confidence,
                provenance=cond_data.provenance or {},
                mandatory=cond_data.mandatory,
                metadata_=cond_data.metadata or {},
            )
            await self.synthesis_repo.create_scenario_condition(cond)

        await self.db.commit()
        return await self.synthesis_repo.get_scenario(scen_id, tenant_id=tenant_id)

    async def get_scenario(
        self, scenario_id: str, tenant_id: Optional[str] = None
    ) -> EngineeringScenario:
        scen = await self.synthesis_repo.get_scenario(scenario_id, tenant_id=tenant_id)
        if not scen:
            raise HTTPException(status_code=404, detail="Scenario not found")
        return scen

    async def get_scenarios_for_system(
        self, system_id: str, tenant_id: Optional[str] = None
    ) -> List[EngineeringScenario]:
        return await self.synthesis_repo.get_scenarios_for_system(system_id, tenant_id=tenant_id)

    async def execute_scenario(
        self, scenario_id: str, user_id: str, tenant_id: Optional[str] = None
    ) -> EngineeringScenarioResult:
        scenario = await self.synthesis_repo.get_scenario(scenario_id, tenant_id=tenant_id)
        if not scenario:
            raise HTTPException(status_code=404, detail="Scenario not found")

        system_id = scenario.system_id
        system = await self.system_repo.get_system(system_id, tenant_id=tenant_id)
        subsystems = await self.system_repo.get_subsystems(system_id, tenant_id=tenant_id)
        interfaces = await self.system_repo.get_interfaces(system_id, tenant_id=tenant_id)
        power_domains = await self.system_repo.get_power_domains(system_id, tenant_id=tenant_id)
        dependencies = await self.system_repo.get_dependencies(system_id, tenant_id=tenant_id)
        modes = await self.system_repo.get_operating_modes(system_id, tenant_id=tenant_id)
        reqs = await self.system_repo.get_requirements(system_id, tenant_id=tenant_id)
        conditions = await self.synthesis_repo.get_conditions_for_scenario(scenario_id, tenant_id=tenant_id)

        # Convert ORM to dicts for clean sandboxing
        sub_dicts = [{"id": s.id, "name": s.name, "subsystem_type": s.subsystem_type, "parent_subsystem_id": s.parent_subsystem_id, "circuit_id": s.circuit_id} for s in subsystems]
        iface_dicts = [{"id": i.id, "name": i.name, "interface_type": i.interface_type, "source_subsystem_id": i.source_subsystem_id, "destination_subsystem_id": i.destination_subsystem_id, "contract": i.contract} for i in interfaces]
        pwr_dicts = [{"id": p.id, "name": p.name, "nominal_voltage": p.nominal_voltage, "current_capacity_a": p.current_capacity_a, "source_subsystem_id": p.source_subsystem_id} for p in power_domains]
        dep_dicts = [{"id": d.id, "source_subsystem_id": d.source_subsystem_id, "target_subsystem_id": d.target_subsystem_id, "dependency_type": d.dependency_type} for d in dependencies]
        mode_dicts = [{"id": m.id, "name": m.name, "active_subsystem_ids": m.active_subsystem_ids} for m in modes]
        req_dicts = [{"id": r.id, "code": r.code, "title": r.title, "requirement_type": r.requirement_type, "constraints": r.constraints} for r in reqs]
        cond_dicts = [{"id": c.id, "condition_type": c.condition_type, "target_type": c.target_type, "target_id": c.target_id, "parameter": c.parameter, "value": c.value, "mandatory": c.mandatory} for c in conditions]

        # Run deterministic execution
        exec_out = self.scenario_exec_service.execute_scenario(
            scenario={"id": scenario.id, "name": scenario.name},
            conditions=cond_dicts,
            system={"id": system.id, "revision": system.revision},
            subsystems=sub_dicts,
            interfaces=iface_dicts,
            power_domains=pwr_dicts,
            dependencies=dep_dicts,
            operating_modes=mode_dicts,
            requirements=req_dicts,
        )

        execution_id = str(uuid.uuid4())

        # Save snapshot
        snapshot = EngineeringScenarioSnapshot(
            id=str(uuid.uuid4()),
            scenario_id=scenario.id,
            system_id=system.id,
            tenant_id=tenant_id,
            system_revision=system.revision,
            scenario_conditions=cond_dicts,
            engine_versions=exec_out.get("provenance", {}).get("engine_versions", {}),
            rule_set_version=exec_out.get("provenance", {}).get("rule_set_version", "v1.0"),
            inputs_digest=exec_out.get("inputs_digest", "digest"),
        )
        await self.synthesis_repo.create_scenario_snapshot(snapshot)

        # Save result
        res = EngineeringScenarioResult(
            id=str(uuid.uuid4()),
            scenario_id=scenario.id,
            execution_id=execution_id,
            system_id=system.id,
            tenant_id=tenant_id,
            status=exec_out.get("status", "COMPLETE"),
            system_revision=system.revision,
            precondition_status=exec_out.get("precondition_status", "SATISFIED"),
            findings=exec_out.get("findings", []),
            requirement_results=exec_out.get("requirement_results", []),
            power_results=exec_out.get("power_results", {}),
            interface_results=exec_out.get("interface_results", {}),
            failure_results=exec_out.get("failure_results", {}),
            unknowns=exec_out.get("unknowns", []),
            provenance=exec_out.get("provenance", {}),
        )
        await self.synthesis_repo.create_scenario_result(res)
        await self.db.commit()

        return res

    async def compare_scenarios(
        self, baseline_id: str, alternative_id: str, tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        base_res = await self.synthesis_repo.get_latest_scenario_result(baseline_id, tenant_id=tenant_id)
        alt_res = await self.synthesis_repo.get_latest_scenario_result(alternative_id, tenant_id=tenant_id)
        if not base_res or not alt_res:
            raise HTTPException(status_code=400, detail="Both scenarios must have execution results to compare.")

        base_dict = {
            "scenario_id": base_res.scenario_id,
            "findings": base_res.findings,
            "power_results": base_res.power_results,
            "failure_results": base_res.failure_results,
            "unknowns": base_res.unknowns,
            "requirement_results": base_res.requirement_results,
        }
        alt_dict = {
            "scenario_id": alt_res.scenario_id,
            "findings": alt_res.findings,
            "power_results": alt_res.power_results,
            "failure_results": alt_res.failure_results,
            "unknowns": alt_res.unknowns,
            "requirement_results": alt_res.requirement_results,
        }
        return self.scenario_compare_service.compare_scenarios(base_dict, alt_dict)

    # ---------------------------------------------------------
    # Candidates & Architecture Comparison
    # ---------------------------------------------------------

    async def generate_candidates(
        self,
        objective_id: str,
        user_id: str,
        strategies: Optional[List[str]] = None,
        tenant_id: Optional[str] = None,
    ) -> List[EngineeringSystemCandidate]:
        objective = await self.synthesis_repo.get_objective(objective_id, tenant_id=tenant_id)
        if not objective:
            raise HTTPException(status_code=404, detail="Objective not found")

        system_id = objective.system_id
        system = await self.system_repo.get_system(system_id, tenant_id=tenant_id)
        subsystems = await self.system_repo.get_subsystems(system_id, tenant_id=tenant_id)
        interfaces = await self.system_repo.get_interfaces(system_id, tenant_id=tenant_id)
        power_domains = await self.system_repo.get_power_domains(system_id, tenant_id=tenant_id)
        dependencies = await self.system_repo.get_dependencies(system_id, tenant_id=tenant_id)
        modes = await self.system_repo.get_operating_modes(system_id, tenant_id=tenant_id)
        reqs = await self.system_repo.get_requirements(system_id, tenant_id=tenant_id)
        constraints = await self.synthesis_repo.get_constraints_for_objective(objective_id, tenant_id=tenant_id)

        obj_dict = {"id": objective.id, "objective_type": objective.objective_type, "created_by": user_id}
        const_dicts = [{"constraint_type": c.constraint_type, "parameter": c.parameter, "operator": c.operator, "value": c.value} for c in constraints]
        sub_dicts = [{"id": s.id, "name": s.name, "subsystem_type": s.subsystem_type, "parent_subsystem_id": s.parent_subsystem_id, "circuit_id": s.circuit_id} for s in subsystems]
        iface_dicts = [{"id": i.id, "name": i.name, "interface_type": i.interface_type, "source_subsystem_id": i.source_subsystem_id, "destination_subsystem_id": i.destination_subsystem_id, "contract": i.contract} for i in interfaces]
        pwr_dicts = [{"id": p.id, "name": p.name, "nominal_voltage": p.nominal_voltage, "current_capacity_a": p.current_capacity_a, "source_subsystem_id": p.source_subsystem_id} for p in power_domains]
        dep_dicts = [{"id": d.id, "source_subsystem_id": d.source_subsystem_id, "target_subsystem_id": d.target_subsystem_id, "dependency_type": d.dependency_type} for d in dependencies]
        mode_dicts = [{"id": m.id, "name": m.name, "active_subsystem_ids": m.active_subsystem_ids} for m in modes]
        req_dicts = [{"id": r.id, "code": r.code, "title": r.title, "requirement_type": r.requirement_type, "constraints": r.constraints} for r in reqs]

        raw_candidates = self.candidate_generator.generate_candidates(
            objective=obj_dict,
            constraints=const_dicts,
            system={"id": system.id, "revision": system.revision},
            subsystems=sub_dicts,
            interfaces=iface_dicts,
            power_domains=pwr_dicts,
            dependencies=dep_dicts,
            operating_modes=mode_dicts,
            requirements=req_dicts,
            requested_strategies=strategies,
        )

        persisted_candidates: List[EngineeringSystemCandidate] = []
        for rc in raw_candidates:
            cand = EngineeringSystemCandidate(
                id=rc["id"],
                objective_id=objective.id,
                system_id=system.id,
                tenant_id=tenant_id,
                candidate_name=rc["candidate_name"],
                generation_strategy=rc["generation_strategy"],
                status=rc["status"],
                base_revision=rc["base_revision"],
                operations=rc["operations"],
                rationale=rc["rationale"],
                assumptions=rc["assumptions"],
                hard_constraints_result=rc["hard_constraints_result"],
                soft_constraints_result=rc["soft_constraints_result"],
                constraints_evaluation=rc["constraints_evaluation"],
                requirement_effects=rc["requirement_effects"],
                verification_effects=rc["verification_effects"],
                failure_effects=rc["failure_effects"],
                power_effects=rc["power_effects"],
                unknowns=rc["unknowns"],
                provenance=rc["provenance"],
                created_by=user_id,
            )
            persisted = await self.synthesis_repo.create_candidate(cand)
            persisted_candidates.append(persisted)

        await self.db.commit()
        return persisted_candidates

    async def get_candidates_for_objective(
        self, objective_id: str, tenant_id: Optional[str] = None
    ) -> List[EngineeringSystemCandidate]:
        return await self.synthesis_repo.get_candidates_for_objective(objective_id, tenant_id=tenant_id)

    async def compare_architectures(
        self, candidate_ids: List[str], tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        candidates = []
        base_rev = 1
        for cid in candidate_ids:
            c = await self.synthesis_repo.get_candidate(cid, tenant_id=tenant_id)
            if c:
                base_rev = c.base_revision
                candidates.append({
                    "id": c.id,
                    "candidate_name": c.candidate_name,
                    "generation_strategy": c.generation_strategy,
                    "hard_constraints_result": c.hard_constraints_result,
                    "soft_constraints_result": c.soft_constraints_result,
                    "operations": c.operations,
                    "power_effects": c.power_effects,
                    "failure_effects": c.failure_effects,
                    "requirement_effects": c.requirement_effects,
                    "verification_effects": c.verification_effects,
                    "unknowns": c.unknowns,
                    "status": c.status,
                })

        return self.arch_compare_service.build_comparison_matrix(candidates, base_rev)
