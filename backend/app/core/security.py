from passlib.context import CryptContext
import hashlib

# Password hashing configuration
pwd_context = CryptContext(
    schemes=["sha256_crypt", "bcrypt"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    """
    Store a SHA-256 hash value for passwords.
    """
    if password is None:
        return ""
    return hashlib.sha256(str(password).encode("utf-8")).hexdigest()


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """
    Verify a plain password against a stored hash.
    Supports current SHA-256, legacy passlib hashes (bcrypt, sha256_crypt), and plain text.
    Handles mobile input variants (e.g. accidental trailing/leading whitespace from keyboards).
    """
    if plain_password is None or hashed_password is None:
        return False

    str_plain = str(plain_password)
    str_hash = str(hashed_password).strip()

    if not str_plain or not str_hash:
        return False

    # 1. Standard SHA-256 hex match (current system standard)
    if hashlib.sha256(str_plain.encode("utf-8")).hexdigest() == str_hash:
        return True
    if hashlib.sha256(str_plain.strip().encode("utf-8")).hexdigest() == str_hash:
        return True

    # 2. Legacy passlib verification (bcrypt, sha256_crypt, etc.)
    try:
        if pwd_context.identify(str_hash):
            if pwd_context.verify(str_plain, str_hash):
                return True
            if pwd_context.verify(str_plain.strip(), str_hash):
                return True
    except Exception:
        pass

    # 3. Plain text fallback (for any legacy development/seeded records)
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