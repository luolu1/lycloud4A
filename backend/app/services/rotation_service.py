"""密码自动轮换服务：生成新密码、驱动目标系统改密、回写新版本。

设计目标（对应 iam.md 的轮换方案）：
- 先改目标系统，改密成功才写回 Vault 新版本；失败则保留旧值并记录错误。
- 目标系统适配器按 rotation_type 分派，缺少驱动/连接失败时给出明确错误。
"""
from __future__ import annotations

import logging
import secrets
import string
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt
from app.models.vault import Secret
from app.services.secret_service import read_value, write_version

log = logging.getLogger("4a.rotation")

_PW_ALPHABET = string.ascii_letters + string.digits + "!@#%^*-_=+"


def generate_password(length: int = 24) -> str:
    while True:
        pw = "".join(secrets.choice(_PW_ALPHABET) for _ in range(length))
        if (any(c.islower() for c in pw) and any(c.isupper() for c in pw)
                and any(c.isdigit() for c in pw) and any(not c.isalnum() for c in pw)):
            return pw


def _split_target(target: Optional[str]) -> tuple[str, int]:
    if not target or ":" not in target:
        raise ValueError(f"rotate_target 需为 host:port 格式，当前为 {target!r}")
    host, port = target.rsplit(":", 1)
    return host, int(port)


def _rotate_mysql(target: str, username: str, old: str, new: str, cfg: dict[str, Any] | None) -> None:
    import pymysql  # 可选依赖

    host, port = _split_target(target)
    conn = pymysql.connect(host=host, port=port, user=username, password=old)
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER USER %s@'%%' IDENTIFIED BY %s", (username, new))
        conn.commit()
    finally:
        conn.close()
    pymysql.connect(host=host, port=port, user=username, password=new).close()


def _rotate_postgres(target: str, username: str, old: str, new: str, cfg: dict[str, Any] | None) -> None:
    import psycopg2  # 可选依赖

    host, port = _split_target(target)
    conn = psycopg2.connect(host=host, port=port, user=username, password=old, dbname=(cfg or {}).get("dbname", "postgres"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(f"ALTER USER {username} WITH PASSWORD %s", (new,))
    finally:
        conn.close()
    psycopg2.connect(host=host, port=port, user=username, password=new, dbname=(cfg or {}).get("dbname", "postgres")).close()


def _rotate_redis(target: str, username: str, old: str, new: str, cfg: dict[str, Any] | None) -> None:
    import redis  # 可选依赖

    host, port = _split_target(target)
    r = redis.Redis(host=host, port=port, password=old or None)
    r.config_set("requirepass", new)
    r.execute_command("CONFIG", "REWRITE")
    redis.Redis(host=host, port=port, password=new).ping()


def _rotate_ssh_local(target: str, username: str, old: str, new: str, cfg: dict[str, Any] | None) -> None:
    import paramiko  # 可选依赖

    host, port = _split_target(target)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(host, port=port, username=username, password=old, timeout=10)
    _, out, err = client.exec_command(f"echo '{username}:{new}' | sudo chpasswd")
    rc = out.channel.recv_exit_status()
    client.close()
    if rc != 0:
        raise RuntimeError(err.read().decode() or "chpasswd 失败")


def _rotate_api(target: str, username: str, old: str, new: str, cfg: dict[str, Any] | None) -> None:
    import httpx  # 已有依赖

    cfg = cfg or {}
    method = cfg.get("method", "POST").upper()
    headers = cfg.get("headers", {})
    body = {"username": username, "old_password": old, "new_password": new, **cfg.get("extra_body", {})}
    resp = httpx.request(method, target, json=body, headers=headers, timeout=15)
    resp.raise_for_status()


def _rotate_manual(target: str, username: str, old: str, new: str, cfg: dict[str, Any] | None) -> None:
    """不做外部改密，仅在 Vault 侧生成新版本（应用侧自行拉取）。"""
    return None


HANDLERS: dict[str, Callable[[str, str, str, str, Optional[dict]], None]] = {
    "manual": _rotate_manual,
    "mysql": _rotate_mysql,
    "postgres": _rotate_postgres,
    "redis": _rotate_redis,
    "ssh_local": _rotate_ssh_local,
    "api": _rotate_api,
}


def rotate_secret(
    db: Session,
    secret: Secret,
    *,
    actor: Optional[str] = None,
    force: bool = False,
    new_password: Optional[str] = None,
) -> tuple[bool, int, str]:
    """执行一次轮换。返回 (成功, 新版本号, 消息)。"""
    handler = HANDLERS.get(secret.rotation_type)
    if handler is None:
        msg = f"不支持的轮换类型：{secret.rotation_type}"
        secret.last_rotation_status = "failed"
        secret.last_rotation_error = msg
        db.commit()
        return False, secret.current_version, msg

    _, data = read_value(db, secret)
    old_password = data.get("password", "")
    new_password = new_password or generate_password()
    username = secret.rotate_username or data.get("username", "")

    try:
        handler(secret.rotate_target or "", username, old_password, new_password,
                secret.rotate_api_config or {})
    except ImportError as exc:
        msg = f"缺少轮换所需依赖：{exc.name}"
        secret.last_rotation_status = "failed"
        secret.last_rotation_error = msg
        db.commit()
        log.error("rotate %s failed: %s", secret.path, msg)
        return False, secret.current_version, msg
    except Exception as exc:  # 目标系统改密失败：保留旧值
        msg = f"目标系统改密失败：{exc}"
        secret.last_rotation_status = "failed"
        secret.last_rotation_error = msg
        db.commit()
        log.error("rotate %s failed: %s", secret.path, msg)
        return False, secret.current_version, msg

    data["password"] = new_password
    data["rotated_at"] = datetime.now(timezone.utc).isoformat()
    version = write_version(db, secret, data, created_by=actor, comment="auto rotation", rotated=True)
    log.info("rotated %s -> v%s", secret.path, version.version)
    return True, version.version, "轮换成功"


def due_secrets(db: Session) -> list[Secret]:
    now = datetime.now(timezone.utc)
    stmt = select(Secret).where(
        Secret.rotation_enabled.is_(True),
        Secret.status.is_(True),
        Secret.next_rotation_at.isnot(None),
        Secret.next_rotation_at <= now,
    )
    return list(db.execute(stmt).scalars().all())
