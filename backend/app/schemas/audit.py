"""审计日志 Schema。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.common import ORMModel


class AuditOut(ORMModel):
    id: int
    timestamp: datetime
    category: str
    action: str
    result: str
    actor_id: Optional[int]
    actor_username: Optional[str]
    actor_ip: Optional[str]
    user_agent: Optional[str]
    target_type: Optional[str]
    target_id: Optional[int]
    target_name: Optional[str]
    device_type: Optional[str] = None
    connect_tool: Optional[str] = None
    log_file_path: Optional[str] = None
    has_log_content: bool = False
    message: Optional[str]
    detail: Optional[Any]
    request_id: Optional[str]


class AuditQuery(BaseModel):
    category: Optional[str] = None
    result: Optional[str] = None
    actor_username: Optional[str] = None
    action: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class AuditStats(BaseModel):
    total: int
    success: int
    failure: int
    by_category: dict[str, int]
    by_day: list[dict[str, Any]]
