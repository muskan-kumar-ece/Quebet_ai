import logging
from redis import asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis global client handle
_redis_client: aioredis.Redis | None = None


async def get_redis_client() -> aioredis.Redis | None:
    """Returns async Redis client, initializing if needed."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2.0,
            )
            # Test connectivity
            await _redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis not reachable at {settings.REDIS_URL}: {e}. Caching will be disabled.")
            _redis_client = None
    return _redis_client


async def close_redis_client():
    """Closes Redis client connection on shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
