from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.circuit import CircuitCreate, CircuitDetailResponse, CircuitResponse
from app.models.schemas.common import ApiResponse
from app.models.schemas.project import ProjectCreate, ProjectListResponse, ProjectResponse, ProjectUpdate
from app.services.circuit_service import circuit_service
from app.services.project_service import project_service

router = APIRouter(prefix="/projects", tags=["Engineering Projects"])


@router.post("", response_model=ApiResponse[ProjectResponse], status_code=status.HTTP_201_CREATED)
async def create_project(
    project_in: ProjectCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new engineering project workspace."""
    project = await project_service.create_project(db=db, project_in=project_in, current_user=current_user)
    return ApiResponse(success=True, data=project)


@router.get("", response_model=ApiResponse[ProjectListResponse])
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List projects accessible within user's tenant or personal workspace."""
    result = await project_service.list_projects(
        db=db,
        current_user=current_user,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(success=True, data=result)


@router.get("/{project_id}", response_model=ApiResponse[ProjectResponse])
async def get_project(
    project_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details for a specific engineering project."""
    project = await project_service.get_project(db=db, project_id=project_id, current_user=current_user)
    return ApiResponse(success=True, data=project)


@router.patch("/{project_id}", response_model=ApiResponse[ProjectResponse])
async def update_project(
    project_id: str,
    update_in: ProjectUpdate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Update project metadata, status, or type."""
    project = await project_service.update_project(
        db=db,
        project_id=project_id,
        update_in=update_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=project)


@router.delete("/{project_id}", response_model=ApiResponse[dict[str, bool]])
async def delete_project(
    project_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete an engineering project."""
    await project_service.delete_project(db=db, project_id=project_id, current_user=current_user)
    return ApiResponse(success=True, data={"deleted": True})


# Nested Circuit Endpoints under Projects
@router.post(
    "/{project_id}/circuits",
    response_model=ApiResponse[CircuitDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_circuit_in_project(
    project_id: str,
    circuit_in: CircuitCreate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a structured electrical circuit inside a project."""
    circuit = await circuit_service.create_circuit(
        db=db,
        project_id=project_id,
        circuit_in=circuit_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=circuit)


@router.get("/{project_id}/circuits", response_model=ApiResponse[list[CircuitResponse]])
async def list_circuits_in_project(
    project_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """List all circuits belonging to an engineering project."""
    circuits = await circuit_service.list_circuits_for_project(
        db=db,
        project_id=project_id,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=circuits)
