import uuid
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException
from httpx import AsyncClient

from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import AuthenticatedUser
from app.core.security import create_access_token

@pytest.fixture(autouse=True)
async def cleanup_db():
    yield
    await engine.dispose()

from app.models.db.circuit import Circuit
from app.models.db.component import Component
from app.models.db.net import Net
from app.models.db.project import Project, ProjectType, ProjectStatus
from app.models.db.system import EngineeringSystem
from app.models.db.user import User
from app.models.db.bom import EngineeringBOM
from app.models.db.pcb import EngineeringBoard, BoardStatus
from app.models.db.simulation import SimulationJob, SimulationStatus
from app.models.db.analysis import CircuitAnalysis
from app.models.db.verification import EngineeringDesignReview, DesignReviewStatus
from app.models.db.cognitive import EngineeringDecisionBrief, DecisionBriefStatus
from app.models.db.decision import EngineeringDecisionRecord
from app.models.schemas.circuit import (
    CircuitCreate,
    CircuitUpdate,
    ComponentCreate,
    ComponentUpdate,
    NetCreate,
    NetUpdate,
)
from app.models.schemas.cognitive import HumanDecisionRecordRequest
from app.services.circuit_service import circuit_service
from app.services.project_service import project_service
from app.services.bom_service import BOMService
from app.services.pcb_service import PCBService
from app.services.simulation_service import simulation_service
from app.services.analysis_service import analysis_service
from app.services.verification_service import verification_service
from app.services.ai.cognitive.decision.decision_brief_service import EngineeringDecisionBriefService


