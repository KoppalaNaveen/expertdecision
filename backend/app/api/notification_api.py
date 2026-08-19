from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database.connection import get_db
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"]
)

@router.get("/{user_id}", response_model=List[NotificationResponse])
def get_notifications(user_id: int, db: Session = Depends(get_db)):
    notifications = db.query(Notification).filter(Notification.user_id == user_id).order_by(Notification.created_at.desc()).all()
    return notifications

@router.put("/{user_id}/mark-all-read")
def mark_all_read(user_id: int, db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read == False).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}

@router.put("/{user_id}/read/{notification_id}")
@router.put("/single/{notification_id}/mark-read")
def mark_single_notification_read(notification_id: int, db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.id == notification_id).update({"is_read": True})
    db.commit()
    return {"message": "Notification marked as read"}

@router.delete("/{user_id}/clear-all")
def clear_all_notifications(user_id: int, db: Session = Depends(get_db)):
    db.query(Notification).filter(Notification.user_id == user_id).delete()
    db.commit()
    return {"message": "All notifications cleared"}
