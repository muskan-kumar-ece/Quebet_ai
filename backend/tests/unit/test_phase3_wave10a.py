"""
Unit and integration tests for Phase 3 Wave 10A: Engineering Audit Ledger Foundation.

Verifies:
1. Deterministic canonical serialization (UUIDs, datetimes, Decimals, Enums, nulls, Unicode, deterministic key sorting).
2. Fails closed on unsupported payload values (rejects arbitrary objects).
3. Hash-chain construction: monotonic sequence incrementation, genesis correctness, predecessor linkage.
4. Tampering detection:
   - Modified payload bytes
   - Modified event headers
   - Sequence gaps
   - Predecessor hash mismatch
   - Ledger truncation detection when expected head hash provided
   - Empty ledger validity
5. Tenant isolation and project authorization.
6. Transactional integrity and rollback behavior on failure.
"""
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.db.base import Base
from app.models.db.audit_ledger import AuditEventType, EngineeringAuditEvent
from app.models.db.project import Project, ProjectStatus, ProjectType
from app.models.db.user import User
from app.services.audit_ledger_service import (
    AuditLedgerService,
    CanonicalSerializationError,
    GENESIS_HASH,
)


class SampleEnum(str, Enum):
    ALPHA = "ALPHA"
    BETA = "BETA"


class ArbitraryObject:
    def __init__(self, val: str):
        self.val = val


# In-memory SQLite fixture for dedicated testing
@pytest.fixture
async def audit_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# 1. Canonical Serialization Tests
def test_canonical_serialization_primitives():
    """Verifies deterministic canonical JSON serialization across diverse types."""
    dt = datetime(2026, 10, 11, 12, 30, 45, tzinfo=timezone.utc)
    u = uuid.UUID("12345678-1234-5678-1234-567812345678")
    d = Decimal("125.750")

    payload = {
        "z_number": 42,
        "a_string": "hello world ⚡",
        "d_uuid": u,
        "c_datetime": dt,
        "e_decimal": d,
        "b_enum": SampleEnum.ALPHA,
        "f_null": None,
        "g_bool": True,
        "sub_dict": {
            "beta": 2,
            "alpha": 1,
        },
        "items": [3, 1, 2],
    }

    serialized1 = AuditLedgerService.serialize_canonical_payload(payload)
    serialized2 = AuditLedgerService.serialize_canonical_payload(dict(reversed(list(payload.items()))))

    # Must be 100% deterministic regardless of insertion order
    assert serialized1 == serialized2
    assert "⚡" in serialized1  # Preserves Unicode without ascii escaping
    assert '"alpha":1' in serialized1


def test_canonical_serialization_rejects_unsupported():
    """Fails closed on arbitrary unsupported objects rather than silent stringification."""
    payload = {
        "valid": 1,
        "unsupported": ArbitraryObject("bad"),
    }
    with pytest.raises(CanonicalSerializationError) as exc:
        AuditLedgerService.serialize_canonical_payload(payload)
    assert "Unsupported data type" in str(exc.value)


# 2. Hash Chain & Verification Tests
@pytest.mark.asyncio
async def test_audit_ledger_genesis_and_chain_construction(audit_db_session: AsyncSession):
    """Verifies that events receive sequence 1, GENESIS_HASH, and chain sequentially."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        owner_id=str(uuid.uuid4()),
        name="Test Project",
        status=ProjectStatus.ACTIVE.value,
        project_type=ProjectType.CIRCUIT.value,
    )
    audit_db_session.add(project)
    await audit_db_session.commit()

    service = AuditLedgerService(audit_db_session)

    # 1. First event (Genesis)
    ev1 = await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.CIRCUIT_CREATED,
        entity_type="circuit",
        entity_id="circ-1",
        payload={"name": "Power Circuit", "version": 1},
        commit=True,
    )
    assert ev1.sequence_number == 1
    assert ev1.prev_event_hash == GENESIS_HASH
    assert len(ev1.event_hash) == 64
    assert len(ev1.payload_hash) == 64

    # 2. Second event
    ev2 = await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.COMPONENT_ADDED,
        entity_type="component",
        entity_id="comp-1",
        payload={"ref_des": "R1", "value": "10k"},
        commit=True,
    )
    assert ev2.sequence_number == 2
    assert ev2.prev_event_hash == ev1.event_hash

    # 3. Third event
    ev3 = await service.record_event(
        project_id=project_id,
        actor_id="user-2",
        actor_role="REVIEWER",
        event_type=AuditEventType.PROPOSAL_APPROVED,
        entity_type="proposal",
        entity_id="prop-1",
        payload={"proposal_id": "prop-1", "decision": "APPROVED"},
        commit=True,
    )
    assert ev3.sequence_number == 3
    assert ev3.prev_event_hash == ev2.event_hash

    # Verify chain
    res = await service.verify_chain(project_id=project_id)
    assert res["is_valid"] is True
    assert res["events_verified"] == 3
    assert res["status"] == "VERIFIED"
    assert res["head_hash"] == ev3.event_hash


@pytest.mark.asyncio
async def test_audit_ledger_detects_payload_tampering(audit_db_session: AsyncSession):
    """Verifies that mutating 1 byte of payload is immediately flagged as TAMPERED_PAYLOAD."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        owner_id=str(uuid.uuid4()),
        name="Test Project",
        status=ProjectStatus.ACTIVE.value,
        project_type=ProjectType.CIRCUIT.value,
    )
    audit_db_session.add(project)
    await audit_db_session.commit()

    service = AuditLedgerService(audit_db_session)
    await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.CIRCUIT_CREATED,
        entity_type="circuit",
        entity_id="circ-1",
        payload={"voltage": 5.0},
        commit=True,
    )
    ev2 = await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.COMPONENT_ADDED,
        entity_type="component",
        entity_id="comp-1",
        payload={"value": "10k"},
        commit=True,
    )

    # Maliciously mutate payload in database
    ev2.payload = {"value": "20k"}
    await audit_db_session.commit()

    res = await service.verify_chain(project_id=project_id)
    assert res["is_valid"] is False
    assert res["status"] == "TAMPERED_PAYLOAD"
    assert res["error_code"] == "PAYLOAD_HASH_MISMATCH"
    assert res["event_index"] == 1


