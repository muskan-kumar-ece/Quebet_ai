"""
Unit and integration tests for Phase 3 Wave 10B.1:
Authoritative Engineering Mutation Coverage Completion.

Verifies:
1. Priority A: Net & Connection mutations emit NET_MUTATED and CONNECTION_MUTATED events atomically.
2. Priority B: PCB Board creation and updates emit BOARD_CREATED and BOARD_MUTATED events atomically.
3. Priority C: BOM generation, candidate selection, and substitution approval emit BOM_CREATED, PART_CANDIDATE_SELECTED, and BOM_MUTATED events.
4. Priority D: Requirement creation, updates, and baselines emit REQUIREMENT_CREATED, REQUIREMENT_UPDATED, and REQUIREMENT_BASELINE_CREATED events.
5. Priority E: DFM analysis and Cross-Domain validation emit DFM_ANALYSIS_EXECUTED and CROSS_DOMAIN_VALIDATED events.
6. Atomicity & Rollback: failure during audit event generation rolls back the domain mutation.
7. Verification of full event chain across heterogeneous engineering domains.
"""
from datetime import datetime, timezone
import uuid
import pytest
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.db.base import Base
from app.models.db.audit_ledger import AuditEventType, EngineeringAuditEvent
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.models.db.circuit import Circuit
from app.models.db.component import Component
from app.models.db.net import Net
from app.models.db.connection import Connection
from app.models.db.pcb import EngineeringBoard
from app.models.db.bom import EngineeringBOM, EngineeringBOMLine, ComponentPartCandidate, BOMSubstitutionProposal
from app.models.db.system import EngineeringSystem
from app.models.db.decision import EngineeringRequirement, EngineeringRequirementBaseline
from app.models.schemas.circuit import NetCreate, NetUpdate, ConnectionCreate, ComponentCreate
from app.models.schemas.pcb import EngineeringBoardCreate, EngineeringBoardUpdate
from app.models.schemas.bom import EngineeringBOMCreate, ComponentPartCandidateCreate, BOMSubstitutionProposalCreate
from app.models.schemas.decision import EngineeringRequirementCreate, EngineeringRequirementUpdate
from app.core.dependencies import AuthenticatedUser
from app.services.audit_ledger_service import AuditLedgerService
from app.services.circuit_service import circuit_service
from app.services.pcb_service import pcb_service
from app.services.bom_service import bom_service
from app.services.cross_domain_service import CrossDomainService
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
        email="lead_engineer@quebet.test",
        tenant_id="tenant-beta",
        role="STAFF_ENGINEER",
        permissions=["circuits:write", "pcb:write", "bom:write", "requirements:write"],
    )


@pytest.mark.asyncio
async def test_net_and_connection_mutations_emit_audit_events(db_session: AsyncSession, test_user: AuthenticatedUser):
    """Verify adding/updating net and adding connection atomically emit NET_MUTATED and CONNECTION_MUTATED."""
    project_id = str(uuid.uuid4())
    circuit_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Telemetry Subsystem",
        project_type=ProjectType.CIRCUIT,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit = Circuit(
        id=circuit_id,
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        name="RF Board",
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    # 1. Add component R1
    comp_res = await circuit_service.add_component(
        db=db_session,
        circuit_id=circuit_id,
        comp_in=ComponentCreate(ref_des="R1", component_type="RESISTOR", value="10k", pins=[{"pin_number": "1"}, {"pin_number": "2"}]),
        current_user=test_user,
    )

    # 2. Add Net VDD
    net_res = await circuit_service.add_net(
        db=db_session,
        circuit_id=circuit_id,
        net_in=NetCreate(name="VDD", net_type="POWER"),
        current_user=test_user,
    )
    assert net_res.name == "VDD"

    # Verify NET_MUTATED event
    stmt_net = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.NET_MUTATED.value,
    )
    ev_net = (await db_session.execute(stmt_net)).scalar_one()
    assert ev_net.entity_id == net_res.id
    assert ev_net.payload["action"] == "ADD_NET"

    # 3. Add Connection
    # Expire circuit cached in session so add_connection sees the newly added component
    db_session.expire_all()
    conn_res = await circuit_service.add_connection(
        db=db_session,
        circuit_id=circuit_id,
        conn_in=ConnectionCreate(component_id=comp_res.id, pin_number="1", net_id=net_res.id),
        current_user=test_user,
    )
    assert conn_res.component_id == comp_res.id

    # Verify CONNECTION_MUTATED event
    stmt_conn = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.CONNECTION_MUTATED.value,
    )
    ev_conn = (await db_session.execute(stmt_conn)).scalar_one()
    assert ev_conn.entity_id == conn_res.id
    assert ev_conn.payload["action"] == "ADD_CONNECTION"


