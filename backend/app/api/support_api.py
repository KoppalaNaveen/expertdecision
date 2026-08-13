from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import random
import threading
import re

from app.database.connection import get_db
from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.models.activity_log import ActivityLog
from app.schemas.support_schema import (
    SupportTicketCreate,
    SupportTicketReply,
    SupportTicketResponse,
    AiSupportChatRequest,
    AiSupportChatResponse
)
from app.services.email_service import _send_smtp_mail
from app.services.ai_support_service import generate_ai_response

router = APIRouter(
    prefix="/support",
    tags=["Support"]
)

@router.post("/ai-chat", response_model=AiSupportChatResponse)
def ai_support_chat(req: AiSupportChatRequest, db: Session = Depends(get_db)):
    """
    Intelligent AI Support Assistant for EDRP with live LLM integrations and fallback knowledge engine.
    """
    user_name = req.user_name or "User"
    if req.user_id:
        user = db.query(User).filter(User.id == req.user_id).first()
        if user and user.full_name:
            user_name = user.full_name

    response_data = generate_ai_response(
        user_message=req.message,
        user_name=user_name,
        user_id=req.user_id,
        conversation_history=req.conversation_history
    )
    return AiSupportChatResponse(
        reply=response_data["reply"],
        suggested_actions=response_data.get("suggested_actions", []),
        source=response_data.get("source", "EDRP AI Assistant")
    )


def _generate_ticket_number() -> str:
    return f"SUP-{random.randint(1000, 9999)}"

