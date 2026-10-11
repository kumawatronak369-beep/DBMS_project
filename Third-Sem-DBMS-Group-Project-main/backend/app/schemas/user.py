from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import Email, NewPassword, UserRole, UserStatus


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    email: Email
    password: NewPassword
    role: UserRole = "ANALYST"


class UserUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    email: Email
    role: UserRole
    password: NewPassword | None = None


class UserStatusUpdate(BaseModel):
    status: UserStatus
