"""设备系统 Schema。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class AppBase(BaseModel):
    name: str = Field(..., max_length=128)
    code: Optional[str] = Field(default=None, max_length=64)
    app_type: str = "web"
    protocol: str = "oidc"
    url: Optional[str] = None
    logout_url: Optional[str] = None
    client_id: Optional[str] = None
    callback_url: Optional[str] = None
    login_username: Optional[str] = None
    credential_type: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    status: bool = True


class AppCreate(AppBase):
    client_secret: Optional[str] = None
    credential: Optional[str] = None


class AppUpdate(BaseModel):
    name: Optional[str] = None
    app_type: Optional[str] = None
    protocol: Optional[str] = None
    url: Optional[str] = None
    logout_url: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    callback_url: Optional[str] = None
    login_username: Optional[str] = None
    credential_type: Optional[str] = None
    credential: Optional[str] = None
    owner: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    status: Optional[bool] = None


class AppOut(ORMModel):
    id: int
    code: str
    name: str
    app_type: str
    protocol: str
    url: Optional[str]
    logout_url: Optional[str]
    client_id: Optional[str]
    callback_url: Optional[str]
    login_username: Optional[str]
    credential_type: Optional[str]
    has_credential: bool = False
    conn_status: str = "unknown"
    last_checked_at: Optional[datetime] = None
    last_check_error: Optional[str] = None
    owner: Optional[str]
    description: Optional[str]
    icon: Optional[str]
    status: bool
    created_at: datetime


class AppCheckResult(BaseModel):
    app_id: int
    conn_status: str
    last_checked_at: datetime
    error: Optional[str] = None


class AppConnectOut(BaseModel):
    ticket: str
    agent_url: str
    device_id: int
    device_name: str
    tool_kind: str


class ConnectResolveIn(BaseModel):
    ticket: str


class ConnectResolveOut(BaseModel):
    device_id: int
    device_name: str
    host: str
    port: Optional[int] = None
    protocol: str
    url: Optional[str] = None
    login_username: Optional[str] = None
    credential_type: Optional[str] = None
    credential: Optional[str] = None
    tool_kind: str
    tool_name: str
    exe_path: str
    username: Optional[str] = None
    audit_id: Optional[int] = None
    session_id: Optional[str] = None
    upload_url: Optional[str] = None


class AppLaunchOut(BaseModel):
    app_id: int
    app_name: str
    protocol: str
    redirect_url: str
    ticket: str
