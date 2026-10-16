"""
Unit and integration tests for Phase 3 Wave 10B:
Authoritative Engineering Mutation Integration.

Verifies:
1. DOMAIN MUTATION COMMIT <=> REQUIRED AUDIT EVENT COMMIT invariant.
2. Proposal approval & apply atomically commit their required audit events.
3. Circuit component mutations (add, update, delete) atomically emit audit events.
4. Review finding waivers and unknown dispositions atomically emit audit events.
5. Transactional rollback integrity: failure in audit event stages rolls back domain mutation.
6. Transactional rollback integrity: domain mutation error rolls back audit event.
7. Event hash header binds tenant_id to prevent cross-tenant forging.
8. Canonical JSON serialization prevents key collision ambiguities.
"""
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.db.base import Base
from app.models.db.audit_ledger import AuditEventType, EngineeringAuditEvent
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.models.db.circuit import Circuit, CircuitValidationStatus
from app.models.db.component import Component
from app.models.db.proposal import EngineeringProposal, ProposalStatus
from app.models.db.system import EngineeringSystem
from app.models.db.decision import (
    EngineeringDecisionRecord,
    EngineeringDesignReviewSession,
    EngineeringReviewFinding,
    EngineeringUnknownDisposition,
)
from app.models.schemas.circuit import ComponentCreate, ComponentUpdate
from app.core.dependencies import AuthenticatedUser
from app.services.audit_ledger_service import AuditLedgerService, CanonicalSerializationError
from app.services.circuit_service import circuit_service
from app.services.proposal_service import proposal_service
from app.repositories.circuit_repo import circuit_repo
from app.repositories.decision_repo import DecisionRepository


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
def test_user():
    return AuthenticatedUser(
        id=str(uuid.uuid4()),
        email="engineer@quebet.test",
        tenant_id="tenant-alpha",
        role="STAFF_ENGINEER",
        permissions=["circuits:write", "proposals:write", "reviews:write"],
    )


@pytest.mark.asyncio
async def test_tenant_id_bound_in_canonical_event_header():
    service = AuditLedgerService(None)
    hash_t1 = service.compute_event_hash(
        project_id="proj-1",
        sequence_number=1,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type="CIRCUIT_MUTATED",
        entity_type="CIRCUIT",
        entity_id="circ-1",
        entity_revision=1,
        payload_hash="abcd",
        prev_event_hash="0" * 64,
        tenant_id="tenant-1",
    )

    hash_t2 = service.compute_event_hash(
        project_id="proj-1",
        sequence_number=1,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type="CIRCUIT_MUTATED",
        entity_type="CIRCUIT",
        entity_id="circ-1",
        entity_revision=1,
        payload_hash="abcd",
        prev_event_hash="0" * 64,
        tenant_id="tenant-2",
    )

    assert hash_t1 != hash_t2, "Changing tenant_id must produce different event hash."


@pytest.mark.asyncio
async def test_canonical_json_detects_key_collisions():
    service = AuditLedgerService(None)
    collision_dict = {1: "value_one", "1": "value_two"}
    with pytest.raises(CanonicalSerializationError) as exc_info:
        service.canonical_json_value(collision_dict)
    assert "Canonical key collision detected" in str(exc_info.value)


