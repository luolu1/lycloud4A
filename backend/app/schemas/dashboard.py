"""仪表盘统计 Schema。"""
from typing import Any

from pydantic import BaseModel


class DashboardStats(BaseModel):
    user_total: int
    user_active: int
    user_disabled: int
    app_total: int
    role_total: int
    policy_total: int
    secret_total: int
    secret_rotation_due: int
    login_today: int
    login_failed_today: int
    audit_total: int
    login_trend: list[dict[str, Any]] = []
    category_distribution: list[dict[str, Any]] = []
    recent_audits: list[dict[str, Any]] = []
    mfa_enabled_rate: float = 0.0
