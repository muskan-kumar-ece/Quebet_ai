from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.models.schemas.circuit import NetResponse, NetUpdate
from app.models.schemas.common import ApiResponse
from app.services.circuit_service import circuit_service

router = APIRouter(prefix="/nets", tags=["Electrical Nets"])


@router.patch("/{net_id}", response_model=ApiResponse[NetResponse])
async def update_net(
    net_id: str,
    update_in: NetUpdate,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Update net name or classification (power, ground, signal, clock)."""
    updated = await circuit_service.update_net(
        db=db,
        net_id=net_id,
        update_in=update_in,
        current_user=current_user,
    )
    return ApiResponse(success=True, data=updated)


@router.delete("/{net_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_net(
    net_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an electrical net and cascade deletion to its associated connections."""
    await circuit_service.delete_net(
        db=db,
        net_id=net_id,
        current_user=current_user,
    )
    return None
