from datetime import datetime, timedelta, timezone

from jose import jwt

from app.config.settings import settings


def create_access_token(data: dict, expires_delta: timedelta = None):
    """
    Create JWT access token (default 72 hours / 3 days for persistent sessions).
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=72)

    to_encode.update(
        {
            "exp": expire
        }
    )

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt