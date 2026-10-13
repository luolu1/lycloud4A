"""设备系统（纳管对象：网络/安全设备、服务器、堡垒机、应用等）。"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.associations import user_application
from app.models.enums import AppProtocol, AppType, ConnStatus
from app.models.mixins import TimestampMixin


class Application(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    app_type: Mapped[str] = mapped_column(String(16), default=AppType.WEB.value, nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), default=AppProtocol.OIDC.value, nullable=False)

    url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    logout_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    client_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    client_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    callback_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    login_username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    credential_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    credential_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    conn_status: Mapped[str] = mapped_column(String(16), default=ConnStatus.UNKNOWN.value, nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_check_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[List["User"]] = relationship(  # noqa: F821
        secondary=user_application, back_populates="applications"
    )
    roles: Mapped[List["Role"]] = relationship(back_populates="application")  # noqa: F821
