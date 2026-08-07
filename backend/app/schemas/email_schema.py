from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class InternalEmailCreate(BaseModel):
    sender_id: int
    recipient_type: Optional[str] = "Employee"
    recipient_names: str
    subject: str
    priority: Optional[str] = "Medium"
    message: str
    attachment_name: Optional[str] = None

class InternalEmailResponse(BaseModel):
    id: int
    sender_id: int
    sender_name: Optional[str] = "User"
    sender_role: Optional[str] = "Employee"
    sender_initials: Optional[str] = "U"
    recipient_type: str
    recipient_names: str
    subject: str
    priority: str
    message: str
    attachment_name: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        orm_mode = True
