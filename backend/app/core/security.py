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
    """
    if not plain_password or not hashed_password:
        return False
    if str(hashed_password) == str(plain_password):
        return False
    return hashlib.sha256(str(plain_password).encode("utf-8")).hexdigest() == str(hashed_password)


def generate_data_hash(*args) -> str:
    """
    Generate a SHA-256 hash for the given string arguments to ensure data integrity.
    """
    hash_obj = hashlib.sha256()
    for arg in args:
        if arg is not None:
            hash_obj.update(str(arg).encode('utf-8'))
    return hash_obj.hexdigest()