"""
Unit and integration tests for Phase 3 Wave 10C:
Deterministic Release Gate Engine & Frozen Release Baselines.

Verifies:
1. Deterministic evaluation of RG-01 through RG-09.
2. Failure-closed semantics: UNKNOWN != SATISFIED, missing evidence fails gates.
3. Audit ledger chain failure blocks overall release readiness.
4. Freshness and staleness detection: circuit mutation marks evaluation STALE.
5. Release baseline creation: canonical SHA-256 snapshot digest and frozen domain entities.
6. Baseline immutability: subsequent domain entity mutation does not alter frozen baseline.
7. Role-based authorization & AI rejection: AI actors cannot authorize release baselines.
8. Single-transaction atomicity: audit ledger failure rolls back baseline creation without orphan.
"""
from datetime import datetime, timezone
import uuid
import pytest
from unittest.mock import patch
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
        email="lead.engineer@quebet.test",
        tenant_id="tenant-alpha",
        role="LEAD_ENGINEER",
        permissions=["release:evaluate", "release:authorize"],
    )


@pytest.fixture
def ai_actor():
    return AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="copilot@quebet.ai",
        tenant_id="tenant-alpha",
        role="AI_AGENT",
        permissions=["release:evaluate"],
    )


@pytest.mark.asyncio
async def test_gate_engine_evaluates_all_gates(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """RG-01 through RG-09 must all be evaluated deterministically."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Telemetry Subsystem",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    # Valid circuit with 1 component
    circuit_id = str(uuid.uuid4())
    circuit = Circuit(
        id=circuit_id,
        project_id=project_id,
        name="Telemetry Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit_id,
        ref_des="U1",
        component_type="regulator",
        value="LM7805",
        created_source="USER",
    )
    db_session.add(comp)

    # Board matching circuit version
    board_id = str(uuid.uuid4())
    board = EngineeringBoard(
        id=board_id,
        project_id=project_id,
        circuit_id=circuit_id,
        circuit_version=1,
        name="Telemetry PCB",
        version=1,
        status=BoardStatus.REVIEW.value,
        dimensions={"width": 100, "height": 80},
        created_by=human_engineer.id,
    )
    db_session.add(board)

    fp = BoardFootprint(
        id=str(uuid.uuid4()),
        board_id=board_id,
        component_id=comp.id,
        ref_des="U1",
        footprint_name="TO-220",
        pos_x=10.0,
        pos_y=10.0,
        rotation=0.0,
        side="TOP",
    )
    db_session.add(fp)

    # BOM matching circuit version
    bom_id = str(uuid.uuid4())
    bom = EngineeringBOM(
        id=bom_id,
        project_id=project_id,
        circuit_id=circuit_id,
        circuit_version=1,
        name="Telemetry BOM",
        version=1,
        status=BOMStatus.EVALUATED.value,
        total_lines=0,
        created_by=human_engineer.id,
    )
    db_session.add(bom)

    # Requirement satisfied
    req_id = str(uuid.uuid4())
    req = EngineeringRequirement(
        id=req_id,
        project_id=project_id,
        system_id=str(uuid.uuid4()),
        requirement_key="REQ-001",
        title="Supply Voltage 3.3V",
        description="Must regulate 3.3V stably",
        status=RequirementStatus.SATISFIED.value,
        category=RequirementCategory.POWER.value,
        created_by=human_engineer.id,
    )
    db_session.add(req)

    # Physical verification evidence matching circuit revision
    ev_id = str(uuid.uuid4())
    evidence = EngineeringEvidence(
        id=ev_id,
        verification_requirement_id=str(uuid.uuid4()),
        review_id=str(uuid.uuid4()),
        evidence_type="BENCH_TEST",
        source="Bench Oscilloscope",
        description="Physical Bench Oscilloscope Trace",
        status=EvidenceStatus.VALID.value,
        circuit_id=circuit_id,
        circuit_revision=1,
        provided_by=human_engineer.id,
    )
    db_session.add(evidence)

    # Cross-domain validation record
    xd = CrossDomainValidationRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit_id,
        board_id=board_id,
        bom_id=bom_id,
        validation_status=CrossDomainValidationStatus.COMPLETED.value,
        is_stale=False,
        findings=[],
        summary={},
        domain_snapshots={},
        staleness_reasons=[],
        snapshot_digest="0" * 64,
    )
    db_session.add(xd)

    # Manufacturing Rule Set and DFM Analysis Record
    rule_set = ManufacturingRuleSet(
        id=str(uuid.uuid4()),
        name="Standard DFM Rules",
        version=1,
        source="STANDARD",
        source_revision="REV_A",
        rules={},
        is_default=True,
    )
    db_session.add(rule_set)

    dfm = ManufacturingAnalysisRecord(
        id=str(uuid.uuid4()),
        board_id=board_id,
        board_revision=1,
        circuit_id=circuit_id,
        circuit_revision=1,
        rule_set_id=rule_set.id,
        rule_set_revision="REV_A",
        status=ManufacturingAnalysisStatus.COMPLETED.value,
        findings=[],
        summary={},
        created_by=human_engineer.id,
    )
    db_session.add(dfm)

    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )

    assert evaluation.project_id == project_id
    assert len(evaluation.gate_results) == 9
    gate_ids = list(evaluation.gate_results.keys())
    assert gate_ids == ["RG-01", "RG-02", "RG-03", "RG-04", "RG-05", "RG-06", "RG-07", "RG-08", "RG-09"]

    # In this well-formed state, overall readiness should be READY_FOR_RELEASE
    assert evaluation.overall_readiness == OverallReadinessState.READY_FOR_RELEASE.value
    assert evaluation.project_revision == 1
    assert evaluation.audit_chain_verified is True


@pytest.mark.asyncio
async def test_gate_engine_failure_closed_when_components_zero(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """RG-01 fails if schematic components list is empty or validation_status != VALID."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Empty Circuit Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Empty Circuit",
        version=1,
        validation_status=CircuitValidationStatus.DRAFT.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)
    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )

    rg01 = evaluation.gate_results["RG-01"]
    assert rg01["status"] in (ReleaseGateStatus.FAIL.value, ReleaseGateStatus.BLOCKED.value)
    assert evaluation.overall_readiness in (OverallReadinessState.NOT_READY.value, OverallReadinessState.BLOCKED.value)


