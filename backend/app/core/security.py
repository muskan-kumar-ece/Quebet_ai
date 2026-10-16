from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generates bcrypt hash of a plain password."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta | None = None,
    claims: dict[str, Any] | None = None,
) -> str:
    """Generates signed JWT access token with optional custom claims."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    if claims:
        to_encode.update(claims)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decodes and validates JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except Exception:
        return None


# In-memory revocation cache for fall-back/testing
_REVOKED_TOKENS_MEM: set[str] = set()


async def is_token_revoked(token: str) -> bool:
    """
    Checks if a token has been explicitly revoked/blacklisted.
    Queries Redis blacklist with an in-memory set fallback.
    """
    if token in _REVOKED_TOKENS_MEM:
        return True

    try:
        from app.core.redis_client import get_redis_client

        redis = await get_redis_client()
        if redis:
            val = await redis.get(f"revoked_token:{token}")
            if val:
                return True
    except Exception:
        pass

    return False


async def revoke_token(token: str, ttl_seconds: int = 3600) -> None:
    """
    Revokes an active JWT token.
    Adds token to Redis with TTL and in-memory fallback cache.
    """
    _REVOKED_TOKENS_MEM.add(token)
    try:
        from app.core.redis_client import get_redis_client

        redis = await get_redis_client()
        if redis:
            await redis.setex(f"revoked_token:{token}", ttl_seconds, "revoked")
    except Exception:
        pass