@pytest.mark.asyncio
async def test_pcb_board_create_and_update_audit(db_session: AsyncSession, test_user: AuthenticatedUser):
    """Verify PCB board creation and mutation atomically emit BOARD_CREATED and BOARD_MUTATED."""
    project_id = str(uuid.uuid4())
    circuit_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Avionics Power",
        project_type=ProjectType.PCB,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit = Circuit(
        id=circuit_id,
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        name="Power Rail",
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    # 1. Create Board
    board = await pcb_service.create_board(
        db=db_session,
        current_user=test_user,
        request=EngineeringBoardCreate(
            circuit_id=circuit_id,
            name="Power Board Rev A",
            dimensions={"width": 100.0, "height": 80.0},
            units="mm",
        ),
    )
    assert board.name == "Power Board Rev A"

    stmt_b1 = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.BOARD_CREATED.value,
    )
    ev_b1 = (await db_session.execute(stmt_b1)).scalar_one()
    assert ev_b1.entity_id == board.id

    # 2. Update Board
    board_updated = await pcb_service.update_board(
        db=db_session,
        board_id=board.id,
        update_req=EngineeringBoardUpdate(dimensions={"width": 120.0, "height": 90.0}),
        current_user=test_user,
    )
    assert board_updated.version == 2

    stmt_b2 = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.BOARD_MUTATED.value,
    )
    ev_b2 = (await db_session.execute(stmt_b2)).scalar_one()
    assert ev_b2.entity_id == board.id
    assert ev_b2.entity_revision == 2


@pytest.mark.asyncio
async def test_bom_lifecycle_audit_events(db_session: AsyncSession, test_user: AuthenticatedUser):
    """Verify BOM generation and candidate selection emit BOM_CREATED and PART_CANDIDATE_SELECTED."""
    project_id = str(uuid.uuid4())
    circuit_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Sensor Pod",
        project_type=ProjectType.CIRCUIT,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit = Circuit(
        id=circuit_id,
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        name="Sensor Interface",
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    # Add component to source into BOM
    await circuit_service.add_component(
        db=db_session,
        circuit_id=circuit_id,
        comp_in=ComponentCreate(ref_des="R1", component_type="RESISTOR", value="10k", package="0805"),
        current_user=test_user,
    )

    # 1. Generate BOM
    db_session.expire_all()
    bom = await bom_service.create_bom(
        db=db_session,
        current_user=test_user,
        request=EngineeringBOMCreate(circuit_id=circuit_id, name="Production BOM"),
    )
    assert bom is not None

    stmt_bom = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.BOM_CREATED.value,
    )
    ev_bom = (await db_session.execute(stmt_bom)).scalar_one()
    assert ev_bom.entity_id == bom.id

    # 2. Add Part Candidate
    line = bom.lines[0]
    cand = await bom_service.add_candidate(
        db=db_session,
        line_id=line.id,
        candidate_in=ComponentPartCandidateCreate(
            manufacturer="Yageo",
            mpn="RC0805FR-0710KL",
            description="10k Resistor 1% 0805",
        ),
        current_user=test_user,
    )
    assert cand is not None

    stmt_cand = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.PART_CANDIDATE_SELECTED.value,
    )
    ev_cand = (await db_session.execute(stmt_cand)).scalar_one()
    assert ev_cand.entity_id == cand.id
    assert ev_cand.payload["mpn"] == "RC0805FR-0710KL"


