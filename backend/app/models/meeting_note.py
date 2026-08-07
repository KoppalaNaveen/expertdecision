from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.connection import Base

class MeetingNote(Base):
    __tablename__ = "meeting_notes"
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"))
    title = Column(String)
    meeting_date = Column(DateTime(timezone=True))
    notes = Column(Text)
    participants = Column(Text, nullable=True)
    agenda = Column(Text, nullable=True)
    action_items = Column(Text, nullable=True)
    next_meeting_date = Column(DateTime(timezone=True), nullable=True)
    meeting_link = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    decision = relationship("Decision", back_populates="meeting_notes")
    author = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
