"""仪表盘路由：平台概览统计。"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.enums import UserStatus
from app.models.policy import AccessPolicy
from app.models.rbac import Role
from app.models.user import User
from app.models.vault import Secret
from app.schemas.dashboard import DashboardStats
from app.services import rotation_service

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


def _count(db: Session, model, *conditions) -> int:
    stmt = select(func.count()).select_from(model)
    if conditions:
        stmt = stmt.where(*conditions)
    return db.scalar(stmt) or 0


@router.get("/stats", response_model=DashboardStats, summary="平台概览")
def dashboard_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("dashboard:read")),
) -> DashboardStats:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = (now - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)

    user_total = _count(db, User)
    user_active = _count(db, User, User.status == UserStatus.ACTIVE.value)
    user_disabled = _count(db, User, User.status == UserStatus.DISABLED.value)
    mfa_count = _count(db, User, User.mfa_enabled.is_(True))

    login_today = _count(
        db, AuditLog,
        AuditLog.category == "auth", AuditLog.action == "login",
        AuditLog.result == "success", AuditLog.timestamp >= today_start,
    )
    login_failed_today = _count(
        db, AuditLog,
        AuditLog.category == "auth", AuditLog.result == "failure",
        AuditLog.timestamp >= today_start,
    )

    week_logs = db.execute(select(AuditLog).where(AuditLog.timestamp >= week_start)).scalars().all()
    login_trend: Counter[str] = Counter()
    for log in week_logs:
        if log.category == "auth" and log.action == "login":
            ts = log.timestamp if log.timestamp.tzinfo else log.timestamp.replace(tzinfo=timezone.utc)
            login_trend[ts.date().isoformat()] += 1
    login_trend_list = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date().isoformat()
        login_trend_list.append({"date": day, "count": login_trend.get(day, 0)})

    all_logs = db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc())).scalars().all()
    category_distribution = [
        {"category": cat, "count": count} for cat, count in Counter(l.category for l in all_logs).items()
    ]
    recent_audits = [
        {
            "id": l.id,
            "timestamp": (l.timestamp.isoformat() if l.timestamp else None),
            "category": l.category,
            "action": l.action,
            "result": l.result,
            "actor_username": l.actor_username,
            "target_name": l.target_name,
            "message": l.message,
        }
        for l in all_logs[:5]
    ]

    return DashboardStats(
        user_total=user_total,
        user_active=user_active,
        user_disabled=user_disabled,
        app_total=_count(db, Application),
        role_total=_count(db, Role),
        policy_total=_count(db, AccessPolicy),
        secret_total=_count(db, Secret),
        secret_rotation_due=len(rotation_service.due_secrets(db)),
        login_today=login_today,
        login_failed_today=login_failed_today,
        audit_total=_count(db, AuditLog),
        login_trend=login_trend_list,
        category_distribution=category_distribution,
        recent_audits=recent_audits,
        mfa_enabled_rate=round(mfa_count / user_total * 100, 1) if user_total else 0.0,
    )
