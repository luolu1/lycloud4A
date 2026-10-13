"""授权策略（RBAC + ABAC 结合的访问控制规则）。"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Effect, SubjectType
from app.models.mixins import TimestampMixin


class AccessPolicy(Base, TimestampMixin):
    __tablename__ = "access_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    subject_type: Mapped[str] = mapped_column(String(16), default=SubjectType.USER.value, nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)

    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    effect: Mapped[str] = mapped_column(String(8), default=Effect.ALLOW.value, nullable=False)
    actions: Mapped[Any] = mapped_column(JSON, default=list, nullable=False)
    conditions: Mapped[Any] = mapped_column(JSON, default=dict, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
