"""认证 Schema：登录、MFA、令牌、改密。"""
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.user import GroupBrief, RoleBrief, UserOut


class LoginRequest(BaseModel):
    username: str
    password: str
    otp_code: Optional[str] = Field(default=None, description="已启用 MFA 时提供 TOTP 验证码")


class LoginResult(BaseModel):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    expires_in: int = 0
    mfa_required: bool = False
    mfa_token: Optional[str] = None
    user: Optional[UserOut] = None


class MFAVerifyRequest(BaseModel):
    mfa_token: str
    otp_code: str


class MFASetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class MFAEnableRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class MeOut(UserOut):
    permissions: List[str] = []
    roles: List[RoleBrief] = []
    groups: List[GroupBrief] = []
    org_name: Optional[str] = None