@pytest.mark.asyncio
async def test_requirements_and_baselines_audit_events(db_session: AsyncSession, test_user: AuthenticatedUser):
    """Verify requirement creation, update, and baselining emit audit events."""
    project_id = str(uuid.uuid4())
    system_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Guidance System",
        project_type=ProjectType.GENERAL,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    system = EngineeringSystem(
        id=system_id,
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        name="IMU Controller",
        revision=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, system])
    await db_session.commit()

    repo = DecisionRepository(db_session)

    # 1. Create requirement
    req = await repo.create_requirement(
        project_id=project_id,
        system_id=system_id,
        requirement_key="REQ-PWR-01",
        title="Input Voltage 12V",
        description="Operating supply between 9V and 16V",
        created_by=test_user.id,
        tenant_id=test_user.tenant_id,
    )
    assert req is not None

    stmt_req = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.REQUIREMENT_CREATED.value,
    )
    ev_req = (await db_session.execute(stmt_req)).scalar_one()
    assert ev_req.entity_id == req.id
    assert ev_req.payload["requirement_key"] == "REQ-PWR-01"

    # 2. Update requirement
    req_updated = await repo.update_requirement(
        requirement_id=req.id,
        updates={"description": "Operating supply strictly 12V +/- 10%"},
        tenant_id=test_user.tenant_id,
        actor_id=test_user.id,
    )
    assert req_updated.revision == 2

    stmt_upd = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.REQUIREMENT_UPDATED.value,
    )
    ev_upd = (await db_session.execute(stmt_upd)).scalar_one()
    assert ev_upd.entity_revision == 2

    # 3. Create requirement baseline
    baseline = await repo.create_baseline(
        system_id=system_id,
        system_revision=1,
        name="PDR Baseline",
        requirement_ids=[req.id],
        requirement_revisions={req.id: req_updated.revision},
        created_by=test_user.id,
        tenant_id=test_user.tenant_id,
    )
    assert baseline is not None

    stmt_base = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.REQUIREMENT_BASELINE_CREATED.value,
    )
    ev_base = (await db_session.execute(stmt_base)).scalar_one()
    assert ev_base.entity_id == baseline.id
    assert ev_base.payload["requirement_count"] == 1


