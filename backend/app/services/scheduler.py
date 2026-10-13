"""密码轮换调度器：APScheduler 定时扫描到期密钥并轮换。"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.rotation_service import due_secrets, rotate_secret

log = logging.getLogger("4a.scheduler")
_scheduler: BackgroundScheduler | None = None


def run_rotation_scan() -> None:
    db = SessionLocal()
    try:
        due = due_secrets(db)
        if not due:
            return
        log.info("rotation scan: %d secret(s) due", len(due))
        for secret in due:
            ok, version, msg = rotate_secret(db, secret, actor="scheduler")
            log.info("rotate %s: ok=%s version=%s msg=%s", secret.path, ok, version, msg)
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if not settings.ROTATION_SCHEDULER_ENABLED or _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        run_rotation_scan,
        CronTrigger.from_crontab(settings.ROTATION_CHECK_CRON),
        id="rotation-scan",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    log.info("rotation scheduler started: cron=%s", settings.ROTATION_CHECK_CRON)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
