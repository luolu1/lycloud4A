"""连接工具 Schema（适配软件：MobaXterm/NetCatty/Xshell/SecureCRT/Chrome）。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

KIND_PROTOCOLS: dict[str, str] = {
    "mobaxterm": "ssh,telnet,rsh,mosh,rdp,vnc,xdmcp,sftp,ftp,scp,serial",
    "netcatty": "ssh,serial",
    "xshell": "ssh,telnet,rlogin,serial",
    "securecrt": "ssh,telnet,rlogin,serial",
    "chrome": "http,https,oidc,saml,web",
}

KIND_NAMES: dict[str, str] = {
    "mobaxterm": "MobaXterm",
    "netcatty": "NetCatty",
    "xshell": "Xshell",
    "securecrt": "SecureCRT",
    "chrome": "Chrome",
}


class ToolBase(BaseModel):
    kind: str = Field(..., max_length=32)
    exe_path: str = Field(..., max_length=512)
    status: bool = True


class ToolCreate(ToolBase):
    name: Optional[str] = None
    description: Optional[str] = None


class ToolUpdate(BaseModel):
    exe_path: Optional[str] = None
    status: Optional[bool] = None


class ToolOut(ORMModel):
    id: int
    kind: str
    name: str
    exe_path: str
    protocols: Optional[str]
    description: Optional[str]
    status: bool
    created_at: datetime
