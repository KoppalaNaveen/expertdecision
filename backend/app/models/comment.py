from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.connection import Base

class DiscussionThread(Base):
    __tablename__ = "discussion_threads"
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"))
    topic = Column(String)
    status = Column(String, default="Open") # Open, In Progress, Resolved, Closed
    is_pinned = Column(Boolean, default=False)
    pinned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    decision = relationship("Decision", back_populates="threads")
    creator = relationship("User", foreign_keys=[created_by])
    comments = relationship("Comment", back_populates="thread", cascade="all, delete-orphan")

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(Integer, ForeignKey("discussion_threads.id"), nullable=True)
    meeting_note_id = Column(Integer, ForeignKey("meeting_notes.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    reply_to_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    content = Column(Text)
    is_edited = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    is_pinned = Column(Boolean, default=False)
    edit_history = Column(Text, nullable=True)
    reactions = Column(Text, nullable=True)
    read_receipts = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    thread = relationship("DiscussionThread", back_populates="comments")
    author = relationship("User", foreign_keys=[user_id])
    parent_comment = relationship("Comment", remote_side=[id], backref="replies")
