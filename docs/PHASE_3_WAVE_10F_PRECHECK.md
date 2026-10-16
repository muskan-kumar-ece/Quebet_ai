# QUEBET AI — Phase 3 Wave 10F Precheck Report

## Neon PostgreSQL Migration Verification, Alembic Configuration & Database State

**Date:** 2026-10-15  
**Auditor / Verification Lead:** Principal Software Architect, Application Security Engineer, Database Concurrency Specialist  
**Target Repository:** `C:\workflow\quebet_ai`  
**Target Database:** Neon Cloud PostgreSQL (PostgreSQL 18.6 via PgBouncer transaction-pooler)  
**Precheck Status:** `WAVE_10F_PRECHECK_PASS_WITH_LIMITATIONS`

---

## 1. Executive Summary

This independent precheck verifies the actual database state, migration history, Alembic engine configuration, driver parameters, and release governance schema on the live Neon PostgreSQL instance ahead of Phase 3 Wave 10F (PostgreSQL Concurrency & Transaction Integrity Verification).

### High-Level Verdict
- **Migration Graph:** Strictly linear from `001_initial_schema` to `027_phase_3_wave_10c_release_gates_and_baselines` with zero gaps, zero branch heads, and zero unapplied revisions.
- **Live Database Head:** Verified at `027_phase_3_wave_10c_release_gates_and_baselines`.
- **Live Database Tables:** 95 relational tables successfully created in the `public` schema.
- **Release Governance & Audit Ledger:** Tables `engineering_audit_events`, `engineering_release_evaluations`, `engineering_release_baselines`, and `cross_domain_validation_records` verified with correct primary keys, unique constraints, foreign keys (including `ON DELETE RESTRICT`), indexes, and column types.
- **Alembic Driver Customizations:** Alembic `DefaultImpl.version_table_impl` successfully configured to use `String(128)`, and asyncpg configured with `statement_cache_size: 0` / `prepared_statement_cache_size: 0` for safe operation with Neon's PgBouncer transaction pooler.
- **Wave 10 Unit Test Baseline:** 46/46 unit tests passing (executed against isolated in-memory SQLite).
- **Live Read-Only Application Engine Integration:** Non-destructive query test against live Neon PostgreSQL executed cleanly with zero errors and successful transactional rollback.

---

## 2. Working-Tree Preservation Status

An inspection of `git status --short` and `git diff` confirms that all pre-existing user modifications have been preserved intact without reset, stash, clean, or checkout:

- **Tracked Modified Files Preserved (20 files):**
  - `admin/tsconfig.json`
  - `backend/app/api/v1/router.py`
  - `backend/app/api/v1/routes/admin.py`
  - `backend/app/api/v1/routes/health.py`
  - `backend/app/api/v1/routes/models_list.py`
  - `backend/app/core/config.py`
  - `backend/app/core/database.py` (updated with PgBouncer statement cache settings)
  - `backend/app/core/dependencies.py`
  - `backend/app/core/security.py`
  - `backend/app/main.py`
  - `backend/app/models/db/project.py`
  - `backend/app/models/db/user.py`
  - `backend/app/repositories/model_repo.py`
  - `backend/app/services/ai/model_router.py`
  - `backend/migrations/env.py` (updated with `_custom_version_table_impl` and pooler arguments)
  - `backend/tests/conftest.py`
  - `backend/tests/unit/test_health.py`
  - `frontend/package.json`
  - `frontend/src/app/api/proxy/[...path]/route.ts`
  - `frontend/tsconfig.json`
- **Untracked Migration Files:** All 26 newly authored migration version scripts (`002` through `027`) remain present and tracked.
- **Safety Violation:** Zero destructive operations executed against live data; zero credentials logged.

---

## 3. Migration Graph Audit

### Alembic Revisions and Linearity Check

Executed:
```bash
python -m alembic heads
# Output:
# 027_phase_3_wave_10c_release_gates_and_baselines (head)

python -m alembic history --indicate-current
```

