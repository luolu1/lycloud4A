"""账号路由：组织架构（树形）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.enums import AuditCategory
from app.models.org import Organization
from app.models.user import User as UserModel
from app.schemas.common import Message
from app.schemas.org import OrgCreate, OrgOut, OrgTree, OrgUpdate
from app.services import audit_service

router = APIRouter(prefix="/orgs", tags=["账号-组织"])


def _get_org(db: Session, org_id: int) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="组织不存在")
    return org


@router.get("", response_model=list[OrgOut], summary="组织列表")
def list_orgs(
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_permission("org:read")),
) -> list[OrgOut]:
    rows = db.execute(select(Organization).order_by(Organization.sort_order, Organization.id)).scalars().all()
    return [OrgOut.model_validate(o) for o in rows]


@router.get("/tree", response_model=list[OrgTree], summary="组织树")
def org_tree(
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_permission("org:read")),
) -> list[OrgTree]:
    rows = db.execute(select(Organization).order_by(Organization.sort_order, Organization.id)).scalars().all()
    nodes: dict[int, OrgTree] = {o.id: OrgTree(**OrgOut.model_validate(o).model_dump(), children=[]) for o in rows}
    roots: list[OrgTree] = []
    for o in rows:
        node = nodes[o.id]
        if o.parent_id and o.parent_id in nodes:
            nodes[o.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


@router.post("", response_model=OrgOut, status_code=201, summary="创建组织")
def create_org(
    payload: OrgCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: UserModel = Depends(require_permission("org:write")),
) -> OrgOut:
    if db.execute(select(Organization).where(Organization.code == payload.code)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="组织编码已存在")
    if payload.parent_id and db.get(Organization, payload.parent_id) is None:
        raise HTTPException(status_code=400, detail="上级组织不存在")
    org = Organization(**payload.model_dump())
    db.add(org)
    db.commit()
    db.refresh(org)
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="创建组织",
        actor_id=actor.id, actor_username=actor.username,
        target_type="org", target_id=org.id, target_name=org.name, request=request,
    )
    return OrgOut.model_validate(org)


@router.put("/{org_id}", response_model=OrgOut, summary="更新组织")
def update_org(
    org_id: int,
    payload: OrgUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: UserModel = Depends(require_permission("org:write")),
) -> OrgOut:
    org = _get_org(db, org_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("parent_id") == org_id:
        raise HTTPException(status_code=400, detail="上级组织不能是自己")
    for key, value in data.items():
        setattr(org, key, value)
    db.commit()
    db.refresh(org)
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="更新组织",
        actor_id=actor.id, actor_username=actor.username,
        target_type="org", target_id=org.id, target_name=org.name, request=request,
    )
    return OrgOut.model_validate(org)


@router.delete("/{org_id}", response_model=Message, summary="删除组织")
def delete_org(
    org_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: UserModel = Depends(require_permission("org:delete")),
) -> Message:
    org = _get_org(db, org_id)
    children = db.scalar(select(func.count()).select_from(Organization).where(Organization.parent_id == org_id))
    if children:
        raise HTTPException(status_code=400, detail="存在下级组织，无法删除")
    users = db.scalar(select(func.count()).select_from(UserModel).where(UserModel.org_id == org_id))
    if users:
        raise HTTPException(status_code=400, detail="组织下存在用户，无法删除")
    code = org.code
    db.delete(org)
    db.commit()
    audit_service.record(
        db, category=AuditCategory.ACCOUNT, action="删除组织",
        actor_id=actor.id, actor_username=actor.username,
        target_type="org", target_id=org_id, target_name=org.name, request=request,
    )
    return Message(message="组织已删除")
