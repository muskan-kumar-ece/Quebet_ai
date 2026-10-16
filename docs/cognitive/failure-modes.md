# Failure Modes & Resilience Architecture

## 1. Failure Isolation
The Cognitive Layer is designed as an advisory copilot layer above deterministic Phase 1 foundations:
- If the cognitive LLM provider times out, fails, or is unavailable, Phase 1 deterministic endpoints (circuit analysis, system architecture, verification, decision management) continue to operate with 100% functionality.
- Cognitive failures never corrupt engineering state, alter circuit nets, or grant unverified approvals.

## 2. Partial Execution Handling
When a multi-task plan encounters an upstream task failure or policy violation:
1. Upstream execution halts immediately.
2. Remaining downstream tasks remain in `PENDING` state with `blocking_reason` populated.
3. Execution record records status `PARTIAL` (if some tasks succeeded) or `FAILED` (if none succeeded). It **NEVER** reports `SUCCESS` or `COMPLETED`.
4. Execution results record an `execution_breakdown`:
   - `completed_tasks`: list of succeeded task IDs.
   - `failed_task`: object with `task_id`, `description`, and `reason`.
   - `remaining_tasks`: list of skipped/halted task IDs.
   - `execution_status`: `"PARTIAL"` or `"FAILED"`.
5. The plan transitions to `PlanStatus.PARTIAL` or `PlanStatus.FAILED`.

## 3. Stale Context Detection
If a system or circuit undergoes modification while a plan is awaiting execution:
- Pre-execution check detects `current_revision > plan.base_revision`.
- HTTP 409 `COGNITIVE_PLAN_STALE` is returned.
- Plan status transitions to `STALE`.
- The user is prompted to regenerate a fresh plan bound to the latest revision.