The migration revision chain was inspected from `<base>` to `head`:
1. `<base> -> 001_initial_schema`
2. `001_initial_schema -> 002_add_user_role`
3. `002_add_user_role -> 003_phase_1_circuit_foundation`
4. `003_phase_1_circuit_foundation -> 004_phase_1_wave_2_proposals`
5. `004_phase_1_wave_2_proposals -> 005_phase_1_wave_3_analysis`
6. `005_phase_1_wave_3_analysis -> 006_phase_1_wave_4_design_intelligence`
7. `006_phase_1_wave_4_design_intelligence -> 007_phase_1_wave_5_verification`
8. `007_phase_1_wave_5_verification -> 008_phase_1_wave_6_provenance`
9. `008_phase_1_wave_6_provenance -> 009_phase_1_wave_7_system`
10. `009_phase_1_wave_7_system -> 010_phase_1_wave_8_system_design_synthesis`
11. `010_phase_1_wave_8_system_design_synthesis -> 011_phase_1_wave_9_requirements_decisions`
12. `011_phase_1_wave_9_requirements_decisions -> 012_phase_2_wave_1_cognitive_intent_planning`
13. `012_phase_2_wave_1_cognitive_intent_planning -> 013_phase_2_wave_1_1_cognitive_hardening`
14. `013_phase_2_wave_1_1_cognitive_hardening -> 014_phase_2_wave_2_cognitive_reflection`
15. `014_phase_2_wave_2_cognitive_reflection -> 015_phase_2_wave_3_decision_brief`
16. `015_phase_2_wave_3_decision_brief -> 016_phase_2_wave_4_engineering_memory`
17. `016_phase_2_wave_4_engineering_memory -> 017_phase_2_wave_5_context_synthesis`
18. `017_phase_2_wave_5_context_synthesis -> 018_phase_2_wave_6_workflow_orchestration`
19. `018_phase_2_wave_6_workflow_orchestration -> 019_phase_3_wave_1_knowledge_intelligence`
20. `019_phase_3_wave_1_knowledge_intelligence -> 020_phase_3_wave_2_component_intelligence`
21. `020_phase_3_wave_2_component_intelligence -> 021_phase_3_wave_4_simulation`
22. `021_phase_3_wave_4_simulation -> 022_phase_3_wave_5_pcb`
23. `022_phase_3_wave_5_pcb -> 023_phase_3_wave_6_bom`
24. `023_phase_3_wave_6_bom -> 024_phase_3_wave_7_dfm`
25. `024_phase_3_wave_7_dfm -> 025_phase_3_wave_8_cross_domain`
26. `025_phase_3_wave_8_cross_domain -> 026_phase_3_wave_10_release_and_audit`
27. `026_phase_3_wave_10_release_and_audit -> 027_phase_3_wave_10c_release_gates_and_baselines (head) (current)`

**Verification Finding:**
- Graph is single-rooted, unbranched, and fully contiguous.
- Current database record strictly matches `027_phase_3_wave_10c_release_gates_and_baselines`.
- Audit ledger tables are introduced in revision `026`.
- Release evaluation and baseline tables are introduced in revision `027`.

---

## 4. Live Database State & Schema Verification

A read-only inspection script was executed against the live Neon PostgreSQL instance via `asyncpg`.

### 4.1 Alembic Version Table
- **Table Name:** `alembic_version`
- **Column Name:** `version_num`
- **Data Type:** `character varying(128)`
- **Nullable:** `NO`
- **Primary Key:** `alembic_version_pkc`
- **Current Row Value:** `'027_phase_3_wave_10c_release_gates_and_baselines'`

### 4.2 Release Governance & Audit Ledger Schema

#### Table: `engineering_audit_events` (15 Columns)
- **Columns:** `id`, `project_id`, `tenant_id`, `sequence_number`, `actor_id`, `actor_role`, `event_type`, `entity_type`, `entity_id`, `entity_revision`, `payload`, `payload_hash`, `prev_event_hash`, `event_hash`, `created_at`
- **Primary Key:** `engineering_audit_events_pkey` (`id`)
- **Unique Constraint:** `uq_audit_project_sequence` on `('project_id', 'sequence_number')`
- **Foreign Key:** `project_id -> projects(id)` ON DELETE CASCADE
- **Indexes Verified:**
  - `ix_engineering_audit_events_project_id`
  - `ix_engineering_audit_events_tenant_id`
  - `ix_engineering_audit_events_event_type`
  - `ix_engineering_audit_events_entity_id`
  - `ix_engineering_audit_events_event_hash`

