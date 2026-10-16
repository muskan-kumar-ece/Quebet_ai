from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import AuthenticatedUser, require_authenticated_user
from app.services.circuit_service import circuit_service

router = APIRouter(prefix="/connections", tags=["Circuit Connections"])


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    connection_id: str,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an electrical connection between a component pin and a net."""
    await circuit_service.delete_connection(
        db=db,
        connection_id=connection_id,
        current_user=current_user,
    )
    return None
