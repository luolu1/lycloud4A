"""密码托管加密层：Fernet 对称加密（AES-128-CBC + HMAC）。

主密钥优先取 VAULT_MASTER_KEY；未配置时（仅开发环境）从 SECRET_KEY 派生并告警。
生产环境请通过 KMS/文件权限保护主密钥。
"""
from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

log = logging.getLogger("4a.crypto")


def _derive_fernet_key(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _load_fernet() -> Fernet:
    key = settings.VAULT_MASTER_KEY.strip()
    if key:
        return Fernet(key.encode("utf-8"))
    if settings.VAULT_KEY_FAIL_MODE == "fail" and settings.ENVIRONMENT == "production":
        raise RuntimeError(
            "VAULT_MASTER_KEY 未配置：生产环境拒绝以派生密钥启动密码托管。"
        )
    log.warning("VAULT_MASTER_KEY 未配置，正从 SECRET_KEY 派生密钥（仅限开发/测试环境）")
    return Fernet(_derive_fernet_key(settings.SECRET_KEY))


_fernet = _load_fernet()


def encrypt(plaintext: str) -> str:
    """明文 → 密文（base64 字符串）。"""
    return _fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """密文 → 明文；解密失败抛出 ValueError。"""
    try:
        return _fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("密文解密失败：主密钥不匹配或数据损坏") from exc


def mask(secret: str, keep: int = 2) -> str:
    """脱敏展示：只保留首尾少量字符。"""
    if not secret:
        return ""
    if len(secret) <= keep * 2:
        return "*" * len(secret)
    return f"{secret[:keep]}{'*' * 6}{secret[-keep:]}"
