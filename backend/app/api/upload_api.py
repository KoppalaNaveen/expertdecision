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

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB in bytes

from fastapi.responses import FileResponse, Response
import mimetypes

@router.post("/", response_model=AttachmentResponse)
async def upload_file(
    file: UploadFile = File(...), 
    user_id: int = Form(1), 
    decision_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    content_bytes = await file.read()
    file_size = len(content_bytes)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed limit of 200 MB ({file_size} bytes received)."
        )

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(content_bytes)
    
    from app.models.user import User
    valid_user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if not valid_user:
        first_user = db.query(User).first()
        user_id = first_user.id if first_user else None

    attachment = Attachment(
        filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        file_data=content_bytes,
        uploaded_by=user_id,
        decision_id=decision_id
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment

@router.get("/{attachment_id}")
def get_uploaded_file(
    attachment_id: int, 
    filename: Optional[str] = None,
    user_id: Optional[int] = None, 
    download: Optional[bool] = False,
    db: Session = Depends(get_db)
):
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if not att and filename:
        att = db.query(Attachment).filter(Attachment.filename == filename).first()
        
    real_path = att.file_path if att else None
    target_filename = (att.filename if att else filename) or f"document_{attachment_id}.bin"

    if not real_path or not os.path.exists(real_path):
        candidates = [
            os.path.join(UPLOAD_DIR, target_filename),
            os.path.join(PROJECT_ROOT, "uploads", target_filename),
            os.path.join(os.getcwd(), "uploads", target_filename),
            os.path.join(PROJECT_ROOT, "backend", "uploads", target_filename),
            os.path.join(PROJECT_ROOT, "frontend", "uploads", target_filename),
        ]
        for p in candidates:
            if os.path.exists(p):
                real_path = p
                break
        
    # If file was not found on ephemeral disk, restore it from DB file_data or create fallback
    content_bytes = None
    if not real_path or not os.path.exists(real_path):
        if att and getattr(att, "file_data", None):
            content_bytes = att.file_data
            try:
                restore_path = os.path.join(UPLOAD_DIR, target_filename)
                with open(restore_path, "wb") as f:
                    f.write(content_bytes)
                real_path = restore_path
            except Exception as save_err:
                print("Could not recreate disk file:", save_err)
        else:
            ext = os.path.splitext(target_filename)[1].lower()
            if ext == ".pdf":
                content_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
            else:
                content_bytes = f"Expert Decision Replay Platform Supporting File: {target_filename}\nDocument ID: #{attachment_id}".encode("utf-8")
        
    if att and att.decision_id and user_id:
        try:
            from app.models.activity_log import ActivityLog
            act_log = ActivityLog(
                user_id=user_id,
                action=f"Accessed supporting document '{target_filename}' for DEC-{att.decision_id}",
                details=f"User accessed and viewed attachment '{target_filename}' for DEC-{att.decision_id}"
            )
            db.add(act_log)
            db.commit()
        except Exception as e:
            print("Error logging document access:", e)

    mime_type, _ = mimetypes.guess_type(target_filename)
    if not mime_type:
        ext = os.path.splitext(target_filename)[1].lower()
        if ext in [".pptx", ".ppt"]:
            mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif ext in [".docx", ".doc"]:
            mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext in [".xlsx", ".xls"]:
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif ext == ".pdf":
            mime_type = "application/pdf"
        elif ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]:
            mime_type = f"image/{ext.lstrip('.')}"
        elif ext in [".txt", ".csv", ".json", ".md", ".log"]:
            mime_type = "text/plain; charset=utf-8"
        else:
            mime_type = "application/octet-stream"

    disp_type = "attachment" if download else "inline"
    safe_filename = target_filename.replace('"', '')

    if content_bytes is not None and (not real_path or not os.path.exists(real_path)):
        return Response(
            content=content_bytes,
            media_type=mime_type,
            headers={
                "Content-Disposition": f'{disp_type}; filename="{safe_filename}"',
                "Access-Control-Allow-Origin": "*"
            }
        )

    return FileResponse(
        real_path,
        filename=target_filename,
        media_type=mime_type,
        content_disposition_type=disp_type
    )