def _extract_contact_sender(message: str, fallback_name: str, fallback_email: str):
    if not message:
        return fallback_name, fallback_email
    match = re.search(r"From:\s*([^<\n]+)\s*<([^>\n]+)>", message, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        email = match.group(2).strip()
        if name and email:
            return name, email
    return fallback_name, fallback_email

@router.post("/create", response_model=SupportTicketResponse)
def create_support_ticket(req: SupportTicketCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == req.user_id).first()
    if not user:
        system_user = db.query(User).first()
        if system_user:
            req.user_id = system_user.id
            user = system_user
        else:
            raise HTTPException(status_code=404, detail="User not found")
            
    ticket_num = _generate_ticket_number()
    new_ticket = SupportTicket(
        ticket_number=ticket_num,
        user_id=req.user_id,
        subject=req.subject.strip(),
        category=req.category,
        priority=req.priority,
        message=req.message.strip(),
        status="Open"
    )
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)

    # Activity log
    try:
        log = ActivityLog(
            user_id=req.user_id,
            action=f"Submitted support ticket {ticket_num}: {new_ticket.subject[:40]}",
            details=f"Category: {req.category}, Priority: {req.priority}"
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Support ticket audit log note: {e}")

    # Email notification to user
    if user and user.email:
        target_email = user.email
        subj = f"Support Ticket Confirmation [{ticket_num}]: {new_ticket.subject}"
        body = f"Hello {user.full_name},\n\nWe have received your support request [{ticket_num}]. Our support team will review your query and get back to you shortly.\n\nTicket Summary:\n- Subject: {new_ticket.subject}\n- Category: {new_ticket.category}\n- Priority: {new_ticket.priority}\n- Status: Open\n\nThank you,\nEDRP Support Team"
        
        def _async_confirm():
            try:
                _send_smtp_mail(target_email, subj, body)
            except Exception as mail_err:
                print(f"Support confirm email error: {mail_err}")
                
        threading.Thread(target=_async_confirm, daemon=True).start()

    # Deliver in-app Notification to Administrators using NotificationService
    try:
        from app.services.notification_service import NotificationService
        from app.models.role import Role
        
        admin_roles = db.query(Role).filter(Role.role_name.in_(["Admin", "Administrator"])).all()
        admin_role_ids = [r.id for r in admin_roles]
        
        admins = []
        if admin_role_ids:
            admins = db.query(User).filter(User.role_id.in_(admin_role_ids)).all()
        
        if not admins:
            admin_user = db.query(User).filter(User.id == 1).first()
            if admin_user:
                admins = [admin_user]

        user_display_name = user.full_name if user else "Visitor"
        notif_msg = f"New Support Request Received [{ticket_num}] from {user_display_name}: {new_ticket.subject}"

        for admin in admins:
            NotificationService.create_notification(
                db,
                user_id=admin.id,
                message=notif_msg,
                notification_type="Support Request"
            )
    except Exception as notif_err:
        print(f"Support ticket admin notification error: {notif_err}")

    res = SupportTicketResponse.from_orm(new_ticket)
    name, email = _extract_contact_sender(new_ticket.message, user.full_name if user else "User", user.email if user else "user@company.com")
    res.user_name = name
    res.user_email = email
    return res

@router.get("/my-tickets/{user_id}", response_model=List[SupportTicketResponse])
def get_user_tickets(user_id: int, db: Session = Depends(get_db)):
    tickets = db.query(SupportTicket).filter(SupportTicket.user_id == user_id).order_by(SupportTicket.id.desc()).all()
    user = db.query(User).filter(User.id == user_id).first()
    
    result = []
    for t in tickets:
        r = SupportTicketResponse.from_orm(t)
        name, email = _extract_contact_sender(t.message, user.full_name if user else "User", user.email if user else "user@company.com")
        r.user_name = name
        r.user_email = email
        result.append(r)
    return result

@router.get("/all", response_model=List[SupportTicketResponse])
def get_all_tickets(db: Session = Depends(get_db)):
    tickets = db.query(SupportTicket).order_by(SupportTicket.id.desc()).all()
    
    result = []
    for t in tickets:
        u = db.query(User).filter(User.id == t.user_id).first()
        r = SupportTicketResponse.from_orm(t)
        name, email = _extract_contact_sender(t.message, u.full_name if u else "User", u.email if u else "user@company.com")
        r.user_name = name
        r.user_email = email
        result.append(r)
    return result

@router.post("/reply", response_model=SupportTicketResponse)
def reply_support_ticket(req: SupportTicketReply, db: Session = Depends(get_db)):
    ticket = db.query(SupportTicket).filter(SupportTicket.id == req.ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Support ticket not found")

    ticket.admin_reply = req.admin_reply.strip()
    ticket.status = req.status or "Resolved"
    from datetime import datetime, timezone
    ticket.resolved_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(ticket)

    user = db.query(User).filter(User.id == ticket.user_id).first()

    # Send resolution email to user
    if user and user.email:
        target_email = user.email
        subj = f"Support Ticket Update [{ticket.ticket_number}]: {ticket.subject}"
        body = f"Hello {user.full_name},\n\nYour support request [{ticket.ticket_number}] has been updated by the EDRP Support Team.\n\nStatus: {ticket.status}\n\nSupport Response:\n{ticket.admin_reply}\n\nBest Regards,\nEDRP Support Team"
        
        def _async_reply_mail():
            try:
                _send_smtp_mail(target_email, subj, body)
            except Exception as err:
                print(f"Support reply email error: {err}")
                
        threading.Thread(target=_async_reply_mail, daemon=True).start()

    res = SupportTicketResponse.from_orm(ticket)
    res.user_name = user.full_name if user else "User"
    res.user_email = user.email if user else "user@company.com"
    return res

@router.delete("/delete/{ticket_id}")
@router.delete("/{ticket_id}")
def delete_support_ticket(ticket_id: str, db: Session = Depends(get_db)):
    clean_id = str(ticket_id).strip()
    ticket = None

    if clean_id.isdigit():
        ticket = db.query(SupportTicket).filter(SupportTicket.id == int(clean_id)).first()

    if not ticket:
        ticket = db.query(SupportTicket).filter(SupportTicket.ticket_number == clean_id).first()

    if not ticket and not clean_id.startswith("SUP-"):
        ticket = db.query(SupportTicket).filter(SupportTicket.ticket_number == f"SUP-{clean_id}").first()

    if not ticket:
        raise HTTPException(status_code=404, detail=f"Support ticket '{ticket_id}' not found")

    real_id = ticket.id
    ticket_num = ticket.ticket_number
    user_id = ticket.user_id
    subj_excerpt = (ticket.subject or "")[:40]

    try:
        db.delete(ticket)
        db.commit()
    except Exception as err:
        db.rollback()
        print(f"Error deleting support ticket #{clean_id}: {err}")
        raise HTTPException(status_code=500, detail=f"Database error deleting ticket: {str(err)}")

    # Post-deletion Activity log in separate isolated transaction
    try:
        valid_user = db.query(User).filter(User.id == user_id).first() if user_id else None
        log_user_id = valid_user.id if valid_user else 1
        log = ActivityLog(
            user_id=log_user_id,
            action=f"Deleted support ticket {ticket_num}",
            details=f"Subject: {subj_excerpt}"
        )
        db.add(log)
        db.commit()
    except Exception as log_err:
        print(f"Support ticket delete audit log note: {log_err}")
        db.rollback()

    return {"message": f"Support ticket {ticket_num} deleted successfully", "id": real_id}
