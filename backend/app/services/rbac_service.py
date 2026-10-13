"""RBAC 服务：解析用户权限集合、鉴权判断。"""
from __future__ import annotations

from typing import Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role
from app.models.user import User


def get_user_permission_codes(db: Session, user: User) -> Set[str]:
    if user.is_superuser:
        rows = db.execute(select(Permission.code)).scalars().all()
        return set(rows) | {"*"}
    codes = db.execute(
        select(Permission.code)
        .join(Role.permissions)
        .join(Role.users)
        .where(User.id == user.id)
    ).scalars().all()
    return set(codes)


def user_has_permission(db: Session, user: User, code: str) -> bool:
    if user.is_superuser:
        return True
    perms = get_user_permission_codes(db, user)
    if "*" in perms or code in perms:
        return True
    resource = code.split(":", 1)[0]
    return f"{resource}:*" in perms
