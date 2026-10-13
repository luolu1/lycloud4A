"""RBAC Schema：角色与权限。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PermissionOut(ORMModel):
    id: int
    code: str
    name: str
    resource: str
    action: str
    description: Optional[str]


class RoleBase(BaseModel):
    name: str = Field(..., max_length=128)
    code: str = Field(..., max_length=64)
    description: Optional[str] = None
    application_id: Optional[int] = None


class RoleCreate(RoleBase):
    permission_ids: List[int] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[List[int]] = None


class RoleOut(ORMModel):
    id: int
    code: str
    name: str
    description: Optional[str]
    is_builtin: bool
    application_id: Optional[int]
    created_at: datetime


class RoleDetailOut(RoleOut):
    permissions: List[PermissionOut] = []
