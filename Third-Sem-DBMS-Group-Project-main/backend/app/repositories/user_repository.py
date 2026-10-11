from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import User
from app.repositories.filters import contains


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(
        self, *, search: str | None, role: str | None, status: str | None, limit: int, offset: int
    ) -> tuple[list[User], int]:
        conditions = []
        if search:
            conditions.append(or_(contains(User.name, search), contains(User.email, search)))
        if role:
            conditions.append(User.role == role)
        if status:
            conditions.append(User.status == status)

        users = self.db.scalars(
            select(User).where(*conditions).order_by(User.name, User.user_id).limit(limit).offset(offset)
        ).all()
        total = self.db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
        return list(users), total

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def count_active_admins(self) -> int:
        return (
            self.db.scalar(select(func.count()).select_from(User).where(User.role == "ADMIN", User.status == "ACTIVE"))
            or 0
        )
