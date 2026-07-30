from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SystemSettingUpdate(BaseModel):
    language: Optional[str] = "English (US)"
    timezone: Optional[str] = "Asia/Kolkata (IST)"
    date_format: Optional[str] = "DD / MM / YYYY"
    theme: Optional[str] = "Light"
    default_dashboard: Optional[str] = "Decision Management"

    enable_two_factor: Optional[bool] = True

    enable_email_notifications: Optional[bool] = True
    enable_inapp_notifications: Optional[bool] = True
    enable_decision_updates: Optional[bool] = True
    enable_approval_requests: Optional[bool] = True
    enable_discussion_replies: Optional[bool] = False
    enable_repo_updates: Optional[bool] = False
    enable_weekly_summary: Optional[bool] = True

    show_online_status: Optional[bool] = True
    profile_visibility: Optional[bool] = True
    activity_visibility: Optional[bool] = False

    default_decision_category: Optional[str] = "Technology"
    default_reviewer: Optional[str] = "Dr. Mark Lee"
    auto_save_draft: Optional[bool] = True
    default_document_format: Optional[str] = "PDF"

    enable_accessibility: Optional[bool] = False
    enable_keyboard_shortcuts: Optional[bool] = True
    auto_logout_minutes: Optional[int] = 30
    browser_session_hours: Optional[int] = 8

    smtp_server: Optional[str] = "smtp.gmail.com"
    smtp_port: Optional[int] = 587
    smtp_username: Optional[str] = "support@edrp-platform.com"
    smtp_password: Optional[str] = ""
    email_sender_name: Optional[str] = "EDRP Platform Support"
    updated_by: Optional[str] = "Administrator"

class SystemSettingResponse(BaseModel):
    id: int
    language: str
    timezone: str
    date_format: str
    theme: str
    default_dashboard: str

    enable_two_factor: bool

    enable_email_notifications: bool
    enable_inapp_notifications: bool
    enable_decision_updates: bool
    enable_approval_requests: bool
    enable_discussion_replies: bool
    enable_repo_updates: bool
    enable_weekly_summary: bool

    show_online_status: bool
    profile_visibility: bool
    activity_visibility: bool

    default_decision_category: str
    default_reviewer: str
    auto_save_draft: bool
    default_document_format: str

    enable_accessibility: bool
    enable_keyboard_shortcuts: bool
    auto_logout_minutes: int
    browser_session_hours: int

    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    email_sender_name: str
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = "Administrator"

    class Config:
        from_attributes = True

class ChangePasswordRequest(BaseModel):
    user_id: int
    current_password: str
    new_password: str
    confirm_password: str

class TestEmailRequest(BaseModel):
    target_email: str
    subject: Optional[str] = "EDRP System Test Email"
    message: Optional[str] = "This is a test notification email sent from EDRP system settings."
