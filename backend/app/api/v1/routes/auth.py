from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from app.core.dependencies import AuthenticatedUser, require_authenticated_user, security_bearer
from app.core.security import revoke_token
from app.models.schemas.common import ApiResponse

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


@router.post("/logout", response_model=ApiResponse[dict[str, str]])
async def logout(
    auth: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """
    Explicitly revoke caller's current JWT session token (SEC-06).
    The token will be added to the revocation blacklist and will no longer be accepted.
    """
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token required for logout",
        )

    await revoke_token(auth.credentials)
    return ApiResponse(
        success=True,
        data={"message": "Successfully logged out. Token revoked."},
    )
