"""密码托管：Secret（密钥条目）与 SecretVersion（加密版本历史）。"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import RotationType, SecretCategory
from app.models.mixins import TimestampMixin


class Secret(Base, TimestampMixin):
    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(16), default=SecretCategory.APPLICATION.value, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    rotation_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rotation_type: Mapped[str] = mapped_column(String(16), default=RotationType.MANUAL.value, nullable=False)
    rotation_interval_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    rotate_target: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rotate_username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    rotate_api_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    current_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_rotation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_rotation_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    last_rotation_error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    versions: Mapped[List["SecretVersion"]] = relationship(
        back_populates="secret", cascade="all, delete-orphan", order_by="SecretVersion.version.desc()"
    )


class SecretVersion(Base):
    __tablename__ = "secret_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    secret_id: Mapped[int] = mapped_column(ForeignKey("secrets.id", ondelete="CASCADE"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    data_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    secret: Mapped["Secret"] = relationship(back_populates="versions")
