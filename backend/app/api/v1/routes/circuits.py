from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.circuit import (
    CircuitDetailResponse,
    CircuitResponse,
    CircuitUpdate,
    ComponentCreate,
    ComponentResponse,
    ConnectionCreate,
    ConnectionResponse,
    NetCreate,
    NetResponse,
    SchematicObjectBatchUpdate,
    SchematicObjectResponse,
)
from app.models.schemas.common import ApiResponse
from app.models.schemas.intent import CircuitIntent, CircuitIntentRequest
from app.models.schemas.proposal import ProposalCreate, ProposalResponse
from app.services.ai.circuit_intent_service import circuit_intent_service
from app.services.ai.validators.base import StageResult
from app.services.circuit_service import circuit_service
from app.services.proposal_service import proposal_service

router = APIRouter(prefix="/circuits", tags=["Circuits & Schematics"])


@router.get("/{circuit_id}", response_model=ApiResponse[CircuitDetailResponse])
async def get_circuit(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full circuit graph including components, nets, connections, and assumptions."""
    circuit = await circuit_service.get_circuit(db=db, circuit_id=circuit_id, current_user=current_user)
    return ApiResponse(success=True, data=circuit)


@router.patch("/{circuit_id}", response_model=ApiResponse[CircuitResponse])
async def update_circuit(
    circuit_id: str,
    update_in: CircuitUpdate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Update circuit name, description, or status."""
    circuit = await circuit_service.update_circuit(
        db=db,
        circuit_id=circuit_id,
        update_in=update_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=circuit)


@router.post("/{circuit_id}/validate", response_model=ApiResponse[StageResult])
async def validate_circuit(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute deterministic Stage 1 structural validation on the circuit.
    Enforces reference designator uniqueness, pin validity, and net integrity.
    """
    result = await circuit_service.validate_circuit(db=db, circuit_id=circuit_id, current_user=current_user)
    return ApiResponse(success=True, data=result)


@router.post("/intent", response_model=ApiResponse[CircuitIntent])
async def interpret_circuit_intent(
    request: CircuitIntentRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """
    AI Circuit Interpretation Boundary.
    Translates natural-language engineering requirements into typed intermediate CircuitIntent.
    Identifies missing parameters and tracks explicit engineering assumptions without mutating the database.
    """
    intent = await circuit_intent_service.interpret_intent(request.prompt)
    return ApiResponse(success=True, data=intent)


@router.post("/{circuit_id}/components", response_model=ApiResponse[ComponentResponse])
async def add_component_to_circuit(
    circuit_id: str,
    comp_in: ComponentCreate,
    pos_x: float = 100.0,
    pos_y: float = 100.0,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a new physical/logical component to the circuit with automatic visual symbol placement."""
    component = await circuit_service.add_component(
        db=db,
        circuit_id=circuit_id,
        comp_in=comp_in,
        current_user=current_user,
        pos_x=pos_x,
        pos_y=pos_y,
    )
    return ApiResponse(success=True, data=component)


@router.post("/{circuit_id}/nets", response_model=ApiResponse[NetResponse])
async def add_net_to_circuit(
    circuit_id: str,
    net_in: NetCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a named electrical net to the circuit."""
    net = await circuit_service.add_net(
        db=db,
        circuit_id=circuit_id,
        net_in=net_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=net)


@router.post("/{circuit_id}/connections", response_model=ApiResponse[ConnectionResponse])
async def add_connection_to_circuit(
    circuit_id: str,
    conn_in: ConnectionCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Add and deterministically validate a component pin-to-net connection.
    Rejects invalid pins, non-existent nets, and duplicate pin mappings.
    """
    connection = await circuit_service.add_connection(
        db=db,
        circuit_id=circuit_id,
        conn_in=conn_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=connection)


@router.post("/{circuit_id}/schematic-objects/batch", response_model=ApiResponse[list[SchematicObjectResponse]])
async def batch_update_schematic_objects(
    circuit_id: str,
    batch_in: SchematicObjectBatchUpdate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Batch update visual layout coordinates and rotations for components and wires during canvas drag/move/save."""
    objects = await circuit_service.batch_update_schematic_objects(
        db=db,
        circuit_id=circuit_id,
        batch_in=batch_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=objects)


@router.post("/{circuit_id}/proposals", response_model=ApiResponse[ProposalResponse])
async def create_engineering_proposal(
    circuit_id: str,
    proposal_in: ProposalCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a staged Engineering Proposal for AI or user suggestions without mutating electrical truth."""
    proposal = await proposal_service.create_proposal(
        db=db,
        circuit_id=circuit_id,
        proposal_in=proposal_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=proposal)


@router.get("/{circuit_id}/proposals", response_model=ApiResponse[list[ProposalResponse]])
async def list_engineering_proposals(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List all staged engineering proposals for this circuit."""
    proposals = await proposal_service.list_proposals(
        db=db,
        circuit_id=circuit_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=proposals)


@router.get("/{circuit_id}/export/json", response_model=ApiResponse[dict])
async def export_circuit_json(
    circuit_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Export normalized engineering circuit schema in JSON format."""
    exported = await circuit_service.export_circuit_json(
        db=db,
        circuit_id=circuit_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=exported)
