"""审计服务：统一写入审计日志，供所有模块调用。"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import AuditCategory, AuditResult


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    for header_name in ("x-forwarded-for", "x-real-ip"):
        raw = request.headers.get(header_name)
        if raw:
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            for p in parts:
                if p not in ("127.0.0.1", "::1", "localhost"):
                    return p
            if parts:
                return parts[0]
    return request.client.host if request.client else None


def record(
    db: Session,
    *,
    category: AuditCategory | str,
    action: str,
    result: AuditResult | str = AuditResult.SUCCESS,
    actor_id: Optional[int] = None,
    actor_username: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
    target_name: Optional[str] = None,
    message: Optional[str] = None,
    detail: Optional[Any] = None,
    request: Optional[Request] = None,
    user_agent: Optional[str] = None,
    commit: bool = True,
) -> AuditLog:
    cat = category.value if isinstance(category, AuditCategory) else category
    res = result.value if isinstance(result, AuditResult) else result
    log = AuditLog(
        category=cat,
        action=action,
        result=res,
        actor_id=actor_id,
        actor_username=actor_username,
        actor_ip=client_ip(request),
        user_agent=user_agent or (request.headers.get("user-agent") if request else None),
        target_type=target_type,
        target_id=target_id,
        target_name=target_name,
        message=message,
        detail=detail,
        request_id=(request.headers.get("x-request-id") if request else None),
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
    else:
        db.flush()
    return log