#### Table: `engineering_release_evaluations` (21 Columns)
- **Columns:** `id`, `project_id`, `tenant_id`, `evaluator_version`, `project_revision`, `overall_readiness`, `is_stale`, `state_fingerprint`, `gate_results`, `blocking_findings`, `missing_evidence`, `stale_evidence`, `audit_chain_verified`, `audit_chain_head_hash`, `audit_chain_sequence`, `audit_chain_trusted_anchor_checked`, `evaluated_by_id`, `evaluated_at`, `created_at`, `updated_at`, `deleted_at`
- **Boolean Integrity:** `is_stale`, `audit_chain_verified`, `audit_chain_trusted_anchor_checked` are `boolean NOT NULL`
- **Primary Key:** `engineering_release_evaluations_pkey` (`id`)
- **Foreign Key:** `project_id -> projects(id)` ON DELETE CASCADE
- **Indexes Verified:**
  - `ix_engineering_release_evaluations_project_id`
  - `ix_engineering_release_evaluations_tenant_id`
  - `ix_engineering_release_evaluations_overall_readiness`

#### Table: `engineering_release_baselines` (28 Columns)
- **Columns:** `id`, `release_tag`, `project_id`, `tenant_id`, `evaluation_id`, `project_revision`, `circuit_id`, `circuit_version`, `circuit_digest`, `board_id`, `board_version`, `board_digest`, `bom_id`, `bom_version`, `bom_digest`, `audit_chain_head_hash`, `audit_chain_sequence`, `audit_chain_trusted_anchor_checked`, `evaluation_snapshot`, `canonical_snapshot_digest`, `authorized_by_id`, `authorized_by_role`, `authorized_at`, `release_rationale`, `exceptions_approved`, `created_at`, `updated_at`, `deleted_at`
- **Primary Key:** `engineering_release_baselines_pkey` (`id`)
- **Unique Constraint:** `uq_release_project_tag` on `('project_id', 'release_tag')`
- **Foreign Keys:**
  - `project_id -> projects(id)` ON DELETE CASCADE
  - `evaluation_id -> engineering_release_evaluations(id)` ON DELETE RESTRICT (prohibits deleting an evaluation when a baseline relies on it)
- **Indexes Verified:**
  - `ix_engineering_release_baselines_release_tag`
  - `ix_engineering_release_baselines_project_id`
  - `ix_engineering_release_baselines_tenant_id`
  - `ix_engineering_release_baselines_evaluation_id`
  - `ix_engineering_release_baselines_canonical_snapshot_digest`

#### Table: `cross_domain_validation_records` (16 Columns)
- **Columns:** `id`, `tenant_id`, `project_id`, `circuit_id`, `board_id`, `bom_id`, `validation_status`, `summary`, `findings`, `domain_snapshots`, `is_stale`, `staleness_reasons`, `snapshot_digest`, `created_at`, `updated_at`, `deleted_at`
- **Boolean Integrity:** `is_stale` is `boolean NOT NULL DEFAULT false`
- **Primary Key:** `cross_domain_validation_records_pkey` (`id`)
- **Foreign Keys:**
  - `project_id -> projects(id)` ON DELETE CASCADE
  - `circuit_id -> circuits(id)` ON DELETE SET NULL
  - `board_id -> engineering_boards(id)` ON DELETE SET NULL
  - `bom_id -> engineering_boms(id)` ON DELETE SET NULL

---

## 5. Alembic Customization Compatibility Review

