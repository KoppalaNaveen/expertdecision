from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.sql import func
from datetime import datetime
from pydantic import BaseModel as BaseModel
import json
import threading

from app.database.connection import get_db
from app.models.system_setting import SystemSetting
from app.models.user import User, VerificationCode
from app.models.decision import Decision
from app.models.review import Review
from app.models.activity_log import ActivityLog
from app.models.role import Role
from app.models.team import Team
from app.models.alternative import Alternative
from app.models.attachment import Attachment
from app.models.comment import Comment, DiscussionThread
from app.models.decision_version import DecisionVersion
from app.models.email_verification import EmailVerification
from app.models.meeting_note import MeetingNote
from app.models.notification import Notification
from app.models.replay import Replay
from app.models.support_ticket import SupportTicket
from app.models.internal_email import InternalEmail
from app.schemas.settings_schema import (
    SystemSettingUpdate, SystemSettingResponse, ChangePasswordRequest, DeleteAccountRequest, TestEmailRequest,
    InitiatePasswordChangeRequest, ConfirmPasswordChangeRequest
)
from app.services.email_service import (
    _send_smtp_mail, send_password_changed_email, send_account_deleted_email,
    get_recipient_email, send_password_change_otp_email
)
from app.services.notification_service import NotificationService
from app.core.security import verify_password, hash_password
from app.models.category import Category
from app.models.backup_record import BackupRecord
from app.repositories.user_repository import UserRepository

router = APIRouter(
    prefix="/settings",
    tags=["Settings"]
)

import time

_SETTINGS_CACHE = {"data": None, "ts": 0}

