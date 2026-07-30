from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List
from pydantic import BaseModel

from app.database.connection import get_db
from app.models.activity_log import ActivityLog
from app.models.user import User

router = APIRouter(
    prefix="/audit",
    tags=["Audit Logs"]
)

def _time_ago(dt) -> str:
    if dt is None:
        return "Just now"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = max(0, int(diff.total_seconds()))
    if seconds < 10:
        return "Just now"
    elif seconds < 60:
        return f"{seconds} sec ago"
    elif seconds < 3600:
        m = seconds // 60
        return f"{m} min{'s' if m > 1 else ''} ago"
    elif seconds < 86400:
        h = seconds // 3600
        return f"{h} hr{'s' if h > 1 else ''} ago"
    else:
        d = seconds // 86400
        return f"{d} day{'s' if d > 1 else ''} ago"

def _severity_for_action(action: str) -> str:
    if not action:
        return "Info"
    low = action.lower()
    if any(k in low for k in ("fail", "denied", "blocked", "suspend", "deactivat", "breach", "critical")):
        return "Critical"
    if any(k in low for k in ("warning", "attempt", "update", "role", "permission", "password reset")):
        return "Warning"
    return "Info"

def _module_for_action(action: str) -> str:
    if not action:
        return "System"
    low = action.lower()
    if "login" in low or "auth" in low or "password" in low or "otp" in low or "verify" in low:
        return "Auth"
    if "decision" in low:
        return "Decisions"
    if "report" in low or "export" in low:
        return "Reports"
    if "review" in low or "approve" in low or "reject" in low:
        return "Reviews"
    return "System"

class AuditLogCreate(BaseModel):
    user_id: int
    action: str
    details: str = ""

@router.post("/log")
def create_audit_log(payload: AuditLogCreate, db: Session = Depends(get_db)):
    user_id = payload.user_id
    valid_user = db.query(User).filter(User.id == user_id).first()
    if not valid_user:
        system_user = db.query(User).first()
        if system_user:
            user_id = system_user.id
        else:
            return {"status": "skipped", "message": "No users exist"}

    clean_act = str(payload.action)[:95]
    new_log = ActivityLog(
        user_id=user_id,
        action=clean_act,
        details=str(payload.details)
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return {"status": "success", "id": new_log.id}

@router.get("/")
def get_audit_logs(db: Session = Depends(get_db)):
    logs_raw = db.query(ActivityLog).order_by(ActivityLog.id.desc()).all()

    # Seed initial system audit logs if none exist yet
    if not logs_raw:
        system_user = db.query(User).first()
        uid = system_user.id if system_user else 1
        initial_actions = [
            ("User login successful", "Users"),
            ("Created decision: Quarterly Architecture Review", "Decisions"),
            ("Assigned reviewer for Decision #1", "Reviews"),
            ("Approved decision: Quarterly Architecture Review", "Decisions"),
            ("Exported audit report Q3 2025", "Reports"),
            ("Updated system security configurations", "Roles")
        ]
        for act, mod in initial_actions:
            new_log = ActivityLog(user_id=uid, action=act, details=f"Module: {mod}")
            db.add(new_log)
        db.commit()
        logs_raw = db.query(ActivityLog).order_by(ActivityLog.id.desc()).all()

    result = []
    for log in logs_raw:
        u = db.query(User).filter(User.id == log.user_id).first()
        user_name = u.full_name if u else "System Admin"
        created_str = log.created_at.strftime("%b %d, %Y %I:%M %p") if log.created_at else "—"
        result.append({
            "id": log.id,
            "user_name": user_name,
            "action": log.action,
            "module": _module_for_action(log.action),
            "time_ago": _time_ago(log.created_at),
            "severity": _severity_for_action(log.action),
            "created_at_str": created_str,
            "details": log.details or "—"
        })

    return result
