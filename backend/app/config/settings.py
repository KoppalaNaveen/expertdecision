import os
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file():
    """Find the .env file from multiple candidate locations (works from any CWD)."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),       # backend/.env
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"), # root .env
        os.path.join(os.getcwd(), ".env"),                                # CWD/.env
        os.path.join(os.getcwd(), "..", ".env"),                          # CWD/../.env
        os.path.join(os.getcwd(), "backend", ".env"),                     # CWD/backend/.env
        os.path.join(os.getcwd(), "..", "backend", ".env"),               # CWD/../backend/.env
    ]
    for p in candidates:
        absp = os.path.abspath(p)
        if os.path.isfile(absp):
            return absp
    return ".env"  # fallback (pydantic silently ignores missing files)


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///edrp.db"
    SECRET_KEY: str = "afbq ktmu njch bgdd"
    SECURITY_SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()