# ==============================================================================
# SEC-02: Tenant Isolation & Personal Resource Scoping Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_read_tenant_circuit():
    """
    An untenanted user (personal workspace, tenant_id=None) must NOT be permitted
    to read circuits owned by an Enterprise Tenant via IDOR. Must fail closed (HTTP 404).
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())  # untenanted user

    async with AsyncSessionLocal() as session:
        # Seed Tenant Alpha project & circuit
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha Power Supply",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Alpha PSU Board",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.commit()
        circuit_id = circuit.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.get_circuit(
                db=session,
                circuit_id=circuit_id,
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_mutate_tenant_circuit():
    """
    An untenanted user must NOT be permitted to mutate or update circuit properties
    belonging to another tenant.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha Telemetry",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Alpha Telemetry RF",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.commit()
        circuit_id = circuit.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.update_circuit(
                db=session,
                circuit_id=circuit_id,
                update_in=CircuitUpdate(name="Tampered Name"),
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_mutate_tenant_components():
    """
    An untenanted user cannot add, update, or delete physical components on a tenant circuit.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha Components Test",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Alpha Schematic",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.flush()

        comp = Component(
            id=str(uuid.uuid4()),
            circuit_id=circuit.id,
            ref_des="R1",
            component_type="resistor",
            value="10k",
        )
        session.add(comp)
        await session.commit()
        circuit_id = circuit.id
        comp_id = comp.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        # Attempt to add component: must fail 404
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.add_component(
                db=session,
                circuit_id=circuit_id,
                comp_in=ComponentCreate(ref_des="R2", component_type="resistor", value="20k"),
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404

        # Attempt to update component: must fail 404
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.update_component(
                db=session,
                component_id=comp_id,
                update_in=ComponentUpdate(value="100k"),
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404

        # Attempt to delete component: must fail 404
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.delete_component(
                db=session,
                component_id=comp_id,
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_mutate_tenant_nets():
    """
    An untenanted user cannot add, update, or delete electrical nets on a tenant circuit.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha Nets Test",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Alpha Nets Schematic",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.flush()

        net = Net(
            id=str(uuid.uuid4()),
            circuit_id=circuit.id,
            name="VCC_3V3",
            net_type="power",
        )
        session.add(net)
        await session.commit()
        circuit_id = circuit.id
        net_id = net.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        # Attempt to add net
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.add_net(
                db=session,
                circuit_id=circuit_id,
                net_in=NetCreate(name="GND", net_type="ground"),
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404

        # Attempt to update net
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.update_net(
                db=session,
                net_id=net_id,
                update_in=NetUpdate(name="VCC_5V"),
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404

        # Attempt to delete net
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.delete_net(
                db=session,
                net_id=net_id,
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_cross_tenant_isolation_between_tenants():
    """
    User in Tenant Beta cannot access circuits owned by Tenant Alpha.
    """
    tenant_alpha = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    tenant_beta = f"tenant-beta-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_beta_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_alpha,
            owner_id=user_alpha_id,
            name="Alpha Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_alpha,
            name="Alpha Core Circuit",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.commit()
        circuit_id = circuit.id

    tenant_beta_user = AuthenticatedUser(
        id=user_beta_id,
        email="beta@enterprise.com",
        role="ENGINEER",
        plan="enterprise",
        tenant_id=tenant_beta,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.get_circuit(
                db=session,
                circuit_id=circuit_id,
                current_user=tenant_beta_user,
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_personal_circuits_isolated_between_untenanted_users():
    """
    Two untentanted users (Charlie and Dave) each have personal circuits.
    Dave cannot access Charlie's personal circuit.
    """
    user_charlie_id = str(uuid.uuid4())
    user_dave_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        # Charlie creates personal project and circuit
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=None,
            owner_id=user_charlie_id,
            name="Charlie Personal Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=None,
            name="Charlie Personal Circuit",
            created_by=user_charlie_id,
        )
        session.add(circuit)
        await session.commit()
        charlie_circuit_id = circuit.id

    dave_user = AuthenticatedUser(
        id=user_dave_id,
        email="dave@personal.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await circuit_service.get_circuit(
                db=session,
                circuit_id=charlie_circuit_id,
                current_user=dave_user,
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_user_can_access_own_personal_circuit():
    """
    An untenanted user can successfully create, read, and update their own personal circuit.
    """
    user_charlie_id = str(uuid.uuid4())

    charlie_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@personal.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=None,
            owner_id=user_charlie_id,
            name="Charlie Workspace",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.commit()
        project_id = project.id

    async with AsyncSessionLocal() as session:
        # Charlie creates circuit
        circuit_res = await circuit_service.create_circuit(
            db=session,
            project_id=project_id,
            circuit_in=CircuitCreate(name="Charlie Audio Filter"),
            current_user=charlie_user,
        )
        circuit_id = circuit_res.id

    async with AsyncSessionLocal() as session:
        # Charlie retrieves circuit
        retrieved = await circuit_service.get_circuit(
            db=session,
            circuit_id=circuit_id,
            current_user=charlie_user,
        )
        assert retrieved.id == circuit_id
        assert retrieved.name == "Charlie Audio Filter"

        # Charlie updates circuit
        updated = await circuit_service.update_circuit(
            db=session,
            circuit_id=circuit_id,
            update_in=CircuitUpdate(name="Charlie Audio Filter v2"),
            current_user=charlie_user,
        )
        assert updated.name == "Charlie Audio Filter v2"


@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_access_tenant_bom():
    """
    An untenanted user cannot query BOMs belonging to an Enterprise Tenant by BOM ID
    or Circuit ID. Must fail with HTTP 404.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha BOM Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Alpha BOM Circuit",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.flush()

        bom = EngineeringBOM(
            id=str(uuid.uuid4()),
            project_id=project.id,
            circuit_id=circuit.id,
            circuit_version=1,
            tenant_id=tenant_id,
            name="Alpha BOM",
            created_by=user_alpha_id,
        )
        session.add(bom)
        await session.commit()
        bom_id = bom.id
        circuit_id = circuit.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    bom_svc = BOMService()
    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await bom_svc.get_bom(db=session, bom_id=bom_id, current_user=untenanted_user)
        assert exc_info.value.status_code == 404

        with pytest.raises(HTTPException) as exc_info:
            await bom_svc.get_bom_by_circuit(db=session, circuit_id=circuit_id, current_user=untenanted_user)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_access_tenant_pcb_board():
    """
    An untenanted user cannot query PCB boards belonging to an Enterprise Tenant.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha PCB Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Alpha PCB Circuit",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.flush()

        board = EngineeringBoard(
            id=str(uuid.uuid4()),
            project_id=project.id,
            circuit_id=circuit.id,
            circuit_version=1,
            tenant_id=tenant_id,
            name="Alpha 4-Layer Board",
            status=BoardStatus.DRAFT.value,
            dimensions={"width_mm": 100.0, "height_mm": 80.0},
            units="mm",
            created_by=user_alpha_id,
        )
        session.add(board)
        await session.commit()
        board_id = board.id
        circuit_id = circuit.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    pcb_svc = PCBService()
    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await pcb_svc.get_board(db=session, board_id=board_id, current_user=untenanted_user)
        assert exc_info.value.status_code == 404

        with pytest.raises(HTTPException) as exc_info:
            await pcb_svc.list_boards(db=session, circuit_id=circuit_id, current_user=untenanted_user)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_access_tenant_simulation():
    """
    An untenanted user cannot query simulation jobs or results belonging to an Enterprise Tenant.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha Sim Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Alpha Sim Circuit",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.flush()

        job = SimulationJob(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project.id,
            circuit_id=circuit.id,
            circuit_version=1,
            simulation_type="TRANSIENT",
            status=SimulationStatus.COMPLETED.value,
            simulator="NGSPICE",
            simulator_version="40",
            created_by=user_alpha_id,
        )
        session.add(job)
        await session.commit()
        job_id = job.id
        circuit_id = circuit.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await simulation_service.get_simulation_job(db=session, simulation_id=job_id, current_user=untenanted_user)
        assert exc_info.value.status_code == 404

        with pytest.raises(HTTPException) as exc_info:
            await simulation_service.list_simulations(db=session, circuit_id=circuit_id, current_user=untenanted_user)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_access_tenant_analysis():
    """
    An untenanted user cannot query analytical calculation snapshots belonging to an Enterprise Tenant.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha Analysis Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Alpha Analysis Circuit",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.flush()

        analysis = CircuitAnalysis(
            id=str(uuid.uuid4()),
            circuit_id=circuit.id,
            circuit_version=1,
            tenant_id=tenant_id,
            created_by=user_alpha_id,
            status="COMPLETE",
            confidence="HIGH",
        )
        session.add(analysis)
        await session.commit()
        analysis_id = analysis.id
        circuit_id = circuit.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await analysis_service.get_analysis_by_id(
                db=session,
                circuit_id=circuit_id,
                analysis_id=analysis_id,
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_access_tenant_project():
    """
    An untenanted user cannot query or mutate parent projects belonging to an Enterprise Tenant.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha Confidential Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.commit()
        project_id = project.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await project_service.get_project(
                db=session,
                project_id=project_id,
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_sec02_untenanted_user_cannot_access_tenant_design_review():
    """
    An untenanted user cannot inspect engineering design review sessions belonging to an Enterprise Tenant.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    user_charlie_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Alpha Review Project",
            project_type=ProjectType.CIRCUIT.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        circuit = Circuit(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Alpha Review Circuit",
            created_by=user_alpha_id,
        )
        session.add(circuit)
        await session.flush()

        review = EngineeringDesignReview(
            id=str(uuid.uuid4()),
            project_id=project.id,
            circuit_id=circuit.id,
            circuit_revision=1,
            analysis_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            created_by=user_alpha_id,
            status=DesignReviewStatus.REVIEW_IN_PROGRESS.value,
        )
        session.add(review)
        await session.commit()

        review_id = review.id

    untenanted_user = AuthenticatedUser(
        id=user_charlie_id,
        email="charlie@untenanted.io",
        role="ENGINEER",
        plan="free",
        tenant_id=None,
    )

    async with AsyncSessionLocal() as session:
        with pytest.raises(HTTPException) as exc_info:
            await verification_service._verify_review_access(
                db=session,
                review_id=review_id,
                current_user=untenanted_user,
            )
        assert exc_info.value.status_code == 404


# ==============================================================================
# SEC-07: Engineering Decision Relational Integrity & system_id Foreign Key Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_sec07_decision_brief_without_system_resolves_or_creates_system_preserving_fk():
    """
    When an EngineeringDecisionBrief has system_id=None, recording a human decision
    must auto-resolve or initialize a valid EngineeringSystem row, ensuring that
    EngineeringDecisionRecord.system_id points to engineering_systems.id (NOT projects.id).
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Project Without System",
            project_type=ProjectType.GENERAL.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        # Create brief with system_id = None
        brief = EngineeringDecisionBrief(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project.id,
            system_id=None,
            base_revision=1,
            question="Which buck topology should be selected for high efficiency?",
            alternative_ids=["ALT-A", "ALT-B"],
            alternatives_data=[{"id": "ALT-A", "name": "Sync Buck"}, {"id": "ALT-B", "name": "Async Buck"}],
            human_decision_required=True,
            status=DecisionBriefStatus.READY_FOR_REVIEW.value,
        )
        session.add(brief)
        await session.commit()
        brief_id = brief.id
        project_id = project.id

    async with AsyncSessionLocal() as session:
        brief_svc = EngineeringDecisionBriefService(session)
        record = await brief_svc.record_human_decision(
            brief_id=brief_id,
            payload=HumanDecisionRecordRequest(
                decision_type="ACCEPT_ALTERNATIVE",
                selected_alternative_id="ALT-A",
                rationale="Synchronous buck topology yields >95% efficiency under thermal constraints.",
                notes="Verified against component loss calculations.",
            ),
            tenant_id=tenant_id,
            actor=user_alpha_id,
        )

        decision = record["decision"]
        # Invariant checks:
        # 1. system_id MUST NOT be project_id (which caused PostgreSQL FK violation)
        assert decision.system_id != project_id
        # 2. system_id must reference a valid EngineeringSystem row
        sys_res = await session.get(EngineeringSystem, decision.system_id)
        assert sys_res is not None
        assert sys_res.project_id == project_id
        assert sys_res.tenant_id == tenant_id

        # 3. Decision record is persisted and ratified
        assert decision.status == "RATIFIED"
        assert decision.selected_alternative_id == "ALT-A"


@pytest.mark.asyncio
async def test_sec07_decision_brief_with_existing_system_preserves_fk():
    """
    When an EngineeringDecisionBrief has a valid system_id, recording a human decision
    preserves that exact system_id in EngineeringDecisionRecord.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Project With System",
            project_type=ProjectType.GENERAL.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        system = EngineeringSystem(
            id=str(uuid.uuid4()),
            project_id=project.id,
            tenant_id=tenant_id,
            name="Power Subsystem Root",
            revision=1,
            created_by=user_alpha_id,
        )
        session.add(system)
        await session.flush()

        brief = EngineeringDecisionBrief(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project.id,
            system_id=system.id,
            base_revision=1,
            question="Select isolation barrier rating.",
            alternative_ids=["ALT-1"],
            alternatives_data=[{"id": "ALT-1", "name": "3kV Reinforced"}],
            human_decision_required=True,
            status=DecisionBriefStatus.READY_FOR_REVIEW.value,
        )
        session.add(brief)
        await session.commit()
        brief_id = brief.id
        system_id = system.id

    async with AsyncSessionLocal() as session:
        brief_svc = EngineeringDecisionBriefService(session)
        record = await brief_svc.record_human_decision(
            brief_id=brief_id,
            payload=HumanDecisionRecordRequest(
                decision_type="ACCEPT_ALTERNATIVE",
                selected_alternative_id="ALT-1",
                rationale="Reinforced 3kV barrier complies with IEC 60601-1 2xMOPP.",
            ),
            tenant_id=tenant_id,
            actor=user_alpha_id,
        )

        decision = record["decision"]
        assert decision.system_id == system_id
        sys_res = await session.get(EngineeringSystem, decision.system_id)
        assert sys_res is not None



@pytest.mark.asyncio
async def test_sec07_decision_brief_with_invalid_system_id_rejected():
    """
    If a brief carries a fabricated or non-existent system_id, ratifying a decision
    must fail closed with HTTP 400 Bad Request before attempting to insert an invalid FK.
    """
    tenant_id = f"tenant-alpha-{uuid.uuid4().hex[:6]}"
    user_alpha_id = str(uuid.uuid4())
    fake_system_id = str(uuid.uuid4())

    async with AsyncSessionLocal() as session:
        project = Project(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            owner_id=user_alpha_id,
            name="Project With Fake System",
            project_type=ProjectType.GENERAL.value,
            status=ProjectStatus.ACTIVE.value,
        )
        session.add(project)
        await session.flush()

        brief = EngineeringDecisionBrief(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            project_id=project.id,
            system_id=fake_system_id,
            base_revision=1,
            question="Fabricated system question.",
            alternative_ids=["ALT-X"],
            alternatives_data=[{"id": "ALT-X", "name": "Option X"}],
            human_decision_required=True,
            status=DecisionBriefStatus.READY_FOR_REVIEW.value,
        )
        session.add(brief)
        await session.commit()
        brief_id = brief.id

    async with AsyncSessionLocal() as session:
        brief_svc = EngineeringDecisionBriefService(session)
        with pytest.raises(HTTPException) as exc_info:
            await brief_svc.record_human_decision(
                brief_id=brief_id,
                payload=HumanDecisionRecordRequest(
                    decision_type="ACCEPT_ALTERNATIVE",
                    selected_alternative_id="ALT-X",
                    rationale="Attempting to record with non-existent system.",
                ),
                tenant_id=tenant_id,
                actor=user_alpha_id,
            )
        assert exc_info.value.status_code == 400
        assert "does not exist" in str(exc_info.value.detail)
