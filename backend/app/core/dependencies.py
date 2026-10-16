from collections.abc import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.db.user import User
from app.services.ai.base_provider import BaseProvider
from app.services.ai.provider_factory import get_ai_provider

# Bearer token extractor
security_bearer = HTTPBearer(auto_error=False)


class AuthenticatedUser(BaseModel):
    """
    Immutable representation of an authenticated user identity
    resolved from verified server-side state or cryptographic token claims.
    """

    id: str
    email: str
    plan: str = "free"
    role: str = "user"
    tenant_id: str | None = None
    is_admin: bool = False


async def require_authenticated_user(
    auth: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> AuthenticatedUser:
    """
    Strict authentication dependency.
    Rejects missing or invalid credentials with HTTP 401 Unauthorized.
    Returns typed AuthenticatedUser with trusted plan and role.
    """
    if not auth or not auth.credentials:
        if settings.ALLOW_DEV_MOCK_AUTH:
            return AuthenticatedUser(
                id="00000000-0000-0000-0000-000000000000",
                email="dev@quebet.ai",
                plan="free",
                role="user",
                is_admin=False,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # SEC-06: Check token revocation status
    from app.core.security import is_token_revoked
    if await is_token_revoked(auth.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, malformed, or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = str(payload["sub"])

    # SEC-01: Server-side identity derivation & fail-closed user status check
    # Check if user exists in the authoritative database (including soft-deleted check)
    # Using an isolated session ensures auth lookup is immediately completed and never interferes
    # with the request handler's transaction state across asyncpg connection poolers.
    from app.core.database import AsyncSessionLocal
    user_db = None
    db_lookup_failed = False
    try:
        async with AsyncSessionLocal() as auth_session:
            stmt = select(User).where(User.id == user_id)
            result = await auth_session.execute(stmt)
            user_db = result.scalar_one_or_none()
    except Exception:
        db_lookup_failed = True

    if user_db is not None:
        # User explicitly exists in database: check active status
        if getattr(user_db, "deleted_at", None) is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account deactivated or deleted",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Server-side authoritative fields strictly override token claims
        role = getattr(user_db, "role", "user") or "user"
        plan = user_db.plan or "free"
        email = user_db.email
        tenant_id = user_db.tenant_id
    else:
        # User not found in DB
        if settings.ENVIRONMENT.lower() == "production" and not settings.ALLOW_DEV_MOCK_AUTH:
            if db_lookup_failed:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service temporarily unavailable",
                )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account not found or deactivated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # In non-production testing/development without seeded DB user:
        role = payload.get("role", "user")
        plan = payload.get("plan", "free")
        email = payload.get("email", f"{user_id}@quebet.ai")
        tenant_id = payload.get("tenant_id")

    is_admin = role in ("admin", "system:admin")

    return AuthenticatedUser(
        id=user_id,
        email=email,
        plan=plan,
        role=role,
        tenant_id=tenant_id,
        is_admin=is_admin,
    )



async def get_optional_user(
    auth: HTTPAuthorizationCredentials | None = Depends(security_bearer),
) -> AuthenticatedUser | None:
    """
    Optional authentication dependency for public endpoints that vary behavior
    for authenticated users (e.g. model catalog listing).
    """
    if not auth or not auth.credentials:
        return None

    payload = decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await require_authenticated_user(auth=auth)



async def require_admin_role(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AuthenticatedUser:
    """
    Strict server-side authorization dependency.
    Requires the authenticated identity to hold an admin role.
    Rejects non-admins with HTTP 403 Forbidden.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative privileges required",
        )
    return current_user


async def get_current_user_id(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> str:
    """
    Extracts the authenticated user's ID.
    Enforces authentication.
    """
    return current_user.id


# Non-negotiable human engineering roles authorized to approve and apply engineering mutations
AUTHORIZED_HUMAN_ROLES = {
    "ENGINEER",
    "LEAD_ENGINEER",
    "CHIEF_ENGINEER",
    "ADMIN",
    "SYSTEM_ADMIN",
    "user",
    "admin",
}

DISALLOWED_AI_ROLE_SUBSTRINGS = ("ai", "bot", "copilot", "assistant", "agent", "autonomous")


async def require_human_engineer_role(
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> AuthenticatedUser:
    """
    Strict authorization dependency enforcing human engineering authority.
    Prohibits AI agents, copilots, bots, and unverified roles from approving or applying mutations.
    Invariant: AI ENGINEERING AUTHORITY = NONE, AUTONOMOUS MUTATION = DISABLED.
    """
    role_norm = (current_user.role or "").strip().lower()

    # Reject any role matching AI, bot, copilot, or assistant
    if any(sub in role_norm for sub in DISALLOWED_AI_ROLE_SUBSTRINGS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Engineering mutation authorization denied: AI agents and non-human actors possess no engineering decision authority. (AI ENGINEERING AUTHORITY = NONE)",
        )

    # Must be in authorized human roles
    if role_norm not in {r.lower() for r in AUTHORIZED_HUMAN_ROLES}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Engineering mutation authorization denied: role '{current_user.role}' is not an authorized human engineering role.",
        )

    return current_user


__all__ = [
    "get_db",
    "require_authenticated_user",
    "get_optional_user",
    "require_admin_role",
    "require_human_engineer_role",
    "get_current_user_id",
    "get_ai_provider",
    "AuthenticatedUser",
]

