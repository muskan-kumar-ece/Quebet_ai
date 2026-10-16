import uuid
import pytest
from httpx import AsyncClient
from app.core.config import Settings
from app.core.security import create_access_token, revoke_token
from app.models.db.user import User


# ==============================================================================
# SEC-01: Fail-Closed Authentication & Server-Side Identity Derivation Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_sec01_active_db_user_derives_identity_from_db(async_client: AsyncClient):
    """
    When a user exists in the authoritative database, their role, plan, and tenant
    are strictly derived from the database record, overriding any forged JWT claims.
    """
    from app.core.database import AsyncSessionLocal

    user_id = str(uuid.uuid4())
    user_email = f"eng_{uuid.uuid4().hex[:6]}@quebet.ai"

    # Seed active user in DB
    async with AsyncSessionLocal() as session:
        db_user = User(
            id=user_id,
            email=user_email,
            role="ENGINEER",
            plan="pro",
            tenant_id="tenant-alpha",
        )
        session.add(db_user)
        await session.commit()

    try:
        # Client presents a forged token claiming role="admin" and plan="enterprise"
        forged_token = create_access_token(
            user_id,
            claims={"role": "admin", "plan": "enterprise", "email": "fake@admin.com"},
        )
        headers = {"Authorization": f"Bearer {forged_token}"}

        # Query models endpoint which derives plan server-side
        resp = await async_client.get("/api/v1/models", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        # Must reflect the DB plan ('pro'), NOT the forged token claim ('enterprise')
        assert data["user_plan"] == "pro"

        # Attempt to access admin portal: must be 403 Forbidden because DB role is ENGINEER
        admin_resp = await async_client.get("/api/v1/admin/kpis", headers=headers)
        assert admin_resp.status_code == 403
    finally:
        # Cleanup seeded user
        async with AsyncSessionLocal() as session:
            del_user = await session.get(User, user_id)
            if del_user:
                await session.delete(del_user)
                await session.commit()


@pytest.mark.asyncio
async def test_sec01_soft_deleted_db_user_fails_closed(async_client: AsyncClient):
    """
    A user whose account is soft-deleted (deleted_at is set) must be rejected
    with HTTP 401 Unauthorized immediately, regardless of valid JWT signature.
    """
    from datetime import datetime, timezone
    from app.core.database import AsyncSessionLocal

    user_id = str(uuid.uuid4())
    user_email = f"deactivated_{uuid.uuid4().hex[:6]}@quebet.ai"

    # Seed soft-deleted user in DB
    async with AsyncSessionLocal() as session:
        db_user = User(
            id=user_id,
            email=user_email,
            role="ENGINEER",
            plan="pro",
            deleted_at=datetime.now(timezone.utc),
        )
        session.add(db_user)
        await session.commit()

    try:
        token = create_access_token(user_id, claims={"role": "ENGINEER", "plan": "pro"})
        headers = {"Authorization": f"Bearer {token}"}

        resp = await async_client.get("/api/v1/projects", headers=headers)
        assert resp.status_code == 401
        assert "deactivated or deleted" in resp.json()["detail"].lower()
    finally:
        async with AsyncSessionLocal() as session:
            del_user = await session.get(User, user_id)
            if del_user:
                await session.delete(del_user)
                await session.commit()


@pytest.mark.asyncio
async def test_sec01_nonexistent_user_in_production_fails_closed(async_client: AsyncClient, monkeypatch):
    """
    In production mode, a token with a subject (UUID) that does not exist in the
    database must fail closed with HTTP 401 Unauthorized.
    """
    from app.core import dependencies

    # Temporarily enforce production environment check
    monkeypatch.setattr(dependencies.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(dependencies.settings, "ALLOW_DEV_MOCK_AUTH", False)

    nonexistent_id = str(uuid.uuid4())
    token = create_access_token(nonexistent_id, claims={"role": "user", "plan": "free"})
    headers = {"Authorization": f"Bearer {token}"}

    resp = await async_client.get("/api/v1/projects", headers=headers)
    assert resp.status_code == 401
    assert "not found" in resp.json()["detail"].lower()


# ==============================================================================
# SEC-03: AI Authority Prohibition & Human-Only Proposal Gating Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_sec03_ai_agent_role_cannot_approve_proposal(async_client: AsyncClient):
    """
    An actor with an AI, bot, or copilot role MUST be forbidden from approving proposals.
    Invariant: AI ENGINEERING AUTHORITY = NONE.
    """
    ai_roles = ["AI_AGENT", "copilot", "BOT", "assistant", "AUTONOMOUS_RUNNER"]
    fake_proposal_id = str(uuid.uuid4())

    for role in ai_roles:
        token = create_access_token(f"ai-{role.lower()}-id", claims={"role": role, "plan": "pro"})
        headers = {"Authorization": f"Bearer {token}"}

        resp = await async_client.post(f"/api/v1/proposals/{fake_proposal_id}/approve", headers=headers)
        assert resp.status_code == 403, f"Expected 403 for role {role}, got {resp.status_code}"
        assert "AI ENGINEERING AUTHORITY = NONE" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_sec03_ai_agent_role_cannot_apply_proposal(async_client: AsyncClient):
    """
    An actor with an AI, bot, or copilot role MUST be forbidden from applying proposals.
    Invariant: AUTONOMOUS MUTATION = DISABLED.
    """
    token = create_access_token("ai-agent-42", claims={"role": "AI_AGENT", "plan": "pro"})
    headers = {"Authorization": f"Bearer {token}"}
    fake_proposal_id = str(uuid.uuid4())

    resp = await async_client.post(f"/api/v1/proposals/{fake_proposal_id}/apply", headers=headers)
    assert resp.status_code == 403
    assert "AI ENGINEERING AUTHORITY = NONE" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_sec03_human_engineer_can_reach_proposal_pipeline(async_client: AsyncClient):
    """
    A verified human engineer role (ENGINEER, LEAD_ENGINEER, ADMIN) passes role validation.
    Even if the proposal is not found, the authorization check must succeed (returning 404, not 403).
    """
    human_roles = ["ENGINEER", "LEAD_ENGINEER", "CHIEF_ENGINEER", "ADMIN", "user"]
    fake_proposal_id = str(uuid.uuid4())

    for role in human_roles:
        token = create_access_token(f"human-{role.lower()}-id", claims={"role": role, "plan": "pro"})
        headers = {"Authorization": f"Bearer {token}"}

        resp = await async_client.post(f"/api/v1/proposals/{fake_proposal_id}/approve", headers=headers)
        assert resp.status_code == 404, f"Expected 404 (authorized but not found) for {role}, got {resp.status_code}"


# ==============================================================================
# SEC-04: Production Secret Validation & Sanitized Error Disclosure Tests
# ==============================================================================

def test_sec04_production_secret_key_validation():
    """
    In production mode, the application startup MUST fail if SECRET_KEY is the
    insecure dev default or shorter than 32 characters.
    """
    # 1. Dev default in production -> ValueError
    insecure_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="dev-secret-key-change-in-production-min-32-chars-long",
    )
    with pytest.raises(ValueError, match="Insecure SECRET_KEY"):
        Settings.validate_security(insecure_settings)

    # 2. Too short in production -> ValueError
    short_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="short-secret-key-12345",
    )
    with pytest.raises(ValueError, match="Insecure SECRET_KEY"):
        Settings.validate_security(short_settings)

    # 3. Secure key in production -> Success
    secure_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="this-is-a-very-secure-randomly-generated-key-with-64-characters-ok",
    )
    validated = Settings.validate_security(secure_settings)
    assert validated.SECRET_KEY == "this-is-a-very-secure-randomly-generated-key-with-64-characters-ok"


