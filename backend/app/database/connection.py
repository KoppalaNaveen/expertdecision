import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

from app.database.base import Base
from app import models
from sqlalchemy import text

def ensure_user_schema_columns():
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS approved BOOLEAN DEFAULT FALSE;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'Pending Approval';
                ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_by VARCHAR(100);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS approved_at VARCHAR(50);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS rejected_by VARCHAR(100);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS rejected_at VARCHAR(50);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at VARCHAR(50);
                ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at VARCHAR(50);
                UPDATE users SET approved = TRUE, status = 'Active', email_verified = TRUE, is_active = TRUE WHERE status IS NULL OR status = '' OR status = 'Active';
                COMMIT;
            """))
    except Exception as e:
        print(f"Schema migration helper note: {e}")

ensure_user_schema_columns()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()