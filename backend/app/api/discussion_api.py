import json
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database.connection import get_db
from app.schemas.decision import (
    DiscussionThreadCreate, DiscussionThreadResponse,
    CommentCreate, CommentResponse,
    MeetingNoteCreate, MeetingNoteResponse,
    DecisionRationaleResponse, DecisionRationaleUpdate,
    AttachmentResponse
)
from app.models.comment import DiscussionThread, Comment
from app.models.meeting_note import MeetingNote
from app.models.decision import Decision
from app.models.user import User
from app.models.attachment import Attachment
from app.models.activity_log import ActivityLog
from app.models.notification import Notification
from app.services.notification_service import NotificationService

router = APIRouter(
    prefix="/decisions",
    tags=["Discussions"]
)

# Active WebSocket Connections Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, decision_id: int, websocket: WebSocket):
        await websocket.accept()
        if decision_id not in self.active_connections:
            self.active_connections[decision_id] = []
        self.active_connections[decision_id].append(websocket)

    def disconnect(self, decision_id: int, websocket: WebSocket):
        if decision_id in self.active_connections:
            if websocket in self.active_connections[decision_id]:
                self.active_connections[decision_id].remove(websocket)

    async def broadcast(self, decision_id: int, message: dict):
        if decision_id in self.active_connections:
            for connection in self.active_connections[decision_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

ws_manager = ConnectionManager()

@router.websocket("/ws/{decision_id}")
async def websocket_endpoint(websocket: WebSocket, decision_id: int):
    await ws_manager.connect(decision_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            await ws_manager.broadcast(decision_id, payload)
    except WebSocketDisconnect:
        ws_manager.disconnect(decision_id, websocket)

# --- 1. THREADS ---
@router.post("/{decision_id}/threads", response_model=DiscussionThreadResponse)
def create_thread(decision_id: int, thread: DiscussionThreadCreate, db: Session = Depends(get_db)):
    db_decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not db_decision:
        raise HTTPException(status_code=404, detail="Decision not found")
        
    db_thread = DiscussionThread(
        decision_id=decision_id,
        topic=thread.topic,
        created_by=thread.created_by,
        status="Open"
    )
    db.add(db_thread)
    db.commit()
    db.refresh(db_thread)

    try:
        act_log = ActivityLog(
            user_id=thread.created_by,
            action=f"Created discussion thread on DEC-{decision_id}",
            details=f"Thread topic: '{thread.topic}'"
        )
        db.add(act_log)
        db.commit()
    except Exception as e:
        print("Error logging thread creation activity:", e)

    return db_thread

@router.get("/{decision_id}/threads", response_model=List[DiscussionThreadResponse])
def get_threads(decision_id: int, db: Session = Depends(get_db)):
    return db.query(DiscussionThread).filter(DiscussionThread.decision_id == decision_id).all()

@router.get("/threads/all", response_model=List[DiscussionThreadResponse])
def get_all_threads(db: Session = Depends(get_db)):
    return db.query(DiscussionThread).all()

@router.patch("/threads/{thread_id}/status")
def update_thread_status(thread_id: int, status: str = Query(...), user_id: int = Query(...), db: Session = Depends(get_db)):
    thread = db.query(DiscussionThread).filter(DiscussionThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    valid_statuses = ["Open", "In Progress", "Resolved", "Closed"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Choose from {valid_statuses}")

    old_status = thread.status
    thread.status = status
    db.commit()

    try:
        act_log = ActivityLog(
            user_id=user_id,
            action=f"Changed thread status on DEC-{thread.decision_id}",
            details=f"Thread '{thread.topic}' status changed from '{old_status}' to '{status}'"
        )
        db.add(act_log)
        db.commit()
    except Exception as e:
        print("Error logging thread status change:", e)

    return {"message": "Thread status updated successfully", "status": status}

@router.delete("/threads/{thread_id}")
def delete_thread(thread_id: int, user_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    thread = db.query(DiscussionThread).filter(DiscussionThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    # Delete dependent comments first
    db.query(Comment).filter(Comment.thread_id == thread_id).delete(synchronize_session=False)
    
    topic = thread.topic
    decision_id = thread.decision_id
    db.delete(thread)
    db.commit()

    if user_id:
        try:
            act_log = ActivityLog(
                user_id=user_id,
                action=f"Deleted discussion thread on DEC-{decision_id}",
                details=f"Thread '{topic}' was deleted"
            )
            db.add(act_log)
            db.commit()
        except Exception as e:
            print("Error logging thread deletion:", e)

    return {"message": "Thread deleted successfully"}

# --- 2. COMMENTS ---
@router.post("/threads/{thread_id}/comments", response_model=CommentResponse)
def create_comment(thread_id: int, comment: CommentCreate, db: Session = Depends(get_db)):
    db_thread = db.query(DiscussionThread).filter(DiscussionThread.id == thread_id).first()
    if not db_thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    db_comment = Comment(
        thread_id=thread_id,
        user_id=comment.user_id,
        reply_to_id=comment.reply_to_id,
        content=comment.content
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)

    author = db.query(User).filter(User.id == comment.user_id).first()
    db_comment.author_name = author.full_name if author else "User"
    db_comment.author_role = author.role.role_name if (author and author.role) else "Employee"

    try:
        act_log = ActivityLog(
            user_id=comment.user_id,
            action=f"Added discussion comment on DEC-{db_thread.decision_id}",
            details=f"Comment in '{db_thread.topic}': {comment.content[:80]}"
        )
        db.add(act_log)
        db.commit()
    except Exception as e:
        print("Error logging comment activity:", e)

    try:
        NotificationService.notify_discussion(db, db_thread.decision_id, comment.user_id, comment.content)
    except Exception as e:
        print("Error sending discussion notification:", e)

    return db_comment

@router.get("/threads/{thread_id}/comments")
def get_thread_comments(thread_id: int, offset: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.thread_id == thread_id).order_by(Comment.id.asc()).offset(offset).limit(limit).all()
    res = []
    for c in comments:
        author = db.query(User).filter(User.id == c.user_id).first()
        parent_text = None
        if c.reply_to_id:
            parent = db.query(Comment).filter(Comment.id == c.reply_to_id).first()
            if parent:
                parent_author = db.query(User).filter(User.id == parent.user_id).first()
                parent_name = parent_author.full_name if parent_author else "User"
                parent_text = f"{parent_name}: {parent.content[:40]}"

        res.append({
            "id": c.id,
            "thread_id": c.thread_id,
            "user_id": c.user_id,
            "reply_to_id": c.reply_to_id,
            "parent_snippet": parent_text,
            "content": "This message was deleted." if c.is_deleted else c.content,
            "is_edited": c.is_edited,
            "is_deleted": c.is_deleted,
            "is_pinned": c.is_pinned,
            "reactions": c.reactions,
            "read_receipts": c.read_receipts,
            "edit_history": c.edit_history,
            "created_at": c.created_at,
            "author_name": author.full_name if author else "User",
            "author_role": author.role.role_name if (author and author.role) else "Employee",
            "author_initials": "".join([p[0].upper() for p in author.full_name.split()])[:2] if (author and author.full_name) else "U"
        })
    return res

@router.get("/comments/all", response_model=List[CommentResponse])
def get_all_comments(db: Session = Depends(get_db)):
    comments = db.query(Comment).all()
    for c in comments:
        author = db.query(User).filter(User.id == c.user_id).first()
        c.author_name = author.full_name if author else "User"
        c.author_role = author.role.role_name if (author and author.role) else "Employee"
    return comments

@router.put("/comments/{comment_id}")
def edit_comment(comment_id: int, content: str = Query(...), user_id: int = Query(...), db: Session = Depends(get_db)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="You can only edit your own comments")

    history = json.loads(comment.edit_history) if comment.edit_history else []
    history.append({
        "old_content": comment.content,
        "edited_at": datetime.utcnow().isoformat()
    })

    comment.content = content
    comment.is_edited = True
    comment.edit_history = json.dumps(history)
    db.commit()

    return {"message": "Comment updated successfully", "content": content}

@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, user_id: int = Query(...), db: Session = Depends(get_db)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    user = db.query(User).filter(User.id == user_id).first()
    is_admin = user and user.role and "admin" in user.role.role_name.lower()
    
    if comment.user_id != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")

    comment.is_deleted = True
    db.commit()

    return {"message": "Comment soft deleted successfully"}

@router.post("/comments/{comment_id}/react")
def react_to_comment(comment_id: int, emoji: str = Query(...), user_id: int = Query(...), db: Session = Depends(get_db)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    reactions_map = json.loads(comment.reactions) if comment.reactions else {}
    if emoji not in reactions_map:
        reactions_map[emoji] = []
    
    if user_id in reactions_map[emoji]:
        reactions_map[emoji].remove(user_id)
        if len(reactions_map[emoji]) == 0:
            del reactions_map[emoji]
    else:
        reactions_map[emoji].append(user_id)

    comment.reactions = json.dumps(reactions_map)
    db.commit()

    return {"message": "Reaction updated", "reactions": reactions_map}

@router.post("/comments/{comment_id}/pin")
def pin_comment(comment_id: int, user_id: int = Query(...), db: Session = Depends(get_db)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    comment.is_pinned = not comment.is_pinned
    db.commit()

    return {"message": "Pin status updated", "is_pinned": comment.is_pinned}

@router.post("/comments/{comment_id}/read")
def mark_comment_read(comment_id: int, user_id: int = Query(...), db: Session = Depends(get_db)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    receipts = json.loads(comment.read_receipts) if comment.read_receipts else []
    if not any(r.get("user_id") == user_id for r in receipts):
        receipts.append({"user_id": user_id, "seen_at": datetime.utcnow().isoformat()})
        comment.read_receipts = json.dumps(receipts)
        db.commit()

    return {"message": "Read receipt recorded", "receipts": receipts}

# --- 3. DECISION RATIONALE APIs ---
@router.get("/{decision_id}/rationale", response_model=DecisionRationaleResponse)
def get_decision_rationale(decision_id: int, db: Session = Depends(get_db)):
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    updater_name = None
    if decision.rationale_updated_by:
        updater = db.query(User).filter(User.id == decision.rationale_updated_by).first()
        updater_name = updater.full_name if updater else None

    return DecisionRationaleResponse(
        decision_id=decision.id,
        why_required=decision.rationale_why or decision.description,
        business_justification=decision.rationale_justification or "Standard business alignment",
        expected_benefits=decision.rationale_benefits or "Improved Operational Efficiency",
        risks=decision.rationale_risks or "Managed low-to-medium risk profile",
        assumptions=decision.rationale_assumptions or "Budget and team member availability",
        created_by=decision.created_by,
        created_at=decision.created_at,
        updated_by=decision.rationale_updated_by,
        updated_at=decision.rationale_updated_at,
        updater_name=updater_name
    )

@router.put("/{decision_id}/rationale", response_model=DecisionRationaleResponse)
def update_decision_rationale(decision_id: int, rationale: DecisionRationaleUpdate, db: Session = Depends(get_db)):
    decision = db.query(Decision).filter(Decision.id == decision_id).first()
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")

    decision.rationale_why = rationale.why_required
    decision.rationale_justification = rationale.business_justification
    decision.rationale_benefits = rationale.expected_benefits
    decision.rationale_risks = rationale.risks
    decision.rationale_assumptions = rationale.assumptions
    decision.rationale_updated_at = datetime.utcnow()
    decision.rationale_updated_by = rationale.user_id
    db.commit()

    try:
        act_log = ActivityLog(
            user_id=rationale.user_id,
            action=f"Updated Decision Rationale for DEC-{decision_id}",
            details=f"Rationale updated: Why: '{rationale.why_required[:40] if rationale.why_required else ''}...'"
        )
        db.add(act_log)
        db.commit()
    except Exception as e:
        print("Error logging rationale update:", e)

    return get_decision_rationale(decision_id, db)

# --- 4. MEETING NOTES APIs ---
def notify_mentioned_users(db: Session, content: str, title: str, decision_id: int, author_id: int, note_date_str: str = ""):
    if not content:
        return
    import re
    # Matches @[Name](EMPxxx) or @Name (EMPxxx) or @EMPxxx
    matches = re.findall(r'@([^\(\n\r<]+?)(?:\s*\(([^)]+)\))?', content)
    author = db.query(User).filter(User.id == author_id).first()
    author_name = author.full_name if author else "A teammate"

    notified_user_ids = set()

    for match in matches:
        raw_name, raw_emp = match
        raw_name = raw_name.strip()
        raw_emp = raw_emp.strip() if raw_emp else ""

        user = None
        if raw_emp:
            user = db.query(User).filter(User.employee_id == raw_emp).first()
        if not user and raw_name:
            user = db.query(User).filter(User.full_name.ilike(f"%{raw_name}%")).first()

        if user and user.id != author_id and user.id not in notified_user_ids:
            notified_user_ids.add(user.id)
            date_info = f" scheduled for {note_date_str}" if note_date_str else ""
            msg = f"{author_name} tagged you in meeting session '{title}' for DEC-{decision_id}{date_info}."
            try:
                from app.services.notification_service import NotificationService
                NotificationService.create_notification(db, user.id, msg, "Mention")
            except Exception as e:
                print("Error notifying mentioned user:", e)

@router.post("/{decision_id}/meeting_notes", response_model=MeetingNoteResponse)
def create_meeting_note(decision_id: int, note: MeetingNoteCreate, db: Session = Depends(get_db)):
    db_note = MeetingNote(
        decision_id=decision_id,
        title=note.title,
        notes=note.notes,
        meeting_date=note.meeting_date,
        participants=note.participants,
        agenda=note.agenda,
        action_items=note.action_items,
        next_meeting_date=note.next_meeting_date,
        meeting_link=getattr(note, 'meeting_link', None),
        created_by=note.created_by
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)

    date_str = db_note.meeting_date.strftime("%b %d, %Y %I:%M %p") if db_note.meeting_date else ""
    full_text = f"{note.title} {note.participants or ''} {note.notes or ''} {note.agenda or ''}"
    notify_mentioned_users(db, full_text, note.title, decision_id, note.created_by, date_str)

    try:
        act_log = ActivityLog(
            user_id=note.created_by,
            action=f"Created meeting note for DEC-{decision_id}",
            details=f"Meeting Note: '{note.title}'"
        )
        db.add(act_log)
        db.commit()
    except Exception as e:
        print("Error logging meeting note activity:", e)

    return db_note

def compute_meeting_status(n):
    if hasattr(n, 'status') and n.status:
        return n.status
    if not n.meeting_date:
        return "Not Scheduled"
    
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    m_date = n.meeting_date
    if m_date.tzinfo is None:
        m_date = m_date.replace(tzinfo=timezone.utc)
    
    m_end = m_date + timedelta(hours=1)
    if now < m_date:
        return "Scheduled"
    elif m_date <= now <= m_end:
        return "In Progress"
    else:
        return "Completed"

@router.get("/{decision_id}/meeting_notes", response_model=List[MeetingNoteResponse])
def get_meeting_notes(decision_id: int, db: Session = Depends(get_db)):
    notes = db.query(MeetingNote).filter(MeetingNote.decision_id == decision_id).all()
    for n in notes:
        author = db.query(User).filter(User.id == n.created_by).first()
        n.author_name = author.full_name if author else "User"
        n.status = compute_meeting_status(n)
    return notes

@router.get("/meeting_notes/all", response_model=List[MeetingNoteResponse])
def get_all_meeting_notes(db: Session = Depends(get_db)):
    notes = db.query(MeetingNote).all()
    for n in notes:
        author = db.query(User).filter(User.id == n.created_by).first()
        n.author_name = author.full_name if author else "User"
        n.status = compute_meeting_status(n)
    return notes

@router.put("/meeting_notes/{note_id}", response_model=MeetingNoteResponse)
def update_meeting_note(note_id: int, note: MeetingNoteCreate, user_id: int = Query(...), db: Session = Depends(get_db)):
    db_note = db.query(MeetingNote).filter(MeetingNote.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Meeting note not found")

    db_note.title = note.title
    db_note.notes = note.notes
    db_note.meeting_date = note.meeting_date
    db_note.participants = note.participants
    db_note.agenda = note.agenda
    db_note.action_items = note.action_items
    db_note.next_meeting_date = note.next_meeting_date
    if hasattr(note, 'meeting_link'):
        db_note.meeting_link = note.meeting_link
    db_note.updated_by = user_id
    db_note.updated_at = datetime.utcnow()
    db.commit()

    date_str = db_note.meeting_date.strftime("%b %d, %Y %I:%M %p") if db_note.meeting_date else ""
    full_text = f"{note.title} {note.participants or ''} {note.notes or ''}"
    notify_mentioned_users(db, full_text, note.title, db_note.decision_id, user_id, date_str)

    try:
        act_log = ActivityLog(
            user_id=user_id,
            action=f"Updated meeting note for DEC-{db_note.decision_id}",
            details=f"Updated Meeting Note: '{note.title}'"
        )
        db.add(act_log)
        db.commit()
    except Exception as e:
        print("Error logging meeting note update:", e)

    return db_note

# --- MEETING NOTE CHAT ENDPOINTS ---
@router.post("/meeting_notes/{note_id}/comments", response_model=CommentResponse)
def create_meeting_note_comment(note_id: int, comment: CommentCreate, db: Session = Depends(get_db)):
    db_note = db.query(MeetingNote).filter(MeetingNote.id == note_id).first()
    if not db_note:
        raise HTTPException(status_code=404, detail="Meeting note not found")

    db_comment = Comment(
        meeting_note_id=note_id,
        user_id=comment.user_id,
        reply_to_id=comment.reply_to_id,
        content=comment.content
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)

    author = db.query(User).filter(User.id == comment.user_id).first()
    db_comment.author_name = author.full_name if author else "User"
    db_comment.author_role = author.role.role_name if (author and author.role) else "Employee"

    date_str = db_note.meeting_date.strftime("%b %d, %Y %I:%M %p") if db_note.meeting_date else ""
    notify_mentioned_users(db, comment.content, db_note.title, db_note.decision_id, comment.user_id, date_str)

    return db_comment

@router.get("/meeting_notes/{note_id}/comments", response_model=List[CommentResponse])
def get_meeting_note_comments(note_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.meeting_note_id == note_id).order_by(Comment.created_at.asc()).all()
    for c in comments:
        author = db.query(User).filter(User.id == c.user_id).first()
        c.author_name = author.full_name if author else "User"
        c.author_role = author.role.role_name if (author and author.role) else "Employee"
    return comments

# --- 5. SUPPORTING FILE MANAGEMENT APIs ---
@router.post("/{decision_id}/files")
async def upload_supporting_file(
    decision_id: int,
    user_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    max_size = 200 * 1024 * 1024
    if len(contents) > max_size:
        raise HTTPException(status_code=400, detail="File exceeds maximum allowed upload limit of 200 MB")

    db_attachment = Attachment(
        filename=file.filename,
        file_path=f"/uploads/{file.filename}",
        file_size=len(contents),
        decision_id=decision_id,
        uploaded_by=user_id
    )
    db.add(db_attachment)
    db.commit()
    db.refresh(db_attachment)

    try:
        act_log = ActivityLog(
            user_id=user_id,
            action=f"Uploaded supporting file for DEC-{decision_id}",
            details=f"File: '{file.filename}' ({len(contents)} bytes)"
        )
        db.add(act_log)
        db.commit()
    except Exception as e:
        print("Error logging file upload:", e)

    return db_attachment

@router.get("/{decision_id}/files", response_model=List[AttachmentResponse])
def get_supporting_files(decision_id: int, db: Session = Depends(get_db)):
    return db.query(Attachment).filter(Attachment.decision_id == decision_id).all()

@router.delete("/files/{file_id}")
def delete_supporting_file(file_id: int, user_id: int = Query(...), db: Session = Depends(get_db)):
    file_record = db.query(Attachment).filter(Attachment.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    decision_id = file_record.decision_id
    filename = file_record.filename
    db.delete(file_record)
    db.commit()

    try:
        act_log = ActivityLog(
            user_id=user_id,
            action=f"Deleted supporting file from DEC-{decision_id}",
            details=f"Deleted file: '{filename}'"
        )
        db.add(act_log)
        db.commit()
    except Exception as e:
        print("Error logging file deletion:", e)

    return {"message": "File deleted successfully"}

# --- 6. NOTIFICATION APIs ---
@router.get("/notifications/user/{user_id}")
def get_user_notifications(user_id: int, db: Session = Depends(get_db)):
    return db.query(Notification).filter(Notification.user_id == user_id).order_by(Notification.id.desc()).all()

@router.post("/notifications/read")
def mark_notification_read(notification_id: int = Query(...), db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if notif:
        notif.is_read = True
        db.commit()
    return {"message": "Notification marked as read"}

@router.post("/notifications/read-all")
def mark_all_notifications_read(user_id: int = Query(...), db: Session = Depends(get_db)):
    notifs = db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read == False).all()
    for n in notifs:
        n.is_read = True
    db.commit()
    return {"message": "All notifications marked as read"}

@router.delete("/notifications/{notification_id}")
def delete_notification(notification_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter(Notification.id == notification_id).first()
    if notif:
        db.delete(notif)
        db.commit()
    return {"message": "Notification deleted"}

# --- 7. DECISION ACTIVITY TIMELINE (Zero-Duplication ActivityLog Source) ---
@router.get("/{decision_id}/timeline")
def get_decision_timeline(decision_id: int, category: Optional[str] = None, q: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(ActivityLog).filter(
        or_(
            ActivityLog.action.ilike(f"%DEC-{decision_id}%"),
            ActivityLog.details.ilike(f"%DEC-{decision_id}%")
        )
    )

    if category and category != "All":
        query = query.filter(ActivityLog.action.ilike(f"%{category}%"))
    if q:
        query = query.filter(
            or_(
                ActivityLog.action.ilike(f"%{q}%"),
                ActivityLog.details.ilike(f"%{q}%")
            )
        )

    logs = query.order_by(ActivityLog.timestamp.desc()).all()
    res = []
    for l in logs:
        user = db.query(User).filter(User.id == l.user_id).first()
        res.append({
            "id": l.id,
            "action": l.action,
            "details": l.details,
            "user_id": l.user_id,
            "user_name": user.full_name if user else "System User",
            "user_role": user.role.role_name if (user and user.role) else "Employee",
            "timestamp": l.timestamp,
        })
    return res

# --- 8. UNIFIED CROSS-MODULE SEARCH API ---
@router.get("/search")
def unified_search(q: str = Query(...), user_id: Optional[int] = None, db: Session = Depends(get_db)):
    term = f"%{q}%"

    threads = db.query(DiscussionThread).filter(DiscussionThread.topic.ilike(term)).all()
    comments = db.query(Comment).filter(Comment.content.ilike(term)).all()
    timeline = db.query(ActivityLog).filter(or_(ActivityLog.action.ilike(term), ActivityLog.details.ilike(term))).limit(20).all()
    notes = db.query(MeetingNote).filter(or_(MeetingNote.title.ilike(term), MeetingNote.notes.ilike(term))).all()
    files = db.query(Attachment).filter(Attachment.filename.ilike(term)).all()
    rationale = db.query(Decision).filter(or_(Decision.rationale_why.ilike(term), Decision.description.ilike(term))).all()

    return {
        "query": q,
        "threads": [{"id": t.id, "topic": t.topic, "decision_id": t.decision_id} for t in threads],
        "messages": [{"id": c.id, "content": c.content, "thread_id": c.thread_id} for c in comments],
        "timeline": [{"id": l.id, "action": l.action, "details": l.details} for l in timeline],
        "meeting_notes": [{"id": n.id, "title": n.title, "decision_id": n.decision_id} for n in notes],
        "files": [{"id": f.id, "filename": f.filename, "decision_id": f.decision_id} for f in files],
        "rationale": [{"id": r.id, "title": r.title} for r in rationale]
    }
