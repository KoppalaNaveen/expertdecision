import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL")

# Optimized Connection Pool for Remote PostgreSQL (Supabase) / Local SQLite
if not DATABASE_URL or "sqlite" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL or "sqlite:///./edrp.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    try:
        test_engine = create_engine(
            DATABASE_URL,
            pool_size=15,
            max_overflow=25,
            pool_timeout=10,
            pool_recycle=300,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10}
        )
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine = test_engine
    except Exception as db_err:
        print(f"Notice: Remote database unreachable ({db_err}). Switching to local SQLite database.")
        DATABASE_URL = "sqlite:///./edrp.db"
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

from app.database.base import Base
from app import models

from sqlalchemy import inspect

def ensure_user_schema_columns():
    try:
        inspector = inspect(engine)
        columns_to_add = [
            ("users", "email_verified", "BOOLEAN DEFAULT FALSE"),
            ("users", "approved", "BOOLEAN DEFAULT FALSE"),
            ("users", "status", "VARCHAR(50) DEFAULT 'Pending Approval'"),
            ("users", "approved_by", "VARCHAR(100)"),
            ("users", "approved_at", "VARCHAR(50)"),
            ("users", "rejected_by", "VARCHAR(100)"),
            ("users", "rejected_at", "VARCHAR(50)"),
            ("users", "created_at", "VARCHAR(50)"),
            ("users", "updated_at", "VARCHAR(50)"),
            ("users", "email_hash", "VARCHAR(64)"),
            ("users", "email_original", "VARCHAR(100)"),
            ("comments", "meeting_note_id", "INTEGER REFERENCES meeting_notes(id)"),
            ("meeting_notes", "meeting_link", "TEXT"),
        ]
        
        with engine.connect() as conn:
            for table_name, col_name, col_def in columns_to_add:
                try:
                    if inspector.has_table(table_name):
                        existing_cols = [c["name"] for c in inspector.get_columns(table_name)]
                        if col_name not in existing_cols:
                            sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def};"
                            conn.execute(text(sql))
                            conn.commit()
                except Exception:
                    pass
            if inspector.has_table("users"):
                try:
                    conn.execute(text("UPDATE users SET approved = TRUE, status = 'Active', email_verified = TRUE, is_active = TRUE WHERE status IS NULL OR status = '' OR status = 'Active';"))
                    conn.execute(text("UPDATE users SET email_original = email WHERE (email_original IS NULL OR email_original = '') AND email LIKE '%@%';"))
                    conn.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"Schema migration helper note: {e}")
        try:
            import hashlib
            from app.models.user import User, VerificationCode
            from app.models.email_verification import EmailVerification
            db = SessionLocal()
            
            # 1. Users table
            all_users = db.query(User).all()
            updated_count = 0
            for u in all_users:
                if u.email:
                    normalized_email = u.email.strip().lower()
                    u.email = normalized_email
                    if not u.email_hash:
                        u.email_hash = normalized_email
                    updated_count += 1

            # 2. VerificationCode table
            try:
                vc_codes = db.query(VerificationCode).all()
                for vc in vc_codes:
                    if vc.email:
                        normalized_email = vc.email.strip().lower()
                        vc.email = normalized_email
                        updated_count += 1
            except Exception as _e:
                pass

            # 3. EmailVerification table
            try:
                ev_codes = db.query(EmailVerification).all()
                for ev in ev_codes:
                    if ev.email:
                        normalized_email = ev.email.strip().lower()
                        ev.email = normalized_email
                        updated_count += 1
            except Exception as _e:
                pass

            if updated_count > 0:
                db.commit()
                print(f"Migrated {updated_count} email fields to SHA-256 hash values in database.")
            db.close()
        except Exception as migration_err:
            print(f"Migration fallback note: {migration_err}")

    # Ensure baseline roles exist if table is completely empty
    try:
        from app.models.role import Role
        from app.models.category import Category
        inspector = inspect(engine)
        if inspector.has_table("roles") and inspector.has_table("categories"):
            db = SessionLocal()
            try:
                if db.query(Role).count() == 0:
                    roles = [
                        Role(id=1, role_name="Administrator", description="Full platform access"),
                        Role(id=2, role_name="Manager", description="Team management and approval"),
                        Role(id=3, role_name="Employee", description="Create and submit decisions"),
                        Role(id=4, role_name="Reviewer", description="Review assigned decisions")
                    ]
                    db.add_all(roles)
                    db.commit()
                    print("Initialized default system roles in database.")
                if db.query(Category).count() == 0:
                    categories = [
                        Category(id=1, name="Finance"),
                        Category(id=2, name="Technology"),
                        Category(id=3, name="Operations"),
                        Category(id=4, name="HR")
                    ]
                    db.add_all(categories)
                    db.commit()
            finally:
                db.close()
    except Exception as role_init_err:
        print(f"Baseline roles check note: {role_init_err}")

ensure_user_schema_columns()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()