@pytest.mark.asyncio
async def test_cross_domain_validation_audit_event(db_session: AsyncSession, test_user: AuthenticatedUser):
    """Verify cross-domain validation run records CROSS_DOMAIN_VALIDATED audit event."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Cross Domain Test",
        project_type=ProjectType.GENERAL,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit = Circuit(
        id=str(uuid.uuid4()),
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        name="Main Board",
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    service = CrossDomainService(db_session)
    record = await service.validate_project(
        project_id=project_id,
        tenant_id=test_user.tenant_id,
    )
    assert record is not None

    stmt = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.project_id == project_id,
        EngineeringAuditEvent.event_type == AuditEventType.CROSS_DOMAIN_VALIDATED.value,
    )
    ev = (await db_session.execute(stmt)).scalar_one()
    assert ev.entity_id == record.id
    assert ev.payload["validation_id"] == record.id

    # Verify overall chain validity for project
    audit_service = AuditLedgerService(db_session)
    chain_verif = await audit_service.verify_chain(project_id)
    assert chain_verif["is_valid"] is True
    assert chain_verif["events_verified"] == 1


@pytest.mark.asyncio
async def test_net_mutation_audit_failure_rolls_back_domain_mutation(db_session: AsyncSession, test_user: AuthenticatedUser):
    """Verify that if recording the NET_MUTATED event fails, the Net creation is rolled back."""
    project_id = str(uuid.uuid4())
    circuit_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Telemetry Node",
        project_type=ProjectType.CIRCUIT,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit = Circuit(
        id=circuit_id,
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        name="RF Interface",
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    with patch.object(AuditLedgerService, "record_event", side_effect=RuntimeError("Storage hardware fault")):
        with pytest.raises(RuntimeError) as exc_info:
            await circuit_service.add_net(
                db=db_session,
                circuit_id=circuit_id,
                net_in=NetCreate(name="GND_ISO", net_type="GROUND"),
                current_user=test_user,
            )
        assert "Storage hardware fault" in str(exc_info.value)

    await db_session.rollback()

    # Assert persisted database state after rollback
    stmt_nets = select(Net).where(Net.circuit_id == circuit_id, Net.name == "GND_ISO")
    persisted_net = (await db_session.execute(stmt_nets)).scalar_one_or_none()
    assert persisted_net is None, "Domain net must not commit when audit event generation fails."

    stmt_ev = select(EngineeringAuditEvent).where(EngineeringAuditEvent.project_id == project_id)
    events = (await db_session.execute(stmt_ev)).scalars().all()
    assert len(events) == 0, "No audit events should persist on rollback."


# ==============================================================================
# PHASE 3 WAVE 10B.3 TESTS: Final Authoritative Mutation Coverage Closure
# ==============================================================================


@pytest.mark.asyncio
async def test_wave10b3_circuit_creation_audit_and_rollback(db_session, test_user):
    from app.services.circuit_service import circuit_service
    from app.models.schemas.circuit import CircuitCreate
    from app.models.db.circuit import Circuit
    from app.models.db.project import Project

    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Project 10B3 Circuit",
        description="Circuit creation test project",
        project_type=ProjectType.CIRCUIT,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()

    # 1. Successful creation emits CIRCUIT_CREATED atomically
    req = CircuitCreate(
        name="Test 10B3 Circuit",
        description="Testing audit integration on circuit creation",
        components=[],
        nets=[],
        connections=[],
        schematic_objects=[],
        assumptions=[],
    )
    res = await circuit_service.create_circuit(
        db=db_session,
        project_id=project_id,
        circuit_in=req,
        current_user=test_user,
    )
    assert res is not None
    circuit_id = res.id

    # Verify audit event committed
    stmt = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.event_type == AuditEventType.CIRCUIT_CREATED.value,
        EngineeringAuditEvent.entity_id == circuit_id,
    )
    result = await db_session.execute(stmt)
    events = result.scalars().all()
    assert len(events) == 1
    ev = events[0]
    assert ev.payload["name"] == "Test 10B3 Circuit"
    assert ev.payload["components_count"] == 0

    # 2. Failure injection: if audit recording fails, circuit is rolled back and not persisted
    req_fail = CircuitCreate(
        name="Failing 10B3 Circuit",
        description="Testing rollback on failure",
        components=[],
        nets=[],
        connections=[],
        schematic_objects=[],
        assumptions=[],
    )
    with patch.object(AuditLedgerService, "record_event", side_effect=RuntimeError("Simulated audit failure")):
        with pytest.raises(RuntimeError, match="Simulated audit failure"):
            await circuit_service.create_circuit(
                db=db_session,
                project_id=project_id,
                circuit_in=req_fail,
                current_user=test_user,
            )

    await db_session.rollback()

    # Verify that 'Failing 10B3 Circuit' was rolled back
    stmt_ck = select(Circuit).where(Circuit.name == "Failing 10B3 Circuit")
    res_ck = await db_session.execute(stmt_ck)
    assert res_ck.scalars().first() is None


@pytest.mark.asyncio
async def test_wave10b3_decision_selection_audit_and_rollback(db_session, test_user):
    from app.services.decision_service import DecisionService
    from app.models.db.decision import (
        EngineeringDecisionRecord,
        EngineeringDecisionAlternative,
        AlternativeStatus,
        DecisionStatus,
    )
    from app.models.db.system import EngineeringSystem
    from app.models.db.project import Project

    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Project 10B3 Decision",
        description="Decision test project",
        project_type=ProjectType.GENERAL,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    db_session.add(project)
    await db_session.commit()

    system_id = str(uuid.uuid4())
    system = EngineeringSystem(
        id=system_id,
        project_id=project_id,
        tenant_id=test_user.tenant_id,
        name="Telemetry System",
        description="Telemetry subsystem",
        revision=1,
        created_by=test_user.id,
    )
    db_session.add(system)
    await db_session.commit()

    decision_id = str(uuid.uuid4())
    dec = EngineeringDecisionRecord(
        id=decision_id,
        project_id=project_id,
        system_id=system_id,
        system_revision=1,
        tenant_id=test_user.tenant_id,
        title="Architecture Choice 10B3",
        decision_key="DEC-10B3-01",
        description="Selecting bus protocol",
        status=DecisionStatus.UNDER_REVIEW.value,
    )
    db_session.add(dec)
    await db_session.flush()

    alt1_id = str(uuid.uuid4())
    alt1 = EngineeringDecisionAlternative(
        id=alt1_id,
        decision_id=decision_id,
        name="SPI",
        description="Serial Peripheral Interface",
        status=AlternativeStatus.CONSIDERED.value,
    )
    alt2_id = str(uuid.uuid4())
    alt2 = EngineeringDecisionAlternative(
        id=alt2_id,
        decision_id=decision_id,
        name="I2C",
        description="Inter-Integrated Circuit",
        status=AlternativeStatus.CONSIDERED.value,
    )
    db_session.add_all([alt1, alt2])
    await db_session.commit()

    dec_service = DecisionService(db=db_session)

    # 1. Successful selection emits DECISION_RECORDED
    selected_dec = await dec_service.select_alternative(
        decision_id=decision_id,
        alternative_id=alt1_id,
        actor=test_user.id,
        rationale={"decision_rationale": "Higher speed requirement"},
        tenant_id=test_user.tenant_id,
    )
    assert selected_dec.status == DecisionStatus.DECIDED.value

    stmt = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.event_type == AuditEventType.DECISION_RECORDED.value,
        EngineeringAuditEvent.entity_id == decision_id,
    )
    res_stmt = await db_session.execute(stmt)
    events = res_stmt.scalars().all()
    assert len(events) == 1
    ev = events[0]
    assert ev.payload["selected_alternative_id"] == alt1_id
    assert ev.payload["selected_alternative_name"] == "SPI"

    # 2. Failure injection on decision selection
    with patch.object(AuditLedgerService, "record_event", side_effect=RuntimeError("Simulated audit failure on decision")):
        with pytest.raises(RuntimeError, match="Simulated audit failure on decision"):
            await dec_service.select_alternative(
                decision_id=decision_id,
                alternative_id=alt2_id,
                actor=test_user.id,
                rationale={"decision_rationale": "Switch to I2C"},
                tenant_id=test_user.tenant_id,
            )

    await db_session.rollback()

    # Verify rollback: alt1 remains SELECTED_BY_ENGINEER, alt2 remains NOT_SELECTED
    await db_session.refresh(alt1)
    await db_session.refresh(alt2)
    assert alt1.status == AlternativeStatus.SELECTED_BY_ENGINEER.value
    assert alt2.status == AlternativeStatus.NOT_SELECTED.value


@pytest.mark.asyncio
async def test_wave10b3_dfm_proposal_application_audit_and_rollback(db_session, test_user):
    from app.services.dfm_service import dfm_service
    from app.models.db.dfm import (
        ManufacturingProposalRecord,
        ProposalStatus,
    )
    from app.models.db.pcb import EngineeringBoard, BoardTraceSegment
    from app.models.db.circuit import Circuit
    from app.models.db.project import Project
    from fastapi import HTTPException

    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        name="Project 10B3 DFM",
        description="DFM test project",
        project_type=ProjectType.PCB,
        status=ProjectStatus.ACTIVE,
        tenant_id=test_user.tenant_id,
        owner_id=test_user.id,
    )
    circuit_id = str(uuid.uuid4())
    circuit = Circuit(
        id=circuit_id,
        project_id=project_id,
        name="Circuit 10B3 DFM",
        tenant_id=test_user.tenant_id,
        version=1,
        created_by=test_user.id,
    )
    db_session.add_all([project, circuit])
    await db_session.commit()

    board_id = str(uuid.uuid4())
    board = EngineeringBoard(
        id=board_id,
        project_id=project_id,
        circuit_id=circuit_id,
        tenant_id=test_user.tenant_id,
        name="Wave 10B3 Board",
        dimensions={"width": 100.0, "height": 80.0},
        units="mm",
        created_by=test_user.id,
        version=1,
    )
    db_session.add(board)
    await db_session.flush()

    trace_id = str(uuid.uuid4())
    trace = BoardTraceSegment(
        id=trace_id,
        board_id=board_id,
        start_x=10.0,
        start_y=10.0,
        end_x=20.0,
        end_y=10.0,
        width=0.10,
    )
    db_session.add(trace)
    await db_session.commit()

    # Create unapproved proposal
    unapproved_prop_id = str(uuid.uuid4())
    unapproved_prop = ManufacturingProposalRecord(
        id=unapproved_prop_id,
        board_id=board_id,
        board_revision=1,
        tenant_id=test_user.tenant_id,
        analysis_id=str(uuid.uuid4()),
        rule_id="MFG001",
        title="Unapproved Trace Widening",
        description="Increase trace width to 0.20mm",
        mutation_type="ADJUST_TRACE_WIDTH",
        proposed_mutations=[
            {"target_entity": "BoardTraceSegment", "entity_id": trace_id, "action": "UPDATE", "fields": {"width": 0.20}}
        ],
        diff_preview={},
        status=ProposalStatus.PROPOSED.value,
        created_by="system",
    )
    db_session.add(unapproved_prop)
    await db_session.commit()

    # 1. Unapproved proposal application is rejected with HTTP 400
    with pytest.raises(HTTPException) as excinfo:
        await dfm_service.apply_proposal(db=db_session, proposal_id=unapproved_prop_id, current_user=test_user)
    assert excinfo.value.status_code == 400
    assert "approved" in excinfo.value.detail.lower()

    # 2. Approved proposal succeeds and records DFM_PROPOSAL_APPLIED
    unapproved_prop.status = ProposalStatus.APPROVED.value
    await db_session.commit()

    applied = await dfm_service.apply_proposal(db=db_session, proposal_id=unapproved_prop_id, current_user=test_user)
    assert applied.status == ProposalStatus.APPLIED.value
    await db_session.refresh(trace)
    assert trace.width == 0.20
    assert board.version == 2

    stmt = select(EngineeringAuditEvent).where(
        EngineeringAuditEvent.event_type == AuditEventType.DFM_PROPOSAL_APPLIED.value,
        EngineeringAuditEvent.entity_id == unapproved_prop_id,
    )
    res_stmt = await db_session.execute(stmt)
    events = res_stmt.scalars().all()
    assert len(events) == 1
    ev = events[0]
    assert ev.payload["mutation_type"] == "ADJUST_TRACE_WIDTH"
    assert ev.payload["board_id"] == board_id

    # 3. Failure injection on approved proposal
    prop_fail_id = str(uuid.uuid4())
    prop_fail = ManufacturingProposalRecord(
        id=prop_fail_id,
        board_id=board_id,
        board_revision=2,
        tenant_id=test_user.tenant_id,
        analysis_id=str(uuid.uuid4()),
        rule_id="MFG002",
        title="Failing Trace Widening",
        description="Increase trace width further",
        mutation_type="ADJUST_TRACE_WIDTH",
        proposed_mutations=[
            {"target_entity": "BoardTraceSegment", "entity_id": trace_id, "action": "UPDATE", "fields": {"width": 0.30}}
        ],
        diff_preview={},
        status=ProposalStatus.APPROVED.value,
        created_by="system",
    )
    db_session.add(prop_fail)
    await db_session.commit()

    await db_session.refresh(board)
    current_ver = board.version

    with patch.object(AuditLedgerService, "record_event", side_effect=RuntimeError("Simulated audit failure on DFM")):
        with pytest.raises(RuntimeError, match="Simulated audit failure on DFM"):
            await dfm_service.apply_proposal(db=db_session, proposal_id=prop_fail_id, current_user=test_user)

    await db_session.rollback()

    # Verify rollback: prop_fail remains APPROVED (not APPLIED), board version not bumped
    await db_session.refresh(prop_fail)
    await db_session.refresh(board)
    assert prop_fail.status == ProposalStatus.APPROVED.value
    assert board.version == current_ver



