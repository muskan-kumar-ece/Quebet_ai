"""
Phase 3 Wave 10F: PostgreSQL Concurrency & Transaction Integrity Verification.

Executes adversarial concurrency, transaction atomicity, and lock serialization
tests against a live, isolated PostgreSQL schema on Neon.

Covers:
A. Concurrent audit append (sequence allocation, hash chain integrity under contention).
B. Concurrent release tags (duplicate tag race, deterministic rejection of loser).
C. Concurrent distinct release tags (audit head advancement invalidates parallel evaluation).
D. Audit failure and baseline atomicity (single-transaction rollback without orphan).
E. Engineering mutation during authorization (freshness check detects circuit mutation).
F. Audit-chain advancement race (unrelated audit event advances head, rejecting stale eval).
G. Transaction rollback (failure injection leaves zero uncommitted or orphaned state).
H. Tenant isolation & AI actor rejection (cross-tenant access denied, AI authority = none).
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import uuid
import pytest
from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Explicitly ensure backend/.env is loaded even if pytest runs from root
backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
if backend_env.exists():
    load_dotenv(backend_env, override=False)

from app.core.config import settings
from app.core.dependencies import AuthenticatedUser
from app.models.db.base import Base
from app.models.db.audit_ledger import AuditEventType, EngineeringAuditEvent
from app.models.db.circuit import Circuit, CircuitValidationStatus
from app.models.db.component import Component
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.models.db.release import (
    EngineeringReleaseBaseline,
    EngineeringReleaseEvaluation,
    OverallReadinessState,
    ReleaseGateStatus,
)
from app.models.schemas.release import ReleaseBaselineCreateRequest
from app.services.audit_ledger_service import AuditLedgerService
from app.services.release_service import ReleaseGateEngine, ReleaseService


from sqlalchemy import event, pool, select, text

TEST_SCHEMA_PREFIX = "wave10f_test_"


@pytest.fixture(scope="function")
async def pg_test_env():
    """
    Initializes a dedicated disposable PostgreSQL test schema on Neon per test.
    Ensures asyncpg engine lifecycle matches the test function's asyncio event loop.
    Tears down and drops the schema completely on exit.
    """
    db_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    if "postgresql" not in db_url:
        pytest.skip("PostgreSQL database URL is required for Wave 10F concurrency verification.")

    test_schema = f"{TEST_SCHEMA_PREFIX}{uuid.uuid4().hex[:8]}"

    # Admin engine to create/drop the schema
    admin_engine = create_async_engine(
        db_url,
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    async with admin_engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {test_schema};"))

    # Test engine using NullPool for complete transaction isolation
    test_engine = create_async_engine(
        db_url,
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )

    # Create all tables in the isolated schema
    async with test_engine.begin() as conn:
        await conn.execute(text(f"SET search_path TO {test_schema}, public;"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    yield {
        "engine": test_engine,
        "session_factory": session_factory,
        "schema": test_schema,
    }

    # Teardown
    await test_engine.dispose()
    async with admin_engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE;"))
    await admin_engine.dispose()


@pytest.fixture
def make_session(pg_test_env):
    """Factory fixture providing isolated AsyncSession instances with search_path applied."""
    from contextlib import asynccontextmanager
    factory = pg_test_env["session_factory"]
    schema = pg_test_env["schema"]

    @asynccontextmanager
    async def _session_scope():
        async with factory() as session:
            await session.execute(text(f"SET search_path TO {schema}, public;"))
            yield session

    return _session_scope


@pytest.fixture
def human_lead():
    return AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="lead.engineer@quebet.test",
        tenant_id="tenant-alpha",
        role="LEAD_ENGINEER",
        permissions=["release:evaluate", "release:authorize"],
    )


@pytest.fixture
def ai_agent():
    return AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="autonomous.copilot@quebet.ai",
        tenant_id="tenant-alpha",
        role="AI_AGENT",
        permissions=["release:evaluate"],
    )


async def _create_test_project_and_circuit(session: AsyncSession, tenant_id: str = "tenant-alpha"):
    """Helper to populate a standard valid project and circuit."""
    owner_id = str(uuid.uuid4())
    proj = Project(
        id=str(uuid.uuid4()),
        name=f"Power Supply {uuid.uuid4().hex[:6]}",
        owner_id=owner_id,
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE.value,
        tenant_id=tenant_id,
        created_at=datetime.now(timezone.utc),
    )
    session.add(proj)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        tenant_id=tenant_id,
        name="Main Power Circuit",
        created_by=owner_id,
        created_source="USER",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_at=datetime.now(timezone.utc),
    )
    session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="R1",
        component_type="resistor",
        value="10k",
        created_source="USER",
        created_at=datetime.now(timezone.utc),
    )
    session.add(comp)

    await session.commit()
    await session.refresh(proj)
    await session.refresh(circuit)
    return proj, circuit


async def _create_passing_evaluation(
    session: AsyncSession,
    project_id: str,
    circuit_version: int,
    user: AuthenticatedUser,
):
    """Helper to evaluate and stage a passing release evaluation."""
    release_service = ReleaseService(session)
    eval_res = await release_service.evaluate_release_readiness(project_id, user)
    return eval_res


# =========================================================================
# TEST A: Concurrent Audit Append
# =========================================================================
@pytest.mark.asyncio
async def test_concurrent_audit_append(make_session, human_lead):
    """
    Spawns 10 concurrent worker sessions appending audit events to the same project.
    Verifies:
    1. SELECT ... FOR UPDATE serializes workers without deadlocks or crashes.
    2. Sequence numbers are strictly monotonic: 1..10.
    3. The prev_event_hash -> event_hash chain is unbroken and valid.
    """
    async with make_session() as session:
        proj, _ = await _create_test_project_and_circuit(session, human_lead.tenant_id)
        project_id = proj.id

    num_workers = 10
    barrier = asyncio.Barrier(num_workers)

    async def worker_append(idx: int):
        async with make_session() as s:
            await barrier.wait()  # Synchronize launch across all tasks
            audit = AuditLedgerService(s)
            ev = await audit.record_event(
                project_id=project_id,
                actor_id=human_lead.id,
                actor_role=human_lead.role,
                event_type=AuditEventType.COMPONENT_ADDED,
                entity_type="COMPONENT",
                entity_id=f"comp-{idx}",
                payload={"index": idx, "name": f"Resistor_{idx}"},
                tenant_id=human_lead.tenant_id,
                commit=True,
            )
            return ev

    results = await asyncio.gather(*(worker_append(i) for i in range(num_workers)))
    assert len(results) == num_workers

    # Verify audit chain from a fresh session
    async with make_session() as session:
        audit = AuditLedgerService(session)
        events = await audit.list_events(project_id, limit=100)
        assert len(events) == num_workers

        # Check sequence numbers
        seqs = [e.sequence_number for e in events]
        assert seqs == list(range(1, num_workers + 1))

        # Check cryptographic chain validity
        chain_status = await audit.verify_chain(project_id)
        assert chain_status["is_valid"] is True
        assert chain_status["events_verified"] == num_workers
        assert chain_status["head_hash"] == events[-1].event_hash


# =========================================================================
# TEST B: Concurrent Release Tags (Duplicate Tag Race)
# =========================================================================
@pytest.mark.asyncio
async def test_concurrent_duplicate_release_tag(make_session, human_lead):
    """
    Two concurrent workers attempt to authorize the EXACT same release tag.
    Verifies:
    1. Only 1 request succeeds in creating the baseline.
    2. The losing request is deterministically rejected with HTTP 409 Conflict.
    3. Exactly 1 RELEASE_BASELINE_CREATED event is committed.
    """
    async with make_session() as session:
        proj, circuit = await _create_test_project_and_circuit(session, human_lead.tenant_id)
        evaluation = await _create_passing_evaluation(session, proj.id, circuit.version, human_lead)
        project_id = proj.id
        eval_id = evaluation.id

    barrier = asyncio.Barrier(2)

    async def worker_authorize():
        async with make_session() as s:
            await barrier.wait()
            rs = ReleaseService(s)
            req = ReleaseBaselineCreateRequest(
                evaluation_id=eval_id,
                release_tag="REL-2026-001",
                release_rationale="Concurrent duplicate tag test",
                exceptions_approved=[{
                    "gate_id": "ALL",
                    "reason": "Concurrent duplicate tag test exemption",
                    "approved_by": human_lead.id,
                }],
            )
            return await rs.authorize_release_baseline(project_id, req, human_lead)

    res1, res2 = await asyncio.gather(
        worker_authorize(),
        worker_authorize(),
        return_exceptions=True,
    )

    successes = [r for r in (res1, res2) if not isinstance(r, Exception)]
    failures = [r for r in (res1, res2) if isinstance(r, Exception)]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"

    exc = failures[0]
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 409
    assert "already exists" in exc.detail or "RELEASE_EVALUATION_STALE" in exc.detail

    # Verify database has exactly 1 baseline and 1 audit event
    async with make_session() as session:
        baselines = (await session.execute(
            select(EngineeringReleaseBaseline).where(EngineeringReleaseBaseline.project_id == project_id)
        )).scalars().all()
        assert len(baselines) == 1
        assert baselines[0].release_tag == "REL-2026-001"

        audit_evs = (await session.execute(
            select(EngineeringAuditEvent).where(
                EngineeringAuditEvent.project_id == project_id,
                EngineeringAuditEvent.event_type == AuditEventType.RELEASE_BASELINE_CREATED.value,
            )
        )).scalars().all()
        assert len(audit_evs) == 1


# =========================================================================
# TEST C: Concurrent Different Release Tags (Audit Head Advancement)
# =========================================================================
@pytest.mark.asyncio
async def test_concurrent_different_release_tags(make_session, human_lead):
    """
    Two concurrent workers attempt to authorize DIFFERENT release tags (e.g. v1.0.0 and v1.0.1)
    sharing the same pre-computed evaluation.
    Verifies:
    1. Winner commits tag A and appends RELEASE_BASELINE_CREATED (advancing project audit head).
    2. Loser unblocks, detects that the audit head advanced past its evaluation anchor,
       and fails closed with HTTP 409 (RELEASE_EVALUATION_STALE).
    3. Exactly 1 baseline commits; evaluation state is strictly single-use.
    """
    async with make_session() as session:
        proj, circuit = await _create_test_project_and_circuit(session, human_lead.tenant_id)
        evaluation = await _create_passing_evaluation(session, proj.id, circuit.version, human_lead)
        project_id = proj.id
        eval_id = evaluation.id

    barrier = asyncio.Barrier(2)

    async def worker_authorize(tag: str):
        async with make_session() as s:
            await barrier.wait()
            rs = ReleaseService(s)
            req = ReleaseBaselineCreateRequest(
                evaluation_id=eval_id,
                release_tag=tag,
                release_rationale=f"Concurrent distinct tag test for {tag}",
                exceptions_approved=[{
                    "gate_id": "ALL",
                    "reason": f"Concurrent test exemption for {tag}",
                    "approved_by": human_lead.id,
                }],
            )
            return await rs.authorize_release_baseline(project_id, req, human_lead)

    resA, resB = await asyncio.gather(
        worker_authorize("REL-TAG-ALPHA"),
        worker_authorize("REL-TAG-BETA"),
        return_exceptions=True,
    )

    successes = [r for r in (resA, resB) if not isinstance(r, Exception)]
    failures = [r for r in (resA, resB) if isinstance(r, Exception)]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}"

    exc = failures[0]
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 409
    assert "RELEASE_EVALUATION_STALE" in exc.detail
    assert "Audit ledger has advanced" in exc.detail or "state changed" in exc.detail


# =========================================================================
# TEST D: Audit Failure and Baseline Atomicity
# =========================================================================
@pytest.mark.asyncio
async def test_audit_failure_baseline_atomicity(make_session, human_lead, monkeypatch):
    """
    Simulates a database failure or unhandled exception inside audit_service.record_event
    during baseline authorization.
    Verifies:
    1. The entire transaction rolls back atomically.
    2. Zero orphan baselines exist in the database.
    3. Zero partial audit events exist.
    """
    async with make_session() as session:
        proj, circuit = await _create_test_project_and_circuit(session, human_lead.tenant_id)
        evaluation = await _create_passing_evaluation(session, proj.id, circuit.version, human_lead)
        project_id = proj.id
        eval_id = evaluation.id

    async with make_session() as session:
        rs = ReleaseService(session)

        # Force audit_service.record_event to raise RuntimeError
        async def mock_record_event_fail(*args, **kwargs):
            raise RuntimeError("SIMULATED_AUDIT_DISK_OR_NETWORK_FAILURE")

        monkeypatch.setattr(rs.audit_service, "record_event", mock_record_event_fail)

        req = ReleaseBaselineCreateRequest(
            evaluation_id=eval_id,
            release_tag="REL-FAIL-TEST",
            release_rationale="Testing rollback on audit failure",
            exceptions_approved=[{
                "gate_id": "ALL",
                "reason": "Rollback test exemption",
                "approved_by": human_lead.id,
            }],
        )

        with pytest.raises(RuntimeError, match="SIMULATED_AUDIT_DISK_OR_NETWORK_FAILURE"):
            await rs.authorize_release_baseline(project_id, req, human_lead)

    # In a fresh session, verify no baseline exists
    async with make_session() as fresh_session:
        baselines = (await fresh_session.execute(
            select(EngineeringReleaseBaseline).where(EngineeringReleaseBaseline.project_id == project_id)
        )).scalars().all()
        assert len(baselines) == 0

        audit_evs = (await fresh_session.execute(
            select(EngineeringAuditEvent).where(EngineeringAuditEvent.project_id == project_id)
        )).scalars().all()
        assert len(audit_evs) == 0


# =========================================================================
# TEST E: Engineering Mutation During Authorization (Freshness Check)
# =========================================================================
@pytest.mark.asyncio
async def test_engineering_mutation_during_authorization(make_session, human_lead):
    """
    Coordinates an engineering mutation (circuit version increment) with release authorization.
    Verifies:
    1. Authorization detects circuit mutation (project revision mismatch).
    2. Rejects authorization with HTTP 409 (RELEASE_EVALUATION_STALE).
    """
    async with make_session() as session:
        proj, circuit = await _create_test_project_and_circuit(session, human_lead.tenant_id)
        evaluation = await _create_passing_evaluation(session, proj.id, circuit.version, human_lead)
        project_id = proj.id
        eval_id = evaluation.id
        circuit_id = circuit.id

    # Mutate circuit version to simulate concurrent design change
    async with make_session() as session:
        c = await session.get(Circuit, circuit_id)
        c.version = 2
        await session.commit()

    # Attempt authorization with the pre-mutation evaluation (which evaluated revision 1)
    async with make_session() as session:
        rs = ReleaseService(session)
        req = ReleaseBaselineCreateRequest(
            evaluation_id=eval_id,
            release_tag="REL-MUTATED-CIRCUIT",
            release_rationale="Mutation race test",
            exceptions_approved=[],
        )
        with pytest.raises(HTTPException) as exc_info:
            await rs.authorize_release_baseline(project_id, req, human_lead)

        assert exc_info.value.status_code == 409
        assert "RELEASE_EVALUATION_STALE" in exc_info.value.detail
        assert "Circuit revision changed (2 != 1)" in exc_info.value.detail


# =========================================================================
# TEST F: Audit-Chain Advancement Race
# =========================================================================
@pytest.mark.asyncio
async def test_audit_chain_advancement_race(make_session, human_lead):
    """
    Advances the audit ledger (by recording an independent audit event) between
    evaluation and baseline authorization.
    Verifies:
    1. Authorization detects current_audit_head != evaluation.audit_chain_head_hash.
    2. Rejects authorization with HTTP 409 (RELEASE_EVALUATION_STALE: Audit ledger has advanced).
    """
    async with make_session() as session:
        proj, circuit = await _create_test_project_and_circuit(session, human_lead.tenant_id)
        evaluation = await _create_passing_evaluation(session, proj.id, circuit.version, human_lead)
        project_id = proj.id
        eval_id = evaluation.id

    # Advance the audit ledger with an external event
    async with make_session() as session:
        audit = AuditLedgerService(session)
        await audit.record_event(
            project_id=project_id,
            actor_id=human_lead.id,
            actor_role=human_lead.role,
            event_type=AuditEventType.REQUIREMENT_UPDATED,
            entity_type="REQUIREMENT",
            entity_id=str(uuid.uuid4()),
            payload={"action": "External concurrent modification"},
            tenant_id=human_lead.tenant_id,
            commit=True,
        )

    # Attempt authorization with the now-stale evaluation
    async with make_session() as session:
        rs = ReleaseService(session)
        req = ReleaseBaselineCreateRequest(
            evaluation_id=eval_id,
            release_tag="REL-STALE-AUDIT",
            release_rationale="Audit advancement race test",
            exceptions_approved=[],
        )
        with pytest.raises(HTTPException) as exc_info:
            await rs.authorize_release_baseline(project_id, req, human_lead)

        assert exc_info.value.status_code == 409
        assert "RELEASE_EVALUATION_STALE" in exc_info.value.detail
        assert "Audit ledger has advanced or mutated post-evaluation" in exc_info.value.detail


# =========================================================================
# TEST G: Transaction Rollback on Failure Injection
# =========================================================================
@pytest.mark.asyncio
async def test_transaction_rollback_failure_injection(make_session, human_lead, monkeypatch):
    """
    Injects an error immediately prior to transaction commit in authorize_release_baseline.
    Verifies:
    1. Transaction rollback is executed.
    2. Neither the baseline nor the staged audit event is committed.
    3. The next append operation succeeds with correct sequential sequence_number.
    """
    async with make_session() as session:
        proj, circuit = await _create_test_project_and_circuit(session, human_lead.tenant_id)
        evaluation = await _create_passing_evaluation(session, proj.id, circuit.version, human_lead)
        project_id = proj.id
        eval_id = evaluation.id

    async with make_session() as session:
        rs = ReleaseService(session)

        # Monkeypatch db.commit to raise an exception
        async def mock_commit_fail():
            raise RuntimeError("SIMULATED_DATABASE_COMMIT_FAILURE")

        monkeypatch.setattr(session, "commit", mock_commit_fail)

        req = ReleaseBaselineCreateRequest(
            evaluation_id=eval_id,
            release_tag="REL-FAIL-INJECT",
            release_rationale="Rollback injection test",
            exceptions_approved=[{
                "gate_id": "ALL",
                "reason": "Injection test exemption",
                "approved_by": human_lead.id,
            }],
        )
        with pytest.raises(RuntimeError, match="SIMULATED_DATABASE_COMMIT_FAILURE"):
            await rs.authorize_release_baseline(project_id, req, human_lead)

    # Verify state clean in fresh session
    async with make_session() as session:
        baselines = (await session.execute(
            select(EngineeringReleaseBaseline).where(EngineeringReleaseBaseline.project_id == project_id)
        )).scalars().all()
        assert len(baselines) == 0

        # Now append a valid event and verify sequence starts at 1
        audit = AuditLedgerService(session)
        ev = await audit.record_event(
            project_id=project_id,
            actor_id=human_lead.id,
            actor_role=human_lead.role,
            event_type=AuditEventType.COMPONENT_ADDED,
            entity_type="COMPONENT",
            entity_id="comp-1",
            payload={"name": "Capacitor"},
            tenant_id=human_lead.tenant_id,
            commit=True,
        )
        assert ev.sequence_number == 1


# =========================================================================
# TEST H: Tenant Isolation and AI Authority Rejection
# =========================================================================
@pytest.mark.asyncio
async def test_tenant_isolation_and_ai_rejection(make_session, human_lead, ai_agent):
    """
    Verifies:
    1. Cross-tenant access is prohibited (Tenant Beta cannot authorize Tenant Alpha release).
    2. AI actors cannot authorize releases (HTTP 403, AI ENGINEERING AUTHORITY = NONE).
    """
    async with make_session() as session:
        proj, circuit = await _create_test_project_and_circuit(session, "tenant-alpha")
        evaluation = await _create_passing_evaluation(session, proj.id, circuit.version, human_lead)
        project_id = proj.id
        eval_id = evaluation.id

    # 1. AI actor authorization rejection
    async with make_session() as session:
        rs = ReleaseService(session)
        req = ReleaseBaselineCreateRequest(
            evaluation_id=eval_id,
            release_tag="REL-AI-DENIED",
            release_rationale="AI autonomous release attempt",
            exceptions_approved=[],
        )
        with pytest.raises(HTTPException) as exc_ai:
            await rs.authorize_release_baseline(project_id, req, ai_agent)
        assert exc_ai.value.status_code == 403
        assert "AI ENGINEERING AUTHORITY = NONE" in exc_ai.value.detail

    # 2. Cross-tenant user rejection
    user_tenant_beta = AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="lead@competitor.test",
        tenant_id="tenant-beta",
        role="LEAD_ENGINEER",
        permissions=["release:evaluate", "release:authorize"],
    )
    async with make_session() as session:
        rs = ReleaseService(session)
        req = ReleaseBaselineCreateRequest(
            evaluation_id=eval_id,
            release_tag="REL-TENANT-DENIED",
            release_rationale="Cross-tenant breach attempt",
            exceptions_approved=[],
        )
        with pytest.raises(HTTPException) as exc_tenant:
            await rs.authorize_release_baseline(project_id, req, user_tenant_beta)
        assert exc_tenant.value.status_code == 404
        assert "not found or tenant access denied" in exc_tenant.value.detail
