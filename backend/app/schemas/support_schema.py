from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class SupportTicketCreate(BaseModel):
    user_id: int
    subject: str
    category: str = "General Query"
    priority: str = "Medium"
    message: str

class SupportTicketReply(BaseModel):
    ticket_id: int
    admin_reply: str
    status: str = "Resolved"

class SupportTicketResponse(BaseModel):
    id: int
    ticket_number: str
    user_id: int
    user_name: Optional[str] = "User"
    user_email: Optional[str] = "user@company.com"
    subject: str
    category: str
    priority: str
    message: str
    status: str
    admin_reply: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AiSupportChatRequest(BaseModel):
    message: str
    user_id: Optional[int] = None
    user_name: Optional[str] = "User"
    category: Optional[str] = "General"
    conversation_history: Optional[List[dict]] = []
    page_context: Optional[str] = None
    page_title: Optional[str] = None
    page_url: Optional[str] = None

class AiSupportChatResponse(BaseModel):
    reply: str
    suggested_actions: Optional[List[str]] = []
    source: str = "EDRP AI Assistant"
