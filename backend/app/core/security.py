"""安全原语：密码哈希（bcrypt）、JWT 签发/校验、TOTP。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt
import pyotp

from app.core.config import settings

# ── 密码哈希 ────────────────────────────────────────────────────
_BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── 密码策略 ────────────────────────────────────────────────────
def validate_password_strength(password: str) -> tuple[bool, str]:
    """返回 (是否合规, 原因)。策略：长度 + 大小写 + 数字 + 符号。"""
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        return False, f"密码长度至少 {settings.PASSWORD_MIN_LENGTH} 位"
    if not re.search(r"[a-z]", password):
        return False, "密码需包含小写字母"
    if not re.search(r"[A-Z]", password):
        return False, "密码需包含大写字母"
    if not re.search(r"\d", password):
        return False, "密码需包含数字"
    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "密码需包含特殊字符"
    return True, ""


# ── JWT ────────────────────────────────────────────────────────
def _create_token(subject: str, token_type: str, expires_delta: timedelta, **claims: Any) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        **claims,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, **claims: Any) -> str:
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        **claims,
    )


def create_refresh_token(subject: str, **claims: Any) -> str:
    return _create_token(
        subject,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        **claims,
    )


def create_mfa_token(subject: str) -> str:
    """登录第一步通过、等待 TOTP 校验用的短时效令牌。"""
    return _create_token(subject, "mfa", timedelta(minutes=5))


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        return None


# ── TOTP ───────────────────────────────────────────────────────
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(secret: str, username: str, issuer: Optional[str] = None) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=username, issuer_name=issuer or settings.APP_NAME
    )


def verify_totp(secret: str, code: str, valid_window: int = 1) -> bool:
    if not secret or not code:
        return False
    try:
        return pyotp.TOTP(secret).verify(code.strip().replace(" ", ""), valid_window=valid_window)
    except Exception:
        return False
