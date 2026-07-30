from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from app.database.connection import Base

class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)

    # General
    language = Column(String(50), default="English (US)")
    timezone = Column(String(100), default="Asia/Kolkata (IST)")
    date_format = Column(String(50), default="DD / MM / YYYY")
    theme = Column(String(50), default="Light")
    default_dashboard = Column(String(100), default="Decision Management")

    # Security
    enable_two_factor = Column(Boolean, default=True)

    # Notifications
    enable_email_notifications = Column(Boolean, default=True)
    enable_inapp_notifications = Column(Boolean, default=True)
    enable_decision_updates = Column(Boolean, default=True)
    enable_approval_requests = Column(Boolean, default=True)
    enable_discussion_replies = Column(Boolean, default=False)
    enable_repo_updates = Column(Boolean, default=False)
    enable_weekly_summary = Column(Boolean, default=True)

    # Privacy
    show_online_status = Column(Boolean, default=True)
    profile_visibility = Column(Boolean, default=True)
    activity_visibility = Column(Boolean, default=False)

    # Decision Preferences
    default_decision_category = Column(String(100), default="Technology")
    default_reviewer = Column(String(100), default="Dr. Mark Lee")
    auto_save_draft = Column(Boolean, default=True)
    default_document_format = Column(String(50), default="PDF")

    # System Preferences
    enable_accessibility = Column(Boolean, default=False)
    enable_keyboard_shortcuts = Column(Boolean, default=True)
    auto_logout_minutes = Column(Integer, default=30)
    browser_session_hours = Column(Integer, default=8)

    # Legacy / SMTP fields
    smtp_server = Column(String(150), default="smtp.gmail.com")
    smtp_port = Column(Integer, default=587)
    smtp_username = Column(String(150), default="support@edrp-platform.com")
    smtp_password = Column(String(255), default="")
    email_sender_name = Column(String(100), default="EDRP Platform Support")

    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    updated_by = Column(String(100), default="Administrator")
