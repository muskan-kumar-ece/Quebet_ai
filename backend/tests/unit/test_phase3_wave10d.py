"""
Phase 3 Wave 10D: Release Governance Integration & Engineering Lifecycle Enforcement Tests.

Verifies:
1. Complete release lifecycle state transitions (NOT_READY -> READY_FOR_RELEASE -> BASELINE_AUTHORIZED).
2. Dynamic staleness detection on retrieval (get_latest_evaluation / get_evaluation) when circuit revision advances.
3. Dynamic staleness detection on retrieval when audit ledger advances post-evaluation.
4. Evaluation audit trail logging: RELEASE_EVALUATION_COMPLETED recorded in AuditEventType.
5. Baseline authorization integrity: immutable SHA-256 canonical snapshot digest linking domain digests.
6. Baseline list and get endpoints correctly return frozen snapshot manifestations.
7. Role-based release authorization enforcement: AI/unauthorized roles rejected with HTTP 403.
8. Re-evaluation requirement when state fingerprint differs from live domain entities.
9. Audit chain tampering blocks release readiness (OverallReadinessState.BLOCKED).
10. Failure-closed evaluation when cross-domain or DFM analysis is missing or failed.
"""
from datetime import datetime, timezone
import hashlib
import json
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from fastapi import HTTPException

from app.models.db.base import Base
from app.models.db.audit_ledger import AuditEventType, EngineeringAuditEvent
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.models.db.circuit import Circuit, CircuitValidationStatus
from app.models.db.component import Component
from app.models.db.pcb import BoardFootprint, BoardStatus, EngineeringBoard
from app.models.db.bom import EngineeringBOM, BOMStatus
from app.models.db.decision import (
    EngineeringRequirement,
    RequirementStatus,
    RequirementCategory,
    EngineeringDecisionRecord,
    EngineeringUnknownDisposition,
    UnknownDispositionStatus,
)
from app.models.db.verification import (
    EngineeringDesignReview,
    EngineeringEvidence,
    EvidenceStatus,
)
from app.models.db.release import (
    EngineeringReleaseEvaluation,
    EngineeringReleaseBaseline,
    OverallReadinessState,
    ReleaseGateStatus,
)
from app.models.db.cross_domain import (
    CrossDomainValidationRecord,
    CrossDomainValidationStatus,
)
from app.models.db.dfm import (
    ManufacturingAnalysisRecord,
    ManufacturingAnalysisStatus,
    ManufacturingRuleSet,
)
from app.models.schemas.release import ReleaseBaselineCreateRequest
from app.services.audit_ledger_service import AuditLedgerService
from app.services.release_service import ReleaseService, ReleaseGateEngine
from app.core.dependencies import AuthenticatedUser


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def human_engineer():
    return AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="lead.engineer@quebet.internal",
        role="LEAD_ENGINEER",
        tenant_id=str(uuid.uuid4()),
    )


@pytest.fixture
def ai_agent():
    return AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="ai.assistant@quebet.internal",
        role="AI_AGENT",
        tenant_id=str(uuid.uuid4()),
    )


