"""审计路由：日志查询与统计。"""
from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.config import settings
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditOut, AuditStats
from app.schemas.common import Page
from app.services.terminal_render import render_terminal

router = APIRouter(prefix="/audits", tags=["审计"])


def _to_audit_out(log: AuditLog) -> AuditOut:
    out = AuditOut.model_validate(log)
    if isinstance(log.detail, dict):
        device_type = log.detail.get("设备类型") or log.detail.get("device_type")
        connect_tool = log.detail.get("连接工具") or log.detail.get("tool") or log.detail.get("tool_name")
        log_file_path = log.detail.get("日志文件路径") or log.detail.get("log_file_path")
        if device_type:
            out.device_type = str(device_type)
        if connect_tool:
            out.connect_tool = str(connect_tool)
        if log_file_path:
            out.log_file_path = str(log_file_path)
            out.has_log_content = True
    return out


@router.get("", response_model=Page[AuditOut], summary="审计日志查询")
def list_audits(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    category: str | None = None,
    result: str | None = None,
    actor_username: str | None = None,
    action: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit:read")),
) -> Page[AuditOut]:
    stmt = select(AuditLog)
    if category:
        stmt = stmt.where(AuditLog.category == category)
    if result:
        stmt = stmt.where(AuditLog.result == result)
    if actor_username:
        stmt = stmt.where(AuditLog.actor_username.ilike(f"%{actor_username}%"))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if start:
        stmt = stmt.where(AuditLog.timestamp >= start)
    if end:
        stmt = stmt.where(AuditLog.timestamp <= end)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        db.execute(stmt.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
                   .offset((page - 1) * page_size).limit(page_size))
        .scalars()
        .all()
    )
    return Page(items=[_to_audit_out(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/{audit_id}/log-content", summary="查看操作审计会话日志内容")
def get_audit_log_content(
    audit_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit:read")),
) -> dict:
    log = db.get(AuditLog, audit_id)
    if not log:
        return {"error": "审计记录不存在", "content": None, "path": None}
    detail = log.detail if isinstance(log.detail, dict) else {}
    file_path = detail.get("日志文件路径") or detail.get("log_file_path")
    if not file_path:
        return {"error": "该条记录无关联操作日志文件", "content": None, "path": None}

    safe_base = os.path.abspath(settings.AUDIT_LOG_DIR)
    abs_path = os.path.abspath(file_path)
    if not abs_path.startswith(safe_base) or not os.path.exists(abs_path):
        return {
            "error": "日志文件尚未上传或文件不存在",
            "path": file_path,
            "content": f"[待客户端上传或文件不存在: {file_path}]",
        }

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(1000000)
        # 渲染成操作者实际看到的文本：既修正历史遗留的乱码，对新日志也是幂等的。
        return {"content": render_terminal(content), "path": file_path, "error": None}
    except Exception as e:
        return {"error": str(e), "path": file_path, "content": None}


@router.get("/stats", response_model=AuditStats, summary="审计统计")
def audit_stats(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit:read")),
) -> AuditStats:
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = db.execute(select(AuditLog).where(AuditLog.timestamp >= window_start)).scalars().all()

    by_category = Counter(r.category for r in rows)
    by_day_counter: Counter[str] = Counter()
    for r in rows:
        ts = r.timestamp if r.timestamp.tzinfo else r.timestamp.replace(tzinfo=timezone.utc)
        by_day_counter[ts.date().isoformat()] += 1

    by_day = []
    for offset in range(days - 1, -1, -1):
        day = (now - timedelta(days=offset)).date().isoformat()
        by_day.append({"date": day, "count": by_day_counter.get(day, 0)})

    return AuditStats(
        total=len(rows),
        success=sum(1 for r in rows if r.result == "success"),
        failure=sum(1 for r in rows if r.result == "failure"),
        by_category=dict(by_category),
        by_day=by_day,
    )
