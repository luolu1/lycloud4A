"""ORM 模型聚合导出：确保 Base.metadata 注册所有表。"""
from app.models.associations import (
    role_permission,
    user_application,
    user_group,
    user_role,
)
from app.models.application import Application
from app.models.audit import AuditLog
from app.models.launch_tool import LaunchTool
from app.models.org import Organization
from app.models.policy import AccessPolicy
from app.models.rbac import Permission, Role
from app.models.session import RefreshToken
from app.models.user import Group, User
from app.models.vault import Secret, SecretVersion

__all__ = [
    "Organization",
    "User",
    "Group",
    "Application",
    "LaunchTool",
    "Role",
    "Permission",
    "AccessPolicy",
    "AuditLog",
    "Secret",
    "SecretVersion",
    "RefreshToken",
    "user_group",
    "user_role",
    "role_permission",
    "user_application",
]
