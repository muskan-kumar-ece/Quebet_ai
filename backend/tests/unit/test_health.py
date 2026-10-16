import pytest
from httpx import AsyncClient
from app.core.logging import sanitize_log_message


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Verify application root metadata endpoint."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "version" in data


@pytest.mark.asyncio
async def test_liveness_probe(async_client: AsyncClient):
    """Verify lightweight liveness probe returns 200."""
    response = await async_client.get("/api/v1/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness_probe(async_client: AsyncClient):
    """Verify deep readiness probe reporting backing services."""
    response = await async_client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert "services" in body["data"]
    assert body["data"]["services"]["api"] == "up"
    assert body["data"]["status"] in ("healthy", "degraded", "unavailable")


@pytest.mark.asyncio
async def test_request_id_generated_when_absent(async_client: AsyncClient):
    """Verify X-Request-ID is generated and returned when not supplied by caller."""
    response = await async_client.get("/")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 10


@pytest.mark.asyncio
async def test_request_id_preserved_when_present(async_client: AsyncClient):
    """Verify custom X-Request-ID is propagated through the response."""
    custom_id = "req-custom-trace-12345"
    response = await async_client.get("/", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == custom_id


def test_structured_log_redaction():
    """Verify passwords, bearer tokens, and API keys are redacted from logs."""
    raw = "User login with Bearer eyJhbGciOiJIUzI1Ni... and key sk-ant-api03-abcdefghijklmn password: 'mypassword'"
    redacted = sanitize_log_message(raw)
    assert "eyJ" not in redacted
    assert "sk-ant" not in redacted
    assert "mypassword" not in redacted
    assert "[REDACTED]" in redacted
