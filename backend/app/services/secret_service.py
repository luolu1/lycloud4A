"""密码托管服务：加解密存储、版本管理。"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt, mask
from app.models.vault import Secret, SecretVersion

SENSITIVE_KEYS = {"password", "secret", "token", "private_key", "api_key", "passphrase"}


def _next_rotation(secret: Secret) -> Optional[datetime]:
    if not secret.rotation_enabled:
        return None
    base = secret.last_rotated_at or datetime.now(timezone.utc)
    return base + timedelta(days=secret.rotation_interval_days)


def write_version(
    db: Session,
    secret: Secret,
    data: dict[str, str],
    *,
    created_by: Optional[str] = None,
    comment: Optional[str] = None,
    rotated: bool = False,
) -> SecretVersion:
    secret.current_version += 1
    encrypted = encrypt(json.dumps(data, ensure_ascii=False))
    version = SecretVersion(
        secret_id=secret.id,
        version=secret.current_version,
        data_encrypted=encrypted,
        created_by=created_by,
        comment=comment,
        created_at=datetime.now(timezone.utc),
    )
    db.add(version)
    if rotated:
        secret.last_rotated_at = datetime.now(timezone.utc)
        secret.last_rotation_status = "success"
        secret.last_rotation_error = None
    secret.next_rotation_at = _next_rotation(secret)
    db.commit()
    db.refresh(version)
    return version


def read_value(db: Session, secret: Secret, version: Optional[int] = None) -> tuple[int, dict[str, Any]]:
    if version is None:
        stmt = (
            select(SecretVersion)
            .where(SecretVersion.secret_id == secret.id)
            .order_by(SecretVersion.version.desc())
            .limit(1)
        )
    else:
        stmt = select(SecretVersion).where(
            SecretVersion.secret_id == secret.id, SecretVersion.version == version
        )
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        raise ValueError("密钥版本不存在")
    return row.version, json.loads(decrypt(row.data_encrypted))


def masked_view(data: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        if key.lower() in SENSITIVE_KEYS and isinstance(value, str):
            out[key] = mask(value)
        else:
            out[key] = str(value)
    return out


def refresh_next_rotation(secret: Secret) -> None:
    secret.next_rotation_at = _next_rotation(secret)
