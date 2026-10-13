"""设备管理路由：网络/安全设备、服务器、堡垒机等纳管对象。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
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

router = APIRouter(prefix="/apps", tags=["设备管理"])


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
    actor = db.get(User, entry.user_id)
    audit_service.record(
        db, category=AuditCategory.ADMIN, action="解析连接凭证",
        actor_id=entry.user_id,
        actor_username=actor.username if actor else None,
        target_type="application", target_id=app.id, target_name=app.name,
        detail={
            "设备类型": app.app_type,
            "连接工具": tool.name,
            "访问IP": entry.actor_ip,
        }, request=request,
    )
    return ConnectResolveOut(**connect_service.resolve(app, tool, entry))


class LogUploadIn(BaseModel):
    audit_id: int
    username: str
    session_id: str
    log_content: str


@router.post("/connect/upload-log", summary="接收客户端上传的操作审计日志")
def upload_connect_log(
    payload: LogUploadIn,
    db: Session = Depends(get_db),
) -> dict:
    import os
    user_dir = os.path.join("/mnt/4a-platform/backend/data/audit_logs", payload.username)
    os.makedirs(user_dir, exist_ok=True)
    filename = f"{payload.session_id}.log"
    target_path = os.path.join(user_dir, filename)

    with open(target_path, "a", encoding="utf-8") as f:
        import re
        ansi_regex = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_regex.sub('', payload.log_content)
        f.write(cleaned)
        if not cleaned.endswith("\n"):
            f.write("\n")

    log_entry = db.get(AuditLog, payload.audit_id)
    if log_entry and isinstance(log_entry.detail, dict):
        log_entry.detail["日志文件路径"] = target_path
        log_entry.detail["会话标识"] = payload.session_id
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
    
    import os
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"{actor.username}_{app.name}_{now_str}_{ticket[:6]}"
    user_log_dir = os.path.join("/mnt/4a-platform/backend/data/audit_logs", actor.username)
    os.makedirs(user_log_dir, exist_ok=True)
    server_log_path = os.path.join(user_log_dir, f"{session_id}.log")

    audit_entry = audit_service.record(
        db, category=AuditCategory.ADMIN, action="连接设备",
        actor_id=actor.id, actor_username=actor.username,
        target_type="application", target_id=app.id, target_name=app.name,
        detail={
            "设备类型": app.app_type,
            "连接工具": tool.name,
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
