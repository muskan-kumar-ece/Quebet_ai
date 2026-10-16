from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.circuit import SchematicObjectResponse, SchematicObjectUpdate
from app.models.schemas.common import ApiResponse
from app.services.circuit_service import circuit_service

router = APIRouter(prefix="/schematic-objects", tags=["Schematic Presentation Objects"])


@router.patch("/{object_id}", response_model=ApiResponse[SchematicObjectResponse])
async def update_schematic_object(
    object_id: str,
    update_in: SchematicObjectUpdate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Update graphical coordinates, rotation, or visual styles for a schematic object."""
    updated = await circuit_service.update_schematic_object(
        db=db,
        obj_id=object_id,
        update_in=update_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=updated)