@pytest.mark.asyncio
async def test_gate_engine_unknown_not_satisfied_for_requirements(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """RG-06 must fail if requirements are UNKNOWN or DRAFT (UNKNOWN != SATISFIED invariant)."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Req Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Valid Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="R1",
        component_type="resistor",
        value="10k",
        created_source="USER",
    )
    db_session.add(comp)

    req = EngineeringRequirement(
        id=str(uuid.uuid4()),
        project_id=project_id,
        system_id=str(uuid.uuid4()),
        requirement_key="REQ-PWR-01",
        title="Thermal Isolation",
        description="Isolation under full load",
        status=RequirementStatus.DRAFT.value,  # Not SATISFIED
        category=RequirementCategory.FUNCTIONAL.value,
        created_by=human_engineer.id,
    )
    db_session.add(req)
    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )

    rg06 = evaluation.gate_results["RG-06"]
    assert rg06["status"] in (ReleaseGateStatus.FAIL.value, ReleaseGateStatus.BLOCKED.value)
    assert evaluation.overall_readiness in (OverallReadinessState.NOT_READY.value, OverallReadinessState.BLOCKED.value)


@pytest.mark.asyncio
async def test_audit_ledger_corruption_blocks_release(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """If audit ledger chain verification fails, release readiness MUST be BLOCKED."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Audit Test Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Valid Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="C1",
        component_type="capacitor",
        value="100nF",
        created_source="USER",
    )
    db_session.add(comp)
    await db_session.commit()

    service = ReleaseService(db_session)
    with patch.object(
        AuditLedgerService,
        "verify_chain",
        return_value={"is_valid": False, "head_hash": None, "error": "Corrupted event sequence hash at #3"},
    ):
        evaluation = await service.evaluate_release_readiness(
            project_id=project_id,
            user=human_engineer,
        )

        assert evaluation.audit_chain_verified is False
        assert evaluation.overall_readiness == OverallReadinessState.BLOCKED.value


