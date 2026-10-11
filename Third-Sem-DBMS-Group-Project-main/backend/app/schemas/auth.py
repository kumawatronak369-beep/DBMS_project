import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, SecretStr

from app.core.security import MAX_PASSWORD_BYTES

UserRole = Literal["ADMIN", "ANALYST"]
UserStatus = Literal["ACTIVE", "DISABLED"]

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+$")


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_PATTERN.match(value):
        raise ValueError("must be a valid email address")
    return value


MIN_PASSWORD_LENGTH = 8


def _check_new_password(value: SecretStr) -> SecretStr:
    secret = value.get_secret_value()
    if len(secret) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(secret.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"must be at most {MAX_PASSWORD_BYTES} bytes")
    return value


# emails are stored lower-case
Email = Annotated[str, Field(min_length=3, max_length=255), AfterValidator(_normalize_email)]

NewPassword = Annotated[SecretStr, AfterValidator(_check_new_password)]


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: SecretStr = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    name: str
    email: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    last_login: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut
