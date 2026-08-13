from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone

from app.database.connection import get_db
from app.models.internal_email import InternalEmail
from app.models.user import User
from app.models.activity_log import ActivityLog
from app.schemas.email_schema import InternalEmailCreate, InternalEmailResponse
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/email",
    tags=["Email Service"]
)

import threading
from app.services.email_service import send_smtp_service_email

@router.post("/send", response_model=InternalEmailResponse)
def send_email(req: InternalEmailCreate, db: Session = Depends(get_db)):
    sender = db.query(User).filter(User.id == req.sender_id).first()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender user not found")

    delivery_method = (req.delivery_method or "gmail").lower().strip()
    if delivery_method not in ["gmail", "smtp"]:
        delivery_method = "gmail"

    new_email = InternalEmail(
        sender_id=req.sender_id,
        recipient_type=req.recipient_type or "Employee",
        recipient_names=req.recipient_names.strip(),
        subject=req.subject.strip(),
        priority=req.priority or "Medium",
        message=req.message.strip(),
        attachment_name=req.attachment_name,
        status="Delivered",
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_email)
    db.commit()
    db.refresh(new_email)

    # Activity log
    try:
        log = ActivityLog(
            user_id=req.sender_id,
            action=f"Sent internal email via {delivery_method.upper()} to {new_email.recipient_names[:30]}",
            details=f"Subject: {new_email.subject[:40]} | Method: {delivery_method}"
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Error logging email activity: {e}")

    # 1. Independent In-App Notifications (Guaranteed to always succeed)
    matched_recipient_emails = []
    try:
        all_users = db.query(User).all()
        for u in all_users:
            if u.id != req.sender_id:
                name_match = u.full_name and u.full_name.lower() in req.recipient_names.lower()
                id_match = u.employee_id and u.employee_id.lower() in req.recipient_names.lower()
                email_match = u.email and u.email.lower() in req.recipient_names.lower()
                
                if name_match or id_match or email_match:
                    if u.email:
                        matched_recipient_emails.append(u.email)
                    NotificationService.create_notification(
                        db,
                        user_id=u.id,
                        message=f"You received an internal email from {sender.full_name}: '{new_email.subject}'",
                        notification_type="Internal Email"
                    )
    except Exception as notif_err:
        print(f"Error notifying email recipients: {notif_err}")

    # If raw email address was typed directly in recipient_names, include it
    for word in req.recipient_names.replace(",", " ").replace(";", " ").split():
        clean_word = word.strip()
        if "@" in clean_word and "." in clean_word and clean_word not in matched_recipient_emails:
            matched_recipient_emails.append(clean_word)

    # 2. Routed Email Delivery (Original Gmail vs Project SMTP Email Service)
    # Strictly sends through the single chosen delivery method
    if matched_recipient_emails:
        target_emails = list(set(matched_recipient_emails))
        sender_name = sender.full_name or "EDRP User"
        subj = new_email.subject
        msg_body = new_email.message
        prio = new_email.priority

        def _async_dispatch_email():
            for dest_email in target_emails:
                try:
                    send_smtp_service_email(
                        to_email=dest_email,
                        sender_name=sender_name,
                        subject=subj,
                        message=msg_body,
                        priority=prio,
                        delivery_method=delivery_method
                    )
                except Exception as mail_err:
                    print(f"Email delivery error ({delivery_method}) to {dest_email}: {mail_err}")

        threading.Thread(target=_async_dispatch_email, daemon=True).start()

    res = InternalEmailResponse.from_orm(new_email)
    res.sender_name = sender.full_name
    res.sender_role = sender.role.role_name if sender.role else "Employee"
    res.sender_initials = "".join([p[0].upper() for p in sender.full_name.split()])[:2] if sender.full_name else "U"
    return res

@router.get("/inbox/{user_id}", response_model=List[InternalEmailResponse])
def get_inbox_emails(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    user_name = user.full_name.lower() if (user and user.full_name) else ""
    user_empid = user.employee_id.lower() if (user and user.employee_id) else ""

    # Fetch emails sent to this user or where user is sender
    emails = db.query(InternalEmail).order_by(InternalEmail.id.desc()).all()
    res = []
    for e in emails:
        sender = db.query(User).filter(User.id == e.sender_id).first()
        r = InternalEmailResponse.from_orm(e)
        r.sender_name = sender.full_name if sender else "User"
        r.sender_role = sender.role.role_name if (sender and sender.role) else "Employee"
        r.sender_initials = "".join([p[0].upper() for p in (sender.full_name if sender else "U").split()])[:2]
        
        rec_lower = (e.recipient_names or "").lower()
        if e.sender_id == user_id or (user_name and user_name in rec_lower) or (user_empid and user_empid in rec_lower) or e.recipient_type == "All":
            res.append(r)
    return res

@router.get("/sent/{user_id}", response_model=List[InternalEmailResponse])
def get_sent_emails(user_id: int, db: Session = Depends(get_db)):
    emails = db.query(InternalEmail).filter(InternalEmail.sender_id == user_id).order_by(InternalEmail.id.desc()).all()
    user = db.query(User).filter(User.id == user_id).first()
    res = []
    for e in emails:
        r = InternalEmailResponse.from_orm(e)
        r.sender_name = user.full_name if user else "User"
        r.sender_role = user.role.role_name if (user and user.role) else "Employee"
        r.sender_initials = "".join([p[0].upper() for p in (user.full_name if user else "U").split()])[:2]
        res.append(r)
    return res

@router.get("/stats/{user_id}")
def get_email_stats(user_id: int, db: Session = Depends(get_db)):
    total_sent = db.query(InternalEmail).filter(InternalEmail.sender_id == user_id).count()
    total_delivered = db.query(InternalEmail).filter(InternalEmail.sender_id == user_id, InternalEmail.status.in_(["Delivered", "Read"])).count()
    total_read = db.query(InternalEmail).filter(InternalEmail.sender_id == user_id, InternalEmail.status == "Read").count()

    return {
        "sent": total_sent,
        "delivered": total_delivered,
        "read": total_read
    }

@router.put("/read/{email_id}")
def mark_email_read(email_id: int, db: Session = Depends(get_db)):
    email = db.query(InternalEmail).filter(InternalEmail.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    email.status = "Read"
    db.commit()
    return {"message": "Email marked as read"}
