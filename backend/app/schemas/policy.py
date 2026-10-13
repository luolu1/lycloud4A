"""授权策略 Schema。"""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PolicyBase(BaseModel):
    name: str = Field(..., max_length=128)
    description: Optional[str] = None
    subject_type: str = "user"
    subject_id: int
    resource_type: str
    resource_id: Optional[int] = None
    effect: str = "allow"
    actions: List[str] = ["*"]
    conditions: dict[str, Any] = {}
    priority: int = 100
    enabled: bool = True
    expires_at: Optional[datetime] = None


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    effect: Optional[str] = None
    actions: Optional[List[str]] = None
    conditions: Optional[dict[str, Any]] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    expires_at: Optional[datetime] = None


class PolicyOut(ORMModel):
    id: int
    name: str
    description: Optional[str]
    subject_type: str
    subject_id: int
    resource_type: str
    resource_id: Optional[int]
    effect: str
    actions: List[str]
    conditions: dict[str, Any]
    priority: int
    enabled: bool
    created_by: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime


class PolicyEvaluateRequest(BaseModel):
    subject_id: int
    subject_type: str = "user"
    resource_type: str
    resource_id: Optional[int] = None
    action: str


class PolicyEvaluateResult(BaseModel):
    allowed: bool
    matched_policy: Optional[str] = None
    reason: str