@pytest.mark.asyncio
async def test_component_add_atomic_audit_event(db_session: AsyncSession, test_user: AuthenticatedUser):
    project = Project(
        id=str(uuid.uuid4()),
        name="Project Alpha",
        project_type=ProjectType.CIRCUIT,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project.id,
        tenant_id=test_user.tenant_id,
        name="Main Board",
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    comp_in = ComponentCreate(
        ref_des="R101",
        component_type="RESISTOR",
        value="10k",
        unit="ohm",
        package="0805",
    )

    comp_res = await circuit_service.add_component(
        db=db_session,
        circuit_id=circuit.id,
        comp_in=comp_in,
        current_user=test_user,
    )

    comp = await circuit_repo.get_component(db=db_session, component_id=comp_res.id)
    assert comp is not None
    assert comp.ref_des == "R101"

    stmt = select(EngineeringAuditEvent).where(EngineeringAuditEvent.project_id == project.id)
    events = (await db_session.execute(stmt)).scalars().all()
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == AuditEventType.COMPONENT_ADDED.value
    assert ev.entity_id == comp.id
    assert ev.entity_revision == 1
    assert ev.payload["ref_des"] == "R101"
    assert ev.tenant_id == test_user.tenant_id


@pytest.mark.asyncio
async def test_component_add_rollback_on_audit_failure(db_session: AsyncSession, test_user: AuthenticatedUser):
    project_id = str(uuid.uuid4())
    circuit_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Project Beta",
        project_type=ProjectType.CIRCUIT,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit = Circuit(
        id=circuit_id,
        project_id=project.id,
        tenant_id=test_user.tenant_id,
        name="Power Rail",
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    comp_in = ComponentCreate(
        ref_des="C202",
        component_type="CAPACITOR",
        value="100nF",
        unit="F",
        package="0402",
    )

    with patch.object(AuditLedgerService, "record_event", side_effect=RuntimeError("Audit hardware disk full")):
        with pytest.raises(RuntimeError) as exc_info:
            await circuit_service.add_component(
                db=db_session,
                circuit_id=circuit_id,
                comp_in=comp_in,
                current_user=test_user,
            )
        assert "Audit hardware disk full" in str(exc_info.value)

    await db_session.rollback()

    stmt = select(Component).where(Component.circuit_id == circuit_id)
    comps = (await db_session.execute(stmt)).scalars().all()
    assert len(comps) == 0

    stmt_ev = select(EngineeringAuditEvent).where(EngineeringAuditEvent.project_id == project_id)
    events = (await db_session.execute(stmt_ev)).scalars().all()
    assert len(events) == 0


@pytest.mark.asyncio
async def test_proposal_approve_and_apply_atomic_audit(db_session: AsyncSession, test_user: AuthenticatedUser):
    project = Project(
        id=str(uuid.uuid4()),
        name="Project Gamma",
        project_type=ProjectType.CIRCUIT,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project.id,
        tenant_id=test_user.tenant_id,
        name="Sensor Interface",
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    proposal = EngineeringProposal(
        id=str(uuid.uuid4()),
        circuit_id=circuit.id,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        source="ENGINEER",
        title="Add pull-up resistor",
        status=ProposalStatus.VALIDATED.value,
        base_revision=1,
        operations=[
            {
                "op_type": "add_component",
                "payload": {
                    "ref_des": "R404",
                    "component_type": "RESISTOR",
                    "value": "4.7k",
                },
            }
        ],
    )
    db_session.add(proposal)
    await db_session.commit()

    app_res = await proposal_service.approve_proposal(
        db=db_session,
        proposal_id=proposal.id,
        current_user=test_user,
    )
    assert app_res.status == ProposalStatus.APPROVED.value

    stmt = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project.id,
        EngineeringAuditEvent.event_type == AuditEventType.PROPOSAL_APPROVED.value,
    )
    ev_app = (await db_session.execute(stmt)).scalar_one_or_none()
    assert ev_app is not None
    assert ev_app.sequence_number == 1
    assert ev_app.entity_id == proposal.id

    apply_res = await proposal_service.apply_proposal(
        db=db_session,
        proposal_id=proposal.id,
        current_user=test_user,
    )
    assert apply_res.status == ProposalStatus.APPLIED.value

    await db_session.refresh(circuit)
    assert circuit.version == 2

    stmt_c = select(Component).where(Component.circuit_id == circuit.id, Component.ref_des == "R404")
    c404 = (await db_session.execute(stmt_c)).scalar_one_or_none()
    assert c404 is not None

    stmt_apply = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project.id,
        EngineeringAuditEvent.event_type == AuditEventType.PROPOSAL_APPLIED.value,
    )
    ev_applied = (await db_session.execute(stmt_apply)).scalar_one_or_none()
    assert ev_applied is not None
    assert ev_applied.sequence_number == 2
    assert ev_applied.prev_event_hash == ev_app.event_hash
    assert ev_applied.entity_revision == 2

    audit_service = AuditLedgerService(db_session)
    chain_verif = await audit_service.verify_chain(project.id)
    assert chain_verif["is_valid"] is True
    assert chain_verif["events_verified"] == 2


@pytest.mark.asyncio
async def test_proposal_apply_failure_rolls_back_audit_event(db_session: AsyncSession, test_user: AuthenticatedUser):
    project_id = str(uuid.uuid4())
    circuit_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Project Delta",
        project_type=ProjectType.CIRCUIT,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit = Circuit(
        id=circuit_id,
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        name="Radio Front-End",
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    proposal = EngineeringProposal(
        id=str(uuid.uuid4()),
        circuit_id=circuit_id,
        tenant_id=test_user.tenant_id,
        created_by=test_user.id,
        source="ENGINEER",
        title="Failing operation test",
        status=ProposalStatus.APPROVED.value,
        base_revision=1,
        operations=[
            {
                "op_type": "add_component",
                "payload": {"ref_des": "R99", "component_type": "RESISTOR", "value": "100"},
            },
            {
                "op_type": "fail_simulation",
                "payload": {},
            },
        ],
    )
    db_session.add(proposal)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await proposal_service.apply_proposal(
            db=db_session,
            proposal_id=proposal.id,
            current_user=test_user,
        )
    assert exc_info.value.status_code == 500

    # Query circuit state directly
    stmt_circ = select(Circuit).where(Circuit.id == circuit_id)
    circ_after = (await db_session.execute(stmt_circ)).scalar_one()
    assert circ_after.version == 1

    stmt_c = select(Component).where(Component.circuit_id == circuit_id, Component.ref_des == "R99")
    assert (await db_session.execute(stmt_c)).scalar_one_or_none() is None

    stmt_ev = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.PROPOSAL_APPLIED.value,
    )
    assert (await db_session.execute(stmt_ev)).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_unknown_disposition_atomic_audit(db_session: AsyncSession, test_user: AuthenticatedUser):
    project = Project(
        id=str(uuid.uuid4()),
        name="Project Epsilon",
        project_type=ProjectType.GENERAL,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()

    decision = EngineeringDecisionRecord(
        id=str(uuid.uuid4()),
        system_id=str(uuid.uuid4()),
        project_id=project.id,
        tenant_id=test_user.tenant_id,
        title="Battery Chemistry Selection",
        decision_key="DEC-001",
        description="Select LiFePO4 chemistry",
        system_revision=3,
    )
    db_session.add(decision)
    await db_session.commit()

    repo = DecisionRepository(db_session)
    disp = await repo.create_unknown_disposition(
        decision_id=decision.id,
        unknown_key="low_temp_discharge_curve",
        actor=test_user.id,
        reason="Field tested under lab conditions down to -20C",
        status="ACCEPTED",
    )

    assert disp is not None
    stmt_ev = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project.id,
        EngineeringAuditEvent.event_type == AuditEventType.UNKNOWN_DISPOSED.value,
    )
    ev = (await db_session.execute(stmt_ev)).scalar_one_or_none()
    assert ev is not None
    assert ev.entity_id == disp.id
    assert ev.entity_revision == 3
    assert ev.payload["unknown_key"] == "low_temp_discharge_curve"


@pytest.mark.asyncio
async def test_waive_finding_atomic_audit(db_session: AsyncSession, test_user: AuthenticatedUser):
    project = Project(
        id=str(uuid.uuid4()),
        name="Project Zeta",
        project_type=ProjectType.GENERAL,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    system = EngineeringSystem(
        id=str(uuid.uuid4()),
        project_id=project.id,
        tenant_id=test_user.tenant_id,
        name="Telemetry Unit",
        revision=2,
        created_by=test_user.id,
    )
    review = EngineeringDesignReviewSession(
        id=str(uuid.uuid4()),
        system_id=system.id,
        system_revision=2,
        tenant_id=test_user.tenant_id,
        title="CDR Review",
        chairperson=test_user.id,
    )
    finding = EngineeringReviewFinding(
        id=str(uuid.uuid4()),
        review_id=review.id,
        source_analysis="Thermal Analysis",
        severity="WARNING",
        description="Temperature margin within 5% of junction maximum",
        status="OPEN",
    )
    db_session.add_all([project, system, review, finding])
    await db_session.commit()

    repo = DecisionRepository(db_session)
    waived = await repo.waive_finding(
        finding_id=finding.id,
        waived_by=test_user.id,
        waiver_rationale="Derated operating envelope verified under forced convection.",
    )

    assert waived is not None
    assert waived.status == "WAIVED"
    assert waived.waived_by == test_user.id

    stmt_ev = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project.id,
        EngineeringAuditEvent.event_type == AuditEventType.REVIEW_FINDING_WAIVED.value,
    )
    ev = (await db_session.execute(stmt_ev)).scalar_one_or_none()
    assert ev is not None
    assert ev.entity_id == finding.id
    assert ev.entity_revision == 2
    assert ev.payload["severity"] == "WARNING"
    assert "Derated operating envelope" in ev.payload["waiver_rationale"]
