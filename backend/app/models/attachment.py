from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.base import Base

class Attachment(Base):
    __tablename__ = "attachments"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String)
    file_size = Column(Integer)
    file_data = Column(LargeBinary, nullable=True)
    decision_id = Column(Integer, ForeignKey("decisions.id"))
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    decision = relationship("Decision", back_populates="attachments")
    uploader = relationship("User")
