"""pytest 全局配置：使用独立测试库、关闭调度器。"""
import os
from pathlib import Path

TEST_DB = Path(__file__).resolve().parent.parent / "data" / "test_4a.db"
TEST_DB.parent.mkdir(parents=True, exist_ok=True)
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["SECRET_KEY"] = "test-secret-key-please-change"
os.environ["VAULT_MASTER_KEY"] = ""
os.environ["ENVIRONMENT"] = "test"
os.environ["ROTATION_SCHEDULER_ENABLED"] = "false"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "Admin@12345"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@12345"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("access_token"), body
    return body["access_token"]


@pytest.fixture(scope="session")
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}
