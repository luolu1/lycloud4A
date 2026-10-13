"""4A 平台后端入口。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
