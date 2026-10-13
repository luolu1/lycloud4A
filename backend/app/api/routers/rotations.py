"""密码轮换路由：到期查询与批量执行。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.enums import AuditCategory
from app.models.user import User
from app.schemas.vault import SecretOut
from app.services import audit_service, rotation_service

router = APIRouter(prefix="/rotations", tags=["密码轮换"])


@router.get("/due", response_model=list[SecretOut], summary="到期未轮换密钥")
def list_due(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("secret:read")),
) -> list[SecretOut]:
    return [SecretOut.model_validate(s) for s in rotation_service.due_secrets(db)]


@router.post("/run", summary="立即执行轮换扫描")
def run_rotation(
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(require_permission("secret:rotate")),
) -> dict:
    due = rotation_service.due_secrets(db)
    results = []
    succeeded = 0
    for secret in due:
        ok, version, msg = rotation_service.rotate_secret(db, secret, actor=actor.username, force=True)
        succeeded += 1 if ok else 0
        results.append({"path": secret.path, "success": ok, "new_version": version, "message": msg})
    audit_service.record(
        db,
        category=AuditCategory.VAULT,
        action="rotation_run",
        actor_id=actor.id,
        actor_username=actor.username,
        message=f"processed={len(due)} succeeded={succeeded}",
        detail=results,
        request=request,
    )
    return {
        "processed": len(due),
        "succeeded": succeeded,
        "failed": len(due) - succeeded,
        "results": results,
    }