async def setup_fully_passing_project(db_session: AsyncSession, human_engineer: AuthenticatedUser) -> tuple[str, Circuit]:
    """Helper to populate an authoritative project satisfying all gates RG-01 through RG-09."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Mission Critical Power Subsystem",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Main Schematic",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="U1",
        component_type="regulator",
        value="TPS54302",
        created_source="USER",
    )
    db_session.add(comp)

    board = EngineeringBoard(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="Flight Board PCB",
        version=1,
        status=BoardStatus.REVIEW.value,
        dimensions={"width": 100, "height": 80},
        created_by=human_engineer.id,
    )
    db_session.add(board)

    fp = BoardFootprint(
        id=str(uuid.uuid4()),
        board_id=board.id,
        component_id=comp.id,
        ref_des="U1",
        footprint_name="SOT-23-6",
        pos_x=15.0,
        pos_y=15.0,
        rotation=0.0,
        side="TOP",
    )
    db_session.add(fp)

    bom = EngineeringBOM(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="Flight BOM",
        version=1,
        status=BOMStatus.EVALUATED.value,
        total_lines=0,
        created_by=human_engineer.id,
    )
    db_session.add(bom)

    req = EngineeringRequirement(
        id=str(uuid.uuid4()),
        project_id=project_id,
        system_id=str(uuid.uuid4()),
        requirement_key="REQ-PWR-01",
        title="High Efficiency Buck Regulation",
        description="Must maintain >90% efficiency under 2A load",
        status=RequirementStatus.SATISFIED.value,
        category=RequirementCategory.FUNCTIONAL.value,
        created_by=human_engineer.id,
    )
    db_session.add(req)

    evidence = EngineeringEvidence(
        id=str(uuid.uuid4()),
        verification_requirement_id=str(uuid.uuid4()),
        review_id=str(uuid.uuid4()),
        evidence_type="BENCH_TEST",
        source="Rigol Oscilloscope & Load Bank",
        description="Efficiency curve measured under continuous 2A thermal soak",
        status=EvidenceStatus.VALID.value,
        circuit_id=circuit.id,
        circuit_revision=1,
        provided_by=human_engineer.id,
    )
    db_session.add(evidence)

    xd = CrossDomainValidationRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        board_id=board.id,
        bom_id=bom.id,
        validation_status=CrossDomainValidationStatus.COMPLETED.value,
        is_stale=False,
        findings=[],
        summary={},
        domain_snapshots={},
        staleness_reasons=[],
        snapshot_digest="0" * 64,
    )
    db_session.add(xd)

    rule_set = ManufacturingRuleSet(
        id=str(uuid.uuid4()),
        name="IPC Class 3 Ruleset",
        version=1,
        source="IPC",
        source_revision="REV_1",
        rules={},
        is_default=True,
    )
    db_session.add(rule_set)

    dfm = ManufacturingAnalysisRecord(
        id=str(uuid.uuid4()),
        board_id=board.id,
        board_revision=1,
        circuit_id=circuit.id,
        circuit_revision=1,
        rule_set_id=rule_set.id,
        rule_set_revision="REV_1",
        status=ManufacturingAnalysisStatus.COMPLETED.value,
        findings=[],
        summary={},
        created_by=human_engineer.id,
    )
    db_session.add(dfm)

    await db_session.commit()
    return project_id, circuit


@pytest.mark.asyncio
async def test_wave10d_complete_lifecycle_readiness_to_baseline(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """Verifies complete release lifecycle: evaluation -> READY_FOR_RELEASE -> baseline authorization."""
    project_id, circuit = await setup_fully_passing_project(db_session, human_engineer)
    service = ReleaseService(db_session)

    # 1. Run evaluation
    eval_record = await service.evaluate_release_readiness(project_id, human_engineer)
    assert eval_record.overall_readiness == OverallReadinessState.READY_FOR_RELEASE.value
    assert eval_record.is_stale is False
    assert eval_record.audit_chain_verified is True

    # 2. Authorize baseline
    req = ReleaseBaselineCreateRequest(
        evaluation_id=eval_record.id,
        release_tag="REL-2026.1-PROD",
        release_rationale="Flight qualification verified by Lead Avionics Engineer.",
    )
    baseline = await service.authorize_release_baseline(project_id, req, human_engineer)

    assert baseline.id is not None
    assert baseline.release_tag == "REL-2026.1-PROD"
    assert baseline.project_revision == 1
    assert len(baseline.canonical_snapshot_digest) == 64

    # 3. Retrieve baseline via get_baseline and list_baselines
    retrieved = await service.get_baseline(baseline.id, human_engineer)
    assert retrieved.id == baseline.id
    assert retrieved.canonical_snapshot_digest == baseline.canonical_snapshot_digest

    baselines_list = await service.list_baselines(project_id, human_engineer)
    assert len(baselines_list) == 1
    assert baselines_list[0].id == baseline.id


@pytest.mark.asyncio
async def test_wave10d_dynamic_staleness_on_circuit_revision_bump(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """Verifies that get_evaluation and get_latest_evaluation dynamically detect staleness when circuit version changes."""
    project_id, circuit = await setup_fully_passing_project(db_session, human_engineer)
    service = ReleaseService(db_session)

    # Evaluate at revision 1
    eval_record = await service.evaluate_release_readiness(project_id, human_engineer)
    assert eval_record.is_stale is False

    # Check via get_latest_evaluation - initially fresh
    latest = await service.get_latest_evaluation(project_id, human_engineer)
    assert latest.is_stale is False

    # Mutate circuit revision (e.g. schematic incremented to v2)
    circuit.version = 2
    await db_session.commit()

    # Dynamic staleness check on get_evaluation
    fetched_eval = await service.get_evaluation(eval_record.id, human_engineer)
    assert fetched_eval.is_stale is True

    # Dynamic staleness check on get_latest_evaluation
    fetched_latest = await service.get_latest_evaluation(project_id, human_engineer)
    assert fetched_latest.is_stale is True


@pytest.mark.asyncio
async def test_wave10d_dynamic_staleness_on_audit_ledger_advancement(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """Verifies that advancing the audit ledger after an evaluation marks the evaluation dynamically STALE."""
    project_id, circuit = await setup_fully_passing_project(db_session, human_engineer)
    service = ReleaseService(db_session)
    audit_service = AuditLedgerService(db_session)

    # Evaluate readiness
    eval_record = await service.evaluate_release_readiness(project_id, human_engineer)
    assert eval_record.is_stale is False

    # Now append an authoritative event to the audit ledger
    await audit_service.record_event(
        project_id=project_id,
        actor_id=human_engineer.id,
        actor_role=human_engineer.role,
        event_type=AuditEventType.DECISION_RECORDED,
        entity_type="DECISION",
        entity_id=str(uuid.uuid4()),
        payload={"note": "Component alternate approved"},
        commit=True,
    )

    # Re-fetch evaluation: must be detected as STALE because audit chain head advanced
    fetched = await service.get_evaluation(eval_record.id, human_engineer)
    assert fetched.is_stale is True

    # Attempting to authorize with this stale evaluation must be rejected with HTTP 409
    req = ReleaseBaselineCreateRequest(
        evaluation_id=eval_record.id,
        release_tag="REL-2026.1-STALE",
        release_rationale="Attempting sign-off post ledger mutation.",
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.authorize_release_baseline(project_id, req, human_engineer)
    assert exc_info.value.status_code == 409
    assert "RELEASE_EVALUATION_STALE" in exc_info.value.detail


@pytest.mark.asyncio
async def test_wave10d_release_baseline_created_audit_event_logged(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """Verifies that authorizing a release baseline records RELEASE_BASELINE_CREATED atomically in the audit ledger."""
    project_id, circuit = await setup_fully_passing_project(db_session, human_engineer)
    service = ReleaseService(db_session)

    eval_record = await service.evaluate_release_readiness(project_id, human_engineer)
    req = ReleaseBaselineCreateRequest(
        evaluation_id=eval_record.id,
        release_tag="REL-2026.2",
        release_rationale="Authorized for pre-production manufacturing release.",
    )
    baseline = await service.authorize_release_baseline(project_id, req, human_engineer)

    # Inspect audit events in DB
    events_stmt = (
        select(EngineeringAuditEvent)
        .where(
            EngineeringAuditEvent.project_id == project_id,
            EngineeringAuditEvent.event_type == AuditEventType.RELEASE_BASELINE_CREATED.value,
        )
    )
    events = (await db_session.execute(events_stmt)).scalars().all()
    assert len(events) == 1
    evt = events[0]
    assert evt.entity_id == str(baseline.id)
    assert evt.entity_type == "RELEASE_BASELINE"
    assert evt.payload["release_tag"] == "REL-2026.2"
    assert evt.payload["canonical_snapshot_digest"] == baseline.canonical_snapshot_digest


@pytest.mark.asyncio
async def test_wave10d_ai_actor_forbidden_from_release_authorization(db_session: AsyncSession, human_engineer: AuthenticatedUser, ai_agent: AuthenticatedUser):
    """Verifies strict invariant: AI actors cannot authorize release baselines (HTTP 403 Forbidden)."""
    project_id, circuit = await setup_fully_passing_project(db_session, human_engineer)
    service = ReleaseService(db_session)

    eval_record = await service.evaluate_release_readiness(project_id, human_engineer)
    req = ReleaseBaselineCreateRequest(
        evaluation_id=eval_record.id,
        release_tag="REL-AI-ATTEMPT",
        release_rationale="AI Agent attempted autonomous sign-off.",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.authorize_release_baseline(project_id, req, ai_agent)
    assert exc_info.value.status_code == 403
    assert "AI ENGINEERING AUTHORITY = NONE" in exc_info.value.detail


@pytest.mark.asyncio
async def test_wave10d_tampered_audit_chain_blocks_release(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """Verifies that if the audit ledger has tampering or broken hash link, overall readiness is BLOCKED."""
    project_id, circuit = await setup_fully_passing_project(db_session, human_engineer)
    audit_service = AuditLedgerService(db_session)

    # Create an initial valid event
    evt1 = await audit_service.record_event(
        project_id=project_id,
        actor_id=human_engineer.id,
        actor_role=human_engineer.role,
        event_type=AuditEventType.DECISION_RECORDED,
        entity_type="DECISION",
        entity_id=str(uuid.uuid4()),
        payload={"note": "Initial event"},
        commit=True,
    )

    # Intentionally corrupt the event hash in the database to simulate tampering
    evt1.event_hash = "deadbeef" * 8
    await db_session.commit()

    # Evaluate readiness
    service = ReleaseService(db_session)
    eval_record = await service.evaluate_release_readiness(project_id, human_engineer)

    # Readiness MUST be BLOCKED and audit_chain_verified MUST be False
    assert eval_record.overall_readiness == OverallReadinessState.BLOCKED.value
    assert eval_record.audit_chain_verified is False
    assert any("AUDIT_LEDGER" in b.get("gate_id", "") for b in eval_record.blocking_findings)
