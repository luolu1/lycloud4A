"""授权策略服务：策略匹配与求值（Deny 优先，priority 小者优先）。"""
from __future__ import annotations

import ipaddress
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.enums import Effect, SubjectType
from app.models.policy import AccessPolicy
from app.models.user import User


def expand_subjects(db: Session, subject_type: str, subject_id: int) -> list[tuple[str, int]]:
    subjects = [(subject_type, subject_id)]
    if subject_type == SubjectType.USER.value:
        user = db.get(User, subject_id)
        if user:
            subjects += [(SubjectType.GROUP.value, g.id) for g in user.groups]
            subjects += [(SubjectType.ROLE.value, r.id) for r in user.roles]
            if user.org_id:
                subjects.append((SubjectType.ORG.value, user.org_id))
    return subjects


def _match_action(policy: AccessPolicy, action: str) -> bool:
    actions = policy.actions or []
    return "*" in actions or action in actions


def _match_conditions(policy: AccessPolicy, context: dict[str, Any]) -> bool:
    cond = policy.conditions or {}
    if not cond:
        return True
    client_ip = context.get("ip")
    if "ip_range" in cond and client_ip:
        try:
            if ipaddress.ip_address(client_ip) not in ipaddress.ip_network(cond["ip_range"], strict=False):
                return False
        except ValueError:
            return False
    if cond.get("mfa_required") and not context.get("mfa", False):
        return False
    window = cond.get("time_window")
    if window:
        try:
            start, end = window.split("-")
            now_hm = datetime.now(timezone.utc).strftime("%H:%M")
            if not (start <= now_hm <= end):
                return False
        except ValueError:
            return False
    return True


def evaluate(
    db: Session,
    *,
    subject_type: str,
    subject_id: int,
    resource_type: str,
    resource_id: Optional[int],
    action: str,
    context: Optional[dict[str, Any]] = None,
) -> tuple[bool, Optional[str], str]:
    context = context or {}
    subjects = expand_subjects(db, subject_type, subject_id)
    now = datetime.now(timezone.utc)

    stmt = select(AccessPolicy).where(
        AccessPolicy.enabled.is_(True),
        AccessPolicy.resource_type == resource_type,
        or_(AccessPolicy.resource_id.is_(None), AccessPolicy.resource_id == resource_id),
        or_(*[(
            (AccessPolicy.subject_type == st) & (AccessPolicy.subject_id == sid)
        ) for st, sid in subjects]),
    ).order_by(AccessPolicy.priority.asc(), AccessPolicy.id.asc())

    policies = list(db.execute(stmt).scalars().all())
    matched: list[AccessPolicy] = [
        p for p in policies
        if _match_action(p, action) and _match_conditions(p, context)
        and (p.expires_at is None or p.expires_at.replace(tzinfo=timezone.utc) > now)
    ]

    for p in matched:
        if p.effect == Effect.DENY.value:
            return False, p.name, f"命中拒绝策略「{p.name}」(priority={p.priority})"
    for p in matched:
        if p.effect == Effect.ALLOW.value:
            return True, p.name, f"命中允许策略「{p.name}」(priority={p.priority})"
    return False, None, "无匹配策略，默认拒绝"
