from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.attachment import Attachment
from app.schemas.decision import AttachmentResponse
import os
import shutil
from typing import Optional

router = APIRouter(
    prefix="/upload",
    tags=["Uploads"]
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB in bytes

@router.post("/", response_model=AttachmentResponse)
async def upload_file(
    file: UploadFile = File(...), 
    user_id: int = Form(1), 
    decision_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_size = os.path.getsize(file_path)
    
    if file_size > MAX_FILE_SIZE:
        os.remove(file_path)
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed limit of 200 MB ({file_size} bytes received)."
        )
    
    from app.models.user import User
    valid_user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if not valid_user:
        first_user = db.query(User).first()
        user_id = first_user.id if first_user else None

    attachment = Attachment(
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        uploaded_by=user_id,
        decision_id=decision_id
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment

from fastapi.responses import FileResponse

@router.get("/{attachment_id}")
def get_uploaded_file(attachment_id: int, user_id: Optional[int] = None, db: Session = Depends(get_db)):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att or not os.path.exists(att.file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    if att.decision_id and user_id:
        try:
            from app.models.activity_log import ActivityLog
            act_log = ActivityLog(
                user_id=user_id,
                action=f"Accessed supporting document '{att.filename}' for DEC-{att.decision_id}",
                details=f"User accessed and viewed attachment '{att.filename}' for DEC-{att.decision_id}"
            )
            db.add(act_log)
            db.commit()
        except Exception as e:
            print("Error logging document access:", e)

    return FileResponse(att.file_path, filename=att.filename)

