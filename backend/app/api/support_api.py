from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import random
import threading

from app.database.connection import get_db
from app.models.support_ticket import SupportTicket
from app.models.user import User
from app.models.activity_log import ActivityLog
from app.schemas.support_schema import SupportTicketCreate, SupportTicketReply, SupportTicketResponse
from app.services.email_service import _send_smtp_mail

router = APIRouter(
    prefix="/support",
    tags=["Support"]
)

def _generate_ticket_number() -> str:
    return f"SUP-{random.randint(1000, 9999)}"

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

    res = SupportTicketResponse.from_orm(new_ticket)
    res.user_name = user.full_name if user else "User"
    res.user_email = user.email if user else "user@company.com"
    return res

@router.get("/my-tickets/{user_id}", response_model=List[SupportTicketResponse])
def get_user_tickets(user_id: int, db: Session = Depends(get_db)):
    tickets = db.query(SupportTicket).filter(SupportTicket.user_id == user_id).order_by(SupportTicket.id.desc()).all()
    user = db.query(User).filter(User.id == user_id).first()
    
    result = []
    for t in tickets:
        r = SupportTicketResponse.from_orm(t)
        r.user_name = user.full_name if user else "User"
        r.user_email = user.email if user else "user@company.com"
        result.append(r)
    return result

@router.get("/all", response_model=List[SupportTicketResponse])
def get_all_tickets(db: Session = Depends(get_db)):
    tickets = db.query(SupportTicket).order_by(SupportTicket.id.desc()).all()
    
    result = []
    for t in tickets:
        u = db.query(User).filter(User.id == t.user_id).first()
        r = SupportTicketResponse.from_orm(t)
        r.user_name = u.full_name if u else "User"
        r.user_email = u.email if u else "user@company.com"
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
