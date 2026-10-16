# Context Snapshots & Canonical Hashing

## 1. Motivation & Purpose
To eliminate race conditions and non-deterministic plan generation, every `EngineeringTaskPlan` is bound to a canonical `EngineeringCognitiveContextSnapshot`.

The snapshot captures:
- `project_id` & `project_revision`
- `system_id` & `system_revision`
- `circuit_id` & `circuit_revision`
- Latest `analysis_id`
- Active `requirement_baseline_id`
- Latest `knowledge_snapshot_id`
- Active `assumption_ids` and `scenario_ids`
- Active `engine_versions` and `rule_set_version`

## 2. Canonical Digest Algorithm
The canonical SHA-256 digest is deterministically computed by `ContextSnapshotService.compute_canonical_digest`:
1. Normalizes all IDs and revisions to strings or integers.
2. Lexicographically sorts all collections (`assumption_ids`, `scenario_ids`, and `engine_versions` keys).
3. Produces compact JSON with sorted keys and minimal separators `(',', ':')`.
4. Computes SHA-256 hash over UTF-8 bytes.

### Invariants:
- **Order Invariance**: The order of assumptions or scenarios provided to the API does not alter the digest.
- **Sensitivity**: Any revision change (project, system, or circuit) produces a completely distinct hash.
- **Auditability**: SHA-256 provides an integrity digest and audit trail; it is not cryptographic authorization.

## 3. Stale Rejection (HTTP 409)
During pre-execution validation, if the current database revision of the system or circuit exceeds `plan.base_revision`, execution is rejected immediately with HTTP 409 `COGNITIVE_PLAN_STALE` and the plan is atomically transitioned to `PlanStatus.STALE`.
