from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserRegister


class UserRepository:

    @staticmethod
    def get_user_by_email(db: Session, email: str):
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_employee_id(db: Session, employee_id: str):
        return db.query(User).filter(User.employee_id == employee_id).first()

    @staticmethod
    def create_user(db: Session, user: UserRegister, hashed_password: str):

        new_user = User(
            full_name=user.full_name,
            email=user.email,
            password=hashed_password,
            employee_id=user.employee_id,
            role_id=user.role_id,
            team_id=user.team_id,
            designation=user.designation,
            phone=user.phone,
            is_active=True
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return new_user

    @staticmethod
    def create_pending_user(db: Session, email: str, full_name: str, hashed_password: str, employee_id: str, role_id: int, team_id: int = 1, designation: str = None, phone: str = None):
        from datetime import datetime
        new_user = User(
            full_name=full_name,
            email=email.strip().lower(),
            password=hashed_password,
            employee_id=employee_id.strip(),
            role_id=role_id,
            team_id=team_id or 1,
            designation=designation,
            phone=phone,
            is_active=True,
            email_verified=True,
            approved=False,
            status="Pending Approval",
            created_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user

    @staticmethod
    def get_pending_users(db: Session):
        return db.query(User).filter(User.status == "Pending Approval").order_by(User.id.desc()).all()

    @staticmethod
    def update_user_approval(db: Session, user_id: int, action: str, actor_name: str = "Administrator"):
        from datetime import datetime
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        if action == "approve":
            user.approved = True
            user.status = "Active"
            user.approved_by = actor_name
            user.approved_at = now_str
        elif action == "reject":
            user.approved = False
            user.status = "Rejected"
            user.rejected_by = actor_name
            user.rejected_at = now_str

        user.updated_at = now_str
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_user_by_id(db: Session, user_id: int):
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def delete_user(db: Session, user_id: int):
        from sqlalchemy import text
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        try:
            from app.models.activity_log import ActivityLog
            from app.models.notification import Notification
            from app.models.review import Review
            from app.models.replay import Replay
            from app.models.decision import Decision
            from app.models.verification_code import VerificationCode

            # Delete related activity logs & notifications
            db.query(ActivityLog).filter(ActivityLog.user_id == user_id).delete(synchronize_session=False)
            db.query(Notification).filter(Notification.user_id == user_id).delete(synchronize_session=False)
            db.query(Review).filter(Review.reviewer_id == user_id).delete(synchronize_session=False)
            db.query(Replay).filter(Replay.performed_by == user_id).delete(synchronize_session=False)
            db.query(VerificationCode).filter(VerificationCode.email == user.email).delete(synchronize_session=False)

            # Nullify or delete references in decision table
            db.query(Decision).filter(Decision.assigned_to == user_id).update({"assigned_to": None}, synchronize_session=False)
            db.query(Decision).filter(Decision.approved_by == user_id).update({"approved_by": None}, synchronize_session=False)
            db.query(Decision).filter(Decision.created_by == user_id).delete(synchronize_session=False)

            db.delete(user)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            try:
                db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
                db.commit()
                return True
            except Exception:
                db.rollback()
                try:
                    target = db.query(User).filter(User.id == user_id).first()
                    if target:
                        target.is_active = False
                        target.status = "Inactive"
                        db.commit()
                        return True
                except Exception:
                    db.rollback()
            return False

    @staticmethod
    def get_all_users(db: Session):
        return db.query(User).all()