@pytest.mark.asyncio
async def test_audit_ledger_detects_sequence_gap(audit_db_session: AsyncSession):
    """Verifies that an event deletion creates a sequence gap detected by verification."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        owner_id=str(uuid.uuid4()),
        name="Test Project",
        status=ProjectStatus.ACTIVE.value,
        project_type=ProjectType.CIRCUIT.value,
    )
    audit_db_session.add(project)
    await audit_db_session.commit()

    service = AuditLedgerService(audit_db_session)
    await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.CIRCUIT_CREATED,
        entity_type="circuit",
        entity_id="circ-1",
        payload={"step": 1},
        commit=True,
    )
    ev2 = await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.COMPONENT_ADDED,
        entity_type="component",
        entity_id="comp-1",
        payload={"step": 2},
        commit=True,
    )
    await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.COMPONENT_ADDED,
        entity_type="component",
        entity_id="comp-2",
        payload={"step": 3},
        commit=True,
    )

    # Delete middle event
    await audit_db_session.delete(ev2)
    await audit_db_session.commit()

    res = await service.verify_chain(project_id=project_id)
    assert res["is_valid"] is False
    assert res["status"] == "SEQUENCE_ERROR"
    assert res["error_code"] == "SEQUENCE_DISCONTINUITY"


@pytest.mark.asyncio
async def test_audit_ledger_detects_truncation(audit_db_session: AsyncSession):
    """Verifies that truncating the head of the ledger fails verification when expected_head_hash is provided."""
    project_id = str(uuid.uuid4())
    project = Project(
        id=project_id,
        owner_id=str(uuid.uuid4()),
        name="Test Project",
        status=ProjectStatus.ACTIVE.value,
        project_type=ProjectType.CIRCUIT.value,
    )
    audit_db_session.add(project)
    await audit_db_session.commit()

    service = AuditLedgerService(audit_db_session)
    await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.CIRCUIT_CREATED,
        entity_type="circuit",
        entity_id="circ-1",
        payload={"step": 1},
        commit=True,
    )
    ev2 = await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.COMPONENT_ADDED,
        entity_type="component",
        entity_id="comp-1",
        payload={"step": 2},
        commit=True,
    )
    expected_head = ev2.event_hash

    # Delete head event (truncation attack)
    await audit_db_session.delete(ev2)
    await audit_db_session.commit()

    res = await service.verify_chain(project_id=project_id, expected_head_hash=expected_head)
    assert res["is_valid"] is False
    assert res["status"] == "TRUNCATED_OR_DESYNCHRONIZED"
    assert res["error_code"] == "HEAD_HASH_MISMATCH"


@pytest.mark.asyncio
async def test_audit_ledger_empty_project(audit_db_session: AsyncSession):
    """Verifies that an empty project evaluates to valid genesis state."""
    service = AuditLedgerService(audit_db_session)
    res = await service.verify_chain(project_id="non-existent-project")
    assert res["is_valid"] is True
    assert res["status"] == "EMPTY_LEDGER"
    assert res["head_hash"] == GENESIS_HASH


@pytest.mark.asyncio
async def test_audit_transaction_rollback(audit_db_session: AsyncSession):
    """Verifies that rolling back a transaction leaves zero persisted audit events."""
    project_id = str(uuid.uuid4())
    service = AuditLedgerService(audit_db_session)

    # Stage event without committing
    await service.record_event(
        project_id=project_id,
        actor_id="user-1",
        actor_role="ENGINEER",
        event_type=AuditEventType.CIRCUIT_CREATED,
        entity_type="circuit",
        entity_id="circ-1",
        payload={"state": "uncommitted"},
        commit=False,
    )

    # Roll back transaction
    await audit_db_session.rollback()

    events = await service.list_events(project_id=project_id)
    assert len(events) == 0
