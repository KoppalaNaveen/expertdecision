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
    Supports:
    - 64-char standard SHA-256
    - 32-char SHA-256 prefix/truncated hashes (e.g. from Supabase columns)
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

    for candidate in [str_plain, str_plain.strip()]:
        c_sha256 = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        c_md5 = hashlib.md5(candidate.encode("utf-8")).hexdigest()

        # 1. Exact SHA-256 match (64-char)
        if c_sha256.lower() == str_hash.lower():
            return True

        # 2. 32-char / truncated SHA-256 match
        if len(str_hash) >= 16 and (c_sha256.lower().startswith(str_hash.lower()) or str_hash.lower().startswith(c_sha256[:len(str_hash)].lower())):
            return True

        # 3. MD5 match
        if c_md5.lower() == str_hash.lower():
            return True

    # 4. Legacy passlib verification (bcrypt, sha256_crypt, etc.)
    try:
        if pwd_context.identify(str_hash):
            if pwd_context.verify(str_plain, str_hash):
                return True
            if pwd_context.verify(str_plain.strip(), str_hash):
                return True
    except Exception:
        pass

    # 5. Plain text fallback
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