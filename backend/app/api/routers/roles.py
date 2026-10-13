"""授权路由：角色与权限。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.enums import AuditCategory
from app.models.rbac import Permission, Role
from app.models.user import User
from app.schemas.common import Message
from app.schemas.rbac import RoleCreate, RoleDetailOut, RoleOut, RoleUpdate
from app.services import audit_service

router = APIRouter(prefix="/roles", tags=["授权-角色"])


class PermissionIds(BaseModel):
    permission_ids: list[int] = []


def _get_role(db: Session, role_id: int) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


@router.get("", response_model=list[RoleOut], summary="角色列表")
def list_roles(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("role:read")),
) -> list[RoleOut]:
    rows = db.execute(select(Role).order_by(Role.id)).scalars().all()
    return [RoleOut.model_validate(r) for r in rows]


@router.post("", response_model=RoleDetailOut, status_code=201, summary="创建角色")
def create_role(
    payload: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("role:write")),
) -> RoleDetailOut:
    if db.execute(select(Role).where(Role.code == payload.code)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="角色编码已存在")
    role = Role(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        application_id=payload.application_id,
    )
    if payload.permission_ids:
        role.permissions = list(
            db.execute(select(Permission).where(Permission.id.in_(payload.permission_ids))).scalars()
        )
    db.add(role)
    db.commit()
    db.refresh(role)
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="role_create",
        actor_id=actor.id, actor_username=actor.username,
        target_type="role", target_id=role.id, target_name=role.code, request=request,
    )
    return RoleDetailOut.model_validate(role)


@router.get("/{role_id}", response_model=RoleDetailOut, summary="角色详情")
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("role:read")),
) -> RoleDetailOut:
    return RoleDetailOut.model_validate(_get_role(db, role_id))


@router.put("/{role_id}", response_model=RoleDetailOut, summary="更新角色")
def update_role(
    role_id: int,
    payload: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("role:write")),
) -> RoleDetailOut:
    role = _get_role(db, role_id)
    data = payload.model_dump(exclude_unset=True)
    permission_ids = data.pop("permission_ids", None)
    for key, value in data.items():
        setattr(role, key, value)
    if permission_ids is not None:
        role.permissions = list(
            db.execute(select(Permission).where(Permission.id.in_(permission_ids))).scalars()
        )
    db.commit()
    db.refresh(role)
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="更新角色",
        actor_id=actor.id, actor_username=actor.username,
        target_type="role", target_id=role.id, target_name=role.name, request=request,
    )
    return RoleDetailOut.model_validate(role)


@router.delete("/{role_id}", response_model=Message, summary="删除角色")
def delete_role(
    role_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("role:delete")),
) -> Message:
    role = _get_role(db, role_id)
    if role.is_builtin:
        raise HTTPException(status_code=400, detail="内置角色不可删除")
    code = role.code
    db.delete(role)
    db.commit()
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="删除角色",
        actor_id=actor.id, actor_username=actor.username,
        target_type="role", target_id=role_id, target_name=role.name, request=request,
    )
    return Message(message="角色已删除")


@router.post("/{role_id}/permissions", response_model=Message, summary="设置角色权限（覆盖）")
def set_role_permissions(
    role_id: int,
    payload: PermissionIds,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("role:write")),
) -> Message:
    role = _get_role(db, role_id)
    if role.code == "super-admin":
        raise HTTPException(status_code=400, detail="超级管理员拥有系统全部权限，无需且不可修改")
    role.permissions = list(
        db.execute(select(Permission).where(Permission.id.in_(payload.permission_ids))).scalars()
    )
    db.commit()
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="设置角色权限",
        actor_id=actor.id, actor_username=actor.username,
        target_type="role", target_id=role.id, target_name=role.name,
        detail={"permission_ids": payload.permission_ids}, request=request,
    )
    return Message(message="角色权限已更新")
