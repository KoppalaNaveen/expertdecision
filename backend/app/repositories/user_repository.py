from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserRegister


class UserRepository:

    @staticmethod
    def get_user_by_email(db: Session, email: str):
        if not email:
            return None
        clean_email = email.strip().lower()
        import hashlib
        from sqlalchemy import func
        from app.core.security import hash_email
        secret_email_hash = hash_email(clean_email)
        standard_email_hash = hashlib.sha256(clean_email.encode('utf-8')).hexdigest() if '@' in clean_email else clean_email
        return db.query(User).filter(
            (func.lower(User.email) == secret_email_hash) |
            (func.lower(User.email) == standard_email_hash) | 
            (func.lower(User.email) == clean_email) | 
            (func.lower(User.email_hash) == secret_email_hash) |
            (func.lower(User.email_hash) == standard_email_hash) | 
            (func.lower(User.email_hash) == clean_email) |
            (func.lower(User.email_original) == clean_email)
        ).first()

    @staticmethod
    def get_user_by_employee_id(db: Session, employee_id: str):
        if not employee_id:
            return None
        clean_id = employee_id.strip()
        from sqlalchemy import func
        return db.query(User).filter(
            (func.lower(User.employee_id) == clean_id.lower()) | 
            (User.employee_id == clean_id)
        ).first()

    @staticmethod
    def create_user(db: Session, user: UserRegister, hashed_password: str):
        from app.core.security import hash_email
        clean_email = (user.email or "").strip().lower()
        email_hash = hash_email(clean_email) if clean_email else ""
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
        from app.core.security import hash_email
        clean_email = (email or "").strip().lower()
        email_hash = hash_email(clean_email) if clean_email else ""
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
    def update_user_approval(db: Session, user_id: int, action: str, actor_name: str = "Administrator", team_id: int = None, designation: str = None):
        from datetime import datetime
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        if action == "approve":
            user.approved = True
            user.status = "Active"
            user.is_active = True
            user.approved_by = actor_name
            user.approved_at = now_str
            if team_id is not None:
                user.team_id = team_id
            if designation:
                user.designation = designation
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
        """
        Permanently delete a user and ALL their references across the database.
        Uses AUTOCOMMIT isolation so each cleanup statement is independent —
        a failure in one cannot roll back another.
        """
        # First, verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return (False, "User not found")

        # Collect user info before we touch anything
        clean_email = user.email.strip().lower() if user.email else ""
        clean_orig = getattr(user, 'email_original', '') or ""
        clean_hash = getattr(user, 'email_hash', '') or ""
        email_values = list({v for v in [clean_email, clean_orig, clean_hash] if v})

        # Close ORM session so it doesn't hold locks
        try:
            db.rollback()
            db.close()
        except Exception:
            pass

        from sqlalchemy import text
        from app.database.connection import engine

        # ── Phase 1: AUTOCOMMIT cleanup ──
        # Each statement is its own transaction. If one fails, it does NOT
        # affect any other statement — no rollback cascade possible.
        try:
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:

                # Find every FK constraint pointing at users.id
                try:
                    fk_rows = conn.execute(text("""
                        SELECT tc.table_name, kcu.column_name
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu
                            ON tc.constraint_name = kcu.constraint_name
                            AND tc.table_schema  = kcu.table_schema
                        JOIN information_schema.constraint_column_usage ccu
                            ON tc.constraint_name = ccu.constraint_name
                            AND tc.table_schema  = ccu.table_schema
                        WHERE tc.constraint_type = 'FOREIGN KEY'
                          AND ccu.table_name  = 'users'
                          AND ccu.column_name = 'id'
                          AND tc.table_schema = 'public'
                    """)).fetchall()
                except Exception:
                    fk_rows = []

                # For each referencing table, remove every row that points at this user
                for ref_table, ref_column in fk_rows:
                    # Try SET NULL first (preserves historical data)
                    try:
                        conn.execute(
                            text(f'UPDATE "{ref_table}" SET "{ref_column}" = NULL WHERE "{ref_column}" = :uid'),
                            {"uid": user_id}
                        )
                    except Exception:
                        pass  # autocommit — no rollback needed

                    # Then DELETE any remaining rows (NOT NULL columns)
                    try:
                        conn.execute(
                            text(f'DELETE FROM "{ref_table}" WHERE "{ref_column}" = :uid'),
                            {"uid": user_id}
                        )
                    except Exception:
                        pass

                # Clean up email-based records (verification_codes, email_verifications)
                if email_values:
                    for tbl in ['verification_codes', 'email_verifications']:
                        try:
                            for ev in email_values:
                                conn.execute(
                                    text(f'DELETE FROM "{tbl}" WHERE email = :e'),
                                    {"e": ev}
                                )
                        except Exception:
                            pass

        except Exception as cleanup_err:
            print(f"[DELETE USER] FK cleanup phase error (non-fatal): {cleanup_err}")

        # ── Phase 2: Delete the user in a normal transaction ──
        try:
            with engine.connect() as conn:
                conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
                conn.commit()
        except Exception as del_err:
            return (False, f"Delete failed: {str(del_err)}")

        # Invalidate dashboard caches
        try:
            from app.repositories.dashboard_repository import _DASHBOARD_CACHE
            _DASHBOARD_CACHE.clear()
        except Exception:
            pass

        return (True, None)

    @staticmethod
    def get_all_users(db: Session):
        return db.query(User).all()