@pytest.mark.asyncio
async def test_staleness_detection_on_circuit_mutation(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """If circuit version increments after evaluation, baseline creation rejects stale evaluation."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Staleness Test Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Valid Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="R1",
        component_type="resistor",
        value="1k",
        created_source="USER",
    )
    db_session.add(comp)
    await db_session.commit()

    service = ReleaseService(db_session)
    eval_record = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )
    assert eval_record.is_stale is False

    # Now mutate circuit version to 2
    circuit.version = 2
    await db_session.commit()

    # Attempt to authorize baseline with stale evaluation should raise HTTP 409
    req = ReleaseBaselineCreateRequest(
        evaluation_id=eval_record.id,
        release_tag="v1.0.0-stale-attempt",
        release_rationale="Attempt release on stale evaluation",
        signoff_notes="Should fail due to stale revision",
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.authorize_release_baseline(
            project_id=project_id,
            request=req,
            user=human_engineer,
        )
    assert exc_info.value.status_code == 409
    assert "RELEASE_EVALUATION_STALE" in exc_info.value.detail


@pytest.mark.asyncio
async def test_authorize_baseline_happy_path(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """Authorizing baseline computes canonical snapshot digest and commits RELEASE_BASELINE_CREATED audit event."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Baseline Happy Path Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Flight Computer Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="U1",
        component_type="mcu",
        value="STM32F4",
        created_source="USER",
    )
    db_session.add(comp)

    board = EngineeringBoard(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="Flight Board",
        version=1,
        status=BoardStatus.REVIEW.value,
        dimensions={"width": 120, "height": 90},
        created_by=human_engineer.id,
    )
    db_session.add(board)

    fp = BoardFootprint(
        id=str(uuid.uuid4()),
        board_id=board.id,
        component_id=comp.id,
        ref_des="U1",
        footprint_name="LQFP-64",
        pos_x=10.0,
        pos_y=10.0,
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
        requirement_key="REQ-FC-01",
        title="Triple Modular Redundancy",
        description="TMR voter circuit logic verified",
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
        source="Chamber Sensor",
        description="Thermal Chamber Flight Certification",
        status=EvidenceStatus.VALID.value,
        circuit_id=circuit.id,
        circuit_revision=1,
        provided_by=human_engineer.id,
    )
    db_session.add(evidence)

    # Cross-domain validation record
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

    # Manufacturing Rule Set and DFM Analysis Record
    rule_set = ManufacturingRuleSet(
        id=str(uuid.uuid4()),
        name="Standard DFM Rules",
        version=1,
        source="STANDARD",
        source_revision="REV_A",
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
        rule_set_revision="REV_A",
        status=ManufacturingAnalysisStatus.COMPLETED.value,
        findings=[],
        summary={},
        created_by=human_engineer.id,
    )
    db_session.add(dfm)

    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )
    assert evaluation.overall_readiness == OverallReadinessState.READY_FOR_RELEASE.value

    # Authorize baseline
    baseline_req = ReleaseBaselineCreateRequest(
        evaluation_id=evaluation.id,
        release_tag="v1.0.0-rc1",
        release_rationale="Authorized by Lead Engineer for qualification testing.",
        signoff_notes="Authorized by Lead Engineer for qualification testing.",
    )
    baseline = await service.authorize_release_baseline(
        project_id=project_id,
        request=baseline_req,
        user=human_engineer,
    )

    assert baseline.id is not None
    assert baseline.release_tag == "v1.0.0-rc1"
    assert len(baseline.canonical_snapshot_digest) == 64
    assert baseline.circuit_version == 1

    # Verify audit event was committed atomically
    events_stmt = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.RELEASE_BASELINE_CREATED.value,
    )
    events = (await db_session.execute(events_stmt)).scalars().all()
    assert len(events) == 1
    audit_evt = events[0]
    assert audit_evt.entity_id == str(baseline.id)
    assert audit_evt.entity_type == "RELEASE_BASELINE"
    assert audit_evt.payload["release_tag"] == "v1.0.0-rc1"
    assert audit_evt.payload["canonical_snapshot_digest"] == baseline.canonical_snapshot_digest


@pytest.mark.asyncio
async def test_baseline_immutability_preserves_frozen_snapshot(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """Domain entity mutations after baseline creation must not alter the frozen baseline snapshot."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Immutability Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Main Board",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="U1",
        component_type="mcu",
        value="AVR",
        created_source="USER",
    )
    db_session.add(comp)

    req = EngineeringRequirement(
        id=str(uuid.uuid4()),
        project_id=project_id,
        system_id=str(uuid.uuid4()),
        requirement_key="REQ-IMM-01",
        title="Immutability Spec",
        description="Verify frozen baseline integrity",
        status=RequirementStatus.SATISFIED.value,
        category=RequirementCategory.FUNCTIONAL.value,
        created_by=human_engineer.id,
    )
    db_session.add(req)

    bom = EngineeringBOM(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="Main BOM",
        version=1,
        status=BOMStatus.EVALUATED.value,
        total_lines=0,
        created_by=human_engineer.id,
    )
    db_session.add(bom)

    evidence = EngineeringEvidence(
        id=str(uuid.uuid4()),
        verification_requirement_id=str(uuid.uuid4()),
        review_id=str(uuid.uuid4()),
        evidence_type="BENCH_TEST",
        source="Scope",
        description="Signal integrity verified",
        status=EvidenceStatus.VALID.value,
        circuit_id=circuit.id,
        circuit_revision=1,
        provided_by=human_engineer.id,
    )
    db_session.add(evidence)

    # Cross-domain validation record (no board, so RG-02 and RG-05 are NOT_APPLICABLE)
    xd = CrossDomainValidationRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        board_id=None,
        bom_id=None,
        validation_status=CrossDomainValidationStatus.COMPLETED.value,
        is_stale=False,
        findings=[],
        summary={},
        domain_snapshots={},
        staleness_reasons=[],
        snapshot_digest="0" * 64,
    )
    db_session.add(xd)

    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )

    baseline_req = ReleaseBaselineCreateRequest(
        evaluation_id=evaluation.id,
        release_tag="v1.0.0-stable",
        release_rationale="Stable baseline release",
        signoff_notes="Stable baseline release",
    )
    baseline = await service.authorize_release_baseline(
        project_id=project_id,
        request=baseline_req,
        user=human_engineer,
    )
    frozen_digest = baseline.canonical_snapshot_digest
    frozen_circuit_version = baseline.circuit_version

    # Now mutate the live circuit to version 5
    circuit.version = 5
    await db_session.commit()

    # Re-fetch baseline
    fetched_baseline = await service.get_baseline(baseline.id, human_engineer)
    assert fetched_baseline.canonical_snapshot_digest == frozen_digest
    assert fetched_baseline.circuit_version == frozen_circuit_version


@pytest.mark.asyncio
async def test_ai_actor_rejected_from_release_authorization(db_session: AsyncSession, ai_actor: AuthenticatedUser, human_engineer: AuthenticatedUser):
    """AI agent cannot authorize release baselines (AI ENGINEERING AUTHORITY = NONE)."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="AI Guard Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Main Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="U1",
        component_type="mcu",
        value="AVR",
        created_source="USER",
    )
    db_session.add(comp)
    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )

    # Attempt baseline authorization by AI actor
    baseline_req = ReleaseBaselineCreateRequest(
        evaluation_id=evaluation.id,
        release_tag="v1.0.0-ai-attempt",
        release_rationale="AI Copilot trying to release",
        signoff_notes="AI Copilot trying to release",
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.authorize_release_baseline(
            project_id=project_id,
            request=baseline_req,
            user=ai_actor,
        )

    assert exc_info.value.status_code == 403
    assert "AI ENGINEERING AUTHORITY = NONE" in exc_info.value.detail


@pytest.mark.asyncio
async def test_baseline_creation_atomicity_rolls_back_on_audit_failure(db_session: AsyncSession, human_engineer: AuthenticatedUser):
    """If audit ledger staging fails, the baseline record must NOT be committed."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Rollback Test Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Circuit Alpha",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="U1",
        component_type="mcu",
        value="AVR",
        created_source="USER",
    )
    db_session.add(comp)

    req = EngineeringRequirement(
        id=str(uuid.uuid4()),
        project_id=project_id,
        system_id=str(uuid.uuid4()),
        requirement_key="REQ-RB-01",
        title="Rollback Spec",
        description="Verify atomicity rollback",
        status=RequirementStatus.SATISFIED.value,
        category=RequirementCategory.FUNCTIONAL.value,
        created_by=human_engineer.id,
    )
    db_session.add(req)

    bom = EngineeringBOM(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="Rollback BOM",
        version=1,
        status=BOMStatus.EVALUATED.value,
        total_lines=0,
        created_by=human_engineer.id,
    )
    db_session.add(bom)

    evidence = EngineeringEvidence(
        id=str(uuid.uuid4()),
        verification_requirement_id=str(uuid.uuid4()),
        review_id=str(uuid.uuid4()),
        evidence_type="BENCH_TEST",
        source="Scope",
        description="Trace verified",
        status=EvidenceStatus.VALID.value,
        circuit_id=circuit.id,
        circuit_revision=1,
        provided_by=human_engineer.id,
    )
    db_session.add(evidence)

    # Cross-domain validation record (no board, so RG-02 and RG-05 are NOT_APPLICABLE)
    xd = CrossDomainValidationRecord(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        board_id=None,
        bom_id=None,
        validation_status=CrossDomainValidationStatus.COMPLETED.value,
        is_stale=False,
        findings=[],
        summary={},
        domain_snapshots={},
        staleness_reasons=[],
        snapshot_digest="0" * 64,
    )
    db_session.add(xd)

    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )

    baseline_req = ReleaseBaselineCreateRequest(
        evaluation_id=evaluation.id,
        release_tag="v1.0.0-rollback",
        release_rationale="Rollback test rationale",
        signoff_notes="Rollback test",
    )

    # Mock AuditLedgerService.record_event to raise RuntimeError
    with patch.object(
        AuditLedgerService,
        "record_event",
        side_effect=RuntimeError("Audit disk write failed"),
    ):
        with pytest.raises(RuntimeError):
            await service.authorize_release_baseline(
                project_id=project_id,
                request=baseline_req,
                user=human_engineer,
            )

    # Ensure NO baseline was persisted
    baselines_stmt = select(EngineeringReleaseBaseline).where(
        EngineeringReleaseBaseline.project_id == project_id
    )
    baselines = (await db_session.execute(baselines_stmt)).scalars().all()
    assert len(baselines) == 0, "Failed audit event must leave zero orphan baselines."


# =========================================================================
# WAVE 10C.1 REGRESSION TESTS (DEF-10C-01, DEF-10C-02, DEF-10C-03)
# =========================================================================

@pytest.mark.asyncio
async def test_remediation_def_10c_01_board_mutation_triggers_stale_conflict(
    db_session: AsyncSession, human_engineer: AuthenticatedUser
):
    """
    DEF-10C-01: When board mutates post-evaluation, authorize_release_baseline
    must detect fingerprint mismatch and raise HTTP 409 RELEASE_EVALUATION_STALE.
    """
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Board Stale Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Board Stale Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="U1",
        component_type="mcu",
        value="AVR",
        created_source="USER",
    )
    db_session.add(comp)

    board = EngineeringBoard(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="Board Stale PCB",
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
        footprint_name="DIP-8",
        pos_x=10.0,
        pos_y=10.0,
        rotation=0.0,
        side="TOP",
    )
    db_session.add(fp)

    bom = EngineeringBOM(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="BOM",
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
        requirement_key="REQ-01",
        title="Spec",
        description="Requirement satisfied",
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
        source="Bench Test",
        description="Bench certified",
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
        name="DFM Rules",
        version=1,
        source="STANDARD",
        source_revision="REV_A",
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
        rule_set_revision="REV_A",
        status=ManufacturingAnalysisStatus.COMPLETED.value,
        findings=[],
        summary={},
        created_by=human_engineer.id,
    )
    db_session.add(dfm)

    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )
    assert evaluation.overall_readiness == OverallReadinessState.READY_FOR_RELEASE.value

    # Mutate board post-evaluation (e.g. bump board version)
    board.version = 2
    await db_session.commit()

    baseline_req = ReleaseBaselineCreateRequest(
        evaluation_id=evaluation.id,
        release_tag="v1.0.0-board-stale",
        release_rationale="Attempting baseline with modified board",
        signoff_notes="Signoff",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.authorize_release_baseline(
            project_id=project_id,
            request=baseline_req,
            user=human_engineer,
        )

    assert exc_info.value.status_code == 409
    assert "RELEASE_EVALUATION_STALE" in exc_info.value.detail


@pytest.mark.asyncio
async def test_remediation_def_10c_01_requirement_mutation_triggers_stale_conflict(
    db_session: AsyncSession, human_engineer: AuthenticatedUser
):
    """
    DEF-10C-01: When an engineering requirement status mutates post-evaluation,
    authorize_release_baseline must reject with HTTP 409 RELEASE_EVALUATION_STALE.
    """
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Req Stale Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Req Stale Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="U1",
        component_type="mcu",
        value="AVR",
        created_source="USER",
    )
    db_session.add(comp)

    req = EngineeringRequirement(
        id=str(uuid.uuid4()),
        project_id=project_id,
        system_id=str(uuid.uuid4()),
        requirement_key="REQ-01",
        title="Power Regulation",
        description="3.3V stable rail",
        status=RequirementStatus.SATISFIED.value,
        category=RequirementCategory.POWER.value,
        created_by=human_engineer.id,
    )
    db_session.add(req)

    bom = EngineeringBOM(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="BOM",
        version=1,
        status=BOMStatus.EVALUATED.value,
        total_lines=0,
        created_by=human_engineer.id,
    )
    db_session.add(bom)

    evidence = EngineeringEvidence(
        id=str(uuid.uuid4()),
        verification_requirement_id=str(uuid.uuid4()),
        review_id=str(uuid.uuid4()),
        evidence_type="BENCH_TEST",
        source="Bench Test",
        description="Bench certified",
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
        board_id=None,
        bom_id=None,
        validation_status=CrossDomainValidationStatus.COMPLETED.value,
        is_stale=False,
        findings=[],
        summary={},
        domain_snapshots={},
        staleness_reasons=[],
        snapshot_digest="0" * 64,
    )
    db_session.add(xd)

    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )
    assert evaluation.overall_readiness == OverallReadinessState.READY_FOR_RELEASE.value

    # Mutate requirement status post-evaluation to UNKNOWN
    req.status = RequirementStatus.UNKNOWN.value
    await db_session.commit()

    baseline_req = ReleaseBaselineCreateRequest(
        evaluation_id=evaluation.id,
        release_tag="v1.0.0-req-stale",
        release_rationale="Attempting baseline with mutated requirement",
        signoff_notes="Signoff",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.authorize_release_baseline(
            project_id=project_id,
            request=baseline_req,
            user=human_engineer,
        )

    assert exc_info.value.status_code == 409
    assert "RELEASE_EVALUATION_STALE" in exc_info.value.detail


@pytest.mark.asyncio
async def test_remediation_def_10c_01_audit_ledger_advance_triggers_stale_conflict(
    db_session: AsyncSession, human_engineer: AuthenticatedUser
):
    """
    DEF-10C-01: When an audit event is appended to the ledger post-evaluation,
    authorize_release_baseline must detect the advanced head hash and reject with HTTP 409.
    """
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Audit Stale Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    db_session.add(project)

    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        name="Audit Stale Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    db_session.add(circuit)

    comp = Component(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        ref_des="U1",
        component_type="mcu",
        value="AVR",
        created_source="USER",
    )
    db_session.add(comp)

    req = EngineeringRequirement(
        id=str(uuid.uuid4()),
        project_id=project_id,
        system_id=str(uuid.uuid4()),
        requirement_key="REQ-01",
        title="Spec",
        description="Satisfied",
        status=RequirementStatus.SATISFIED.value,
        category=RequirementCategory.FUNCTIONAL.value,
        created_by=human_engineer.id,
    )
    db_session.add(req)

    bom = EngineeringBOM(
        id=str(uuid.uuid4()),
        project_id=project_id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="BOM",
        version=1,
        status=BOMStatus.EVALUATED.value,
        total_lines=0,
        created_by=human_engineer.id,
    )
    db_session.add(bom)

    evidence = EngineeringEvidence(
        id=str(uuid.uuid4()),
        verification_requirement_id=str(uuid.uuid4()),
        review_id=str(uuid.uuid4()),
        evidence_type="BENCH_TEST",
        source="Bench Test",
        description="Bench certified",
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
        board_id=None,
        bom_id=None,
        validation_status=CrossDomainValidationStatus.COMPLETED.value,
        is_stale=False,
        findings=[],
        summary={},
        domain_snapshots={},
        staleness_reasons=[],
        snapshot_digest="0" * 64,
    )
    db_session.add(xd)

    await db_session.commit()

    service = ReleaseService(db_session)
    evaluation = await service.evaluate_release_readiness(
        project_id=project_id,
        user=human_engineer,
    )
    assert evaluation.overall_readiness == OverallReadinessState.READY_FOR_RELEASE.value

    # Append an audit event to the project audit ledger post-evaluation
    audit_service = AuditLedgerService(db_session)
    await audit_service.record_event(
        project_id=project_id,
        actor_id=human_engineer.id,
        actor_role=human_engineer.role,
        event_type=AuditEventType.CIRCUIT_MUTATED,
        entity_type="CIRCUIT",
        entity_id=circuit.id,
        entity_revision=1,
        payload={"mutation": "post_eval_audit_entry"},
        tenant_id=human_engineer.tenant_id,
    )

    baseline_req = ReleaseBaselineCreateRequest(
        evaluation_id=evaluation.id,
        release_tag="v1.0.0-audit-stale",
        release_rationale="Attempting baseline with advanced audit ledger",
        signoff_notes="Signoff",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.authorize_release_baseline(
            project_id=project_id,
            request=baseline_req,
            user=human_engineer,
        )

    assert exc_info.value.status_code == 409
    assert "RELEASE_EVALUATION_STALE" in exc_info.value.detail


@pytest.mark.asyncio
async def test_remediation_def_10c_02_exact_role_matching_and_ai_rejection(
    db_session: AsyncSession, human_engineer: AuthenticatedUser
):
    """
    DEF-10C-02: Exact role matching rejects AI roles (e.g. AI_ENGINEER, AI_LEAD)
    and unauthorized human roles (e.g. VIEWER, INTERN) with HTTP 403.
    """
    eval_time = datetime.now(timezone.utc)

    # 1. AI role rejected in RG-09
    ai_eng = AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="ai.eng@quebet.ai",
        tenant_id="tenant-alpha",
        role="AI_ENGINEER",
        permissions=["release:evaluate"],
    )
    g9_ai = ReleaseGateEngine.evaluate_rg09(ai_eng, eval_time)
    assert g9_ai.status == ReleaseGateStatus.BLOCKED
    assert any("AI actor" in r or "not authorized" in r for r in g9_ai.failure_reasons)

    # 2. Unauthorized role rejected in RG-09
    intern_user = AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="intern@quebet.test",
        tenant_id="tenant-alpha",
        role="INTERN",
        permissions=["release:evaluate"],
    )
    g9_intern = ReleaseGateEngine.evaluate_rg09(intern_user, eval_time)
    assert g9_intern.status == ReleaseGateStatus.BLOCKED
    assert any("not authorized" in r for r in g9_intern.failure_reasons)

    # 3. Authorized exact human role passes RG-09
    g9_human = ReleaseGateEngine.evaluate_rg09(human_engineer, eval_time)
    assert g9_human.status == ReleaseGateStatus.PASS

    # 4. In authorize_release_baseline, AI_ENGINEER is rejected with HTTP 403
    service = ReleaseService(db_session)
    baseline_req = ReleaseBaselineCreateRequest(
        evaluation_id=str(uuid.uuid4()),
        release_tag="v1.0.0-ai-exact",
        release_rationale="AI role attempt",
        signoff_notes="Signoff",
    )
    with pytest.raises(HTTPException) as exc_info:
        await service.authorize_release_baseline(
            project_id=str(uuid.uuid4()),
            request=baseline_req,
            user=ai_eng,
        )
    assert exc_info.value.status_code == 403
    assert "AI ENGINEERING AUTHORITY = NONE" in exc_info.value.detail


@pytest.mark.asyncio
async def test_remediation_def_10c_03_pcb_drc_fail_closed_on_exception(
    db_session: AsyncSession, human_engineer: AuthenticatedUser
):
    """
    DEF-10C-03: PCBRuleEngine.run_drc raising an unexpected exception or returning
    malformed output causes RG-02 to return ReleaseGateStatus.FAIL (Fail-Closed).
    """
    eval_time = datetime.now(timezone.utc)
    project = Project(
        id=str(uuid.uuid4()),
        name="DRC Fail Closed Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id=human_engineer.tenant_id,
        owner_id=human_engineer.id,
    )
    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project.id,
        name="DRC Circuit",
        version=1,
        validation_status=CircuitValidationStatus.VALID.value,
        created_by=human_engineer.id,
    )
    board = EngineeringBoard(
        id=str(uuid.uuid4()),
        project_id=project.id,
        circuit_id=circuit.id,
        circuit_version=1,
        name="DRC PCB",
        version=1,
        status=BoardStatus.REVIEW.value,
        dimensions={"width": 100, "height": 80},
        created_by=human_engineer.id,
    )

    # Test 1: run_drc raises unexpected RuntimeError -> RG-02 FAIL with diagnostic reason
    with patch("app.services.release_service.PCBRuleEngine.run_drc", side_effect=RuntimeError("DRC engine crash")):
        g2 = ReleaseGateEngine.evaluate_rg02(project, circuit, board, eval_time)
        assert g2.status == ReleaseGateStatus.FAIL
        assert any("PCB DRC execution failed with unexpected exception: RuntimeError" in r for r in g2.failure_reasons)

    # Test 2: run_drc returns malformed tuple -> RG-02 FAIL with diagnostic reason
    with patch("app.services.release_service.PCBRuleEngine.run_drc", return_value="malformed_string"):
        g2_malformed = ReleaseGateEngine.evaluate_rg02(project, circuit, board, eval_time)
        assert g2_malformed.status == ReleaseGateStatus.FAIL
        assert any("malformed or incomplete output tuple" in r for r in g2_malformed.failure_reasons)

    # Test 3: run_drc returns invalid findings -> RG-02 FAIL
    with patch("app.services.release_service.PCBRuleEngine.run_drc", return_value=(None, [], {})):
        g2_none_findings = ReleaseGateEngine.evaluate_rg02(project, circuit, board, eval_time)
        assert g2_none_findings.status == ReleaseGateStatus.FAIL
        assert any("findings output is invalid or missing" in r for r in g2_none_findings.failure_reasons)

    # Test 4: run_drc returns findings containing None or objects lacking severity -> RG-02 FAIL
    with patch("app.services.release_service.PCBRuleEngine.run_drc", return_value=([None, "not_a_finding_obj"], [], {})):
        g2_malformed_items = ReleaseGateEngine.evaluate_rg02(project, circuit, board, eval_time)
        assert g2_malformed_items.status == ReleaseGateStatus.FAIL
        assert any("malformed or invalid finding entries" in r for r in g2_malformed_items.failure_reasons)


@pytest.mark.asyncio
async def test_adversarial_actor_variations_and_cross_tenant_baseline_authorization(
    db_session: AsyncSession, human_engineer: AuthenticatedUser
):
    """
    Wave 10C.2 Adversarial Verification:
    1. Rejection of synthetic/adversarial roles (PROMPT_ENGINEER, ENGINEER_BOT, COPILOT_ENGINEER, empty, None).
    2. Rejection of cross-tenant baseline authorization attempts (HTTP 404/403).
    """
    eval_time = datetime.now(timezone.utc)
    service = ReleaseService(db_session)

    # 1. Adversarial role rejection across various substrings and empty values
    adversarial_roles = [
        "PROMPT_ENGINEER",
        "ENGINEER_BOT",
        "COPILOT_ENGINEER",
        "AI_RESEARCHER",
        "AUTONOMOUS_SYSTEM",
        "",
        "   ",
        "UNKNOWN_ROLE",
    ]

    for adv_role in adversarial_roles:
        adv_user = AuthenticatedUser(
            id=str(uuid.uuid4()),
            email=f"{adv_role.lower().strip() or 'empty'}@quebet.test",
            tenant_id="tenant-alpha",
            role=adv_role,
            permissions=["release:evaluate"],
        )
        # Gate RG-09 evaluation must BLOCK
        g9 = ReleaseGateEngine.evaluate_rg09(adv_user, eval_time)
        assert g9.status == ReleaseGateStatus.BLOCKED, f"Role '{adv_role}' should be BLOCKED by RG-09"

        # Baseline authorization must raise HTTP 403 Forbidden
        baseline_req = ReleaseBaselineCreateRequest(
            evaluation_id=str(uuid.uuid4()),
            release_tag=f"v1.0.0-{adv_role.strip().lower() or 'none'}",
            release_rationale="Adversarial role attempt",
            signoff_notes="Adversarial test notes",
        )
        with pytest.raises(HTTPException) as exc_info:
            await service.authorize_release_baseline(
                project_id=str(uuid.uuid4()),
                request=baseline_req,
                user=adv_user,
            )
        assert exc_info.value.status_code == 403
        assert "AI ENGINEERING AUTHORITY = NONE" in exc_info.value.detail

    # 2. Cross-tenant baseline authorization isolation
    # Project owned by tenant-alpha
    proj_alpha = Project(
        id=str(uuid.uuid4()),
        name="Alpha Project",
        project_type=ProjectType.GENERAL.value,
        status=ProjectStatus.ACTIVE,
        tenant_id="tenant-alpha",
        owner_id=human_engineer.id,
    )
    db_session.add(proj_alpha)
    await db_session.commit()

    # User belonging to tenant-beta attempting to baseline proj_alpha
    beta_engineer = AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="engineer@tenant-beta.test",
        tenant_id="tenant-beta",
        role="ENGINEER",
        permissions=["release:evaluate", "release:authorize"],
    )

    baseline_cross_req = ReleaseBaselineCreateRequest(
        evaluation_id=str(uuid.uuid4()),
        release_tag="v1.0.0-cross-tenant",
        release_rationale="Cross tenant baseline breach attempt",
        signoff_notes="Cross tenant attempt",
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.authorize_release_baseline(
            project_id=proj_alpha.id,
            request=baseline_cross_req,
            user=beta_engineer,
        )
    assert exc_info.value.status_code == 404
    assert "tenant access denied" in exc_info.value.detail or "not found" in exc_info.value.detail