import pytest
from httpx import AsyncClient
from app.core.security import create_access_token


@pytest.mark.asyncio
async def test_missing_auth_returns_401(async_client: AsyncClient):
    """Anonymous requests to admin routes must return HTTP 401."""
    resp = await async_client.get("/api/v1/admin/kpis")
    assert resp.status_code == 401

    resp_models = await async_client.get("/api/v1/admin/models")
    assert resp_models.status_code == 401

    resp_limits = await async_client.get("/api/v1/admin/rate-limits")
    assert resp_limits.status_code == 401


@pytest.mark.asyncio
async def test_invalid_auth_returns_401(async_client: AsyncClient):
    """Requests with forged or invalid tokens must return HTTP 401."""
    headers = {"Authorization": "Bearer totally-fake-unparseable-token"}
    resp = await async_client.get("/api/v1/admin/kpis", headers=headers)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_returns_403(async_client: AsyncClient):
    """Authenticated non-admin users must be rejected with HTTP 403."""
    user_token = create_access_token("regular-user-id", claims={"role": "user", "plan": "pro"})
    headers = {"Authorization": f"Bearer {user_token}"}

    resp = await async_client.get("/api/v1/admin/kpis", headers=headers)
    assert resp.status_code == 403

    resp_models = await async_client.get("/api/v1/admin/models", headers=headers)
    assert resp_models.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_admin_routes(async_client: AsyncClient):
    """Authenticated admin users must have full access to admin endpoints."""
    admin_token = create_access_token("admin-user-id", claims={"role": "admin", "plan": "enterprise"})
    headers = {"Authorization": f"Bearer {admin_token}"}

    resp_kpis = await async_client.get("/api/v1/admin/kpis", headers=headers)
    assert resp_kpis.status_code == 200
    assert resp_kpis.json()["success"] is True

    resp_models = await async_client.get("/api/v1/admin/models", headers=headers)
    assert resp_models.status_code == 200
    assert resp_models.json()["success"] is True

    resp_limits = await async_client.get("/api/v1/admin/rate-limits", headers=headers)
    assert resp_limits.status_code == 200
    assert resp_limits.json()["success"] is True


@pytest.mark.asyncio
async def test_admin_can_modify_model_configuration(async_client: AsyncClient):
    """Non-admins cannot mutate model configs, while admins can."""
    import uuid

    user_token = create_access_token("regular-user", claims={"role": "user"})
    admin_token = create_access_token("admin-user", claims={"role": "admin"})
    unique_id = f"test/model-{uuid.uuid4().hex[:8]}"

    payload = {
        "model_id": unique_id,
        "display_name": "Test Custom Model",
        "provider": "custom",
    }

    # Non-admin rejected
    resp_user = await async_client.post(
        "/api/v1/admin/models",
        json=payload,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert resp_user.status_code == 403

    # Admin accepted
    resp_admin = await async_client.post(
        "/api/v1/admin/models",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 200
    assert resp_admin.json()["success"] is True


@pytest.mark.asyncio
async def test_plan_header_cannot_escalate_privileges(async_client: AsyncClient):
    """
    Spoofing X-User-Plan: pro header must NOT elevate an anonymous or free user
    to the Pro tier catalog.
    """
    # 1. Anonymous user attempting to spoof Pro
    resp_anon = await async_client.get("/api/v1/models", headers={"X-User-Plan": "pro"})
    assert resp_anon.status_code == 200
    body = resp_anon.json()["data"]
    assert body["user_plan"] == "free"
    assert body["can_switch_models"] is False
    assert body["active_model"] == "deepseek/deepseek-chat-v3-0324"

    # 2. Authenticated Free user attempting to spoof Pro
    free_token = create_access_token("free-user", claims={"role": "user", "plan": "free"})
    resp_free = await async_client.get(
        "/api/v1/models",
        headers={"Authorization": f"Bearer {free_token}", "X-User-Plan": "pro"},
    )
    assert resp_free.status_code == 200
    body_free = resp_free.json()["data"]
    assert body_free["user_plan"] == "free"
    assert body_free["can_switch_models"] is False


@pytest.mark.asyncio
async def test_user_plan_comes_from_trusted_identity(async_client: AsyncClient):
    """
    User plan and model tier authorization must be derived strictly
    from trusted server-side identity across all subscription tiers.
    """
    tiers = ["free", "plus", "pro", "team", "enterprise"]

    for tier in tiers:
        token = create_access_token(f"user-{tier}", claims={"role": "user", "plan": tier})
        resp = await async_client.get("/api/v1/models", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["user_plan"] == tier

        if tier == "free":
            assert data["can_switch_models"] is False
        else:
            assert data["can_switch_models"] is True


@pytest.mark.asyncio
async def test_soft_deleted_model_is_not_accessible(async_client: AsyncClient):
    """Soft-deleted model records must not be visible or updatable."""
    import uuid

    admin_token = create_access_token("admin-user", claims={"role": "admin"})
    unique_id = f"test/model-del-{uuid.uuid4().hex[:8]}"

    # 1. Admin creates a model
    create_resp = await async_client.post(
        "/api/v1/admin/models",
        json={"model_id": unique_id, "display_name": "Temporary Model", "provider": "test"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 200

    # 2. Admin soft-deletes the model
    del_resp = await async_client.delete(
        f"/api/v1/admin/models/{unique_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert del_resp.status_code == 200
    assert del_resp.json()["data"]["deleted"] is True

    # 3. Model is excluded from active admin list
    list_resp = await async_client.get(
        "/api/v1/admin/models",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_resp.status_code == 200
    active_ids = [m["model_id"] for m in list_resp.json()["data"]]
    assert unique_id not in active_ids

    # 4. Attempt to update soft-deleted model returns error
    patch_resp = await async_client.patch(
        f"/api/v1/admin/models/{unique_id}",
        json={"display_name": "Should Fail"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert patch_resp.json()["success"] is False
    assert patch_resp.json()["error"]["code"] == "MODEL_NOT_FOUND"
