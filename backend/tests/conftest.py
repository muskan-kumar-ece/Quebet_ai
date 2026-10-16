import pytest
from httpx import ASGITransport, AsyncClient
from app.core.database import engine
from app.main import app
from app.models.db.base import Base


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Ensure test database schema is initialized for test execution."""
    if "sqlite" in str(engine.url):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture
async def async_client():
    """Async test client targeting the FastAPI application with clean connection pool."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    # Cleanly dispose and return pooled asyncpg connections to prevent pool contention between test runs
    await engine.dispose()

