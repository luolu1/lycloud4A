"""授权路由：访问策略。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.enums import AuditCategory
from app.models.policy import AccessPolicy
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.policy import (
    PolicyCreate,
    PolicyEvaluateRequest,
    PolicyEvaluateResult,
    PolicyOut,
    PolicyUpdate,
)
from app.services import audit_service, policy_service

router = APIRouter(prefix="/policies", tags=["授权-策略"])


def _get_policy(db: Session, policy_id: int) -> AccessPolicy:
    policy = db.get(AccessPolicy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="策略不存在")
    return policy


@router.get("", response_model=Page[PolicyOut], summary="策略列表")
def list_policies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("policy:read")),
) -> Page[PolicyOut]:
    stmt = select(AccessPolicy)
    if q:
        stmt = stmt.where(AccessPolicy.name.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        db.execute(stmt.order_by(AccessPolicy.priority, AccessPolicy.id).offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=[PolicyOut.model_validate(p) for p in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=PolicyOut, status_code=201, summary="创建策略")
def create_policy(
    payload: PolicyCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("policy:write")),
) -> PolicyOut:
    if db.execute(select(AccessPolicy).where(AccessPolicy.name == payload.name)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="策略名称已存在")
    policy = AccessPolicy(**payload.model_dump(), created_by=actor.username)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="创建策略",
        actor_id=actor.id, actor_username=actor.username,
        target_type="policy", target_id=policy.id, target_name=policy.name, request=request,
    )
    return PolicyOut.model_validate(policy)


@router.post("/evaluate", response_model=PolicyEvaluateResult, summary="策略求值")
def evaluate_policy(
    payload: PolicyEvaluateRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("policy:read")),
) -> PolicyEvaluateResult:
    allowed, matched, reason = policy_service.evaluate(
        db,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        action=payload.action,
        context={"ip": audit_service.client_ip(request)},
    )
    return PolicyEvaluateResult(allowed=allowed, matched_policy=matched, reason=reason)


@router.put("/{policy_id}", response_model=PolicyOut, summary="更新策略")
def update_policy(
    policy_id: int,
    payload: PolicyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("policy:write")),
) -> PolicyOut:
    policy = _get_policy(db, policy_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, key, value)
    db.commit()
    db.refresh(policy)
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="更新策略",
        actor_id=actor.id, actor_username=actor.username,
        target_type="policy", target_id=policy.id, target_name=policy.name, request=request,
    )
    return PolicyOut.model_validate(policy)


@router.delete("/{policy_id}", response_model=Message, summary="删除策略")
def delete_policy(
    policy_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("policy:delete")),
) -> Message:
    policy = _get_policy(db, policy_id)
    name = policy.name
    db.delete(policy)
    db.commit()
    audit_service.record(
        db, category=AuditCategory.AUTHZ, action="删除策略",
        actor_id=actor.id, actor_username=actor.username,
        target_type="policy", target_id=policy_id, target_name=name, request=request,
    )
    return Message(message="策略已删除")
