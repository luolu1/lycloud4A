"""账号路由：用户管理。"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.security import hash_password, validate_password_strength
from app.models.enums import AuditCategory, UserStatus
from app.models.rbac import Role
from app.models.session import RefreshToken
from app.models.user import Group, User
from app.schemas.common import Message, Page
from app.schemas.user import (
    AssignGroups,
    AssignRoles,
    ResetPassword,
    UserCreate,
    UserDetailOut,
    UserOut,
    UserUpdate,
)
from app.services import audit_service
from app.services.rotation_service import generate_password

router = APIRouter(prefix="/users", tags=["账号-用户"])

_VALID_STATUS = {UserStatus.ACTIVE.value, UserStatus.DISABLED.value, UserStatus.LOCKED.value}


def _get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.get("", response_model=Page[UserOut], summary="用户列表")
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    status: str | None = None,
    org_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("user:read")),
) -> Page[UserOut]:
    stmt = select(User)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(User.username.ilike(like), User.display_name.ilike(like), User.email.ilike(like))
        )
    if status:
        stmt = stmt.where(User.status == status)
    if org_id:
        stmt = stmt.where(User.org_id == org_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        db.execute(stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=[UserOut.model_validate(u) for u in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=UserDetailOut, status_code=201, summary="创建用户")
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("user:write")),
) -> UserDetailOut:
    if db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")
    if payload.email and db.execute(select(User).where(User.email == str(payload.email))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="邮箱已被使用")
    ok, reason = validate_password_strength(payload.password)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)

    user = User(
        username=payload.username,
        display_name=payload.display_name or payload.username,
        email=str(payload.email) if payload.email else None,
        phone=payload.phone,
        employee_no=payload.employee_no,
        title=payload.title,
        org_id=payload.org_id,
        remark=payload.remark,
        password_hash=hash_password(payload.password),
        must_change_password=payload.must_change_password,
        status=UserStatus.ACTIVE.value,
    )
    if payload.role_ids:
        user.roles = list(db.execute(select(Role).where(Role.id.in_(payload.role_ids))).scalars())
    if payload.group_ids:
        user.groups = list(db.execute(select(Group).where(Group.id.in_(payload.group_ids))).scalars())
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="创建用户",
        actor_id=actor.id, actor_username=actor.username,
        target_type="user", target_id=user.id, target_name=user.username, request=request,
    )
    return UserDetailOut.model_validate(user)


@router.get("/{user_id}", response_model=UserDetailOut, summary="用户详情")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("user:read")),
) -> UserDetailOut:
    return UserDetailOut.model_validate(_get_user(db, user_id))


@router.put("/{user_id}", response_model=UserDetailOut, summary="更新用户")
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("user:write")),
) -> UserDetailOut:
    user = _get_user(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    if "email" in data and data["email"]:
        exists = db.execute(
            select(User).where(User.email == str(data["email"]), User.id != user_id)
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(status_code=409, detail="邮箱已被使用")
        data["email"] = str(data["email"])
    if "status" in data and data["status"] not in _VALID_STATUS:
        raise HTTPException(status_code=400, detail="非法的账号状态")
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="更新用户",
        actor_id=actor.id, actor_username=actor.username,
        target_type="user", target_id=user.id, target_name=user.username,
        detail=data, request=request,
    )
    return UserDetailOut.model_validate(user)


@router.delete("/{user_id}", response_model=Message, summary="删除用户")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("user:delete")),
) -> Message:
    if user_id == actor.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    user = _get_user(db, user_id)
    name = user.username
    db.delete(user)
    db.commit()
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="删除用户",
        actor_id=actor.id, actor_username=actor.username,
        target_type="user", target_id=user_id, target_name=name, request=request,
    )
    return Message(message="用户已删除")


@router.post("/{user_id}/reset-password", response_model=Message, summary="重置密码")
def reset_password(
    user_id: int,
    payload: ResetPassword,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("user:reset_password")),
) -> Message:
    user = _get_user(db, user_id)
    temp = payload.new_password or generate_password(16)
    ok, reason = validate_password_strength(temp)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    user.password_hash = hash_password(temp)
    user.must_change_password = True
    user.password_changed_at = datetime.now(timezone.utc)
    for row in db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id)).scalars():
        row.revoked = True
    db.commit()
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="重置密码",
        actor_id=actor.id, actor_username=actor.username,
        target_type="user", target_id=user.id, target_name=user.username, request=request,
    )
    return Message(message=f"密码已重置，临时密码：{temp}")


@router.post("/{user_id}/roles", response_model=Message, summary="分配角色")
def assign_roles(
    user_id: int,
    payload: AssignRoles,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("user:write")),
) -> Message:
    user = _get_user(db, user_id)
    user.roles = list(db.execute(select(Role).where(Role.id.in_(payload.role_ids))).scalars())
    db.commit()
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="分配角色",
        actor_id=actor.id, actor_username=actor.username,
        target_type="user", target_id=user.id, target_name=user.username,
        detail={"role_ids": payload.role_ids}, request=request,
    )
    return Message(message="角色已更新")


@router.post("/{user_id}/groups", response_model=Message, summary="分配用户组")
def assign_groups(
    user_id: int,
    payload: AssignGroups,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("user:write")),
) -> Message:
    user = _get_user(db, user_id)
    user.groups = list(db.execute(select(Group).where(Group.id.in_(payload.group_ids))).scalars())
    db.commit()
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="分配用户组",
        actor_id=actor.id, actor_username=actor.username,
        target_type="user", target_id=user.id, target_name=user.username,
        detail={"group_ids": payload.group_ids}, request=request,
    )
    return Message(message="用户组已更新")


@router.post("/{user_id}/unlock", response_model=Message, summary="解除锁定")
def unlock_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("user:write")),
) -> Message:
    user = _get_user(db, user_id)
    user.locked_until = None
    user.failed_login_count = 0
    if user.status == UserStatus.LOCKED.value:
        user.status = UserStatus.ACTIVE.value
    db.commit()
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="解锁用户",
        actor_id=actor.id, actor_username=actor.username,
        target_type="user", target_id=user.id, target_name=user.username, request=request,
    )
    return Message(message="账号已解锁")
