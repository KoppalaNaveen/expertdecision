from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.database.base import Base


class BackupRecord(Base):
    __tablename__ = "backup_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    backup_name = Column(String(255), nullable=False)
    backup_payload = Column(Text, nullable=False)
    created_at = Column(String(50), nullable=False, default=lambda: func.current_timestamp())
