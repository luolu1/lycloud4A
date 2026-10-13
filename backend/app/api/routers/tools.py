"""连接工具管理路由（适配软件：固定种类，用户仅配置本地安装路径）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_permission
from app.models.enums import AuditCategory
from app.models.launch_tool import LaunchTool
from app.models.user import User
from app.schemas.common import Message
from app.schemas.launch_tool import (
    KIND_NAMES,
    KIND_PROTOCOLS,
    ToolCreate,
    ToolOut,
    ToolUpdate,
)
from app.services import audit_service

router = APIRouter(prefix="/tools", tags=["连接工具"])


def _get_tool(db: Session, tool_id: int) -> LaunchTool:
    tool = db.get(LaunchTool, tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail="连接工具不存在")
    return tool


@router.get("", response_model=list[ToolOut], summary="连接工具列表")
def list_tools(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ToolOut]:
    rows = db.execute(select(LaunchTool).order_by(LaunchTool.id)).scalars().all()
    return [ToolOut.model_validate(t) for t in rows]


@router.post("", response_model=ToolOut, status_code=201, summary="新增连接工具")
def create_tool(
    payload: ToolCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:write")),
) -> ToolOut:
    if payload.kind not in KIND_NAMES:
        raise HTTPException(status_code=400, detail=f"不支持的工具类型：{payload.kind}")
    if db.execute(select(LaunchTool).where(LaunchTool.kind == payload.kind)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="该工具已存在")
    tool = LaunchTool(
        kind=payload.kind,
        name=payload.name or KIND_NAMES[payload.kind],
        exe_path=payload.exe_path,
        protocols=KIND_PROTOCOLS[payload.kind],
        description=payload.description,
        status=payload.status,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    audit_service.record(
        db, category=AuditCategory.ADMIN, action="新增连接工具",
        actor_id=actor.id, actor_username=actor.username,
        target_type="launch_tool", target_id=tool.id, target_name=tool.name, request=request,
    )
    return ToolOut.model_validate(tool)


@router.put("/{tool_id}", response_model=ToolOut, summary="更新连接工具路径/状态")
def update_tool(
    tool_id: int,
    payload: ToolUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:write")),
) -> ToolOut:
    tool = _get_tool(db, tool_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(tool, key, value)
    db.commit()
    db.refresh(tool)
    audit_service.record(
        db, category=AuditCategory.ADMIN, action="更新连接工具",
        actor_id=actor.id, actor_username=actor.username,
        target_type="launch_tool", target_id=tool.id, target_name=tool.name, request=request,
    )
    return ToolOut.model_validate(tool)


@router.delete("/{tool_id}", response_model=Message, summary="删除连接工具")
def delete_tool(
    tool_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("application:write")),
) -> Message:
    tool = _get_tool(db, tool_id)
    kind = tool.kind
    db.delete(tool)
    db.commit()
    audit_service.record(
        db, category=AuditCategory.ADMIN, action="删除连接工具",
        actor_id=actor.id, actor_username=actor.username,
        target_type="launch_tool", target_id=tool_id, target_name=tool.name, request=request,
    )
    return Message(message="连接工具已删除")
