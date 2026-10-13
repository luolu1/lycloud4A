"""授权路由：权限清单。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.rbac import Permission
from app.models.user import User
from app.schemas.rbac import PermissionOut

router = APIRouter(prefix="/permissions", tags=["授权-权限"])


@router.get("", response_model=list[PermissionOut], summary="权限清单")
def list_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("permission:read")),
) -> list[PermissionOut]:
    rows = db.execute(select(Permission).order_by(Permission.resource, Permission.action)).scalars().all()
    return [PermissionOut.model_validate(p) for p in rows]