def _get_or_create_settings(db: Session) -> SystemSetting:
    setting = db.query(SystemSetting).first()
    if not setting:
        first_reviewer = db.query(User).filter(User.is_active == True).first()
        def_reviewer = first_reviewer.full_name if first_reviewer else "Automated Assignment"
        setting = SystemSetting(
            language="English (US)",
            timezone="Asia/Kolkata (IST)",
            date_format="DD / MM / YYYY",
            theme="Light",
            default_dashboard="Decision Management",
            enable_two_factor=True,
            enable_email_notifications=True,
            enable_inapp_notifications=True,
            enable_decision_updates=True,
            enable_approval_requests=True,
            enable_discussion_replies=False,
            enable_repo_updates=False,
            enable_weekly_summary=True,
            show_online_status=True,
            profile_visibility=True,
            activity_visibility=False,
            default_decision_category="Technology",
            default_reviewer=def_reviewer,
            auto_save_draft=True,
            default_document_format="PDF",
            enable_accessibility=False,
            enable_keyboard_shortcuts=True,
            auto_logout_minutes=30,
            browser_session_hours=8,
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            smtp_username="support@edrp-platform.com",
            smtp_password="",
            email_sender_name="EDRP Platform Support",
            updated_by="System Initializer"
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting

@router.get("/options")
def get_settings_options(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.is_active == True).all()
    reviewers_list = []
    for u in users:
        role_name = (u.role.role_name if u.role else "User").strip()
        reviewers_list.append({
            "id": u.id,
            "full_name": u.full_name,
            "role_name": role_name,
            "employee_id": u.employee_id or f"EMP-{u.id:04d}",
            "display": f"{u.full_name} ({role_name} · {u.employee_id or 'ID'})"
        })
    reviewers_list.sort(key=lambda x: x["full_name"])

    try:
        categories = db.query(Category).all()
        cat_names = [c.name for c in categories if c.name]
    except Exception:
        cat_names = []

    if not cat_names:
        cat_names = ["Technology", "Finance", "Operations", "HR Policy", "Legal & Compliance", "Product Engineering"]

    return {
        "reviewers": reviewers_list,
        "categories": cat_names
    }

@router.get("/", response_model=SystemSettingResponse)
def get_settings(db: Session = Depends(get_db)):
    now = time.time()
    if _SETTINGS_CACHE["data"] is not None and (now - _SETTINGS_CACHE["ts"] < 30):
        return _SETTINGS_CACHE["data"]
    setting = _get_or_create_settings(db)
    _SETTINGS_CACHE["data"] = setting
    _SETTINGS_CACHE["ts"] = now
    return setting

@router.put("/", response_model=SystemSettingResponse)
def update_settings(payload: SystemSettingUpdate, db: Session = Depends(get_db)):
    setting = _get_or_create_settings(db)
    
    # Update fields if provided
    for key, value in payload.dict(exclude_unset=True).items():
        if hasattr(setting, key) and value is not None:
            setattr(setting, key, value)

    db.commit()
    db.refresh(setting)
    _SETTINGS_CACHE["ts"] = 0  # Invalidate cache
    
    # Audit log
    try:
        u = db.query(User).first()
        uid = u.id if u else 1
        log = ActivityLog(user_id=uid, action="Updated platform application settings", details=f"Theme: {setting.theme}, Language: {setting.language}")
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Settings audit log error: {e}")
        
    return setting

@router.post("/change-password")
def change_password(req: ChangePasswordRequest, db: Session = Depends(get_db)):
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match.")
        
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters long.")
        
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        # Fallback to first user for testing if user_id not matched
        user = db.query(User).first()
        if not user:
            raise HTTPException(status_code=404, detail="User account not found.")

    if not verify_password(req.current_password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect current password entered.")

    user.password = hash_password(req.new_password)
    db.commit()

    # 1. In-App Notification (Guaranteed independent)
    try:
        NotificationService.create_notification(
            db,
            user_id=user.id,
            message="Your account password was changed successfully.",
            notification_type="Security Alert"
        )
    except Exception as notif_err:
        print(f"Password change notification error: {notif_err}")

    # 2. Automated Security Email via Original Gmail (Async post-commit)
    target_email = get_recipient_email(user)
    if target_email:
        threading.Thread(
            target=send_password_changed_email,
            args=(target_email, user.full_name),
            daemon=True
        ).start()

    # Log security audit
    try:
        log = ActivityLog(user_id=user.id, action="Changed account password", details="Password updated successfully from Settings")
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Password change audit log note: {e}")

    return {"message": "Password changed successfully! Please use your new password for future sign-ins.", "status": "success"}

import re as _re
import random as _random

def _validate_password_strength(password: str) -> list:
    """Returns a list of unmet password rules."""
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not _re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter.")
    if not _re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter.")
    if not _re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number.")
    if not _re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?~`]', password):
        errors.append("Password must contain at least one special character.")
    return errors


def _mask_email(email: str) -> str:
    """Masks an email address for display: n***n@gmail.com"""
    if not email or "@" not in email:
        return "***@***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "***"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


@router.post("/change-password/initiate")
def initiate_password_change(req: InitiatePasswordChangeRequest, db: Session = Depends(get_db)):
    """
    Step 1: Validate current password and new password strength,
    then send a 6-digit verification code to the user's registered email.
    """
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match.")

    # Validate password strength
    strength_errors = _validate_password_strength(req.new_password)
    if strength_errors:
        raise HTTPException(status_code=400, detail=strength_errors[0])

    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    if not verify_password(req.current_password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect current password entered.")

    # Get user's registered email
    target_email = get_recipient_email(user)
    if not target_email:
        raise HTTPException(status_code=400, detail="No registered email address found for this account.")

    # Generate 6-digit OTP code
    code = str(_random.randint(100000, 999999))
    expiry_seconds = 120  # 2 minutes
    expires_at = int(time.time()) + expiry_seconds

    # Delete any existing password_change codes for this user's email
    db.query(VerificationCode).filter(
        VerificationCode.email == target_email,
        VerificationCode.purpose == "password_change"
    ).delete(synchronize_session='fetch')

    vc = VerificationCode(
        email=target_email,
        code=code,
        expires_at=expires_at,
        purpose="password_change"
    )
    db.add(vc)
    db.commit()

    # Send verification email asynchronously
    def _async_send_otp(email_addr, otp_code, name):
        try:
            send_password_change_otp_email(email_addr, otp_code, name)
        except Exception as e:
            print(f"[PASSWORD CHANGE OTP] Email dispatch error: {e}")

    threading.Thread(
        target=_async_send_otp,
        args=(target_email, code, user.full_name),
        daemon=True
    ).start()

    # Log audit
    try:
        log = ActivityLog(user_id=user.id, action="Password change initiated", details="Verification code sent to registered email")
        db.add(log)
        db.commit()
    except Exception:
        pass

    return {
        "message": "Verification code sent to your registered email.",
        "email_hint": _mask_email(target_email),
        "status": "otp_sent"
    }


@router.post("/change-password/confirm")
def confirm_password_change(req: ConfirmPasswordChangeRequest, db: Session = Depends(get_db)):
    """
    Step 2: Verify the 6-digit OTP code and apply the password change.
    """
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    if not verify_password(req.current_password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect current password entered.")

    # Get user's registered email
    target_email = get_recipient_email(user)
    if not target_email:
        raise HTTPException(status_code=400, detail="No registered email address found for this account.")

    # Verify the OTP code
    vc = db.query(VerificationCode).filter(
        VerificationCode.email == target_email,
        VerificationCode.code == req.verification_code,
        VerificationCode.purpose == "password_change"
    ).first()

    if not vc:
        raise HTTPException(status_code=400, detail="Invalid verification code. Please check and try again.")

    if vc.expires_at < int(time.time()):
        db.delete(vc)
        db.commit()
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")

    # Code is valid — delete it and apply the password change
    db.delete(vc)

    # Validate password strength one more time (server-side)
    strength_errors = _validate_password_strength(req.new_password)
    if strength_errors:
        db.commit()
        raise HTTPException(status_code=400, detail=strength_errors[0])

    user.password = hash_password(req.new_password)
    db.commit()

    # 1. In-App Notification
    try:
        NotificationService.create_notification(
            db,
            user_id=user.id,
            message="Your account password was changed successfully via email verification.",
            notification_type="Security Alert"
        )
    except Exception as notif_err:
        print(f"Password change notification error: {notif_err}")

    # 2. Automated Security Email (Async)
    if target_email:
        threading.Thread(
            target=send_password_changed_email,
            args=(target_email, user.full_name),
            daemon=True
        ).start()

    # Log security audit
    try:
        log = ActivityLog(user_id=user.id, action="Password changed (verified)", details="Password updated with email verification from Settings")
        db.add(log)
        db.commit()
    except Exception:
        pass

    return {
        "message": "Password changed successfully! Please use your new password for future sign-ins.",
        "status": "success"
    }


@router.post("/delete-account")
def delete_account(req: DeleteAccountRequest, db: Session = Depends(get_db)):
    if not req.password or not req.password.strip():
        raise HTTPException(status_code=400, detail="Account password is required for verification.")

    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    if not verify_password(req.password, user.password):
        raise HTTPException(status_code=400, detail="Incorrect password. Account deletion aborted.")

    user_name = user.full_name
    target_email = get_recipient_email(user)

    success, err_msg = UserRepository.delete_user(db, user.id)
    if not success:
        raise HTTPException(status_code=500, detail=err_msg or "Failed to delete account.")

    # Send account deletion email after successful database deletion
    if target_email:
        threading.Thread(
            target=send_account_deleted_email,
            args=(target_email, user_name),
            daemon=True
        ).start()

    return {
        "message": f"Account '{user_name}' and all associated data have been permanently deleted.",
        "status": "success"
    }


# ─── Login Session History ──────────────────────────────────────────
from app.models.login_session import LoginSession

class EndSessionRequest(BaseModel):
    session_id: int
    user_id: int


@router.get("/sessions/{user_id}")
def get_user_sessions(user_id: int, db: Session = Depends(get_db)):
    """Fetch all login sessions for a user, ordered by most recent first (max 50)."""
    try:
        sessions = db.query(LoginSession).filter(
            LoginSession.user_id == user_id
        ).order_by(LoginSession.logged_in_at.desc()).limit(50).all()

        result = []
        for s in sessions:
            result.append({
                "id": s.id,
                "device_name": s.device_name or "Unknown Device",
                "ip_address": s.ip_address or "Unknown",
                "user_agent": s.user_agent or "",
                "logged_in_at": s.logged_in_at.isoformat() if s.logged_in_at else None,
                "logged_out_at": s.logged_out_at.isoformat() if s.logged_out_at else None,
                "is_active": s.is_active if s.is_active is not None else False
            })

        return {"sessions": result, "total": len(result)}
    except Exception as e:
        print(f"[SESSIONS] Fetch error: {e}")
        return {"sessions": [], "total": 0}


@router.post("/sessions/end")
def end_login_session(req: EndSessionRequest, db: Session = Depends(get_db)):
    """Mark a login session as ended (set logged_out_at and is_active = False)."""
    try:
        sess = db.query(LoginSession).filter(
            LoginSession.id == req.session_id,
            LoginSession.user_id == req.user_id
        ).first()

        if sess:
            sess.logged_out_at = func.now()
            sess.is_active = False
            db.commit()
            return {"message": "Session ended", "status": "ok"}
        else:
            return {"message": "Session not found", "status": "not_found"}
    except Exception as e:
        print(f"[SESSIONS] End session error: {e}")
        return {"message": "Error ending session", "status": "error"}


@router.post("/sessions/end-all")
def end_all_user_sessions(req: EndSessionRequest, db: Session = Depends(get_db)):
    """Mark all active sessions for a user as ended, excluding the current session."""
    try:
        query = db.query(LoginSession).filter(
            LoginSession.user_id == req.user_id,
            LoginSession.is_active == True
        )
        # Exclude current session if provided
        if req.session_id and req.session_id > 0:
            query = query.filter(LoginSession.id != req.session_id)
        query.update({
            LoginSession.logged_out_at: func.now(),
            LoginSession.is_active: False
        }, synchronize_session='fetch')
        db.commit()
        return {"message": "All other sessions ended", "status": "ok"}
    except Exception as e:
        print(f"[SESSIONS] End all sessions error: {e}")
        return {"message": "Error ending sessions", "status": "error"}


@router.post("/reset", response_model=SystemSettingResponse)
def reset_settings(db: Session = Depends(get_db)):
    setting = _get_or_create_settings(db)
    setting.language = "English (US)"
    setting.timezone = "Asia/Kolkata (IST)"
    setting.date_format = "DD / MM / YYYY"
    setting.theme = "Light"
    setting.default_dashboard = "Decision Management"
    setting.enable_two_factor = True
    setting.enable_email_notifications = True
    setting.enable_inapp_notifications = True
    setting.enable_decision_updates = True
    setting.enable_approval_requests = True
    setting.enable_discussion_replies = False
    setting.enable_repo_updates = False
    setting.enable_weekly_summary = True
    setting.show_online_status = True
    setting.profile_visibility = True
    setting.activity_visibility = False
    setting.default_decision_category = "Technology"
    setting.default_reviewer = "Dr. Mark Lee"
    setting.auto_save_draft = True
    setting.default_document_format = "PDF"
    setting.enable_accessibility = False
    setting.enable_keyboard_shortcuts = True
    setting.auto_logout_minutes = 30
    setting.browser_session_hours = 8
    db.commit()
    db.refresh(setting)
    return setting

def _serialize_rows(rows):
    serialized = []
    for row in rows:
        data = {}
        for key, value in row.__dict__.items():
            if key.startswith("_"):
                continue
            if isinstance(value, (datetime,)):
                data[key] = value.isoformat()
            elif isinstance(value, (str, int, float, bool)) or value is None:
                data[key] = value
            else:
                data[key] = str(value)
        serialized.append(data)
    return serialized


@router.get("/export-data/{user_id}")
def export_user_data(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = db.query(User).first()

    user_info = {
        "full_name": user.full_name if user else "User",
        "email": user.email if user else "",
        "employee_id": user.employee_id if user else "",
        "created_at": str(user.created_at) if user else ""
    }

    decisions = db.query(Decision).filter(Decision.created_by == (user.id if user else 1)).all()
    dec_data = [{"id": d.id, "title": d.title, "category": d.category, "status": d.status, "created_at": str(d.created_at)} for d in decisions]

    export_payload = {
        "platform": "Expert Decision Replay Platform (EDRP)",
        "user_profile": user_info,
        "decisions_created": dec_data,
        "export_date": datetime.utcnow().isoformat()
    }

    return Response(
        content=json.dumps(export_payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=edrp_user_data_{user_id}.json"}
    )


def _serialize_rows(rows):
    serialized = []
    if not rows:
        return serialized
    from datetime import date, datetime
    from decimal import Decimal
    import uuid
    for r in rows:
        if r is None:
            continue
        row_dict = {}
        try:
            for col in r.__table__.columns:
                val = getattr(r, col.name, None)
                if isinstance(val, (datetime, date)):
                    val = val.isoformat()
                elif isinstance(val, Decimal):
                    val = float(val)
                elif isinstance(val, uuid.UUID):
                    val = str(val)
                elif isinstance(val, bytes):
                    val = val.decode('utf-8', errors='ignore')
                row_dict[col.name] = val
        except Exception:
            pass
        serialized.append(row_dict)
    return serialized


def _parse_column_val(col, val):
    if val is None:
        return None
    from datetime import datetime, date
    from sqlalchemy import DateTime, Date, Integer, Float, Numeric, Boolean
    
    col_type = col.type
    if isinstance(col_type, (DateTime, Date)):
        if isinstance(val, (datetime, date)):
            return val
        if isinstance(val, str):
            val_clean = val.strip().replace('Z', '+00:00')
            try:
                return datetime.fromisoformat(val_clean)
            except Exception:
                pass
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(val_clean, fmt)
                except Exception:
                    pass
            return None
    elif isinstance(col_type, Boolean):
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "y", "t")
        return bool(val)
    elif isinstance(col_type, Integer):
        try:
            return int(val)
        except Exception:
            return None
    elif isinstance(col_type, (Float, Numeric)):
        try:
            return float(val)
        except Exception:
            return None
    return val


def _restore_backup_data(db: Session, backup_payload: dict, admin_user: User) -> dict:
    if not isinstance(backup_payload, dict):
        raise HTTPException(status_code=400, detail="Invalid backup payload format.")
    
    data_dict = backup_payload.get("data", backup_payload)
    if not isinstance(data_dict, dict):
        raise HTTPException(status_code=400, detail="Backup data must contain a dictionary of table records.")

    RESTORE_TABLE_DEFS = [
        ("roles", Role, "id"),
        ("teams", Team, "id"),
        ("categories", Category, "id"),
        ("users", User, "id"),
        ("system_settings", SystemSetting, "id"),
        ("decisions", Decision, "id"),
        ("alternatives", Alternative, "id"),
        ("reviews", Review, "id"),
        ("replays", Replay, "id"),
        ("discussion_threads", DiscussionThread, "id"),
        ("meeting_notes", MeetingNote, "id"),
        ("comments", Comment, "id"),
        ("attachments", Attachment, "id"),
        ("decision_versions", DecisionVersion, "id"),
        ("verification_codes", VerificationCode, "id"),
        ("email_verifications", EmailVerification, "email"),
        ("activity_logs", ActivityLog, "id"),
        ("notifications", Notification, "id"),
        ("support_tickets", SupportTicket, "id"),
        ("internal_emails", InternalEmail, "id"),
    ]

    restored_stats = {}
    
    for table_name, model_class, pk_name in RESTORE_TABLE_DEFS:
        rows = data_dict.get(table_name)
        if not rows or not isinstance(rows, list):
            continue
        
        pk_vals = [r.get(pk_name) for r in rows if isinstance(r, dict) and r.get(pk_name) is not None]
        existing_map = {}
        if pk_vals:
            try:
                found = db.query(model_class).filter(getattr(model_class, pk_name).in_(pk_vals)).all()
                existing_map = {getattr(f, pk_name): f for f in found}
            except Exception:
                existing_map = {}
        
        count = 0
        for row_dict in rows:
            if not isinstance(row_dict, dict):
                continue
            
            pk_val = row_dict.get(pk_name)
            existing_record = existing_map.get(pk_val)
            
            valid_fields = {}
            for col in model_class.__table__.columns:
                if col.name in row_dict:
                    val = row_dict[col.name]
                    valid_fields[col.name] = _parse_column_val(col, val)
            
            try:
                if existing_record:
                    for k, v in valid_fields.items():
                        setattr(existing_record, k, v)
                else:
                    new_record = model_class(**valid_fields)
                    db.add(new_record)
                count += 1
            except Exception as e:
                print(f"[RESTORE ROW NOTE] Failed on {table_name} pk={pk_val}: {e}")
                continue
                
        if count > 0:
            restored_stats[table_name] = count

    try:
        db.commit()
    except Exception as commit_err:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database commit failed during restore: {str(commit_err)}")

    # Update sequence for PostgreSQL if applicable
    try:
        engine_str = str(db.get_bind().engine.url).lower()
        if "postgres" in engine_str:
            for table_name, model_class, pk_name in RESTORE_TABLE_DEFS:
                if pk_name == "id":
                    try:
                        db.execute(text(f"SELECT setval(pg_get_serial_sequence('{model_class.__tablename__}', 'id'), coalesce(max(id), 1)) FROM {model_class.__tablename__};"))
                        db.commit()
                    except Exception:
                        pass
    except Exception:
        pass

    total_records = sum(restored_stats.values())
    
    # Add audit log entry
    try:
        act = ActivityLog(
            user_id=admin_user.id,
            action="Backup Data Restored",
            details=f"Admin {admin_user.full_name} restored {total_records} records across {len(restored_stats)} tables into live system data."
        )
        db.add(act)
        db.commit()
    except Exception:
        pass

    return {
        "success": True,
        "message": f"Successfully restored {total_records} records across {len(restored_stats)} tables into normal platform data.",
        "restored_stats": restored_stats,
        "total_records": total_records
    }


@router.get("/backup-data/{user_id}")
@router.get("/backup-data")
def backup_all_data(user_id: int = None, db: Session = Depends(get_db)):
    user = None
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = db.query(User).filter(User.role_id == 1, User.is_active == True).first() or db.query(User).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user found for backup.")

    role_name = (user.role.role_name if user.role else "").strip().lower()
    if role_name not in {"administrator", "admin"} and "admin" not in role_name and user.role_id != 1:
        raise HTTPException(status_code=403, detail="Only administrators can perform a full backup.")

    backup_payload = {
        "platform": "Expert Decision Replay Platform (EDRP)",
        "backup_type": "full",
        "exported_by": user.full_name,
        "exported_by_id": user.id,
        "exported_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "data": {
            "roles": _serialize_rows(db.query(Role).all()),
            "teams": _serialize_rows(db.query(Team).all()),
            "categories": _serialize_rows(db.query(Category).all()),
            "users": _serialize_rows(db.query(User).all()),
            "system_settings": _serialize_rows(db.query(SystemSetting).all()),
            "decisions": _serialize_rows(db.query(Decision).all()),
            "reviews": _serialize_rows(db.query(Review).all()),
            "replays": _serialize_rows(db.query(Replay).all()),
            "discussion_threads": _serialize_rows(db.query(DiscussionThread).all()),
            "comments": _serialize_rows(db.query(Comment).all()),
            "alternatives": _serialize_rows(db.query(Alternative).all()),
            "meeting_notes": _serialize_rows(db.query(MeetingNote).all()),
            "attachments": _serialize_rows(db.query(Attachment).all()),
            "decision_versions": _serialize_rows(db.query(DecisionVersion).all()),
            "verification_codes": _serialize_rows(db.query(VerificationCode).all()),
            "email_verifications": _serialize_rows(db.query(EmailVerification).all()),
            "activity_logs": _serialize_rows(db.query(ActivityLog).all()),
            "notifications": _serialize_rows(db.query(Notification).all()),
            "support_tickets": _serialize_rows(db.query(SupportTicket).all()),
            "internal_emails": _serialize_rows(db.query(InternalEmail).all())
        }
    }

    raw_json = json.dumps(backup_payload, indent=2)
    backup_record = BackupRecord(
        user_id=user.id,
        backup_name=f"edrp_full_backup_{user.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        backup_payload=raw_json,
        created_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(backup_record)
    db.commit()

    return Response(
        content=raw_json,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={backup_record.backup_name}.json"}
    )


@router.get("/backup-history/{user_id}")
@router.get("/backup-history")
def get_backup_history(user_id: int = None, db: Session = Depends(get_db)):
    user = None
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
    if not user:
        user = db.query(User).filter(User.role_id == 1, User.is_active == True).first() or db.query(User).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user found.")

    role_name = (user.role.role_name if user.role else "").strip().lower()
    if role_name not in {"administrator", "admin"} and "admin" not in role_name and user.role_id != 1:
        raise HTTPException(status_code=403, detail="Only administrators can view backup history.")

    records = db.query(BackupRecord).order_by(BackupRecord.id.desc()).all()
    results = []
    for record in records:
        parsed = {}
        stats = {}
        if record.backup_payload:
            try:
                parsed = json.loads(record.backup_payload)
                data_dict = parsed.get("data", {})
                for k, v in data_dict.items():
                    if isinstance(v, list):
                        stats[k] = len(v)
            except Exception:
                pass
        
        payload_size_kb = round(len(record.backup_payload.encode('utf-8')) / 1024, 1) if record.backup_payload else 0
        results.append({
            "id": record.id,
            "backup_name": record.backup_name,
            "created_at": record.created_at,
            "size_kb": payload_size_kb,
            "stats": stats,
            "preview": parsed
        })
    return results


@router.post("/restore-backup/{backup_id}")
def restore_backup_by_id(backup_id: int, user_id: int = None, db: Session = Depends(get_db)):
    admin_user = None
    if user_id:
        admin_user = db.query(User).filter(User.id == user_id).first()
    if not admin_user:
        admin_user = db.query(User).filter(User.role_id == 1, User.is_active == True).first() or db.query(User).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user not found.")

    role_name = (admin_user.role.role_name if admin_user.role else "").strip().lower()
    if role_name not in {"administrator", "admin"} and "admin" not in role_name and admin_user.role_id != 1:
        raise HTTPException(status_code=403, detail="Only administrators can restore backup data.")

    record = db.query(BackupRecord).filter(BackupRecord.id == backup_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Backup record not found.")

    try:
        backup_payload = json.loads(record.backup_payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Corrupted backup payload in record.")

    return _restore_backup_data(db, backup_payload, admin_user)


@router.post("/restore-data")
def restore_backup_json(payload: dict = Body(...), user_id: int = None, db: Session = Depends(get_db)):
    admin_user = None
    uid = payload.get("user_id") or user_id
    if uid:
        admin_user = db.query(User).filter(User.id == int(uid)).first()
    if not admin_user:
        admin_user = db.query(User).filter(User.role_id == 1, User.is_active == True).first() or db.query(User).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user not found.")

    role_name = (admin_user.role.role_name if admin_user.role else "").strip().lower()
    if role_name not in {"administrator", "admin"} and "admin" not in role_name and admin_user.role_id != 1:
        raise HTTPException(status_code=403, detail="Only administrators can restore backup data.")

    backup_content = payload.get("backup_data", payload)
    return _restore_backup_data(db, backup_content, admin_user)


@router.post("/restore-upload")
async def restore_backup_file(file: UploadFile = File(...), user_id: int = None, db: Session = Depends(get_db)):
    admin_user = None
    if user_id:
        admin_user = db.query(User).filter(User.id == user_id).first()
    if not admin_user:
        admin_user = db.query(User).filter(User.role_id == 1, User.is_active == True).first() or db.query(User).first()
    if not admin_user:
        raise HTTPException(status_code=404, detail="Admin user not found.")

    role_name = (admin_user.role.role_name if admin_user.role else "").strip().lower()
    if role_name not in {"administrator", "admin"} and "admin" not in role_name and admin_user.role_id != 1:
        raise HTTPException(status_code=403, detail="Only administrators can restore backup data.")

    try:
        content = await file.read()
        backup_payload = json.loads(content.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON backup file: {str(e)}")

    return _restore_backup_data(db, backup_payload, admin_user)


@router.post("/test-email")
def test_email(req: TestEmailRequest, db: Session = Depends(get_db)):
    setting = _get_or_create_settings(db)
    target = req.target_email.strip()
    
    if not target:
        raise HTTPException(status_code=400, detail="Target email address is required")
        
    def _dispatch():
        try:
            body = f"Hello,\n\nThis is a test email sent from the Expert Decision Replay Platform (EDRP) System Settings.\n\nSubject: {req.subject}\nMessage: {req.message}\n\nConfiguration Status: Connected Successfully!\n\nBest Regards,\n{setting.email_sender_name}"
            _send_smtp_mail(target, req.subject, body)
        except Exception as err:
            print(f"Test email dispatch note: {err}")
            
    threading.Thread(target=_dispatch, daemon=True).start()
    return {"message": f"Test email dispatched to {target}. Please check inbox.", "status": "success"}
