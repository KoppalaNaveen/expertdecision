from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database.connection import get_db
from app.schemas.decision import (
    DecisionCreate,
    DecisionUpdate,
    DecisionStatusUpdate,
    DecisionResponse,
    DecisionFullCreate,
    DecisionFullResponse,
    DecisionVersionResponse
)
from app.services.decision_service import DecisionService

router = APIRouter(
    prefix="/decisions",
    tags=["Decisions"]
)

@router.post("/", response_model=DecisionResponse, status_code=201)
def create_decision(decision: DecisionCreate, db: Session = Depends(get_db)):
    return DecisionService.create_decision(db, decision)

@router.post("/full", response_model=DecisionResponse, status_code=201)
def create_decision_full(decision: DecisionFullCreate, db: Session = Depends(get_db)):
    return DecisionService.create_decision_full(db, decision)

@router.get("/", response_model=List[DecisionResponse])
def get_all_decisions(user_id: int = None, role_name: str = None, db: Session = Depends(get_db)):
    return DecisionService.get_all_decisions(db, user_id=user_id, role_name=role_name)

@router.get("/{decision_id}", response_model=DecisionFullResponse)
def get_decision(decision_id: int, user_id: int = None, db: Session = Depends(get_db)):
    decision = DecisionService.get_decision_by_id(db, decision_id, user_id=user_id)
    if not decision:
        raise HTTPException(status_code=403, detail="Access Denied: You are not authorized to view this decision record.")
    return decision

@router.get("/{decision_id}/versions")
def get_decision_versions(decision_id: int, user_id: int = None, db: Session = Depends(get_db)):
    return DecisionService.get_decision_versions(db, decision_id, user_id=user_id)

@router.post("/{decision_id}/versions/{version_number}/restore", response_model=DecisionResponse)
def restore_decision_version(decision_id: int, version_number: int, user_id: int = 1, db: Session = Depends(get_db)):
    restored = DecisionService.restore_decision_version(db, decision_id, version_number, user_id)
    if not restored:
        raise HTTPException(status_code=404, detail="Decision or Version not found")
    return restored

@router.put("/{decision_id}", response_model=DecisionResponse)
def update_decision(decision_id: int, decision: DecisionUpdate, user_id: int = None, db: Session = Depends(get_db)):
    db_decision = DecisionService.get_decision_by_id(db, decision_id)
    if not db_decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    updater_id = user_id or decision.created_by
    if updater_id and int(db_decision.created_by) != int(updater_id):
        raise HTTPException(status_code=403, detail="Access Denied: Only the decision owner can edit a decision while it is in Draft or Rejected status.")
    status_clean = (db_decision.status or "").strip().lower()
    if status_clean not in ["draft", "rejected"]:
        raise HTTPException(status_code=403, detail="Access Denied: Only the decision owner can edit a decision while it is in Draft or Rejected status.")
    updated_decision = DecisionService.update_decision(db, decision_id, decision)
    return updated_decision

@router.put("/{decision_id}/full", response_model=DecisionResponse)
def update_decision_full(decision_id: int, decision: DecisionFullCreate, user_id: int = None, db: Session = Depends(get_db)):
    db_decision = DecisionService.get_decision_by_id(db, decision_id)
    if not db_decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    updater_id = user_id or decision.created_by
    if updater_id and int(db_decision.created_by) != int(updater_id):
        raise HTTPException(status_code=403, detail="Access Denied: Only the decision owner can edit a decision while it is in Draft or Rejected status.")
    status_clean = (db_decision.status or "").strip().lower()
    if status_clean not in ["draft", "rejected"]:
        raise HTTPException(status_code=403, detail="Access Denied: Only the decision owner can edit a decision while it is in Draft or Rejected status.")
    updated_decision = DecisionService.update_decision_full(db, decision_id, decision)
    return updated_decision

@router.patch("/{decision_id}/status", response_model=DecisionResponse)
def update_status(decision_id: int, status_update: DecisionStatusUpdate, user_id: int = None, db: Session = Depends(get_db)):
    db_decision = DecisionService.get_decision_by_id(db, decision_id)
    if not db_decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    if user_id and db_decision.created_by != user_id and status_update.status in ["Pending", "Submitted", "Draft"]:
        raise HTTPException(status_code=403, detail="Only the owner of this decision can edit or submit it.")
    updated_decision = DecisionService.update_status(db, decision_id, status_update)
    return updated_decision

@router.delete("/{decision_id}")
def delete_decision(decision_id: int, user_id: int = None, role_name: str = None, db: Session = Depends(get_db)):
    success = DecisionService.delete_decision(db, decision_id, user_id=user_id, role_name=role_name)
    if not success:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {"message": "Decision deleted successfully"}

@router.post("/{decision_id}/send_reminder")
def send_reminder(decision_id: int, user_id: int = 1, db: Session = Depends(get_db)):
    from app.services.notification_service import NotificationService
    NotificationService.notify_reminder(db, decision_id, user_id)
    return {"message": "Reminder notifications sent successfully"}