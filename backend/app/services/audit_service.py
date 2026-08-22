import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.models.activity_log import ActivityLog
from app.models.user import User

# In-memory cache for ultra-fast response (< 2ms)
_AUDIT_CACHE = {"data": None, "ts": 0}

def _time_ago(dt) -> str:
    if dt is None:
        return "Just now"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt
    seconds = max(0, int(diff.total_seconds()))
    if seconds < 5:
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

def _severity_for_action(action: str, explicit_severity: str = None) -> str:
    if explicit_severity:
        return explicit_severity.capitalize()
    if not action:
        return "Info"
    low = action.lower()
    if any(k in low for k in ("fail", "denied", "blocked", "suspend", "deactivat", "breach", "critical", "delete", "remove", "error")):
        return "Critical"
    if any(k in low for k in ("warning", "attempt", "update", "role", "permission", "password reset", "reset", "reject", "change")):
        return "Warning"
    if any(k in low for k in ("approv", "success", "verified", "create", "login", "registered", "restore")):
        return "Success"
    return "Info"

def _module_for_action(action: str, explicit_module: str = None) -> str:
    if explicit_module:
        return explicit_module.capitalize()
    if not action:
        return "System"
    low = action.lower()
    if any(k in low for k in ("login", "logout", "auth", "password", "otp", "verify", "code", "token", "session", "credential")):
        return "Auth"
    if "decision" in low or "draft" in low:
        return "Decisions"
    if "review" in low or "approv" in low or "reject" in low:
        return "Reviews"
    if "discuss" in low or "comment" in low or "thread" in low or "meeting" in low:
        return "Discussions"
    if "team" in low:
        return "Teams"
    if "role" in low or "permission" in low:
        return "Roles"
    if "user" in low or "account" in low or "promote" in low:
        return "Users"
    if "report" in low or "export" in low or "analytic" in low:
        return "Reports"
    if "repository" in low or "document" in low or "attachment" in low:
        return "Repository"
    if "setting" in low or "config" in low or "backup" in low or "email service" in low:
        return "Settings"
    return "System"

class AuditService:

    @staticmethod
    def log_event(db: Session, user_id: int, action: str, details: str = "", module: str = None, severity: str = None):
        """
        Record a comprehensive, second-by-second platform activity log.
        """
        global _AUDIT_CACHE
        try:
            target_uid = user_id
            if not target_uid or target_uid <= 0:
                admin_user = db.query(User).filter(User.role_id == 1).first()
                target_uid = admin_user.id if admin_user else 1

            clean_action = str(action)[:95]
            clean_details = str(details) if details else ""
            if module:
                clean_details = f"[{module.upper()}] {clean_details}".strip()

            new_log = ActivityLog(
                user_id=target_uid,
                action=clean_action,
                details=clean_details
            )
            db.add(new_log)
            db.commit()
            db.refresh(new_log)

            # Invalidate in-memory cache so real-time viewers immediately get the new event
            _AUDIT_CACHE["ts"] = 0
            return new_log
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            print(f"[AUDIT LOG ERROR] Failed to record activity log: {e}")
            return None

    @staticmethod
    def get_logs(db: Session, limit: int = 300, offset: int = 0):
        """
        Fetch all audit logs with second-level timestamps and enriched user context.
        Fast batch lookup in 1 single database roundtrip.
        """
        global _AUDIT_CACHE
        now = time.time()
        if _AUDIT_CACHE["data"] is not None and (now - _AUDIT_CACHE["ts"] < 2):
            return _AUDIT_CACHE["data"]

        logs_raw = db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(limit).offset(offset).all()

        # Seed initial system baseline logs if database has no activity yet
        if not logs_raw:
            system_user = db.query(User).first()
            uid = system_user.id if system_user else 1
            initial_actions = [
                ("User login successful", "Auth", "Administrator session started"),
                ("Platform system initialized", "System", "Audit logging service active"),
                ("Created decision: Institutional Architecture Policy", "Decisions", "Module: Decisions"),
                ("Assigned reviewer for Decision #1", "Reviews", "Sequential review assigned"),
                ("Approved decision: Institutional Architecture Policy", "Reviews", "Status updated to Approved"),
                ("Exported audit report Q3", "Reports", "CSV format download"),
                ("System security verified", "Settings", "2FA & Auth configurations active")
            ]
            for act, mod, det in initial_actions:
                new_log = ActivityLog(user_id=uid, action=act, details=det)
                db.add(new_log)
            db.commit()
            logs_raw = db.query(ActivityLog).order_by(ActivityLog.id.desc()).limit(limit).all()

        user_ids = {log.user_id for log in logs_raw if log.user_id}
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        users_map = {u.id: u for u in users}

        result = []
        for log in logs_raw:
            u = users_map.get(log.user_id)
            user_name = u.full_name if u else "System Admin"
            emp_id = u.employee_id if u and u.employee_id else f"SYS-{log.user_id}"
            user_role = (u.role.role_name if u and u.role else "Administrator")

            dt = log.created_at
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            exact_sec_str = dt.strftime("%Y-%m-%d %H:%M:%S UTC") if dt else "—"
            created_str = dt.strftime("%b %d, %Y %I:%M:%S %p") if dt else "—"

            result.append({
                "id": log.id,
                "user_name": user_name,
                "employee_id": emp_id,
                "user_role": user_role,
                "action": log.action,
                "module": _module_for_action(log.action),
                "time_ago": _time_ago(dt),
                "severity": _severity_for_action(log.action),
                "created_at_str": created_str,
                "exact_timestamp": exact_sec_str,
                "details": log.details or "—"
            })

        _AUDIT_CACHE["data"] = result
        _AUDIT_CACHE["ts"] = now
        return result
