from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database.base import Base

class InternalEmail(Base):
    __tablename__ = "internal_emails"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_type = Column(String(50), default="Employee") # Employee, Reviewer, Manager, Administrator
    recipient_names = Column(String(255), nullable=False)   # e.g. "Dr. Mark Lee, Sarah Chen"
    subject = Column(String(255), nullable=False)
    priority = Column(String(20), default="Medium")        # Low, Medium, High
    message = Column(Text, nullable=False)
    attachment_name = Column(String(255), nullable=True)
    status = Column(String(50), default="Delivered")        # Sent, Delivered, Read
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    sender = relationship("User", foreign_keys=[sender_id])
