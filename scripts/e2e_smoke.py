#!/usr/bin/env python3
"""端到端 HTTP 冒烟测试：启动真实 uvicorn -> 完整业务链路 -> 关闭。"""
import os
import sys
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent
_VENV_PY = _PROJECT / "backend" / ".venv" / "bin" / "python"

# 若被系统 python 直接执行，强制切换到项目 venv（venv 内才有 httpx/uvicorn 依赖）。
# 注意：venv 的解释器是符号链接，不能用 resolve() 比较，用环境变量标记防止递归。
if os.environ.get("4A_SMOKE_IN_VENV") != "1":
    os.environ["4A_SMOKE_IN_VENV"] = "1"
    os.execv(str(_VENV_PY), [str(_VENV_PY), str(Path(__file__).resolve())])

import subprocess
import time

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
VENV_PY = str(_VENV_PY)
BACKEND = str(_PROJECT / "backend")
LOG = "/tmp/uvicorn_e2e.log"
FAILED = []


def check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    if not cond:
        FAILED.append(name)
    print(f"[{status}] {name} {extra}")


server = subprocess.Popen(
    [VENV_PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd=BACKEND,
    stdout=open(LOG, "w"),
    stderr=subprocess.STDOUT,
    start_new_session=True,
)

try:
    ready = False
    for _ in range(90):
        if server.poll() is not None:
            break
        try:
            with httpx.Client(base_url="http://127.0.0.1:8000", timeout=3) as hc:
                if hc.get("/docs").status_code == 200:
                    ready = True
                    break
        except Exception:
            pass
        time.sleep(1)
    if not ready:
        print("SERVER FAILED TO START")
        print(open(LOG).read()[-3000:])
        sys.exit(2)
    print("server started")

    with httpx.Client(base_url=BASE, timeout=15) as c:
        # ── 认证 ──
        r = c.get("/auth/me")
        check("未认证 /auth/me -> 401", r.status_code == 401, f"({r.status_code})")

        r = c.post("/auth/login", json={"username": "admin", "password": "Admin@12345"})
        check("登录成功", r.status_code == 200, f"({r.status_code})")
        body = r.json()
        check("返回 access+refresh token", bool(body.get("access_token")) and bool(body.get("refresh_token")))
        h = {"Authorization": f"Bearer {body['access_token']}"}
        refresh = body["refresh_token"]

        r = c.post("/auth/refresh", json={"refresh_token": refresh})
        check("刷新 token 成功", r.status_code == 200, f"({r.status_code})")
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = c.get("/auth/me", headers=h)
        me = r.json()
        check("/auth/me 成功且为超管", r.status_code == 200 and me["is_superuser"], f"user={me['username']}")
        check("me.permissions 含全量权限", len(me["permissions"]) >= 27 and "user:write" in me["permissions"],
              f"perms={len(me['permissions'])}")

        # ── 账号域 ──
        r = c.get("/users", params={"page": 1, "page_size": 5}, headers=h)
        check("用户分页列表", r.status_code == 200 and r.json()["total"] >= 1)
        r = c.get("/groups", headers=h)
        check("用户组列表", r.status_code == 200)
        r = c.get("/orgs/tree", headers=h)
        check("组织树", r.status_code == 200 and len(r.json()) >= 1)
        r = c.get("/orgs", headers=h)
        check("组织列表", r.status_code == 200)

        # ── 授权域 ──
        r = c.get("/roles", headers=h)
        roles = r.json()
        check("角色列表 >=5(内置)", r.status_code == 200 and len(roles) >= 5, f"roles={len(roles)}")
        admin_role = next(x for x in roles if x["code"] == "super-admin")
        r = c.get(f"/roles/{admin_role['id']}", headers=h)
        check("角色详情(含权限)", r.status_code == 200 and len(r.json()["permissions"]) > 0)
        r = c.get("/permissions", headers=h)
        check("权限清单 >=27", r.status_code == 200 and len(r.json()) >= 27, f"perms={len(r.json())}")
        r = c.get("/policies", headers=h)
        check("策略列表", r.status_code == 200)

        r = c.post(
            "/policies/evaluate",
            json={"subject_type": "user", "subject_id": me["id"], "resource_type": "application",
                  "resource_id": 1, "action": "launch"},
            headers=h,
        )
        check("策略求值接口", r.status_code == 200 and "allowed" in r.json(), f"allowed={r.json().get('allowed')}")

        # ── 应用 ──
        r = c.get("/apps", headers=h)
        apps = r.json()
        check("应用列表 >=5(种子)", r.status_code == 200 and apps["total"] >= 5, f"apps={apps['total']}")
        r = c.get("/apps/launchable", headers=h)
        check("可启动应用", r.status_code == 200 and len(r.json()) >= 1)
        r = c.post(f"/apps/{apps['items'][0]['id']}/launch", headers=h)
        check("应用 launch", r.status_code == 200 and "redirect_url" in r.json(), f"({r.status_code})")

        # ── 用户/组 CRUD ──
        r = c.post("/users", json={"username": "smoke_user", "display_name": "冒烟测试",
                                   "password": "Smoke@123456", "status": "active"}, headers=h)
        check("创建用户", r.status_code == 201, f"({r.status_code})")
        uid = r.json()["id"]
        r = c.post(f"/users/{uid}/roles", json={"role_ids": [admin_role["id"]]}, headers=h)
        check("分配角色", r.status_code == 200)
        r = c.post(f"/users/{uid}/reset-password", json={"new_password": "Smoke@678901"}, headers=h)
        check("重置密码", r.status_code == 200)
        r = c.put(f"/users/{uid}", json={"status": "disabled"}, headers=h)
        check("停用用户", r.status_code == 200)
        r = c.delete(f"/users/{uid}", headers=h)
        check("删除用户", r.status_code == 200)

        r = c.post("/groups", json={"name": "冒烟组", "code": "smoke_group"}, headers=h)
        check("创建用户组", r.status_code == 201, f"({r.status_code})")
        gid = r.json()["id"]
        r = c.delete(f"/groups/{gid}", headers=h)
        check("删除用户组", r.status_code == 200)

        # ── 密码托管全链路 ──
        r = c.post("/secrets", json={"name": "冒烟数据库", "category": "database", "path": "smoke/db/root",
                                     "description": "e2e", "rotation_enabled": True,
                                     "rotation_type": "manual", "rotation_interval_days": 7,
                                     "tags": {"env": "e2e"}, "data": {"username": "root", "password": "P@ssw0rd!123"}}, headers=h)
        check("创建密钥", r.status_code == 201, f"({r.status_code}) {r.text[:120]}")
        sid = r.json()["id"]
        r = c.get(f"/secrets/{sid}/value", headers=h)
        masked = r.json()
        check("读取值(掩码)", r.status_code == 200 and masked["data"]["password"] != "P@ssw0rd!123", f"v{masked['version']}")
        r = c.get(f"/secrets/{sid}/value", params={"reveal": True}, headers=h)
        check("读取值(明文-reveal)", r.status_code == 200 and r.json()["data"]["password"] == "P@ssw0rd!123")
        r = c.post(f"/secrets/{sid}/rotate", headers=h)
        check("手动轮换", r.status_code == 200 and r.json()["success"], f"v{r.json().get('new_version')}")
        r = c.get(f"/secrets/{sid}/versions", headers=h)
        check("版本历史 >=2", r.status_code == 200 and len(r.json()) >= 2, f"versions={len(r.json())}")
        r = c.get("/rotations/due", headers=h)
        check("到期列表接口", r.status_code == 200)
        r = c.put(f"/secrets/{sid}", json={"rotation_enabled": False}, headers=h)
        check("更新密钥元数据", r.status_code == 200)
        r = c.post(f"/secrets/{sid}/value", json={"data": {"username": "root", "password": "NewPass@456"},
                                                  "comment": "e2e 更新"}, headers=h)
        check("写入新版本", r.status_code == 200 and r.json()["current_version"] >= 3)

        # 重复路径唯一性（放在删除之前，路径仍存在 -> 409）
        r = c.post("/secrets", json={"name": "dup", "path": "smoke/db/root", "data": {"password": "x12345678"}}, headers=h)
        check("重复路径 -> 409", r.status_code == 409, f"({r.status_code})")

        r = c.delete(f"/secrets/{sid}", headers=h)
        check("删除密钥", r.status_code == 200)

        r = c.post("/rotations/run", headers=h)
        check("轮换扫描执行", r.status_code == 200 and "processed" in r.json(), f"processed={r.json().get('processed')}")

        # ── 审计域 ──
        r = c.get("/audits", params={"page": 1, "page_size": 10}, headers=h)
        check("审计日志列表", r.status_code == 200 and r.json()["total"] >= 10, f"total={r.json()['total']}")
        r = c.get("/audits", params={"category": "vault", "result": "success"}, headers=h)
        check("审计过滤(vault+success)", r.status_code == 200)
        r = c.get("/audits/stats", headers=h)
        stats = r.json()
        check("审计统计", r.status_code == 200 and stats["total"] > 0 and len(stats["by_day"]) == 7)

        # ── 仪表盘 ──
        r = c.get("/dashboard/stats", headers=h)
        ds = r.json()
        check("仪表盘统计", r.status_code == 200 and ds["user_total"] >= 1,
              f"users={ds['user_total']} audits={ds['audit_total']}")

        # ── RBAC 权限隔离 ──
        r = c.post("/users", json={"username": "smoke_limited", "display_name": "受限用户",
                                   "password": "Smoke@123456"}, headers=h)
        check("创建受限用户", r.status_code == 201, f"({r.status_code})")
        lid = r.json()["id"]
        r = c.post("/auth/login", json={"username": "smoke_limited", "password": "Smoke@123456"})
        lh = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = c.get("/audits", headers=lh)
        check("普通用户访问审计 -> 403", r.status_code == 403, f"({r.status_code})")
        c.delete(f"/users/{lid}", headers=h)

        # ── 登出 ──
        r = c.post("/auth/logout", json={"refresh_token": refresh}, headers=h)
        check("登出", r.status_code == 200)
        r = c.post("/auth/refresh", json={"refresh_token": refresh})
        check("登出后 refresh 失效 -> 401", r.status_code == 401, f"({r.status_code})")

    print()
    if FAILED:
        print(f"FAILED: {len(FAILED)} 项 -> {FAILED}")
        sys.exit(1)
    print("E2E 冒烟全部通过")
finally:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)