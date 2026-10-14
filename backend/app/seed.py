"""幂等初始化数据：权限、内置角色、组织、组、管理员、示例应用/密钥/策略。"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.application import Application
from app.models.enums import (
    AppProtocol,
    AppType,
    Effect,
    ResourceType,
    RotationType,
    SecretCategory,
    SubjectType,
)
from app.models.org import Organization
from app.models.launch_tool import LaunchTool
from app.models.policy import AccessPolicy
from app.models.rbac import Permission, Role
from app.models.user import Group, User
from app.models.vault import Secret
from app.services.secret_service import write_version

log = logging.getLogger("4a.seed")

PERMISSIONS: list[tuple[str, str, str, str, str]] = [
    ("dashboard:read", "查看仪表盘", "仪表盘", "查看", "访问系统运行、用户统计与审计统计概览面板"),
    ("user:read", "查看用户列表与详情", "用户管理", "查看", "查看平台所有用户账号的基本信息与状态"),
    ("user:write", "创建与编辑用户", "用户管理", "管理", "新建用户、修改用户信息、启用或禁用账号"),
    ("user:delete", "删除用户账号", "用户管理", "删除", "永久删除平台用户账号"),
    ("user:reset_password", "重置用户口令", "用户管理", "重置密码", "为其他用户重置登录口令或临时密码"),
    ("group:read", "查看用户组列表", "用户组", "查看", "查看部门/业务用户组及成员信息"),
    ("group:write", "创建与管理用户组", "用户组", "管理", "新建或修改用户组、添加与移除组成员"),
    ("group:delete", "删除用户组", "用户组", "删除", "永久删除指定用户组"),
    ("org:read", "查看组织架构树", "组织架构", "查看", "查看多级部门组织架构层级与部门人员"),
    ("org:write", "创建与管理组织部门", "组织架构", "管理", "新建、修改或调整组织部门层级"),
    ("org:delete", "删除组织部门", "组织架构", "删除", "删除未挂载子部门或用户的空部门"),
    ("application:read", "查看纳管设备与连接", "设备管理", "查看", "查看纳管网络设备、安全设备、服务器并使用工具连接"),
    ("application:write", "纳管与编辑设备", "设备管理", "管理", "登记新设备、修改设备凭证与参数、配置连接工具"),
    ("application:delete", "移除纳管设备", "设备管理", "删除", "取消纳管并从平台移除指定设备"),
    ("role:read", "查看角色列表与权限", "角色权限", "查看", "查看内置及自定义角色清单与权限详情"),
    ("role:write", "创建与管理角色权限", "角色权限", "管理", "新建角色、修改角色信息或调整分配权限清单"),
    ("role:delete", "删除自定义角色", "角色权限", "删除", "删除非内置的自定义角色"),
    ("permission:read", "查看系统功能权限清单", "权限字典", "查看", "查看系统底层功能权限码与资源定义字典"),
    ("policy:read", "查看访问控制策略", "访问策略", "查看", "查看基于属性和优先级的 ABAC 访问控制规则"),
    ("policy:write", "创建与配置访问策略", "访问策略", "管理", "新增或修改访问控制策略规则与时效条件"),
    ("policy:delete", "删除访问控制策略", "访问策略", "删除", "删除已失效或过期的访问控制策略"),
    ("audit:read", "查看操作与安全审计日志", "审计日志", "查看", "检索登录、设备连接、密码解密及系统管理操作审计"),
    ("secret:read", "查看密码凭证元数据", "密码托管", "查看", "查看账号密码凭证路径、版本及自动轮换策略"),
    ("secret:reveal", "查看敏感密码明文", "密码托管", "查看明文", "解密并以明文形式查看托管的设备/账号密码"),
    ("secret:write", "录入与更新密码版本", "密码托管", "管理", "录入新密码、手动更新凭证版本或修改轮换间隔"),
    ("secret:delete", "删除密码托管条目", "密码托管", "删除", "彻底移除指定的密码凭证及其历史版本"),
    ("secret:rotate", "手动触发密码自动轮换", "密码托管", "手动轮换", "立即发起目标设备的密码自动修改与轮换流程"),
]

BUILTIN_ROLES: dict[str, dict] = {
    "super-admin": {"name": "超级管理员", "perms": ["*"]},
    "iam-admin": {
        "name": "身份管理员",
        "perms": [
            "dashboard:read", "user:read", "user:write", "user:delete", "user:reset_password",
            "group:read", "group:write", "group:delete", "org:read", "org:write",
            "application:read", "application:write", "application:delete",
            "role:read", "role:write", "role:delete", "permission:read",
            "policy:read", "policy:write", "policy:delete",
            "secret:read", "secret:write", "secret:rotate",
        ],
    },
    "security-auditor": {
        "name": "安全审计员",
        "perms": ["dashboard:read", "audit:read", "user:read", "application:read", "policy:read", "secret:read"],
    },
    "secret-admin": {
        "name": "密码托管管理员",
        "perms": ["dashboard:read", "secret:read", "secret:reveal", "secret:write", "secret:rotate", "application:read"],
    },
    "ops-user": {
        "name": "运维用户",
        "perms": [
            "dashboard:read", "application:read", "secret:read", "secret:reveal",
            "secret:rotate", "audit:read",
        ],
    },
    "readonly": {
        "name": "只读用户",
        "perms": ["dashboard:read", "user:read", "application:read", "role:read", "policy:read"],
    },
}


def _get_or_create_permission(db: Session, code: str, name: str, resource: str, action: str, desc: str) -> Permission:
    perm = db.execute(select(Permission).where(Permission.code == code)).scalar_one_or_none()
    if perm is None:
        perm = Permission(code=code, name=name, resource=resource, action=action, description=desc or None)
        db.add(perm)
        db.flush()
    else:
        perm.name = name
        perm.resource = resource
        perm.action = action
        perm.description = desc or None
        db.flush()
    return perm


def seed() -> None:
    db = SessionLocal()
    try:
        if _seed(db):
            db.commit()
            log.info("seed completed")
    except Exception:
        db.rollback()
        log.exception("seed failed")
        raise
    finally:
        db.close()


def _seed(db: Session) -> bool:
    perms: dict[str, Permission] = {}
    for code, name, resource, action, desc in PERMISSIONS:
        perms[code] = _get_or_create_permission(db, code, name, resource, action, desc)

    roles: dict[str, Role] = {}
    for code, cfg in BUILTIN_ROLES.items():
        role = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
        if role is None:
            role = Role(code=code, name=cfg["name"], description=f"内置角色：{cfg['name']}", is_builtin=True)
            db.add(role)
            db.flush()
        wanted = set(perms.values()) if cfg["perms"] == ["*"] else {perms[c] for c in cfg["perms"]}
        role.permissions = list(wanted)
        roles[code] = role

    root = db.execute(select(Organization).where(Organization.code == "CORP")).scalar_one_or_none()
    if root is None:
        root = Organization(name="示例集团", code="CORP", description="根组织", sort_order=0)
        db.add(root)
        db.flush()
    org_it = db.execute(select(Organization).where(Organization.code == "CORP-IT")).scalar_one_or_none()
    if org_it is None:
        org_it = Organization(name="信息化中心", code="CORP-IT", parent_id=root.id, sort_order=1)
        db.add(org_it)
        db.flush()
    org_ops = db.execute(select(Organization).where(Organization.code == "CORP-OPS")).scalar_one_or_none()
    if org_ops is None:
        org_ops = Organization(name="运维中心", code="CORP-OPS", parent_id=root.id, sort_order=2)
        db.add(org_ops)
        db.flush()

    for name, code in [("运维管理员组", "ops-admin"), ("运维只读组", "ops-readonly"), ("OA 应用用户组", "app-oa-users")]:
        if db.execute(select(Group).where(Group.code == code)).scalar_one_or_none() is None:
            db.add(Group(name=name, code=code, org_id=org_ops.id, description=f"示例用户组 {name}"))
    db.flush()

    admin = db.execute(select(User).where(User.username == settings.BOOTSTRAP_ADMIN_USERNAME)).scalar_one_or_none()
    if admin is None:
        admin = User(
            username=settings.BOOTSTRAP_ADMIN_USERNAME,
            display_name="超级管理员",
            email=settings.BOOTSTRAP_ADMIN_EMAIL,
            password_hash=hash_password(settings.BOOTSTRAP_ADMIN_PASSWORD),
            org_id=org_it.id,
            is_superuser=True,
            status="active",
        )
        admin.roles = [roles["super-admin"]]
        db.add(admin)
        db.flush()

    if db.execute(select(Application).where(Application.code == "CORE-SW")).scalar_one_or_none() is None:
        from app.services.device_service import store_credential

        db.add_all([
            Application(code="CORE-SW", name="核心交换机集群", app_type=AppType.NETWORK.value,
                        protocol=AppProtocol.TACACS.value, url="10.0.1.1",
                        login_username="netadmin", credential_type="password",
                        credential_encrypted=store_credential("Sw!tch@Core2024"),
                        owner="运维中心", description="数据中心核心交换机，TACACS+ 统一认证与命令授权"),
            Application(code="ACCESS-SW", name="接入层交换机", app_type=AppType.NETWORK.value,
                        protocol=AppProtocol.RADIUS.value, url="10.0.1.0/24",
                        login_username="netadmin", credential_type="password",
                        credential_encrypted=store_credential("Access@Sw2024"),
                        owner="运维中心", description="楼层接入交换机，RADIUS 集中认证"),
            Application(code="FW-EDGE", name="边界防火墙", app_type=AppType.SECURITY.value,
                        protocol=AppProtocol.RADIUS.value, url="10.0.0.1",
                        login_username="fwadmin", credential_type="password",
                        credential_encrypted=store_credential("F!reWall@2024"),
                        owner="安全团队", description="互联网边界防火墙，管理员 RADIUS 登录"),
            Application(code="LINUX-PROD", name="生产 Linux 服务器组", app_type=AppType.SERVER.value,
                        protocol=AppProtocol.SSH.value, url="10.0.2.0/24",
                        login_username="root", credential_type="ssh_key",
                        credential_encrypted=store_credential("-----BEGIN OPENSSH PRIVATE KEY-----\\nDEMO_KEY\\n-----END OPENSSH PRIVATE KEY-----"),
                        owner="运维中心", description="生产服务器集群，SSH Key 统一分发与登录"),
            Application(code="JUMP", name="堡垒机 JumpServer", app_type=AppType.BASTION.value,
                        protocol=AppProtocol.SSH.value, url="10.0.3.10",
                        login_username="ops", credential_type="password",
                        credential_encrypted=store_credential("Jump@Server2024"),
                        owner="运维中心", description="运维堡垒机，所有设备访问经此审计"),
        ])
        db.flush()

    if db.execute(select(Secret).where(Secret.path == "middleware/redis/redis-cache-01")).scalar_one_or_none() is None:
        secret = Secret(
            path="middleware/redis/redis-cache-01",
            name="Redis 缓存实例",
            category=SecretCategory.MIDDLEWARE.value,
            description="订单缓存 Redis",
            owner="运维中心",
            rotation_enabled=True,
            rotation_type=RotationType.MANUAL.value,
            rotation_interval_days=30,
            rotate_target="10.0.2.20:6379",
            rotate_username="default",
        )
        db.add(secret)
        db.flush()
        write_version(db, secret, {"username": "default", "password": "Redis@Initial123"},
                      created_by="seed", comment="初始化")

    if db.execute(select(AccessPolicy).where(AccessPolicy.name == "运维组可管理应用")).scalar_one_or_none() is None:
        db.add(AccessPolicy(
            name="运维组可管理应用",
            description="示例：运维管理员组允许读取应用资源",
            subject_type=SubjectType.GROUP.value, subject_id=1,
            resource_type=ResourceType.APPLICATION.value, resource_id=None,
            effect=Effect.ALLOW.value, actions=["read"], priority=100, created_by="seed",
        ))

    if db.execute(select(LaunchTool).where(LaunchTool.kind == "mobaxterm")).scalar_one_or_none() is None:
        db.add_all([
            LaunchTool(
                kind="mobaxterm", name="MobaXterm",
                exe_path=r"C:\Program Files (x86)\Mobatek\MobaXterm\MobaXterm.exe",
                protocols="ssh,telnet,rsh,mosh,rdp,vnc,xdmcp,sftp,ftp,scp,serial",
                description="多协议远程终端（SSH/Telnet/RDP/VNC/SFTP/Serial 等）",
            ),
            LaunchTool(
                kind="netcatty", name="NetCatty",
                exe_path=r"C:\Program Files\NetCatty\NetCatty.exe",
                protocols="ssh,serial",
                description="现代 SSH 工作区（支持网络设备串口与 SSH）",
            ),
            LaunchTool(
                kind="xshell", name="Xshell",
                exe_path=r"C:\Program Files\NetSarang\Xshell 7\Xshell.exe",
                protocols="ssh,telnet,rlogin,serial", description="SSH 终端模拟器",
            ),
            LaunchTool(
                kind="securecrt", name="SecureCRT",
                exe_path=r"C:\Program Files\VanDyke Software\SecureCRT\SecureCRT.exe",
                protocols="ssh,telnet,rlogin,serial", description="SSH/Telnet 终端客户端",
            ),
            LaunchTool(
                kind="chrome", name="Chrome",
                exe_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                protocols="http,https,oidc,saml,web", description="Web 应用浏览器",
            ),
        ])

    # WinSCP 单独判断：老库中 mobaxterm 已存在时上面的整块不会执行，
    # 因此这里做幂等补齐，保证既有部署也能拿到文件传输工具。
    if db.execute(select(LaunchTool).where(LaunchTool.kind == "winscp")).scalar_one_or_none() is None:
        db.add(LaunchTool(
            kind="winscp", name="WinSCP",
            exe_path=r"C:\Program Files (x86)\WinSCP\WinSCP.exe",
            protocols="sftp,scp,ftp,ftps",
            description="SFTP/SCP/FTP 图形化文件传输客户端",
        ))
    return True


if __name__ == "__main__":
    seed()
