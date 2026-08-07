from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserRegister


class UserRepository:

    @staticmethod
    def get_user_by_email(db: Session, email: str):
        clean_email = (email or "").strip().lower()
        import hashlib
        email_hash = hashlib.sha256(clean_email.encode('utf-8')).hexdigest() if '@' in clean_email else clean_email
        return db.query(User).filter((User.email == email_hash) | (User.email == clean_email) | (User.email_hash == email_hash) | (User.email_hash == clean_email)).first()

    @staticmethod
    def get_user_by_employee_id(db: Session, employee_id: str):
        if not employee_id:
            return None
        clean_id = employee_id.strip()
        from sqlalchemy import func
        return db.query(User).filter((func.lower(User.employee_id) == clean_id.lower()) | (User.employee_id == clean_id)).first()

    @staticmethod
    def create_user(db: Session, user: UserRegister, hashed_password: str):
        import hashlib
        clean_email = (user.email or "").strip().lower()
        email_hash = hashlib.sha256(clean_email.encode('utf-8')).hexdigest() if '@' in clean_email else clean_email
        new_user = User(
            full_name=user.full_name,
            email=email_hash,
            email_hash=email_hash,
            email_original=clean_email,
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
        import hashlib
        clean_email = (email or "").strip().lower()
        email_hash = hashlib.sha256(clean_email.encode('utf-8')).hexdigest() if '@' in clean_email else clean_email
        new_user = User(
            full_name=full_name,
            email=email_hash,
            email_hash=email_hash,
            email_original=clean_email,
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
            return (False, "User not found")

        try:
            from app.models.activity_log import ActivityLog
            from app.models.notification import Notification
            from app.models.review import Review
            from app.models.replay import Replay
            from app.models.decision import Decision
            from app.models.user import VerificationCode
            from app.models.support_ticket import SupportTicket
            from app.models.comment import DiscussionThread, Comment
            from app.models.alternative import Alternative
            from app.models.meeting_note import MeetingNote
            from app.models.attachment import Attachment
            from app.models.decision_version import DecisionVersion
            from app.models.email_verification import EmailVerification

            # Delete related logs, notifications, tickets, verification codes & discussions
            db.query(ActivityLog).filter(ActivityLog.user_id == user_id).delete(synchronize_session=False)
            db.query(Notification).filter(Notification.user_id == user_id).delete(synchronize_session=False)
            db.query(Review).filter(Review.reviewer_id == user_id).delete(synchronize_session=False)
            db.query(Replay).filter(Replay.performed_by == user_id).delete(synchronize_session=False)
            if user.email:
                clean_e = user.email.strip().lower() if user.email else ""
                db.query(VerificationCode).filter((VerificationCode.email == user.email) | (VerificationCode.email == getattr(user, 'email_hash', user.email))).delete(synchronize_session=False)
                db.query(EmailVerification).filter(EmailVerification.email == clean_e).delete(synchronize_session=False)

            db.query(SupportTicket).filter(SupportTicket.user_id == user_id).delete(synchronize_session=False)

            # Nullify self-referential replies on comments created by user
            user_comment_ids = [c.id for c in db.query(Comment.id).filter(Comment.user_id == user_id).all()]
            if user_comment_ids:
                db.query(Comment).filter(Comment.reply_to_id.in_(user_comment_ids)).update({"reply_to_id": None}, synchronize_session=False)
            db.query(Comment).filter(Comment.user_id == user_id).delete(synchronize_session=False)

            # Clean up discussion threads created by user and their comments
            user_threads = [t.id for t in db.query(DiscussionThread.id).filter(DiscussionThread.created_by == user_id).all()]
            if user_threads:
                db.query(Comment).filter(Comment.thread_id.in_(user_threads)).delete(synchronize_session=False)
                db.query(DiscussionThread).filter(DiscussionThread.id.in_(user_threads)).delete(synchronize_session=False)

            # Nullify references in decision, discussion, meeting note & attachment tables
            db.query(Decision).filter(Decision.rationale_updated_by == user_id).update({"rationale_updated_by": None}, synchronize_session=False)
            db.query(DiscussionThread).filter(DiscussionThread.pinned_by == user_id).update({"pinned_by": None}, synchronize_session=False)
            db.query(MeetingNote).filter(MeetingNote.created_by == user_id).update({"created_by": None}, synchronize_session=False)
            db.query(MeetingNote).filter(MeetingNote.updated_by == user_id).update({"updated_by": None}, synchronize_session=False)
            db.query(Attachment).filter(Attachment.uploaded_by == user_id).update({"uploaded_by": None}, synchronize_session=False)
            db.query(DecisionVersion).filter(DecisionVersion.changed_by == user_id).update({"changed_by": None}, synchronize_session=False)

            # Clean up decisions created by user and their child dependencies
            user_decisions = db.query(Decision.id).filter(Decision.created_by == user_id).all()
            dec_ids = [d[0] for d in user_decisions]
            if dec_ids:
                db.query(Alternative).filter(Alternative.decision_id.in_(dec_ids)).delete(synchronize_session=False)
                db.query(Review).filter(Review.decision_id.in_(dec_ids)).delete(synchronize_session=False)
                db.query(Replay).filter(Replay.decision_id.in_(dec_ids)).delete(synchronize_session=False)
                
                # Delete discussion threads, meeting notes, attachments for these decisions
                dec_threads = [t.id for t in db.query(DiscussionThread.id).filter(DiscussionThread.decision_id.in_(dec_ids)).all()]
                if dec_threads:
                    db.query(Comment).filter(Comment.thread_id.in_(dec_threads)).delete(synchronize_session=False)
                    db.query(DiscussionThread).filter(DiscussionThread.id.in_(dec_threads)).delete(synchronize_session=False)

                db.query(MeetingNote).filter(MeetingNote.decision_id.in_(dec_ids)).delete(synchronize_session=False)
                db.query(Attachment).filter(Attachment.decision_id.in_(dec_ids)).delete(synchronize_session=False)
                db.query(DecisionVersion).filter(DecisionVersion.decision_id.in_(dec_ids)).delete(synchronize_session=False)
                db.query(Decision).filter(Decision.id.in_(dec_ids)).delete(synchronize_session=False)

            db.delete(user)
            db.commit()
            return (True, None)
        except Exception as primary_err:
            db.rollback()
            try:
                db.execute(text("DELETE FROM activity_logs WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM reviews WHERE reviewer_id = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM replays WHERE performed_by = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM support_tickets WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("UPDATE comments SET reply_to_id = NULL WHERE reply_to_id IN (SELECT id FROM comments WHERE user_id = :uid)"), {"uid": user_id})
                db.execute(text("DELETE FROM comments WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM comments WHERE thread_id IN (SELECT id FROM discussion_threads WHERE created_by = :uid)"), {"uid": user_id})
                db.execute(text("DELETE FROM discussion_threads WHERE created_by = :uid"), {"uid": user_id})
                db.execute(text("UPDATE decisions SET rationale_updated_by = NULL WHERE rationale_updated_by = :uid"), {"uid": user_id})
                db.execute(text("UPDATE discussion_threads SET pinned_by = NULL WHERE pinned_by = :uid"), {"uid": user_id})
                db.execute(text("UPDATE meeting_notes SET created_by = NULL WHERE created_by = :uid"), {"uid": user_id})
                db.execute(text("UPDATE meeting_notes SET updated_by = NULL WHERE updated_by = :uid"), {"uid": user_id})
                db.execute(text("UPDATE attachments SET uploaded_by = NULL WHERE uploaded_by = :uid"), {"uid": user_id})
                db.execute(text("UPDATE decision_versions SET changed_by = NULL WHERE changed_by = :uid"), {"uid": user_id})

                db.execute(text("DELETE FROM alternatives WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)"), {"uid": user_id})
                db.execute(text("DELETE FROM reviews WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)"), {"uid": user_id})
                db.execute(text("DELETE FROM replays WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)"), {"uid": user_id})
                db.execute(text("DELETE FROM comments WHERE thread_id IN (SELECT id FROM discussion_threads WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid))"), {"uid": user_id})
                db.execute(text("DELETE FROM discussion_threads WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)"), {"uid": user_id})
                db.execute(text("DELETE FROM meeting_notes WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)"), {"uid": user_id})
                db.execute(text("DELETE FROM attachments WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)"), {"uid": user_id})
                db.execute(text("DELETE FROM decision_versions WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)"), {"uid": user_id})
                db.execute(text("DELETE FROM decisions WHERE created_by = :uid"), {"uid": user_id})

                db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
                db.commit()
                return (True, None)
            except Exception as secondary_err:
                db.rollback()
                return (False, f"Delete failed: {str(primary_err)} | {str(secondary_err)}")

    @staticmethod
    def get_all_users(db: Session):
        return db.query(User).all()