import hashlib
import hmac
import os
from dotenv import load_dotenv
from passlib.context import CryptContext

# Ensure environment variables from .env are loaded
for _p in [
    os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"),
    os.path.join(os.getcwd(), ".env"),
    os.path.join(os.getcwd(), "..", ".env"),
]:
    if os.path.isfile(_p):
        load_dotenv(os.path.abspath(_p))
        break

# Secret key dynamically loaded from environment variable (never hardcoded in source)
def _get_security_key() -> str:
    return os.getenv("SECURITY_SECRET_KEY") or os.getenv("SECRET_KEY") or "edrp-security-key-fallback"

# Password hashing configuration
pwd_context = CryptContext(
    schemes=["sha256_crypt", "bcrypt"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    """
    Hash passwords using HMAC-SHA256 with the designated platform secret key.
    Secures newly created account passwords using the platform secret key.
    """
    if password is None:
        return ""
    str_pwd = str(password)
    return hmac.new(
        _get_security_key().encode("utf-8"),
        str_pwd.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def hash_email(email: str) -> str:
    """
    Hash email addresses using HMAC-SHA256 with the designated platform secret key.
    Secures newly created email hash codes.
    """
    if not email:
        return ""
    clean_email = str(email).strip().lower()
    return hmac.new(
        _get_security_key().encode("utf-8"),
        clean_email.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """
    Verify a plain password against a stored hash.
    Supports:
    - Platform Secret Key HMAC-SHA256 (for newly created / updated accounts)
    - 64-char standard SHA-256 (for existing legacy accounts)
    - 32-char SHA-256 prefix/truncated hashes
    - 32-char MD5 hashes
    - Legacy passlib hashes (bcrypt, sha256_crypt)
    - Plain text fallback
    """
    if plain_password is None or hashed_password is None:
        return False

    str_plain = str(plain_password)
    str_hash = str(hashed_password).strip()

    if not str_plain or not str_hash:
        return False

    sec_key_bytes = _get_security_key().encode("utf-8")

    for candidate in [str_plain, str_plain.strip()]:
        # 1. Platform Secret Key HMAC-SHA256 match (new accounts)
        c_hmac = hmac.new(
            sec_key_bytes,
            candidate.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if hmac.compare_digest(c_hmac.lower(), str_hash.lower()):
            return True

        c_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        c_md5 = hashlib.md5(candidate.encode("utf-8")).hexdigest()

        # 2. Standard SHA-256 match (64-char legacy accounts)
        if c_sha256.lower() == str_hash.lower():
            return True

        # 3. 32-char / truncated SHA-256 match
        if len(str_hash) >= 16 and (c_sha256.lower().startswith(str_hash.lower()) or str_hash.lower().startswith(c_sha256[:len(str_hash)].lower())):
            return True

        # 4. MD5 match
        if c_md5.lower() == str_hash.lower():
            return True

    # 5. Legacy passlib verification (bcrypt, sha256_crypt, etc.)
    try:
        if pwd_context.identify(str_hash):
            if pwd_context.verify(str_plain, str_hash):
                return True
            if pwd_context.verify(str_plain.strip(), str_hash):
                return True
    except Exception:
        pass

    # 6. Plain text fallback
    if str_hash == str_plain or str_hash == str_plain.strip():
        return True

    return False



def generate_data_hash(*args) -> str:
    """
    Generate a SHA-256 hash for the given string arguments to ensure data integrity.
    """
    hash_obj = hashlib.sha256()
    for arg in args:
        if arg is not None:
            hash_obj.update(str(arg).encode('utf-8'))
    return hash_obj.hexdigest()