"""设备连接：一次性票据签发与解析，凭证解密后交由本地客户端 lycloud4A 启动工具。"""
from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock
from typing import Optional
from uuid import uuid4

from app.models.application import Application
from app.models.launch_tool import LaunchTool
from app.services.device_service import _resolve_host_port, reveal_credential

TICKET_TTL_SECONDS = 60


@dataclass
class _Ticket:
    device_id: int
    tool_id: int
    user_id: int
    actor_ip: Optional[str]
    expires_at: float
    audit_id: Optional[int] = None
    username: Optional[str] = None
    session_id: Optional[str] = None
    server_log_path: Optional[str] = None


_TICKETS: dict[str, _Ticket] = {}
_LOCK = Lock()


def issue_ticket(device_id: int, tool_id: int, user_id: int, actor_ip: Optional[str]) -> str:
    ticket = uuid4().hex
    with _LOCK:
        now = time.time()
        for k in [k for k, v in _TICKETS.items() if v.expires_at < now]:
            _TICKETS.pop(k, None)
        _TICKETS[ticket] = _Ticket(
            device_id=device_id, tool_id=tool_id, user_id=user_id,
            actor_ip=actor_ip,
            expires_at=now + TICKET_TTL_SECONDS,
        )
    return ticket


def attach_audit_info(ticket: str, audit_id: int, username: str, session_id: str, server_log_path: str) -> None:
    with _LOCK:
        entry = _TICKETS.get(ticket)
        if entry:
            entry.audit_id = audit_id
            entry.username = username
            entry.session_id = session_id
            entry.server_log_path = server_log_path


def consume_ticket(ticket: str) -> Optional[_Ticket]:
    with _LOCK:
        entry = _TICKETS.pop(ticket, None)
    if entry is None or entry.expires_at < time.time():
        return None
    return entry


def resolve(app: Application, tool: LaunchTool, entry: Optional[_Ticket] = None) -> dict:
    host, port = _resolve_host_port(app)
    credential = reveal_credential(app)
    return {
        "device_id": app.id,
        "device_name": app.name,
        "host": host or "",
        "port": port,
        "protocol": app.protocol,
        "url": app.url or "",
        "login_username": app.login_username,
        "credential_type": app.credential_type,
        "credential": credential,
        "tool_kind": tool.kind,
        "tool_name": tool.name,
        "exe_path": tool.exe_path,
        "username": entry.username if entry else None,
        "audit_id": entry.audit_id if entry else None,
        "session_id": entry.session_id if entry else None,
        "upload_url": "/api/v1/apps/connect/upload-log",
    }
