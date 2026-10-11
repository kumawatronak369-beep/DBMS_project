from datetime import datetime

from sqlalchemy.orm import Session

from app.core.security import (
    access_token_lifetime_seconds,
    create_access_token,
    verify_against_dummy,
    verify_password,
)
from app.exceptions.handlers import ForbiddenError, UnauthorizedError
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse, UserOut

INVALID_CREDENTIALS = "Invalid email or password"


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def login(self, email: str, password: str) -> TokenResponse:
        user = self.users.get_by_email(email.strip().lower())

        if user is None:
            verify_against_dummy(password)
            raise UnauthorizedError(INVALID_CREDENTIALS)
        if not verify_password(password, user.password_hash):
            raise UnauthorizedError(INVALID_CREDENTIALS)
        # only reveal a disabled account after the right password
        if user.status != "ACTIVE":
            raise ForbiddenError("This account is disabled")

        user.last_login = datetime.now()
        self.db.commit()
        self.db.refresh(user)

        return TokenResponse(
            access_token=create_access_token(user.user_id),
            expires_in=access_token_lifetime_seconds(),
            user=UserOut.model_validate(user),
        )
