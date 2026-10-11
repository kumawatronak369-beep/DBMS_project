import hashlib
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
import jwt

from app.core.config import get_settings

# fixed algorithm, so a token can't pick its own (e.g. none)
ALGORITHM = "HS256"
MIN_SECRET_LENGTH = 32
# bcrypt only uses the first 72 bytes of a password
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def hash_api_key(api_key: str) -> str:
    """API keys are long random secrets, so a fast SHA-256 hash is enough."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


@lru_cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-constant-time-checks")


def verify_against_dummy(password: str) -> None:
    """Spend the same time as a real check so unknown emails can't be spotted by timing."""
    verify_password(password, _dummy_hash())


_PLACEHOLDER_MARKERS = ("change-me", "changeme", "change_me", "your-secret", "your_secret", "example")


def ensure_jwt_secret_configured() -> None:
    secret = get_settings().jwt_secret
    if len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET must be set to a random string of at least {MIN_SECRET_LENGTH} characters"
        )
    if any(marker in secret.lower() for marker in _PLACEHOLDER_MARKERS):
        raise RuntimeError(
            "JWT_SECRET is still a placeholder value; generate a random one with: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )


def create_access_token(user_id: int, *, expires_delta: timedelta | None = None) -> str:
    """Sign a short-lived token that carries only the user id."""
    ensure_jwt_secret_configured()
    now = datetime.now(timezone.utc)
    lifetime = expires_delta if expires_delta is not None else timedelta(
        minutes=get_settings().access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id from a valid token, otherwise None."""
    ensure_jwt_secret_configured()
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        return None


def access_token_lifetime_seconds() -> int:
    return get_settings().access_token_expire_minutes * 60
