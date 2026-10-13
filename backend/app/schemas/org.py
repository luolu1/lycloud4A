"""组织架构 Schema。"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class OrgBase(BaseModel):
    name: str = Field(..., max_length=128)
    code: str = Field(..., max_length=64)
    parent_id: Optional[int] = None
    description: Optional[str] = None
    manager: Optional[str] = None
    sort_order: int = 0


class OrgCreate(OrgBase):
    pass


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    description: Optional[str] = None
    manager: Optional[str] = None
    sort_order: Optional[int] = None


class OrgOut(ORMModel):
    id: int
    name: str
    code: str
    parent_id: Optional[int]
    description: Optional[str]
    manager: Optional[str]
    sort_order: int
    created_at: datetime


class OrgTree(OrgOut):
    children: List["OrgTree"] = []
