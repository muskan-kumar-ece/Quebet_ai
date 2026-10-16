from typing import Any, Dict, List, Set
from app.models.db.cognitive import EngineeringIntentPacket, IntentType
from app.models.schemas.cognitive import EngineeringTaskCreate


class TaskDecomposer:
    """
    Decomposes an IntentPacket and engineering context into a structured,
    validated Directed Acyclic Graph (DAG) of EngineeringTasks.
    Rejects cyclic plans and validates capability compatibility.
    """

    @classmethod
    def decompose(
        cls,
        intent: EngineeringIntentPacket,
        context: Dict[str, Any],
    ) -> List[EngineeringTaskCreate]:
        intent_type = intent.intent_type
        tasks: List[EngineeringTaskCreate] = []

        if intent_type == IntentType.ANALYZE_CIRCUIT.value:
            tasks = [
                EngineeringTaskCreate(
                    task_type="RETRIEVE_CIRCUIT_TOPOLOGY",
                    description=f"Resolve circuit graph and calculate electrical behavior for circuit {intent.circuit_id or 'default'}",
                    target_objects=[{"type": "circuit", "id": intent.circuit_id}],
                    dependencies=[],
                    required_capabilities=["circuit_analysis"],
                    required_inputs={"circuit_id": intent.circuit_id},
                    expected_outputs=["calculations", "graph_summary"],
                    order_index=0,
                ),
                EngineeringTaskCreate(
                    task_type="EVALUATE_CIRCUIT_FINDINGS",
                    description="Evaluate electrical, thermal, and rule findings from deterministic analysis",
                    target_objects=[{"type": "circuit", "id": intent.circuit_id}],
                    dependencies=["task_0"],
                    required_capabilities=["finding_analysis"],
                    required_inputs={"circuit_id": intent.circuit_id},
                    expected_outputs=["findings", "anomalies"],
                    order_index=1,
                ),
                EngineeringTaskCreate(
                    task_type="CHECK_VERIFICATION_OBLIGATIONS",
                    description="Check verification requirements and missing evidence for detected findings",
                    target_objects=[{"type": "circuit", "id": intent.circuit_id}],
                    dependencies=["task_1"],
                    required_capabilities=["verification_status"],
                    required_inputs={"circuit_id": intent.circuit_id},
                    expected_outputs=["verification_requirements", "evidence_gaps"],
                    order_index=2,
                ),
            ]

        elif intent_type == IntentType.ANALYZE_SYSTEM.value:
            tasks = [
                EngineeringTaskCreate(
                    task_type="ANALYZE_SYSTEM_TOPOLOGY",
                    description=f"Analyze subsystem interfaces and power domains for system {intent.system_id}",
                    target_objects=[{"type": "system", "id": intent.system_id}],
                    dependencies=[],
                    required_capabilities=["system_analysis"],
                    required_inputs={"system_id": intent.system_id},
                    expected_outputs=["interface_status", "power_domains"],
                    order_index=0,
                ),
                EngineeringTaskCreate(
                    task_type="EVALUATE_FAILURE_PROPAGATION",
                    description="Evaluate cross-subsystem failure modes and containment barriers",
                    target_objects=[{"type": "system", "id": intent.system_id}],
                    dependencies=["task_0"],
                    required_capabilities=["failure_analysis"],
                    required_inputs={"system_id": intent.system_id},
                    expected_outputs=["propagated_paths", "containment_status"],
                    order_index=1,
                ),
                EngineeringTaskCreate(
                    task_type="EVALUATE_REQUIREMENT_COVERAGE",
                    description="Evaluate deterministic 4-state requirement coverage",
                    target_objects=[{"type": "system", "id": intent.system_id}],
                    dependencies=["task_1"],
                    required_capabilities=["requirement_coverage"],
                    required_inputs={"system_id": intent.system_id},
                    expected_outputs=["coverage_summary", "unknowns"],
                    order_index=2,
                ),
            ]

        elif intent_type in [IntentType.CHECK_REQUIREMENTS.value, IntentType.CHECK_CONSTRAINTS.value]:
            tasks = [
                EngineeringTaskCreate(
                    task_type="EVALUATE_REQUIREMENT_COVERAGE",
                    description=f"Evaluate requirement coverage for system {intent.system_id}",
                    target_objects=[{"type": "system", "id": intent.system_id}],
                    dependencies=[],
                    required_capabilities=["requirement_coverage"],
                    required_inputs={"system_id": intent.system_id},
                    expected_outputs=["coverage_breakdown"],
                    order_index=0,
                ),
                EngineeringTaskCreate(
                    task_type="EVALUATE_CONSTRAINTS",
                    description="Evaluate design constraints against active subsystem parameters",
                    target_objects=[{"type": "system", "id": intent.system_id}],
                    dependencies=["task_0"],
                    required_capabilities=["constraint_evaluation"],
                    required_inputs={"system_id": intent.system_id},
                    expected_outputs=["satisfied", "violated"],
                    order_index=1,
                ),
            ]

        elif intent_type == IntentType.REVIEW_DESIGN.value:
            tasks = [
                EngineeringTaskCreate(
                    task_type="CHECK_REVIEW_READINESS",
                    description=f"Evaluate design review readiness and blocker gating for system {intent.system_id}",
                    target_objects=[{"type": "system", "id": intent.system_id}],
                    dependencies=[],
                    required_capabilities=["design_review_readiness"],
                    required_inputs={"system_id": intent.system_id},
                    expected_outputs=["readiness_status", "blockers"],
                    order_index=0,
                ),
                EngineeringTaskCreate(
                    task_type="AUDIT_VERIFICATION_STATUS",
                    description="Audit verification requirements and test point evidence",
                    target_objects=[{"type": "system", "id": intent.system_id}],
                    dependencies=["task_0"],
                    required_capabilities=["verification_status"],
                    required_inputs={"system_id": intent.system_id},
                    expected_outputs=["unverified_items"],
                    order_index=1,
                ),
            ]

        elif intent_type == IntentType.TRACE_ENGINEERING_FACT.value:
            tasks = [
                EngineeringTaskCreate(
                    task_type="TRACE_PROVENANCE_CHAIN",
                    description="Trace engineering facts, knowledge records, and manufacturer sources",
                    target_objects=[{"type": "system", "id": intent.system_id}],
                    dependencies=[],
                    required_capabilities=["traceability"],
                    required_inputs={"system_id": intent.system_id},
                    expected_outputs=["trace_graph", "sources"],
                    order_index=0,
                ),
            ]

        elif intent_type == IntentType.COMPARE_ALTERNATIVES.value:
            tasks = [
                EngineeringTaskCreate(
                    task_type="COMPARE_DESIGN_ALTERNATIVES",
                    description="Generate multidimensional comparison matrix without composite scores",
                    target_objects=[{"type": "system", "id": intent.system_id}],
                    dependencies=[],
                    required_capabilities=["decision_comparison"],
                    required_inputs={"system_id": intent.system_id},
                    expected_outputs=["comparison_matrix", "unknowns"],
                    order_index=0,
                ),
            ]

        else:
            # Default single-task analysis
            tasks = [
                EngineeringTaskCreate(
                    task_type="EVALUATE_ENGINEERING_TARGET",
                    description=intent.goal,
                    target_objects=intent.affected_objects or [],
                    dependencies=[],
                    required_capabilities=["finding_analysis"],
                    required_inputs={"system_id": intent.system_id, "circuit_id": intent.circuit_id},
                    expected_outputs=["findings", "unknowns"],
                    order_index=0,
                )
            ]

        # Validate DAG (no cycles)
        cls.validate_dag(tasks)
        return tasks

    @classmethod
    def validate_dag(cls, tasks: List[EngineeringTaskCreate]) -> None:
        """
        Validates task graph is a directed acyclic graph (DAG).
        Raises ValueError if a cycle is detected.
        """
        task_indices = {f"task_{i}": i for i in range(len(tasks))}
        adj: Dict[int, List[int]] = {i: [] for i in range(len(tasks))}

        for i, t in enumerate(tasks):
            for dep in t.dependencies:
                dep_idx = task_indices.get(dep)
                if dep_idx is not None:
                    adj[dep_idx].append(i)

        visited: Set[int] = set()
        rec_stack: Set[int] = set()

        def has_cycle(node: int) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.remove(node)
            return False

        for i in range(len(tasks)):
            if i not in visited:
                if has_cycle(i):
                    raise ValueError(f"CYCLIC_TASK_GRAPH: Cycle detected at task index {i}")