### 5.1 Custom `version_table_impl`
In [backend/migrations/env.py](file:///c:/workflow/quebet_ai/backend/migrations/env.py):
```python
def _custom_version_table_impl(
    self,
    *,
    version_table: str,
    version_table_schema=None,
    version_table_pk: bool = True,
    **kw,
) -> Table:
    vt = Table(
        version_table,
        MetaData(),
        Column("version_num", String(128), nullable=False),
        schema=version_table_schema,
    )
    if version_table_pk:
        vt.append_constraint(
            PrimaryKeyConstraint("version_num", name=f"{version_table}_pkc")
        )
    return vt

alembic_impl.DefaultImpl.version_table_impl = _custom_version_table_impl
```

**Technical Verification:**
- Installed Alembic version is **1.18.4**.
- Alembic introduced `DefaultImpl.version_table_impl` in version **1.14** specifically as an extensible hook for dialects and custom structures.
- In clean database environments, Alembic invokes this hook during initial table creation, generating `VARCHAR(128)`.
- Verified in live Neon database: `version_num` is indeed `character varying(128)`.
- **Limitation on Existing Databases:** If an existing database previously created `alembic_version` under Alembic's unpatched default (`VARCHAR(32)`), this hook alone does not issue an `ALTER TABLE` DDL. To ensure cross-environment safety on legacy databases, a startup safety check or pre-migration DDL will be required if existing instances are upgraded.

### 5.2 Offline Mode Verification
Tested command:
```bash
python -m alembic upgrade 026_phase_3_wave_10_release_and_audit:027_phase_3_wave_10c_release_gates_and_baselines --sql
```
- Generated standard, valid transactional SQL statements wrapped in `BEGIN; ... COMMIT;`.
- Correctly referenced `alembic_version` updates and foreign key constraints (`ON DELETE RESTRICT`).

---

## 6. PostgreSQL Driver & Connection Pooler Configuration

### 6.1 Statement Caching Interaction with PgBouncer
Neon utilizes PgBouncer in transaction-pooling mode (`-pooler.c-3.ap-southeast-1.aws.neon.tech`).

In transaction pooling, consecutive transactions or queries from the same client connection can be dispatched to different PostgreSQL backend server processes. If client-side or driver-side statement caching is enabled:
1. `asyncpg` assigns a server-side prepared statement name (e.g., `__asyncpg_stmt_1__`).
2. When the backend changes, or when transactional DDL alters an underlying schema or table column, the prepared statement cache is invalidated on the server, causing `InvalidCachedStatementError: cached statement plan is invalid due to a database schema or configuration change`.
3. If an asyncpg prepared statement is executed on a different pooled backend, PostgreSQL raises `prepared statement does not exist`.

### 6.2 Application Engine vs Migration Engine Configuration

1. **Migration Engine (`backend/migrations/env.py`):**
   - Uses `poolclass=pool.NullPool` to completely eliminate connection pooling across migration phases.
   - Configured with `connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0}`.
   - Result: Zero cached statements during DDL creation; migrations executed through to revision 027 without pooler errors.

2. **Application Engine (`backend/app/core/database.py`):**
   - Uses SQLAlchemy `AsyncAdaptedQueuePool` for connection reuse.
   - Configured with:
     ```python
     connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {
         "prepared_statement_cache_size": 0,
         "statement_cache_size": 0,
     }
     ```
   - Disables statement caching both at the SQLAlchemy adapter level (`prepared_statement_cache_size=0`) and the asyncpg driver level (`statement_cache_size=0`).
   - Retains normal connection pooling without suffering PgBouncer prepared-statement collisions.

---

## 7. Migration 025 Inspection (`025_phase_3_wave_8_cross_domain.py`)

- **Root Cause Identified:** Earlier revision of 025 used `server_default=sa.text("0")` for column `is_stale BOOLEAN`. PostgreSQL does not allow integer defaults for boolean columns (`DatatypeMismatchError: column "is_stale" is of type boolean but default expression is of type integer`).
- **Correction Applied:** Replaced with SQLAlchemy dialect-agnostic boolean default `server_default=sa.false()`.
- **Database Status:** The migration has been applied cleanly. In the live Neon database:
  - Column `is_stale` is verified as `boolean NOT NULL DEFAULT false`.
- **Downgrade Behavior:** Downgrade properly drops indexes and removes `cross_domain_validation_records`.
- **No Remediation Required:** The live database schema and migration script are in 100% concordance.

---

## 8. Test Execution Evidence

### 8.1 SQLite In-Memory Test Suites
The unit test suite runs against isolated in-memory SQLite fixtures (`sqlite+aiosqlite:///:memory:`):

| Test Suite | Scope | Result | Execution Time |
| :--- | :--- | :--- | :--- |
| `backend/tests/unit/test_phase3_wave10a.py` | Audit Ledger Foundation | 8/8 PASSED | ~1.5s |
| `backend/tests/unit/test_phase3_wave10b.py` | Mutation Integrations & Immutability | 8/8 PASSED | ~2.1s |
| `backend/tests/unit/test_phase3_wave10b1.py`| Verification/Memory Audit Chains | 9/9 PASSED | ~2.3s |
| `backend/tests/unit/test_phase3_wave10c.py` | Release Gate Engine & Baselines | 15/15 PASSED | ~11.2s |
| `backend/tests/unit/test_phase3_wave10d.py` | Lifecycle Governance & Integrity | 6/6 PASSED | ~3.0s |
| **Total Wave 10 Suite** | **Comprehensive Wave 10** | **46/46 PASSED** | **20.14s** |
| `backend/tests/unit/test_phase3_wave8.py`   | Cross-Domain Consistency | **63/63 PASSED** | **0.86s** |

### 8.2 Live Neon PostgreSQL Integration Check
Executed dedicated non-destructive live integration script:
```text
Testing live application AsyncSessionLocal against Neon PostgreSQL...
Verified Project table query: count = 0
Verified EngineeringAuditEvent table query: count = 0
Verified EngineeringReleaseEvaluation table query: count = 0
Verified EngineeringReleaseBaseline table query: count = 0
Verified CrossDomainValidationRecord table query: count = 0
Testing transactional rollback semantics...
Transaction rollback verified successfully.
Application engine verification completed cleanly.
```

---

## 9. Categorized Findings & Fact Classification

### 9.1 Verified Facts
1. All 27 migrations are applied on live Neon PostgreSQL with `alembic_version` at `027_phase_3_wave_10c_release_gates_and_baselines`.
2. All 95 tables exist in the `public` schema.
3. `alembic_version.version_num` is `character varying(128)`.
4. `engineering_audit_events`, `engineering_release_evaluations`, `engineering_release_baselines`, and `cross_domain_validation_records` match SQLAlchemy declarative models and migration specifications.
5. Foreign key constraint `ON DELETE RESTRICT` from release baselines to release evaluations is physically enforced in the database.
6. The entire 46-test Wave 10 unit test suite passes cleanly.
7. Live queries via `AsyncSessionLocal` succeed against the Neon pooler without prepared statement errors.

### 9.2 Inferred Findings
1. While `NullPool` and `statement_cache_size: 0` resolved the `InvalidCachedStatementError` during migration execution and basic queries, heavy concurrent traffic against the PgBouncer pooler may encounter connection pool exhaustion if connections are held open across lengthy external AI calls. (Recommendation: Ensure short-lived sessions).

### 9.3 Unverified Claims
1. **PostgreSQL Concurrent Race Handling:** Although the audit ledger and release baseline engine use `SELECT FOR UPDATE` and sequence numbers to prevent concurrent sequence collision, **actual multi-process concurrency has only been validated in SQLite in-memory suites**. SQLite uses database-level locking and does not replicate PostgreSQL's row-level locking, MVCC read-committed anomalies, or PgBouncer transaction-boundary behavior.
   - *This unverified claim is the exact objective of Wave 10F.*

---

## 10. Remaining Risks & Recommended Wave 10F Plan

### 10.1 Identified Risks
1. **PostgreSQL Concurrency Under PgBouncer:** Transactional locking (`SELECT ... FOR UPDATE`) across concurrent transactions within PgBouncer requires verification to ensure locks are released promptly upon transaction completion.
2. **Legacy Alembic Versions:** If another environment has an existing `alembic_version` created with `VARCHAR(32)`, it will fail without an explicit `ALTER TABLE` statement.

### 10.2 Wave 10F Execution Plan
1. Implement PostgreSQL-native concurrent test harness simulating:
   - Simultaneous release baseline creation requests for the same project.
   - Concurrent audit event appending to verify sequence ordering under contention.
   - Read-after-write consistency across pooled connections.
2. Verify lock contention resolution and timeout handling.

---

## 11. Final Verdict

```text
WAVE_10F_PRECHECK_PASS_WITH_LIMITATIONS
```

**Limitations Summary:**
1. Unit tests pass in SQLite in-memory fixtures; true multi-worker transaction concurrency against Neon PostgreSQL remains to be executed in Wave 10F.
2. Existing legacy databases require pre-widening of `alembic_version.version_num` if previously initialized with `VARCHAR(32)`.
