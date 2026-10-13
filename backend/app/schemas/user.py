"""用户与用户组 Schema。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class UserBase(BaseModel):
    display_name: str = Field(..., max_length=128)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    employee_no: Optional[str] = None
    title: Optional[str] = None
    org_id: Optional[int] = None
    remark: Optional[str] = None


class UserCreate(UserBase):
    username: str = Field(..., max_length=64, pattern=r"^[A-Za-z0-9_.@-]{3,64}$")
    password: str
    role_ids: List[int] = []
    group_ids: List[int] = []
    must_change_password: bool = True


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    employee_no: Optional[str] = None
    title: Optional[str] = None
    org_id: Optional[int] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class UserSelfUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class AssignRoles(BaseModel):
    role_ids: List[int] = []


class AssignGroups(BaseModel):
    group_ids: List[int] = []


class UserOut(ORMModel):
    id: int
    username: str
    display_name: str
    email: Optional[str]
    phone: Optional[str]
    employee_no: Optional[str]
    title: Optional[str]
    org_id: Optional[int]
    status: str
    source: str
    is_superuser: bool
    mfa_enabled: bool
    must_change_password: bool
    last_login_at: Optional[datetime]
    last_login_ip: Optional[str]
    created_at: datetime


class UserDetailOut(UserOut):
    roles: List["RoleBrief"] = []
    groups: List["GroupBrief"] = []


class ResetPassword(BaseModel):
    new_password: Optional[str] = None


class GroupBase(BaseModel):
    name: str = Field(..., max_length=128)
    code: str = Field(..., max_length=64)
    description: Optional[str] = None
    org_id: Optional[int] = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    org_id: Optional[int] = None


class GroupBrief(ORMModel):
    id: int
    name: str
    code: str


class GroupOut(GroupBrief):
    description: Optional[str]
    org_id: Optional[int]
    created_at: datetime


class RoleBrief(ORMModel):
    id: int
    name: str
    code: str


class GroupMembers(BaseModel):
    user_ids: List[int] = []
