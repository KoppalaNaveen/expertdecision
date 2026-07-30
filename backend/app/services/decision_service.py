from sqlalchemy.orm import Session
from app.schemas.decision import DecisionCreate, DecisionUpdate, DecisionStatusUpdate, DecisionFullCreate
from app.repositories.decision_repository import DecisionRepository

class DecisionService:

    @staticmethod
    def create_decision(db: Session, decision: DecisionCreate):
        return DecisionRepository.create_decision(db, decision)

    @staticmethod
    def create_decision_full(db: Session, full_decision: DecisionFullCreate):
        return DecisionRepository.create_decision_full(db, full_decision)

    @staticmethod
    def get_all_decisions(db: Session):
        return DecisionRepository.get_all_decisions(db)

    @staticmethod
    def get_decision_by_id(db: Session, decision_id: int, user_id: int = None):
        return DecisionRepository.get_decision_by_id(db, decision_id, user_id=user_id)

    @staticmethod
    def update_decision(db: Session, decision_id: int, decision: DecisionUpdate):
        return DecisionRepository.update_decision(db, decision_id, decision)

    @staticmethod
    def update_decision_full(db: Session, decision_id: int, full_decision: DecisionFullCreate):
        return DecisionRepository.update_decision_full(db, decision_id, full_decision)

    @staticmethod
    def update_status(db: Session, decision_id: int, status_update: DecisionStatusUpdate):
        return DecisionRepository.update_status(db, decision_id, status_update.status)

    @staticmethod
    def delete_decision(db: Session, decision_id: int, user_id: int = None, role_name: str = None):
        return DecisionRepository.delete_decision(db, decision_id, user_id=user_id, role_name=role_name)

    @staticmethod
    def verify_decision_integrity(db: Session, decision_id: int) -> bool:
        return DecisionRepository.verify_decision_integrity(db, decision_id)

    @staticmethod
    def get_decision_versions(db: Session, decision_id: int, user_id: int = None):
        return DecisionRepository.get_decision_versions(db, decision_id, user_id=user_id)

    @staticmethod
    def restore_decision_version(db: Session, decision_id: int, version_number: int, user_id: int = 1):
        return DecisionRepository.restore_decision_version(db, decision_id, version_number, user_id)