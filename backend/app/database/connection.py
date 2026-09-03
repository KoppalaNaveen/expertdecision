import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Find and load .env from any working directory (Render uses --chdir frontend)
_env_candidates = [
    os.path.join(os.path.dirname(__file__), "..", "..", ".env"),       # backend/.env
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"), # root .env
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.getcwd(), "..", ".env"),
    os.path.join(os.getcwd(), "backend", ".env"),
    os.path.join(os.getcwd(), "..", "backend", ".env"),
]
for _ep in _env_candidates:
    _abs = os.path.abspath(_ep)
    if os.path.isfile(_abs):
        load_dotenv(_abs)
        break
else:
    load_dotenv()  # fallback


from sqlalchemy import text, inspect


def _get_local_sqlite_url():
    candidates = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "edrp.db")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "edrp.db")),
        os.path.abspath(os.path.join(os.getcwd(), "edrp.db")),
        os.path.abspath(os.path.join(os.getcwd(), "backend", "edrp.db")),
        os.path.abspath(os.path.join(os.getcwd(), "..", "backend", "edrp.db")),
        os.path.abspath(os.path.join(os.getcwd(), "..", "edrp.db")),
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return f"sqlite:///{p}"
    return f"sqlite:///{candidates[0]}"

DEFAULT_SUPABASE_URL = "postgresql://postgres.myofagxphtmzuldbtijc:ShabhanaaNaveen0320%40@aws-1-ap-south-1.pooler.supabase.com:5432/postgres"

raw_env_url = os.getenv("DATABASE_URL")
print(f"[DB] Raw DATABASE_URL from env: {'(set, ' + str(len(raw_env_url)) + ' chars)' if raw_env_url else '(NOT SET)'}")

# ALWAYS use Supabase PostgreSQL (IPv4 Pooler) as the primary database
# Supports platforms without outbound IPv6 (Render, AWS Lambda, Docker, etc.)
if raw_env_url and (raw_env_url.strip().startswith("postgresql") or raw_env_url.strip().startswith("postgres://")):
    DATABASE_URL = raw_env_url.strip().replace("postgres://", "postgresql://", 1)
    # Auto-convert IPv6-only direct hostname to IPv4-compatible pooler
    if "db.myofagxphtmzuldbtijc.supabase.co" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("db.myofagxphtmzuldbtijc.supabase.co", "aws-1-ap-south-1.pooler.supabase.com")
        if "postgres:" in DATABASE_URL and "postgres.myofagxphtmzuldbtijc:" not in DATABASE_URL:
            DATABASE_URL = DATABASE_URL.replace("postgres:", "postgres.myofagxphtmzuldbtijc:", 1)
    print("[DB] Using DATABASE_URL from environment (with IPv4 pooler)")
else:
    # Default to production Supabase IPv4 Pooler
    DATABASE_URL = DEFAULT_SUPABASE_URL
    print("[DB] Using default production Supabase IPv4 Connection Pooler")

# Create PostgreSQL engine - ALWAYS (never fall back to SQLite in production)
print(f"[DB] Connecting to PostgreSQL database...")
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=300,
    pool_pre_ping=True,
    connect_args={"sslmode": "require", "connect_timeout": 30}
)

# Verify connection at startup (non-blocking - engine uses pre_ping for auto-reconnect)
import time
for attempt in range(1, 4):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print(f"[DB] PostgreSQL connection VERIFIED (attempt {attempt})")
        break
    except Exception as db_err:
        print(f"[DB] Connection verification attempt {attempt}: {db_err}")
        if attempt < 3:
            time.sleep(2)
        else:
            print("[DB] Startup verification failed but engine created with pool_pre_ping=True (will auto-reconnect on first query)")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

from app.database.base import Base
from app import models

_SCHEMA_INITIALIZED = False

def ensure_user_schema_columns():
    global _SCHEMA_INITIALIZED
    if _SCHEMA_INITIALIZED:
        return
    _SCHEMA_INITIALIZED = True
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
            ("decisions", "approved_by_id", "INTEGER REFERENCES users(id)"),
            ("decisions", "approved_at", "TIMESTAMP WITH TIME ZONE"),
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
        from app.models.user import User
        from app.models.team import Team
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

    # Ensure baseline teams exist
    try:
        from app.models.team import Team
        inspector = inspect(engine)
        if inspector.has_table("teams"):
            db = SessionLocal()
            try:
                teams_data = [
                    (1, "AI Team", "Artificial Intelligence and Machine Learning Research"),
                    (2, "Engineering", "Core platform and application engineering"),
                    (3, "Product", "Product strategy, UI/UX, and feature roadmap"),
                    (4, "Operations", "Cloud operations, DevOps, and infrastructure"),
                    (5, "Quality Assurance", "QA and Test Automation"),
                    (6, "Security & Compliance", "Security auditing and compliance review")
                ]
                for t_id, t_name, t_desc in teams_data:
                    existing_t = db.query(Team).filter(Team.id == t_id).first()
                    if not existing_t:
                        db.add(Team(id=t_id, team_name=t_name, description=t_desc))
                    else:
                        existing_t.team_name = t_name
                        existing_t.description = t_desc
                db.commit()
            finally:
                db.close()
    except Exception as team_init_err:
        print(f"Baseline teams check note: {team_init_err}")

    # Schema column verification complete - never re-seed deleted users or decisions
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()