"""端到端冒烟测试：覆盖 4A 平台核心路径。"""
import pytest


def test_health(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json()["status"] == "ready"


def test_openapi_available(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert "/api/v1/auth/login" in resp.json()["paths"]


def test_login_me_and_permissions(client, auth):
    me = client.get("/api/v1/auth/me", headers=auth)
    assert me.status_code == 200, me.text
    data = me.json()
    assert data["username"] == "admin"
    assert data["is_superuser"] is True
    assert isinstance(data["permissions"], list)
    assert "user:write" in data["permissions"]


def test_login_wrong_password(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong-pass"})
    assert resp.status_code == 401


def test_account_crud(client, auth):
    created = client.post(
        "/api/v1/users",
        headers=auth,
        json={
            "username": "zhangsan",
            "display_name": "张三",
            "password": "ZhangSan@12345",
            "email": "zhangsan@corp.example.com",
        },
    )
    assert created.status_code in (200, 201), created.text
    uid = created.json()["id"]

    listing = client.get("/api/v1/users", headers=auth, params={"q": "zhangsan"})
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    updated = client.put(f"/api/v1/users/{uid}", headers=auth, json={"title": "运维工程师"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "运维工程师"

    reset = client.post(f"/api/v1/users/{uid}/reset-password", headers=auth, json={})
    assert reset.status_code == 200

    assert client.post(f"/api/v1/users/{uid}/unlock", headers=auth).status_code == 200

    deleted = client.delete(f"/api/v1/users/{uid}", headers=auth)
    assert deleted.status_code == 200


def test_cannot_delete_self(client, auth):
    me = client.get("/api/v1/auth/me", headers=auth).json()
    resp = client.delete(f"/api/v1/users/{me['id']}", headers=auth)
    assert resp.status_code == 400


def test_orgs_and_groups(client, auth):
    tree = client.get("/api/v1/orgs/tree", headers=auth)
    assert tree.status_code == 200
    assert isinstance(tree.json(), list) and len(tree.json()) >= 1

    groups = client.get("/api/v1/groups", headers=auth)
    assert groups.status_code == 200
    assert len(groups.json()) >= 1


def test_applications_and_launch(client, auth):
    apps = client.get("/api/v1/apps", headers=auth)
    assert apps.status_code == 200
    assert apps.json()["total"] >= 1

    launchable = client.get("/api/v1/apps/launchable", headers=auth)
    assert launchable.status_code == 200
    assert len(launchable.json()) >= 1

    app_id = launchable.json()[0]["id"]
    launch = client.post(f"/api/v1/apps/{app_id}/launch", headers=auth)
    assert launch.status_code == 200
    assert launch.json()["ticket"]


def test_roles_permissions_policies(client, auth):
    perms = client.get("/api/v1/permissions", headers=auth)
    assert perms.status_code == 200
    assert len(perms.json()) >= 20

    roles = client.get("/api/v1/roles", headers=auth)
    assert roles.status_code == 200
    assert any(r["code"] == "super-admin" for r in roles.json())

    role = client.post(
        "/api/v1/roles",
        headers=auth,
        json={"name": "测试角色", "code": "test-role", "description": "临时"},
    )
    assert role.status_code in (200, 201), role.text
    rid = role.json()["id"]
    assert client.delete(f"/api/v1/roles/{rid}", headers=auth).status_code == 200

    audit_role = client.post(
        "/api/v1/roles",
        headers=auth,
        json={"name": "内置类角色", "code": "tmp-builtin"},
    )
    assert audit_role.status_code in (200, 201)

    policies = client.get("/api/v1/policies", headers=auth)
    assert policies.status_code == 200

    evaluate = client.post(
        "/api/v1/policies/evaluate",
        headers=auth,
        json={
            "subject_type": "user",
            "subject_id": 1,
            "resource_type": "application",
            "action": "read",
        },
    )
    assert evaluate.status_code == 200
    assert "allowed" in evaluate.json()


def test_secrets_vault(client, auth):
    created = client.post(
        "/api/v1/secrets",
        headers=auth,
        json={
            "path": "app/oa/oa_service",
            "name": "OA 服务账号",
            "category": "application",
            "data": {"username": "oa_svc", "password": "OaService@12345"},
            "rotation_enabled": True,
            "rotation_interval_days": 30,
        },
    )
    assert created.status_code in (200, 201), created.text
    sid = created.json()["id"]

    masked = client.get(f"/api/v1/secrets/{sid}/value", headers=auth)
    assert masked.status_code == 200
    assert "****" in masked.json()["data"]["password"]

    revealed = client.get(f"/api/v1/secrets/{sid}/value", headers=auth, params={"reveal": "true"})
    assert revealed.status_code == 200
    assert revealed.json()["data"]["password"] == "OaService@12345"

    rotated = client.post(f"/api/v1/secrets/{sid}/rotate", headers=auth)
    assert rotated.status_code == 200
    assert rotated.json()["success"] is True

    versions = client.get(f"/api/v1/secrets/{sid}/versions", headers=auth)
    assert versions.status_code == 200
    assert len(versions.json()) >= 2

    after = client.get(f"/api/v1/secrets/{sid}/value", headers=auth, params={"reveal": "true"}).json()
    assert after["data"]["password"] != "OaService@12345"


def test_rotation_endpoints(client, auth):
    due = client.get("/api/v1/rotations/due", headers=auth)
    assert due.status_code == 200
    run = client.post("/api/v1/rotations/run", headers=auth)
    assert run.status_code == 200
    assert "processed" in run.json()


def test_audit_and_dashboard(client, auth):
    audits = client.get("/api/v1/audits", headers=auth)
    assert audits.status_code == 200
    assert audits.json()["total"] >= 1

    stats = client.get("/api/v1/audits/stats", headers=auth, params={"days": 7})
    assert stats.status_code == 200
    assert stats.json()["total"] >= 1

    dash = client.get("/api/v1/dashboard/stats", headers=auth)
    assert dash.status_code == 200
    body = dash.json()
    assert body["user_total"] >= 1
    assert body["app_total"] >= 1


def test_rbac_forbidden_for_new_user(client, auth):
    created = client.post(
        "/api/v1/users",
        headers=auth,
        json={
            "username": "noperm",
            "display_name": "无权限用户",
            "password": "NoPerm@123456",
        },
    )
    assert created.status_code in (200, 201)
    login = client.post("/api/v1/auth/login", json={"username": "noperm", "password": "NoPerm@123456"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
