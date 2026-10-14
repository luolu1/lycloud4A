"""设备管理路由：网络/安全设备、服务器、堡垒机等纳管对象。"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.core.config import settings
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.enums import AuditCategory
from app.models.launch_tool import LaunchTool
from app.models.user import User
from app.schemas.application import (
    AppCheckResult,
    AppConnectOut,
    AppCreate,
    AppLaunchOut,
    AppOut,
    AppUpdate,
    ConnectResolveIn,
    ConnectResolveOut,
)
from app.schemas.common import Message, Page
from app.schemas.user import UserOut
from app.services import audit_service, connect_service, device_service, policy_service
from app.services.audit_service import client_ip
from app.services.terminal_render import render_terminal

router = APIRouter(prefix="/apps", tags=["设备管理"])

log = logging.getLogger("app.connect")

# 同一会话的原始流按到达顺序落盘，渲染时读取整份原始流，避免分片导致的乱码。
_audit_log_lock = threading.Lock()


class ConnectRequest(BaseModel):
    tool_id: int
    agent_url: str = "http://127.0.0.1:47621"
    client_ip: Optional[str] = None


class UserIds(BaseModel):
    user_ids: list[int] = []


def _to_out(app: Application) -> AppOut:
    out = AppOut.model_validate(app)
    out.has_credential = bool(app.credential_encrypted)
    return out


def _get_app(db: Session, app_id: int) -> Application:
    app = db.get(Application, app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return app


def _can_launch(db: Session, user: User, app: Application) -> bool:
    if user.is_superuser:
        return True
    if any(u.id == user.id for u in app.users):
        return True
    allowed, _, _ = policy_service.evaluate(
        db,
        subject_type="user",
        subject_id=user.id,
        resource_type="application",
        resource_id=app.id,
        action="read",
    )
    return allowed


@router.get("", response_model=Page[AppOut], summary="设备列表")
def list_apps(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    app_type: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("application:read")),
) -> Page[AppOut]:
    stmt = select(Application)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Application.name.ilike(like), Application.code.ilike(like)))
    if app_type:
        stmt = stmt.where(Application.app_type == app_type)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        db.execute(stmt.order_by(Application.id.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=[_to_out(a) for a in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=AppOut, status_code=201, summary="纳管设备")
def create_app(
    payload: AppCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:write")),
) -> AppOut:
    data = payload.model_dump(exclude={"credential"})
    if not data.get("code"):
        data["code"] = f"DEV-{uuid4().hex[:10].upper()}"
    if db.execute(select(Application).where(Application.code == data["code"])).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="设备编码已存在")
    app = Application(**data)
    if payload.credential:
        app.credential_encrypted = device_service.store_credential(payload.credential)
    db.add(app)
    db.commit()
    db.refresh(app)
    device_service.check_connectivity(db, app)
    db.refresh(app)
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="纳管设备",
        actor_id=actor.id, actor_username=actor.username,
        target_type="application", target_id=app.id, target_name=app.name,
        detail={
            "设备类型": app.app_type,
            "认证协议": app.protocol,
            "连接状态": app.conn_status,
            "访问IP": client_ip(request),
        }, request=request,
    )
    return _to_out(app)


@router.get("/launchable", response_model=list[AppOut], summary="当前用户可访问的设备")
def launchable_apps(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AppOut]:
    apps = db.execute(select(Application).where(Application.status.is_(True)).order_by(Application.id)).scalars().all()
    return [_to_out(a) for a in apps if _can_launch(db, user, a)]


@router.get("/{app_id}", response_model=AppOut, summary="设备详情")
def get_app(
    app_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("application:read")),
) -> AppOut:
    return _to_out(_get_app(db, app_id))


@router.post("/{app_id}/check", response_model=AppCheckResult, summary="检测设备连通状态")
def check_app(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:read")),
) -> AppCheckResult:
    app = _get_app(db, app_id)
    status, error = device_service.check_connectivity(db, app)
    audit_service.record(
        db, category=AuditCategory.ADMIN, action="检测设备连接",
        actor_id=actor.id, actor_username=actor.username,
        target_type="application", target_id=app.id, target_name=app.name,
        detail={
            "设备类型": app.app_type,
            "连接状态": status,
            "错误信息": error,
            "访问IP": client_ip(request),
        }, request=request,
    )
    return AppCheckResult(
        app_id=app.id, conn_status=status, last_checked_at=app.last_checked_at, error=error
    )


@router.post("/connect/resolve", response_model=ConnectResolveOut, summary="解析连接票据（供本地 Agent 调用）")
def resolve_connect(
    payload: ConnectResolveIn,
    request: Request,
    db: Session = Depends(get_db),
) -> ConnectResolveOut:
    entry = connect_service.consume_ticket(payload.ticket)
    if entry is None:
        raise HTTPException(status_code=404, detail="票据无效或已过期")
    app = db.get(Application, entry.device_id)
    tool = db.get(LaunchTool, entry.tool_id)
    if app is None or tool is None:
        raise HTTPException(status_code=404, detail="设备或连接工具不存在")
    # 连接事件在签发票据（connect_app）时已记录一条审计，此处解析票据不再重复留痕，
    # 否则一次连接会出现“连接设备 + 解析连接凭证”两条记录。
    # 顺便把连接助手版本写回该条审计、并打到服务端日志：客户端未升级时，
    # 对应适配软件（如 MobaXterm 的 ftp/sftp）可能没有会话日志，便于定位。
    if entry.audit_id:
        log_entry = db.get(AuditLog, entry.audit_id)
        if log_entry is not None and isinstance(log_entry.detail, dict):
            detail = dict(log_entry.detail)
            detail["客户端版本"] = payload.client_version or "未知"
            log_entry.detail = detail
            db.commit()
    log.info(
        "连接解析：设备=%s 协议=%s 工具=%s 客户端版本=%s 会话=%s",
        app.name, app.protocol, tool.kind, payload.client_version or "未知", entry.session_id,
    )
    return ConnectResolveOut(**connect_service.resolve(app, tool, entry))


class LogUploadIn(BaseModel):
    audit_id: int
    username: str
    session_id: str
    log_content: str
    # append：log_content 是新增片段，追加到原始流（tee -a / NetCatty raw）。
    # snapshot：log_content 是整份快照，覆盖原始流（NetCatty txt/html 每次刷新整体重写）。
    mode: str = "append"


@router.post("/connect/upload-log", summary="接收客户端上传的操作审计日志")
def upload_connect_log(
    payload: LogUploadIn,
    db: Session = Depends(get_db),
) -> dict:
    # 客户端上传的是**原始终端流**（可能被 2 秒轮询切分成多段）。这里先落到 .raw，
    # 再把整份原始流渲染成可读的 .log，因此分片也不会造成乱码。
    # - append：追加片段（tee -a / NetCatty raw 日志只增不改）
    # - snapshot：整体覆盖（NetCatty txt 日志每次刷新都用完整内容重写文件）
    user_dir = os.path.join(settings.AUDIT_LOG_DIR, payload.username)
    os.makedirs(user_dir, exist_ok=True)
    raw_path = os.path.join(user_dir, f"{payload.session_id}.raw")
    target_path = os.path.join(user_dir, f"{payload.session_id}.log")

    file_mode = "w" if payload.mode == "snapshot" else "a"
    with _audit_log_lock:
        with open(raw_path, file_mode, encoding="utf-8", errors="replace") as f:
            f.write(payload.log_content)
        try:
            with open(raw_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            raw = payload.log_content
        rendered = render_terminal(raw)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(rendered)
            f.write("\n")

    log_entry = db.get(AuditLog, payload.audit_id)
    if log_entry and isinstance(log_entry.detail, dict):
        detail = dict(log_entry.detail)
        detail["日志文件路径"] = target_path
        detail["会话标识"] = payload.session_id
        log_entry.detail = detail
        db.commit()

    return {"status": "ok", "path": target_path}


@router.post("/{app_id}/connect", response_model=AppConnectOut, summary="发起设备连接（签发一次性票据）")
def connect_app(
    app_id: int,
    payload: ConnectRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:read")),
) -> AppConnectOut:
    app = _get_app(db, app_id)
    tool = db.get(LaunchTool, payload.tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="连接工具不存在")
    supported = {item.strip().lower() for item in (tool.protocols or "").split(",") if item.strip()}
    if app.protocol.lower() not in supported:
        raise HTTPException(
            status_code=400,
            detail=f"连接工具 {tool.name} 不支持设备协议 {app.protocol}",
        )
    actor_ip = payload.client_ip or client_ip(request)
    ticket = connect_service.issue_ticket(app.id, tool.id, actor.id, actor_ip)

    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"{actor.username}_{app.name}_{now_str}_{ticket[:6]}"
    user_log_dir = os.path.join(settings.AUDIT_LOG_DIR, actor.username)
    os.makedirs(user_log_dir, exist_ok=True)
    server_log_path = os.path.join(user_log_dir, f"{session_id}.log")

    proto = (app.protocol or "").strip().lower()
    audit_entry = audit_service.record(
        db, category=AuditCategory.CONNECTION,
        action=f"{proto}连接" if proto else "连接设备",
        actor_id=actor.id, actor_username=actor.username,
        target_type="application", target_id=app.id, target_name=app.name,
        detail={
            "设备类型": app.app_type,
            "连接工具": tool.name,
            "连接协议": app.protocol,
            "访问IP": actor_ip,
            "日志文件路径": server_log_path,
            "会话标识": session_id,
        }, request=request,
    )
    connect_service.attach_audit_info(ticket, audit_entry.id, actor.username, session_id, server_log_path)
    return AppConnectOut(
        ticket=ticket, agent_url=payload.agent_url,
        device_id=app.id, device_name=app.name, tool_kind=tool.kind,
    )


@router.put("/{app_id}", response_model=AppOut, summary="更新设备")
def update_app(
    app_id: int,
    payload: AppUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:write")),
) -> AppOut:
    app = _get_app(db, app_id)
    updates = payload.model_dump(exclude_unset=True)
    credential = updates.pop("credential", None)
    for key, value in updates.items():
        setattr(app, key, value)
    if credential:
        app.credential_encrypted = device_service.store_credential(credential)
    db.commit()
    db.refresh(app)
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="更新设备",
        actor_id=actor.id, actor_username=actor.username,
        target_type="application", target_id=app.id, target_name=app.name,
        detail={
            "设备类型": app.app_type,
            "认证协议": app.protocol,
            "访问IP": client_ip(request),
        }, request=request,
    )
    return _to_out(app)


@router.delete("/{app_id}", response_model=Message, summary="删除应用")
def delete_app(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:delete")),
) -> Message:
    app = _get_app(db, app_id)
    code = app.code
    db.delete(app)
    db.commit()
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="移除设备",
        actor_id=actor.id, actor_username=actor.username,
        target_type="application", target_id=app_id, target_name=app.name,
        detail={
            "设备类型": app.app_type,
            "访问IP": client_ip(request),
        }, request=request,
    )
    return Message(message="应用已删除")


@router.post("/{app_id}/launch", response_model=AppLaunchOut, summary="发起 SSO 跳转（简化）")
def launch_app(
    app_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AppLaunchOut:
    app = _get_app(db, app_id)
    if not app.status:
        raise HTTPException(status_code=403, detail="设备已停用")
    if not _can_launch(db, user, app):
        raise HTTPException(status_code=403, detail="无权访问该设备")
    ticket = uuid4().hex
    base = app.url or ""
    sep = "&" if "?" in base else "?"
    redirect = f"{base}{sep}ticket={ticket}" if base else ticket
    audit_service.record(
        db, category=AuditCategory.ADMIN, action="启动应用",
        actor_id=user.id, actor_username=user.username,
        target_type="application", target_id=app.id, target_name=app.name, request=request,
    )
    return AppLaunchOut(
        app_id=app.id, app_name=app.name, protocol=app.protocol, redirect_url=redirect, ticket=ticket
    )


@router.get("/{app_id}/users", response_model=list[UserOut], summary="已授权用户")
def app_users(
    app_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("application:read")),
) -> list[UserOut]:
    app = _get_app(db, app_id)
    return [UserOut.model_validate(u) for u in app.users]


@router.post("/{app_id}/users", response_model=Message, summary="设置授权用户（覆盖）")
def set_app_users(
    app_id: int,
    payload: UserIds,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:write")),
) -> Message:
    app = _get_app(db, app_id)
    app.users = list(db.execute(select(User).where(User.id.in_(payload.user_ids))).scalars())
    db.commit()
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="更新设备授权用户",
        actor_id=actor.id, actor_username=actor.username,
        target_type="application", target_id=app.id, target_name=app.name,
        detail={"user_ids": payload.user_ids}, request=request,
    )
    return Message(message="授权用户已更新")


@router.delete("/{app_id}/users/{user_id}", response_model=Message, summary="移除授权用户")
def remove_app_user(
    app_id: int,
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:write")),
) -> Message:
    app = _get_app(db, app_id)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user in app.users:
        app.users.remove(user)
        db.commit()
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="移除设备授权用户",
        actor_id=actor.id, actor_username=actor.username,
        target_type="application", target_id=app.id, target_name=app.name,
        detail={"removed_user_id": user_id}, request=request,
    )
    return Message(message="已移除授权")
