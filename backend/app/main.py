"""4A 平台后端入口。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routers import (
    apps,
    audit,
    auth,
    client,
    dashboard,
    groups,
    orgs,
    permissions,
    policies,
    roles,
    rotations,
    secrets,
    tools,
    users,
)
from app.core.config import settings
from app.core.database import init_db
from app.seed import seed
from app.services.scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed()
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="统一身份认证与访问管理 4A 平台（认证 / 授权 / 账号 / 审计）",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    users.router,
    groups.router,
    orgs.router,
    apps.router,
    roles.router,
    permissions.router,
    policies.router,
    audit.router,
    secrets.router,
    rotations.router,
    tools.router,
    client.router,
    dashboard.router,
):
    app.include_router(router, prefix=settings.API_V1_PREFIX)


@app.get("/healthz", tags=["系统"], summary="存活探针")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/readyz", tags=["系统"], summary="就绪探针")
def readyz() -> dict:
    return {"status": "ready"}


def _mount_frontend(fastapi_app: FastAPI) -> None:
    """单容器部署：后端直接托管前端 SPA（存在 frontend/dist 时生效）。

    - `/assets/*` 由 StaticFiles 提供静态资源与缓存头；
    - 其余 GET 路径优先返回真实文件，否则回退 `index.html`，交给前端路由处理；
    - 该兜底路由最后注册，不会覆盖已注册的 `/api`、`/docs`、`/healthz` 等路由。
    """
    if not settings.SERVE_FRONTEND:
        return

    dist = Path(settings.FRONTEND_DIST_DIR)
    if not dist.is_dir():
        return

    dist_root = dist.resolve()
    assets = dist_root / "assets"
    if assets.is_dir():
        fastapi_app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index_file = dist_root / "index.html"
    if not index_file.is_file():
        return

    @fastapi_app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path:
            candidate = (dist_root / full_path).resolve()
            if candidate.is_file() and str(candidate).startswith(str(dist_root)):
                return FileResponse(candidate)
        return FileResponse(index_file)

    logging.getLogger(__name__).info("前端 SPA 已挂载：%s", dist_root)


_mount_frontend(app)
