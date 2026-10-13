"""密码托管路由：密钥条目、版本、取值、轮换。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.enums import AuditCategory
from app.models.user import User
from app.models.vault import Secret
from app.schemas.common import Message, Page
from app.schemas.vault import (
    RotateResult,
    SecretCreate,
    SecretOut,
    SecretUpdate,
    SecretValueIn,
    SecretValueOut,
    SecretVersionOut,
)
from app.services import audit_service, rotation_service
from app.services.rbac_service import user_has_permission
from app.services.secret_service import (
    masked_view,
    read_value,
    refresh_next_rotation,
    write_version,
)

router = APIRouter(prefix="/secrets", tags=["密码托管"])


def _get_secret(db: Session, secret_id: int) -> Secret:
    secret = db.get(Secret, secret_id)
    if secret is None:
        raise HTTPException(status_code=404, detail="密钥不存在")
    return secret


@router.get("", response_model=Page[SecretOut], summary="密钥列表")
def list_secrets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    category: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("secret:read")),
) -> Page[SecretOut]:
    stmt = select(Secret)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Secret.name.ilike(like) | Secret.path.ilike(like))
    if category:
        stmt = stmt.where(Secret.category == category)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        db.execute(stmt.order_by(Secret.id.desc()).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=[SecretOut.model_validate(s) for s in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=SecretOut, status_code=201, summary="创建密钥")
def create_secret(
    payload: SecretCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("secret:write")),
) -> SecretOut:
    if db.execute(select(Secret).where(Secret.path == payload.path)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="密钥路径已存在")
    secret = Secret(**payload.model_dump(exclude={"data"}))
    db.add(secret)
    db.flush()
    write_version(db, secret, payload.data, created_by=actor.username, comment="create")
    db.refresh(secret)
    audit_service.record(
        db, category=AuditCategory.VAULT, action="创建密钥",
        actor_id=actor.id, actor_username=actor.username,
        target_type="secret", target_id=secret.id, target_name=secret.path, request=request,
    )
    return SecretOut.model_validate(secret)


@router.get("/{secret_id}", response_model=SecretOut, summary="密钥详情")
def get_secret(
    secret_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("secret:read")),
) -> SecretOut:
    return SecretOut.model_validate(_get_secret(db, secret_id))


@router.put("/{secret_id}", response_model=SecretOut, summary="更新密钥元数据/轮换配置")
def update_secret(
    secret_id: int,
    payload: SecretUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("secret:write")),
) -> SecretOut:
    secret = _get_secret(db, secret_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(secret, key, value)
    refresh_next_rotation(secret)
    db.commit()
    db.refresh(secret)
    audit_service.record(
        db, category=AuditCategory.VAULT, action="更新密钥",
        actor_id=actor.id, actor_username=actor.username,
        target_type="secret", target_id=secret.id, target_name=secret.path, request=request,
    )
    return SecretOut.model_validate(secret)


@router.delete("/{secret_id}", response_model=Message, summary="删除密钥")
def delete_secret(
    secret_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("secret:delete")),
) -> Message:
    secret = _get_secret(db, secret_id)
    path = secret.path
    db.delete(secret)
    db.commit()
    audit_service.record(
        db, category=AuditCategory.VAULT, action="删除密钥",
        actor_id=actor.id, actor_username=actor.username,
        target_type="secret", target_id=secret_id, target_name=path, request=request,
    )
    return Message(message="密钥已删除")


@router.get("/{secret_id}/value", response_model=SecretValueOut, summary="读取密钥值")
def get_secret_value(
    secret_id: int,
    version: int | None = None,
    reveal: bool = False,
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("secret:read")),
) -> SecretValueOut:
    secret = _get_secret(db, secret_id)
    try:
        used_version, data = read_value(db, secret, version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    masked = masked_view(data)
    can_reveal = reveal and user_has_permission(db, user, "secret:reveal")
    if can_reveal:
        audit_service.record(
            db, category=AuditCategory.VAULT, action="查看密钥明文",
            actor_id=user.id, actor_username=user.username,
            target_type="secret", target_id=secret.id, target_name=secret.path,
            detail={"version": used_version}, request=request,
        )
        return SecretValueOut(path=secret.path, version=used_version, data=data, masked=masked)
    return SecretValueOut(path=secret.path, version=used_version, data=masked, masked=masked)


@router.post("/{secret_id}/value", response_model=SecretOut, summary="写入新版本")
def set_secret_value(
    secret_id: int,
    payload: SecretValueIn,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("secret:write")),
) -> SecretOut:
    secret = _get_secret(db, secret_id)
    write_version(db, secret, payload.data, created_by=actor.username, comment=payload.comment or "manual update")
    db.refresh(secret)
    audit_service.record(
        db, category=AuditCategory.VAULT, action="更新密钥内容",
        actor_id=actor.id, actor_username=actor.username,
        target_type="secret", target_id=secret.id, target_name=secret.path, request=request,
    )
    return SecretOut.model_validate(secret)


@router.get("/{secret_id}/versions", response_model=list[SecretVersionOut], summary="版本历史")
def list_versions(
    secret_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("secret:read")),
) -> list[SecretVersionOut]:
    secret = _get_secret(db, secret_id)
    return [SecretVersionOut.model_validate(v) for v in secret.versions]


@router.post("/{secret_id}/rotate", response_model=RotateResult, summary="手动轮换")
def rotate_secret(
    secret_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("secret:rotate")),
) -> RotateResult:
    secret = _get_secret(db, secret_id)
    ok, version, msg = rotation_service.rotate_secret(db, secret, actor=actor.username, force=True)
    audit_service.record(
        db,
        category=AuditCategory.VAULT,
        action="轮换密钥",
        result="success" if ok else "failure",
        actor_id=actor.id,
        actor_username=actor.username,
        target_type="secret",
        target_id=secret.id,
        target_name=secret.path,
        message=msg,
        request=request,
    )
    return RotateResult(path=secret.path, success=ok, new_version=version, message=msg)
