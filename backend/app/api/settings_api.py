from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session
from datetime import datetime
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
from app.models.user import VerificationCode
from app.models.alternative import Alternative
from app.models.attachment import Attachment
from app.models.comment import Comment, DiscussionThread
from app.models.decision_version import DecisionVersion
from app.models.email_verification import EmailVerification
from app.models.meeting_note import MeetingNote
from app.models.notification import Notification
from app.models.replay import Replay
from app.models.support_ticket import SupportTicket
from app.schemas.settings_schema import (
    SystemSettingUpdate, SystemSettingResponse, ChangePasswordRequest, TestEmailRequest
)
from app.services.email_service import _send_smtp_mail
from app.core.security import verify_password, hash_password
from app.models.backup_record import BackupRecord

router = APIRouter(
    prefix="/settings",
    tags=["Settings"]
)

def _get_or_create_settings(db: Session) -> SystemSetting:
    setting = db.query(SystemSetting).first()
    if not setting:
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
            default_reviewer="Dr. Mark Lee",
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

@router.get("/", response_model=SystemSettingResponse)
def get_settings(db: Session = Depends(get_db)):
    setting = _get_or_create_settings(db)
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

    # Log security audit
    try:
        log = ActivityLog(user_id=user.id, action="Changed account password", details="Password updated successfully from Settings")
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Password change audit log note: {e}")

    return {"message": "Password changed successfully! Please use your new password for future sign-ins.", "status": "success"}

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


@router.get("/backup-data/{user_id}")
def backup_all_data(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    role_name = (user.role.role_name if user.role else "").strip().lower()
    if role_name not in {"administrator", "admin"} and "admin" not in role_name:
        raise HTTPException(status_code=403, detail="Only administrators can perform a full backup.")

    backup_payload = {
        "platform": "Expert Decision Replay Platform (EDRP)",
        "backup_type": "full",
        "exported_by": user.full_name,
        "exported_at": datetime.utcnow().isoformat(),
        "data": {
            "roles": _serialize_rows(db.query(Role).all()),
            "teams": _serialize_rows(db.query(Team).all()),
            "users": _serialize_rows(db.query(User).all()),
            "verification_codes": _serialize_rows(db.query(VerificationCode).all()),
            "email_verifications": _serialize_rows(db.query(EmailVerification).all()),
            "decisions": _serialize_rows(db.query(Decision).all()),
            "reviews": _serialize_rows(db.query(Review).all()),
            "replays": _serialize_rows(db.query(Replay).all()),
            "discussion_threads": _serialize_rows(db.query(DiscussionThread).all()),
            "comments": _serialize_rows(db.query(Comment).all()),
            "alternatives": _serialize_rows(db.query(Alternative).all()),
            "meeting_notes": _serialize_rows(db.query(MeetingNote).all()),
            "attachments": _serialize_rows(db.query(Attachment).all()),
            "decision_versions": _serialize_rows(db.query(DecisionVersion).all()),
            "activity_logs": _serialize_rows(db.query(ActivityLog).all()),
            "notifications": _serialize_rows(db.query(Notification).all()),
            "support_tickets": _serialize_rows(db.query(SupportTicket).all())
        }
    }

    backup_record = BackupRecord(
        user_id=user.id,
        backup_name=f"edrp_full_backup_{user.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        backup_payload=json.dumps(backup_payload, indent=2),
        created_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(backup_record)
    db.commit()

    return Response(
        content=json.dumps(backup_payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={backup_record.backup_name}.json"}
    )


@router.get("/backup-history/{user_id}")
def get_backup_history(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User account not found.")

    role_name = (user.role.role_name if user.role else "").strip().lower()
    if role_name not in {"administrator", "admin"} and "admin" not in role_name:
        raise HTTPException(status_code=403, detail="Only administrators can view backup history.")

    records = db.query(BackupRecord).filter(BackupRecord.user_id == user.id).order_by(BackupRecord.id.desc()).all()
    return [{
        "id": record.id,
        "backup_name": record.backup_name,
        "created_at": record.created_at,
        "preview": json.loads(record.backup_payload) if record.backup_payload else {}
    } for record in records]

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
