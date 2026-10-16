# Task Planning Model & DAG Invariants

## 1. DAG Invariants
Every `EngineeringTaskPlan` represents a Directed Acyclic Graph (DAG) of discrete tasks.

1. **Cycle Prevention:**
   The `TaskDecomposer` validates the task list via topological sort (Kahn's algorithm). If any cycle is detected (e.g. `Task A -> Task B -> Task A`), a `ValueError("CYCLIC_TASK_GRAPH")` is raised and plan synthesis is aborted.

2. **Explicit Capability Dependencies:**
   Tasks declare dependencies explicitly (e.g. `dependencies: ["task_0"]`). Downstream tasks consume outputs from upstream tasks without implicit side-effects.

3. **Revision Binding:**
   Plans are bound to a specific `base_revision` corresponding to the system or circuit at the moment of plan creation. If concurrent modifications advance the system revision, the plan is marked stale and execution is blocked with HTTP 409 `COGNITIVE_PLAN_STALE`.

## 2. Plan Validation Dimensions
The `EngineeringPlanValidator` runs 5 checks:
- **Structural:** DAG topology, valid capabilities declared in registry, non-empty task list.
- **Context:** Object existence (project, system, circuit), revision freshness.
- **Engineering:** All ambiguities resolved; no pending `CLARIFICATION_REQUIRED` flags.
- **Security:** Strict tenant isolation; requesting user belongs to the plan's tenant.
- **Governance:** Non-mutation enforcement; all declared capabilities must have `mutates_state = False`.
