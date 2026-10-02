from collections.abc import AsyncGenerator
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.security import decode_access_token
from app.services.ai.base_provider import BaseProvider
from app.services.ai.provider_factory import get_ai_provider

# Bearer token extractor
security_bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    auth: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
) -> str:
    """
    Extracts user_id from JWT token or X-User-Id header injected by BFF proxy.
    """
    if auth and auth.credentials:
        payload = decode_access_token(auth.credentials)
        if payload and "sub" in payload:
            return payload["sub"]

    if x_user_id:
        return x_user_id

    # For dev / unauthenticated requests, return default free user ID
    return "00000000-0000-0000-0000-000000000000"


__all__ = ["get_db", "get_current_user_id", "get_ai_provider"]
