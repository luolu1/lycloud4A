"""密码托管 Schema。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SecretBase(BaseModel):
    name: str = Field(..., max_length=128)
    category: str = "application"
    description: Optional[str] = None
    owner: Optional[str] = None
    tags: dict[str, Any] = {}
    rotation_enabled: bool = False
    rotation_type: str = "manual"
    rotation_interval_days: int = 30
    rotate_target: Optional[str] = None
    rotate_username: Optional[str] = None
    rotate_api_config: Optional[dict[str, Any]] = None


class SecretCreate(SecretBase):
    path: str = Field(..., max_length=255)
    data: dict[str, str] = Field(..., description="密钥内容，如 {username, password}")


class SecretUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    tags: Optional[dict[str, Any]] = None
    rotation_enabled: Optional[bool] = None
    rotation_type: Optional[str] = None
    rotation_interval_days: Optional[int] = None
    rotate_target: Optional[str] = None
    rotate_username: Optional[str] = None
    rotate_api_config: Optional[dict[str, Any]] = None
    status: Optional[bool] = None


class SecretValueIn(BaseModel):
    data: dict[str, str]
    comment: Optional[str] = None


class SecretOut(ORMModel):
    id: int
    path: str
    name: str
    category: str
    description: Optional[str]
    owner: Optional[str]
    tags: Optional[dict[str, Any]]
    rotation_enabled: bool
    rotation_type: str
    rotation_interval_days: int
    rotate_target: Optional[str]
    rotate_username: Optional[str]
    current_version: int
    last_rotated_at: Optional[datetime]
    next_rotation_at: Optional[datetime]
    last_rotation_status: Optional[str]
    last_rotation_error: Optional[str]
    status: bool
    created_at: datetime


class SecretValueOut(BaseModel):
    path: str
    version: int
    data: dict[str, str]
    masked: dict[str, str]


class SecretVersionOut(ORMModel):
    id: int
    version: int
    comment: Optional[str]
    created_by: Optional[str]
    created_at: datetime


class RotateResult(BaseModel):
    path: str
    success: bool
    new_version: Optional[int] = None
    message: str