@pytest.mark.asyncio
async def test_sec04_unhandled_exception_returns_sanitized_500(async_client: AsyncClient, monkeypatch):
    """
    Unhandled 500 errors must never disclose internal exception details or tracebacks
    in the HTTP JSON response body.
    """
    from app.main import app
    from httpx import ASGITransport

    # Add a temporary test endpoint that raises an unhandled exception with sensitive leak
    @app.get("/api/v1/test-error-disclosure")
    async def buggy_route():
        raise RuntimeError("CRITICAL DATABASE LEAK: postgresql://admin:secret_pass@db.local:5432/core")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/test-error-disclosure")
    assert resp.status_code == 500
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "An unexpected server error occurred" in body["error"]["message"]
    # Details must be empty and must not leak the raw exception or connection string
    assert body["error"]["details"] == {}
    assert "postgresql://" not in str(body)
    assert "secret_pass" not in str(body)



# ==============================================================================
# SEC-06: JWT Expiration & Revocation Lifecycle Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_sec06_revoked_token_is_rejected_on_subsequent_requests(async_client: AsyncClient):
    """
    When a user logs out, their token is revoked and cannot be reused for authentication.
    """
    token = create_access_token("logout-test-user", claims={"role": "user", "plan": "pro"})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Before logout: request succeeds or returns authenticated status
    resp_before = await async_client.get("/api/v1/models", headers=headers)
    assert resp_before.status_code == 200

    # 2. Call /api/v1/auth/logout to revoke token
    logout_resp = await async_client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["success"] is True

    # 3. Subsequent request with the same revoked token must fail with 401
    resp_after = await async_client.get("/api/v1/models", headers=headers)
    assert resp_after.status_code == 401
    assert "revoked" in resp_after.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sec06_expired_token_is_rejected(async_client: AsyncClient):
    """
    Tokens expired past their exp timestamp must return HTTP 401 Unauthorized.
    """
    from datetime import timedelta
    # Generate token already expired 10 minutes ago
    expired_token = create_access_token("expired-user", expires_delta=timedelta(minutes=-10))
    headers = {"Authorization": f"Bearer {expired_token}"}

    resp = await async_client.get("/api/v1/models", headers=headers)
    assert resp.status_code == 401
