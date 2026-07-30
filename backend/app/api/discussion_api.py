from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database.connection import get_db
from app.schemas.decision import (
    DiscussionThreadCreate, DiscussionThreadResponse,
    CommentCreate, CommentResponse,
    MeetingNoteCreate, MeetingNoteResponse
)
from app.models.comment import DiscussionThread, Comment
from app.models.meeting_note import MeetingNote
from app.models.decision import Decision

router = APIRouter(
    prefix="/decisions",
    tags=["Discussions"]
)

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
    return db_thread

@router.get("/{decision_id}/threads", response_model=List[DiscussionThreadResponse])
def get_threads(decision_id: int, db: Session = Depends(get_db)):
    return db.query(DiscussionThread).filter(DiscussionThread.decision_id == decision_id).all()

@router.post("/threads/{thread_id}/comments", response_model=CommentResponse)
def create_comment(thread_id: int, comment: CommentCreate, db: Session = Depends(get_db)):
    db_thread = db.query(DiscussionThread).filter(DiscussionThread.id == thread_id).first()
    if not db_thread:
        raise HTTPException(status_code=404, detail="Thread not found")
        
    db_comment = Comment(
        thread_id=thread_id,
        user_id=comment.user_id,
        content=comment.content
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)

    try:
        from app.models.activity_log import ActivityLog
        act_log = ActivityLog(
            user_id=comment.user_id,
            action=f"Added discussion comment on DEC-{db_thread.decision_id}",
            details=f"Comment in '{db_thread.topic}': {comment.content[:80]}"
        )
        db.add(act_log)
        db.commit()
    except Exception as e:
        print("Error logging discussion comment activity:", e)

    try:
        from app.services.notification_service import NotificationService
        NotificationService.notify_discussion(db, db_thread.decision_id, comment.user_id, comment.content)
    except Exception as e:
        print("Error sending discussion notification:", e)

    return db_comment

@router.post("/{decision_id}/meeting_notes", response_model=MeetingNoteResponse)
def create_meeting_note(decision_id: int, note: MeetingNoteCreate, db: Session = Depends(get_db)):
    db_note = MeetingNote(
        decision_id=decision_id,
        title=note.title,
        notes=note.notes,
        meeting_date=note.meeting_date,
        created_by=note.created_by
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)

    try:
        from app.models.activity_log import ActivityLog
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

@router.get("/{decision_id}/meeting_notes", response_model=List[MeetingNoteResponse])
def get_meeting_notes(decision_id: int, db: Session = Depends(get_db)):
    return db.query(MeetingNote).filter(MeetingNote.decision_id == decision_id).all()

@router.get("/threads/all", response_model=List[DiscussionThreadResponse])
def get_all_threads(db: Session = Depends(get_db)):
    return db.query(DiscussionThread).all()

@router.get("/meeting_notes/all", response_model=List[MeetingNoteResponse])
def get_all_meeting_notes(db: Session = Depends(get_db)):
    return db.query(MeetingNote).all()

@router.get("/comments/all", response_model=List[CommentResponse])
def get_all_comments(db: Session = Depends(get_db)):
    return db.query(Comment).all()

