"""领域枚举：统一各模块使用的取值。"""
from enum import Enum


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"


class UserSource(str, Enum):
    LOCAL = "local"
    LDAP = "ldap"


class AppType(str, Enum):
    WEB = "web"            # Web 应用（SSO）
    DATABASE = "database"  # 数据库
    MIDDLEWARE = "middleware"  # 中间件
    NETWORK = "network"    # 网络设备（交换机/路由器）
    SECURITY = "security"  # 安全设备（防火墙/VPN/WAF）
    SERVER = "server"      # 服务器/操作系统
    INFRA = "infra"        # 其它基础设施
    BASTION = "bastion"    # 堡垒机
    OS = "os"              # 服务器操作系统（兼容旧值）


class AppProtocol(str, Enum):
    OIDC = "oidc"
    SAML = "saml"
    CAS = "cas"
    RADIUS = "radius"
    TACACS = "tacacs"
    SSH = "ssh"
    TELNET = "telnet"
    RDP = "rdp"
    VNC = "vnc"
    SFTP = "sftp"
    FTP = "ftp"
    SERIAL = "serial"
    HTTP = "http"
    HTTPS = "https"
    LDAP = "ldap"
    LOCAL = "local"


class SubjectType(str, Enum):
    USER = "user"
    GROUP = "group"
    ROLE = "role"
    ORG = "org"


class ResourceType(str, Enum):
    APPLICATION = "application"
    USER = "user"
    GROUP = "group"
    ROLE = "role"
    POLICY = "policy"
    SECRET = "secret"
    AUDIT = "audit"
    ORG = "org"
    ALL = "all"


class Effect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


class AuditCategory(str, Enum):
    AUTH = "auth"             # 认证事件（登录/登出/MFA）
    ACCOUNT = "account"       # 账号管理
    AUTHZ = "authz"           # 授权/策略变更
    ADMIN = "admin"           # 系统管理
    VAULT = "vault"           # 密码托管操作
    CONNECTION = "connection"  # 设备连接（发起连接/解析凭证）


class AuditResult(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class SecretCategory(str, Enum):
    DATABASE = "database"
    MIDDLEWARE = "middleware"
    APPLICATION = "application"
    INFRA = "infra"
    SERVER = "server"
    SSH = "ssh"


class RotationType(str, Enum):
    MANUAL = "manual"     # 仅托管，手动更新
    MYSQL = "mysql"
    POSTGRES = "postgres"
    REDIS = "redis"
    MONGODB = "mongodb"
    API = "api"           # 通过 HTTP API 改密
    SSH_LOCAL = "ssh_local"  # SSH 登录主机 chpasswd


class CredentialType(str, Enum):
    PASSWORD = "password"  # 登录密码
    SSH_KEY = "ssh_key"    # SSH 私钥


class ConnStatus(str, Enum):
    UNKNOWN = "unknown"    # 尚未探测
    ONLINE = "online"      # 连通正常
    OFFLINE = "offline"    # 无法连接
    UNREACHABLE = "unreachable"  # 网段/地址无法探测


class ToolKind(str, Enum):
    MOBAXTERM = "mobaxterm"
    NETCATTY = "netcatty"
    XSHELL = "xshell"
    SECURECRT = "securecrt"
    CHROME = "chrome"
