"""客户端下载路由：lycloud4A 本地连接助手安装包。"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/client", tags=["客户端下载"])

_DOWNLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "download"

_SETUP = ("lycloud4A-Setup.exe", "application/vnd.microsoft.portable-executable")


@router.get("/download", summary="下载 lycloud4A 连接助手安装包（Windows）")
def download_client() -> FileResponse:
    filename, media_type = _SETUP
    path = _DOWNLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="安装包未就绪")
    return FileResponse(path, media_type=media_type, filename=filename)
