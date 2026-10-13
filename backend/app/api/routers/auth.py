"""认证路由：登录、MFA、令牌刷新、改密。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.security import (
    create_access_token,
    create_mfa_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    validate_password_strength,
    verify_password,
    verify_totp,
)
from app.models.enums import AuditCategory, AuditResult, UserStatus
from app.models.session import RefreshToken
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResult,
    LogoutRequest,
    MeOut,
    MFADisableRequest,
    MFAEnableRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    RefreshRequest,
    TokenPair,
)
from app.schemas.common import Message
from app.schemas.user import GroupBrief, RoleBrief, UserOut
from app.services import audit_service
from app.services.rbac_service import get_user_permission_codes

router = APIRouter(prefix="/auth", tags=["认证"])


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _issue_tokens(db: Session, user: User, request: Request) -> tuple[str, str]:
    access = create_access_token(user.id, username=user.username)
    jti = uuid4().hex
    refresh = create_refresh_token(user.id, username=user.username, jti=jti)
    db.add(
        RefreshToken(
            jti=jti,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=request.headers.get("user-agent"),
            ip=audit_service.client_ip(request),
        )
    )
    return access, refresh


def _complete_login(db: Session, user: User, request: Request) -> LoginResult:
    now = datetime.now(timezone.utc)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    user.last_login_ip = audit_service.client_ip(request)
    access, refresh = _issue_tokens(db, user, request)
    audit_service.record(
        db,
        category=AuditCategory.AUTH,
        action="登录",
        result=AuditResult.SUCCESS,
        actor_id=user.id,
        actor_username=user.username,
        request=request,
    )
    return LoginResult(
        access_token=access,
        refresh_token=refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user),
    )


def _login_failed(db: Session, request: Request, username: str, message: str) -> None:
    audit_service.record(
        db,
        category=AuditCategory.AUTH,
        action="登录失败",
        result=AuditResult.FAILURE,
        actor_username=username,
        message=message,
        request=request,
    )


@router.post("/login", response_model=LoginResult, summary="密码登录")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> LoginResult:
    now = datetime.now(timezone.utc)
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            db.commit()
        _login_failed(db, request, payload.username, "用户名或密码错误")
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user.status == UserStatus.DISABLED.value:
        _login_failed(db, request, payload.username, "账号已被禁用")
        raise HTTPException(status_code=403, detail="账号已被禁用")

    locked_until = _aware(user.locked_until)
    if (locked_until and locked_until > now) or user.status == UserStatus.LOCKED.value:
        _login_failed(db, request, payload.username, "账号已锁定")
        raise HTTPException(status_code=403, detail="账号已锁定，请稍后再试")

    if user.mfa_enabled and user.mfa_secret:
        if payload.otp_code and verify_totp(decrypt(user.mfa_secret), payload.otp_code):
            return _complete_login(db, user, request)
        return LoginResult(mfa_required=True, mfa_token=create_mfa_token(user.id))

    return _complete_login(db, user, request)


@router.post("/mfa/verify", response_model=LoginResult, summary="校验 MFA 完成登录")
def mfa_verify(payload: MFAVerifyRequest, request: Request, db: Session = Depends(get_db)) -> LoginResult:
    token_payload = decode_token(payload.mfa_token)
    if not token_payload or token_payload.get("type") != "mfa":
        raise HTTPException(status_code=401, detail="MFA 会话无效或已过期")
    user = db.get(User, int(token_payload.get("sub", 0)))
    if user is None or not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=401, detail="账号未启用 MFA")
    if not verify_totp(decrypt(user.mfa_secret), payload.otp_code):
        _login_failed(db, request, user.username, "MFA 验证码错误")
        raise HTTPException(status_code=401, detail="动态验证码错误")
    return _complete_login(db, user, request)


@router.post("/refresh", response_model=TokenPair, summary="刷新令牌")
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    token_payload = decode_token(payload.refresh_token)
    if not token_payload or token_payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="刷新令牌无效")
    row = db.execute(
        select(RefreshToken).where(RefreshToken.jti == token_payload.get("jti"))
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if row is None or row.revoked or (_aware(row.expires_at) or now) < now:
        raise HTTPException(status_code=401, detail="刷新令牌已失效")
    user = db.get(User, row.user_id)
    if user is None or user.status != UserStatus.ACTIVE.value:
        raise HTTPException(status_code=401, detail="账号不可用")
    row.revoked = True
    row.last_used_at = now
    access, new_refresh = _issue_tokens(db, user, request)
    db.commit()
    return TokenPair(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=Message, summary="登出")
def logout(
    payload: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    if payload.refresh_token:
        token_payload = decode_token(payload.refresh_token)
        if token_payload:
            row = db.execute(
                select(RefreshToken).where(RefreshToken.jti == token_payload.get("jti"))
            ).scalar_one_or_none()
            if row is not None:
                row.revoked = True
    audit_service.record(
        db,
        category=AuditCategory.AUTH,
        action="退出登录",
        actor_id=user.id,
        actor_username=user.username,
        request=request,
    )
    return Message(message="已登出")


@router.get("/me", response_model=MeOut, summary="当前用户信息与权限")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> MeOut:
    permissions = sorted(p for p in get_user_permission_codes(db, user) if p != "*")
    base = UserOut.model_validate(user)
    return MeOut(
        **base.model_dump(),
        permissions=permissions,
        roles=[RoleBrief.model_validate(r) for r in user.roles],
        groups=[GroupBrief.model_validate(g) for g in user.groups],
        org_name=user.org.name if user.org else None,
    )


@router.post("/change-password", response_model=Message, summary="修改本人密码")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    ok, reason = validate_password_strength(payload.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    user.must_change_password = False
    for row in db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id)).scalars():
        row.revoked = True
    audit_service.record(
        db,
        category=AuditCategory.AUTH,
        action="change_password",
        actor_id=user.id,
        actor_username=user.username,
        request=request,
    )
    return Message(message="密码修改成功，请重新登录")


@router.post("/mfa/setup", response_model=MFASetupResponse, summary="初始化 MFA（生成密钥）")
def mfa_setup(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> MFASetupResponse:
    secret = generate_totp_secret()
    user.mfa_secret = encrypt(secret)
    db.commit()
    return MFASetupResponse(secret=secret, otpauth_uri=get_totp_uri(secret, user.username))


@router.post("/mfa/enable", response_model=Message, summary="启用 MFA")
def mfa_enable(
    payload: MFAEnableRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="请先初始化 MFA 密钥")
    if not verify_totp(decrypt(user.mfa_secret), payload.code):
        raise HTTPException(status_code=400, detail="动态验证码错误")
    user.mfa_enabled = True
    audit_service.record(
        db,
        category=AuditCategory.AUTH,
        action="mfa_enable",
        actor_id=user.id,
        actor_username=user.username,
        request=request,
    )
    return Message(message="MFA 已启用")


@router.post("/mfa/disable", response_model=Message, summary="关闭 MFA")
def mfa_disable(
    payload: MFADisableRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Message:
    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA 未启用")
    if not verify_totp(decrypt(user.mfa_secret), payload.code):
        raise HTTPException(status_code=400, detail="动态验证码错误")
    user.mfa_enabled = False
    user.mfa_secret = None
    audit_service.record(
        db,
        category=AuditCategory.AUTH,
        action="mfa_disable",
        actor_id=user.id,
        actor_username=user.username,
        request=request,
    )
    return Message(message="MFA 已关闭")
