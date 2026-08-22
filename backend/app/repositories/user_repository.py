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
        from sqlalchemy import text, inspect
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return (False, "User not found")

        try:
            inspector = inspect(db.get_bind())
            existing_tables = set(inspector.get_table_names())

            def safe_exec(sql: str, params: dict):
                try:
                    db.execute(text(sql), params)
                except Exception as _e:
                    # Ignore missing tables / columns gracefully
                    pass

            clean_email = user.email.strip().lower() if user.email else ""
            clean_orig = getattr(user, 'email_original', '') or ""
            clean_hash = getattr(user, 'email_hash', '') or ""
            email_params = {"e": clean_email, "eh": clean_hash, "eo": clean_orig, "uid": user_id}

            # 1. Clean up activity logs
            if "activity_logs" in existing_tables:
                safe_exec("DELETE FROM activity_logs WHERE user_id = :uid", email_params)
            if "audit_logs" in existing_tables:
                safe_exec("DELETE FROM audit_logs WHERE actor_id = :uid", email_params)

            # 2. Clean up notifications, support tickets, internal emails, and backup records
            if "notifications" in existing_tables:
                safe_exec("DELETE FROM notifications WHERE user_id = :uid", email_params)
            if "support_tickets" in existing_tables:
                safe_exec("DELETE FROM support_tickets WHERE user_id = :uid", email_params)
            if "internal_emails" in existing_tables:
                safe_exec("DELETE FROM internal_emails WHERE sender_id = :uid", email_params)
            if "backup_records" in existing_tables:
                safe_exec("DELETE FROM backup_records WHERE user_id = :uid", email_params)

            # 3. Clean up reviews and replays performed by user
            if "reviews" in existing_tables:
                safe_exec("DELETE FROM reviews WHERE reviewer_id = :uid", email_params)
            if "replays" in existing_tables:
                safe_exec("DELETE FROM replays WHERE performed_by = :uid", email_params)

            # 4. Clean up email verification records
            if "verification_codes" in existing_tables:
                safe_exec("DELETE FROM verification_codes WHERE email = :e OR email = :eh OR email = :eo", email_params)
            if "email_verifications" in existing_tables:
                safe_exec("DELETE FROM email_verifications WHERE email = :e OR email = :eh OR email = :eo", email_params)

            # 5. Nullify user references in configs, meeting notes, attachments, versions & decisions
            if "approval_chain_configs" in existing_tables:
                safe_exec("UPDATE approval_chain_configs SET created_by = NULL WHERE created_by = :uid", email_params)
            if "meeting_notes" in existing_tables:
                safe_exec("UPDATE meeting_notes SET created_by = NULL WHERE created_by = :uid", email_params)
                safe_exec("UPDATE meeting_notes SET updated_by = NULL WHERE updated_by = :uid", email_params)
            if "attachments" in existing_tables:
                safe_exec("UPDATE attachments SET uploaded_by = NULL WHERE uploaded_by = :uid", email_params)
            if "decision_versions" in existing_tables:
                safe_exec("UPDATE decision_versions SET changed_by = NULL WHERE changed_by = :uid", email_params)
            if "decisions" in existing_tables:
                safe_exec("UPDATE decisions SET rationale_updated_by = NULL WHERE rationale_updated_by = :uid", email_params)
            if "discussion_threads" in existing_tables:
                safe_exec("UPDATE discussion_threads SET pinned_by = NULL WHERE pinned_by = :uid", email_params)

            # 6. Nullify self-referential comment replies & delete comments by user
            if "comments" in existing_tables:
                safe_exec("UPDATE comments SET reply_to_id = NULL WHERE reply_to_id IN (SELECT id FROM comments WHERE user_id = :uid)", email_params)
                safe_exec("DELETE FROM comments WHERE user_id = :uid", email_params)

            # 7. Clean up discussion threads created by user
            if "discussion_threads" in existing_tables:
                if "comments" in existing_tables:
                    safe_exec("DELETE FROM comments WHERE thread_id IN (SELECT id FROM discussion_threads WHERE created_by = :uid)", email_params)
                safe_exec("DELETE FROM discussion_threads WHERE created_by = :uid", email_params)

            # 8. Clean up decisions created by user and their cascaded dependencies
            if "decisions" in existing_tables:
                try:
                    user_decision_ids = [d[0] for d in db.execute(text("SELECT id FROM decisions WHERE created_by = :uid"), email_params).fetchall()]
                    if user_decision_ids:
                        if "alternatives" in existing_tables:
                            safe_exec("DELETE FROM alternatives WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)", email_params)
                        if "reviews" in existing_tables:
                            safe_exec("DELETE FROM reviews WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)", email_params)
                        if "replays" in existing_tables:
                            safe_exec("DELETE FROM replays WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)", email_params)
                        if "comments" in existing_tables and "discussion_threads" in existing_tables:
                            safe_exec("DELETE FROM comments WHERE thread_id IN (SELECT id FROM discussion_threads WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid))", email_params)
                        if "discussion_threads" in existing_tables:
                            safe_exec("DELETE FROM discussion_threads WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)", email_params)
                        if "meeting_notes" in existing_tables:
                            safe_exec("DELETE FROM meeting_notes WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)", email_params)
                        if "attachments" in existing_tables:
                            safe_exec("DELETE FROM attachments WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)", email_params)
                        if "decision_versions" in existing_tables:
                            safe_exec("DELETE FROM decision_versions WHERE decision_id IN (SELECT id FROM decisions WHERE created_by = :uid)", email_params)
                        safe_exec("DELETE FROM decisions WHERE created_by = :uid", email_params)
                except Exception:
                    pass

            # 9. Delete the user
            db.execute(text("DELETE FROM users WHERE id = :uid"), email_params)
            db.commit()

            # Invalidate dashboard in-memory caches
            try:
                from app.repositories.dashboard_repository import _DASHBOARD_CACHE
                _DASHBOARD_CACHE.clear()
            except Exception:
                pass

            return (True, None)
        except Exception as err:
            db.rollback()
            return (False, f"Delete failed: {str(err)}")

    @staticmethod
    def get_all_users(db: Session):
        return db.query(User).all()