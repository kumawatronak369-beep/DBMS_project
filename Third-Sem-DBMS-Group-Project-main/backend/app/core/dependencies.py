from collections.abc import Callable, Iterator

from fastapi import Depends
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.exceptions.handlers import ForbiddenError, UnauthorizedError
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.collector_auth_service import CollectorAuthService, CollectorPrincipal

# auto_error=False so a missing header gets our own 401
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate from the Bearer token; the user is re-read from the DB on every request."""
    if credentials is None:
        raise UnauthorizedError("Not authenticated")

    user_id = decode_access_token(credentials.credentials)
    user = UserRepository(db).get(user_id) if user_id is not None else None
    if user is None or user.status != "ACTIVE":
        raise UnauthorizedError("Invalid or expired token")
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("You do not have permission to perform this action")
        return user

    return checker


require_admin = require_roles("ADMIN")


def get_collector_principal(
    api_key: str | None = Depends(api_key_scheme),
    db: Session = Depends(get_db),
) -> CollectorPrincipal:
    return CollectorAuthService(db).authenticate(api_key)
