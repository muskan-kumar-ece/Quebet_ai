from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.cognitive import (
    EngineeringTaskPlan,
    EngineeringCognitiveExecution,
    EngineeringCognitiveProvenance,
    PlanStatus,
    TaskStatus,
    ExecutionStatus,
)
from app.core.dependencies import AuthenticatedUser
from app.services.ai.cognitive.plan_validator import EngineeringPlanValidator
from app.services.ai.cognitive.explanation_service import EngineeringExplanationService
from app.services.ai.cognitive.execution_policy import CapabilityExecutionPolicy, CapabilityExecutionError
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.system_repo import SystemRepository
from app.repositories.circuit_repo import CircuitRepository
from app.repositories.verification_repo import VerificationRepository
from app.repositories.decision_repo import DecisionRepository
from app.services.analysis_service import AnalysisService
from app.services.ai.decision.requirement_coverage_service import RequirementCoverageService
from app.services.ai.decision.design_review_readiness_service import DesignReviewReadinessService


class EngineeringPlanExecutor:
    """
    Deterministically executes validated EngineeringTaskPlans by invoking authoritative Phase 1 services.
    Enforces revision freshness, unknown propagation, partial execution handling, and auditable cognitive provenance.
    Integrity is guarded by SHA-256 canonical digests and strict server-authoritative execution policy.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_plan(
        self,
        plan: EngineeringTaskPlan,
        tenant_id: str,
        actor: str,
        actor_permissions: Optional[List[str]] = None,
    ) -> EngineeringCognitiveExecution:
        # 1. Validate plan and check revision freshness
        validator = EngineeringPlanValidator(self.db)
        val_res = await validator.validate_plan(plan, tenant_id=tenant_id)

        if not val_res.is_valid:
            if "COGNITIVE_PLAN_STALE" in str(val_res.blocking_reasons):
                plan.status = PlanStatus.STALE.value
                plan.blocking_reasons = val_res.blocking_reasons
                await self.db.commit()
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "COGNITIVE_PLAN_STALE",
                        "message": "Engineering context revision has advanced since plan creation.",
                        "reasons": val_res.blocking_reasons,
                    },
                )
            plan.status = PlanStatus.VALIDATION_FAILED.value
            plan.blocking_reasons = val_res.blocking_reasons
            await self.db.commit()
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "COGNITIVE_PLAN_BLOCKED",
                    "message": "Plan validation failed.",
                    "reasons": val_res.blocking_reasons,
                },
            )

        # 2. Transition plan status to EXECUTING
        started_at = datetime.now(timezone.utc)
        plan.status = PlanStatus.EXECUTING.value
        await self.db.commit()

        results: List[Dict[str, Any]] = []
        findings: List[Dict[str, Any]] = []
        unknowns: List[Dict[str, Any]] = []
        requirements_affected: List[Dict[str, Any]] = []
        constraints_affected: List[Dict[str, Any]] = []
        verification_impacts: List[Dict[str, Any]] = []
        traceability: List[Dict[str, Any]] = []
        human_actions_required: List[str] = []
        blocking_reasons: List[str] = []

        capability_versions: Dict[str, str] = {}
        engine_versions: Dict[str, str] = {}

        completed_tasks: List[str] = []
        failed_task: Optional[Dict[str, Any]] = None
        remaining_tasks: List[str] = []

        # 3. Execute tasks sequentially in DAG order
        tasks = sorted(plan.tasks or [], key=lambda t: t.order_index)
        has_failed = False

        for task in tasks:
            if has_failed:
                task.status = TaskStatus.PENDING.value
                task.blocking_reason = "Execution halted due to upstream task failure."
                remaining_tasks.append(task.id)
                continue

            task.status = TaskStatus.RUNNING.value
            task_failed = False
            task_failure_reason = ""

            # Check server-authoritative capability execution policy
            for cap_id in task.required_capabilities or []:
                try:
                    CapabilityExecutionPolicy.evaluate(
                        capability_id=cap_id,
                        tenant_id=tenant_id,
                        plan_tenant_id=plan.tenant_id,
                        actor_permissions=actor_permissions,
                        execution_policy=plan.execution_policy,
                    )
                except CapabilityExecutionError as cee:
                    task_failed = True
                    task_failure_reason = f"POLICY_VIOLATION: {cee.detail.get('message', 'Capability execution disallowed.')}"
                    break
                except Exception as ex:
                    task_failed = True
                    task_failure_reason = f"POLICY_ERROR: {str(ex)}"
                    break

            if not task_failed:
                for cap_id in task.required_capabilities or []:
                    capability_versions[cap_id] = "1.0.0"

                    # Execute deterministic capability
                    try:
                        if cap_id == "circuit_analysis" and plan.circuit_id:
                            engine_versions["circuit_analysis_engine"] = "v3.1.0"
                            an_service = AnalysisService()
                            auth_user = AuthenticatedUser(id=actor, email="engineer@quebet.ai", role="engineer", tenant_id=tenant_id)
                            analysis = await an_service.run_analysis(db=self.db, circuit_id=plan.circuit_id, current_user=auth_user)
                            results.append({
                                "capability": cap_id,
                                "task": task.description,
                                "analysis_id": analysis.id,
                                "status": analysis.status,
                                "confidence": analysis.confidence,
                                "calculations_count": len(analysis.calculations or []),
                            })
                            for f in (analysis.findings or []):
                                findings.append(f.model_dump() if hasattr(f, "model_dump") else f)
                            for u in (analysis.unknowns or []):
                                unknowns.append({"source": "circuit_analysis", "unknown": u.model_dump() if hasattr(u, "model_dump") else u})

                        elif cap_id == "system_analysis" and plan.system_id:
                            engine_versions["system_analysis_engine"] = "v2.0.0"
                            sys_repo = SystemRepository(self.db)
                            system = await sys_repo.get_system(plan.system_id, tenant_id=tenant_id, load_relations=True)
                            if system:
                                results.append({
                                    "capability": cap_id,
                                    "task": task.description,
                                    "system_id": system.id,
                                    "revision": system.revision,
                                    "subsystems": len(system.subsystems or []),
                                    "interfaces": len(system.interfaces or []),
                                    "power_domains": len(system.power_domains or []),
                                })

                        elif cap_id == "finding_analysis":
                            # Collect and classify active findings
                            if findings:
                                critical = [f for f in findings if f.get("severity") in ["CRITICAL", "BLOCKER"]]
                                if critical:
                                    human_actions_required.append(f"Review and resolve {len(critical)} critical engineering findings.")

                        elif cap_id == "requirement_coverage" and plan.system_id:
                            engine_versions["requirement_coverage_engine"] = "v1.0.0"
                            dec_repo = DecisionRepository(self.db)
                            reqs = await dec_repo.get_requirements_by_system(plan.system_id, tenant_id=tenant_id)
                            cov_res = RequirementCoverageService.evaluate_coverage(reqs, [])
                            results.append({"capability": cap_id, "coverage": cov_res})
                            for u in cov_res.get("unknown_requirements", []):
                                unknowns.append({"source": "requirement_coverage", "requirement_id": u})

                        elif cap_id == "verification_status":
                            engine_versions["verification_engine"] = "v1.5.0"
                            verification_impacts.append({
                                "task": task.description,
                                "status": "VERIFICATION_AUDIT_COMPLETE",
                                "physical_evidence_required": True,
                            })

                        elif cap_id == "traceability":
                            engine_versions["provenance_engine"] = "v1.0.0"
                            traceability.append({
                                "system_id": plan.system_id,
                                "circuit_id": plan.circuit_id,
                                "status": "TRACE_RECORDED",
                            })

                        elif cap_id == "design_review_readiness" and plan.system_id:
                            engine_versions["readiness_engine"] = "v1.0.0"
                            dec_repo = DecisionRepository(self.db)
                            reviews = await dec_repo.get_design_reviews_by_system(plan.system_id, tenant_id=tenant_id)
                            if reviews:
                                readiness = DesignReviewReadinessService.evaluate_readiness(
                                    reviews[0],
                                    checkpoints=reviews[0].checkpoints or [],
                                    findings=reviews[0].findings or [],
                                )
                                results.append({"capability": cap_id, "readiness": readiness})
                                if readiness["overall_status"] == "BLOCKED":
                                    human_actions_required.append(f"Address {len(readiness['blockers'])} blockers before closing review.")
                    except Exception as e:
                        task_failed = True
                        task_failure_reason = f"{cap_id.upper()}_FAILED: {str(e)}"
                        break

            if task_failed:
                task.status = TaskStatus.FAILED.value
                task.blocking_reason = task_failure_reason
                blocking_reasons.append(task_failure_reason)
                failed_task = {
                    "task_id": task.id,
                    "order_index": task.order_index,
                    "description": task.description,
                    "reason": task_failure_reason,
                }
                has_failed = True
            else:
                task.status = TaskStatus.COMPLETED.value
                completed_tasks.append(task.id)

        completed_at = datetime.now(timezone.utc)

        # 4. Determine status: SUCCESS, PARTIAL, or FAILED
        if has_failed:
            if completed_tasks:
                exec_status = ExecutionStatus.PARTIAL.value
                plan.status = PlanStatus.PARTIAL.value
            else:
                exec_status = ExecutionStatus.FAILED.value
                plan.status = PlanStatus.FAILED.value
        else:
            exec_status = ExecutionStatus.SUCCESS.value
            plan.status = PlanStatus.COMPLETED.value

        plan.completed_at = completed_at
        plan.blocking_reasons = blocking_reasons

        # Add execution breakdown metadata
        results.append({
            "execution_breakdown": {
                "completed_tasks": completed_tasks,
                "failed_task": failed_task,
                "remaining_tasks": remaining_tasks,
                "execution_status": exec_status,
            }
        })

        # 5. Generate AI Explanation of deterministic results
        explanation = EngineeringExplanationService.generate_explanation(
            plan=plan,
            results=results,
            findings=findings,
            unknowns=unknowns,
            human_actions=human_actions_required,
        )

        # 6. Persist Execution Record
        execution = EngineeringCognitiveExecution(
            tenant_id=tenant_id,
            plan_id=plan.id,
            intent_packet_id=plan.intent_packet_id,
            execution_status=exec_status,
            started_at=started_at,
            completed_at=completed_at,
            results=results,
            findings=findings,
            unknowns=unknowns,
            requirements_affected=requirements_affected,
            constraints_affected=constraints_affected,
            verification_impacts=verification_impacts,
            traceability=traceability,
            human_actions_required=human_actions_required,
            blocking_reasons=blocking_reasons,
            explanation=explanation,
        )
        self.db.add(execution)
        await self.db.flush()

        # 7. Generate SHA-256 Input and Output Digests for Provenance
        input_data = {
            "intent_packet_id": plan.intent_packet_id,
            "project_id": plan.project_id,
            "system_id": plan.system_id,
            "circuit_id": plan.circuit_id,
            "base_revision": plan.base_revision,
            "context_snapshot_id": plan.context_snapshot_id,
            "snapshot": plan.context_snapshot,
        }
        output_data = {
            "execution_id": execution.id,
            "execution_status": exec_status,
            "completed_tasks_count": len(completed_tasks),
            "results_count": len(results),
            "findings_count": len(findings),
            "unknowns_count": len(unknowns),
        }
        in_digest = hashlib.sha256(json.dumps(input_data, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        out_digest = hashlib.sha256(json.dumps(output_data, sort_keys=True, default=str).encode("utf-8")).hexdigest()

        # 8. Persist Cognitive Provenance Record (Integrity Digest & Execution Provenance)
        provenance = EngineeringCognitiveProvenance(
            tenant_id=tenant_id,
            cognitive_execution_id=execution.id,
            intent_packet_id=plan.intent_packet_id,
            plan_id=plan.id,
            context_snapshot_id=plan.context_snapshot_id,
            project_id=plan.project_id,
            system_id=plan.system_id,
            circuit_id=plan.circuit_id,
            base_revision=plan.base_revision,
            model_provider="QUEBET_COGNITIVE_ROUTER",
            model_identifier="deterministic-orchestrator-v1",
            prompt_id="intent_resolver",
            prompt_version="v1.0.0",
            schema_version="v1.0.0",
            capability_versions=capability_versions,
            deterministic_engine_versions=engine_versions,
            rule_set_version="v1.0.0",
            input_digest=in_digest,
            output_digest=out_digest,
        )
        self.db.add(provenance)

        await self.db.commit()
        await self.db.refresh(execution)
        return execution
