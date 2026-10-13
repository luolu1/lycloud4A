"""设备纳管服务：登录凭证加解密、TCP 连通性探测。"""
from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt
from app.models.application import Application
from app.models.enums import ConnStatus

PROTOCOL_PORTS: dict[str, int] = {
    "ssh": 22,
    "telnet": 23,
    "rdp": 3389,
    "vnc": 5900,
    "sftp": 22,
    "ftp": 21,
    "tacacs": 49,
    "radius": 1812,
    "ldap": 389,
    "oidc": 443,
    "saml": 443,
    "cas": 443,
    "http": 80,
    "https": 443,
    "serial": 0,
    "local": 0,
}


def store_credential(secret_plain: str) -> str:
    return encrypt(secret_plain)


def reveal_credential(app: Application) -> Optional[str]:
    if not app.credential_encrypted:
        return None
    return decrypt(app.credential_encrypted)


def _resolve_host_port(app: Application) -> tuple[Optional[str], Optional[int]]:
    """从 url 解析出可探测的 host:port。

    支持三种写法：带 scheme 的完整 URL（http://host:8080/path）、host:port、裸 host / 网段。
    网段（含 "/" 且非 URL path）无法探测单点，返回端口 None。
    """
    raw = (app.url or "").strip()
    if not raw:
        return None, None

    scheme = ""
    rest = raw
    if "://" in raw:
        scheme, _, rest = raw.partition("://")
        scheme = scheme.lower()

    authority = rest.split("/", 1)[0]

    if scheme == "":
        if "/" in rest:
            return rest.split("/")[0], None
    else:
        if ":" not in authority:
            return authority, PROTOCOL_PORTS.get(scheme) or PROTOCOL_PORTS.get(app.protocol)

    if ":" in authority:
        host, _, port_str = authority.partition(":")
        try:
            return host, int(port_str)
        except ValueError:
            return host, PROTOCOL_PORTS.get(app.protocol)
    return authority, PROTOCOL_PORTS.get(scheme or app.protocol)


def check_connectivity(db: Session, app: Application, *, timeout: float = 3.0) -> tuple[str, Optional[str]]:
    """对设备发起一次 TCP 连通性探测，更新并持久化 conn_status。返回 (状态, 错误信息)。"""
    host, port = _resolve_host_port(app)
    status = ConnStatus.UNKNOWN.value
    error: Optional[str] = None

    if not host:
        status, error = ConnStatus.UNREACHABLE.value, "未配置地址"
    elif port is None or port == 0:
        status, error = ConnStatus.UNREACHABLE.value, "地址为网段或协议无固定端口，无法单点探测"
    else:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                status = ConnStatus.ONLINE.value
        except OSError as exc:
            status, error = ConnStatus.OFFLINE.value, f"{host}:{port} 连接失败：{exc.strerror or exc}"

    app.conn_status = status
    app.last_checked_at = datetime.now(timezone.utc)
    app.last_check_error = (error or "")[:255] or None
    db.commit()
    return status, error
