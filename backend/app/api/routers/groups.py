"""账号路由：用户组管理。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.enums import AuditCategory
from app.models.user import Group, User
from app.schemas.common import Message
from app.schemas.user import GroupCreate, GroupMembers, GroupOut, GroupUpdate, UserOut
from app.services import audit_service

router = APIRouter(prefix="/groups", tags=["账号-用户组"])


def _get_group(db: Session, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="用户组不存在")
    return group


@router.get("", response_model=list[GroupOut], summary="用户组列表")
def list_groups(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("group:read")),
) -> list[GroupOut]:
    rows = db.execute(select(Group).order_by(Group.id)).scalars().all()
    return [GroupOut.model_validate(g) for g in rows]


@router.post("", response_model=GroupOut, status_code=201, summary="创建用户组")
def create_group(
    payload: GroupCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("group:write")),
) -> GroupOut:
    if db.execute(select(Group).where(Group.code == payload.code)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户组编码已存在")
    group = Group(**payload.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="创建用户组",
        actor_id=actor.id, actor_username=actor.username,
        target_type="group", target_id=group.id, target_name=group.name, request=request,
    )
    return GroupOut.model_validate(group)


@router.put("/{group_id}", response_model=GroupOut, summary="更新用户组")
def update_group(
    group_id: int,
    payload: GroupUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("group:write")),
) -> GroupOut:
    group = _get_group(db, group_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, key, value)
    db.commit()
    db.refresh(group)
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="更新用户组",
        actor_id=actor.id, actor_username=actor.username,
        target_type="group", target_id=group.id, target_name=group.name, request=request,
    )
    return GroupOut.model_validate(group)


@router.delete("/{group_id}", response_model=Message, summary="删除用户组")
def delete_group(
    group_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("group:delete")),
) -> Message:
    group = _get_group(db, group_id)
    code = group.code
    db.delete(group)
    db.commit()
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="删除用户组",
        actor_id=actor.id, actor_username=actor.username,
        target_type="group", target_id=group_id, target_name=name, request=request,
    )
    return Message(message="用户组已删除")


@router.get("/{group_id}/members", response_model=list[UserOut], summary="组成员")
def group_members(
    group_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("group:read")),
) -> list[UserOut]:
    group = _get_group(db, group_id)
    return [UserOut.model_validate(u) for u in group.users]


@router.post("/{group_id}/members", response_model=Message, summary="设置组成员（覆盖）")
def set_group_members(
    group_id: int,
    payload: GroupMembers,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("group:write")),
) -> Message:
    group = _get_group(db, group_id)
    group.users = list(db.execute(select(User).where(User.id.in_(payload.user_ids))).scalars())
    db.commit()
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="更新组成员",
        actor_id=actor.id, actor_username=actor.username,
        target_type="group", target_id=group.id, target_name=group.name,
        detail={"user_ids": payload.user_ids}, request=request,
    )
    return Message(message="组成员已更新")


@router.delete("/{group_id}/members/{user_id}", response_model=Message, summary="移除组成员")
def remove_group_member(
    group_id: int,
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("group:write")),
) -> Message:
    group = _get_group(db, group_id)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user in group.users:
        group.users.remove(user)
        db.commit()
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="移除组成员",
        actor_id=actor.id, actor_username=actor.username,
        target_type="group", target_id=group.id, target_name=group.name,
        detail={"removed_user_id": user_id}, request=request,
    )
    return Message(message="成员已移除")
