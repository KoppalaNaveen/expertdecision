from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database.connection import get_db
from app.services.audit_service import AuditService

router = APIRouter(
    prefix="/audit",
    tags=["Audit Logs"]
)

class AuditLogCreate(BaseModel):
    user_id: Optional[int] = 1
    action: str
    details: Optional[str] = ""
    module: Optional[str] = None
    severity: Optional[str] = None

@router.post("/log")
def create_audit_log(payload: AuditLogCreate, db: Session = Depends(get_db)):
    """
    Records a live platform audit event.
    """
    log = AuditService.log_event(
        db,
        user_id=payload.user_id or 1,
        action=payload.action,
        details=payload.details or "",
        module=payload.module,
        severity=payload.severity
    )
    if log:
        return {"status": "success", "id": log.id}
    return {"status": "error", "message": "Failed to write audit log"}

@router.get("")
@router.get("/")
@router.get("/logs")
def get_audit_logs(
    limit: Optional[int] = Query(None, ge=1, le=1000000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Returns full system audit logs for administrative monitoring.
    When limit is omitted, returns all platform activity records.
    """
    return AuditService.get_logs(db, limit=limit, offset=offset)
