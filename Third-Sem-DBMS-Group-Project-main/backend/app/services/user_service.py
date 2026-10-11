from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.query_params import Pagination
from app.core.security import hash_password
from app.exceptions.handlers import ConflictError, NotFoundError
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserOut
from app.schemas.common import Paginated
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = UserRepository(db)

    def list_users(
        self, search: str | None, role: str | None, status: str | None, pagination: Pagination
    ) -> Paginated[UserOut]:
        users, total = self.repository.list(
            search=search, role=role, status=status, limit=pagination.page_size, offset=pagination.offset
        )
        return Paginated[UserOut](
            items=[UserOut.model_validate(u) for u in users],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    def get_user(self, user_id: int) -> UserOut:
        return UserOut.model_validate(self._get_or_404(user_id))

    def create_user(self, data: UserCreate) -> UserOut:
        self._ensure_email_available(data.email)
        user = User(
            name=data.name,
            email=data.email,
            role=data.role,
            password_hash=hash_password(data.password.get_secret_value()),
        )
        try:
            self.repository.add(user)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(f"Email '{data.email}' is already in use") from None
        self.db.refresh(user)
        return UserOut.model_validate(user)

    def update_user(self, user_id: int, data: UserUpdate) -> UserOut:
        user = self._get_or_404(user_id)
        if data.email != user.email:
            self._ensure_email_available(data.email)
        self._ensure_admin_remains(user, new_role=data.role, new_status=user.status)

        user.name = data.name
        user.email = data.email
        user.role = data.role
        if data.password is not None:
            user.password_hash = hash_password(data.password.get_secret_value())
        return self._commit(user)

    def update_status(self, user_id: int, status: str) -> UserOut:
        user = self._get_or_404(user_id)
        self._ensure_admin_remains(user, new_role=user.role, new_status=status)
        user.status = status
        return self._commit(user)

    def _commit(self, user: User) -> UserOut:
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError("Email is already in use") from None
        self.db.refresh(user)
        return UserOut.model_validate(user)

    def _get_or_404(self, user_id: int) -> User:
        user = self.repository.get(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    def _ensure_email_available(self, email: str) -> None:
        if self.repository.get_by_email(email) is not None:
            raise ConflictError(f"Email '{email}' is already in use")

    def _ensure_admin_remains(self, user: User, *, new_role: str, new_status: str) -> None:
        """Never allow the last active admin to be demoted or disabled."""
        is_active_admin = user.role == "ADMIN" and user.status == "ACTIVE"
        stays_active_admin = new_role == "ADMIN" and new_status == "ACTIVE"
        if is_active_admin and not stays_active_admin and self.repository.count_active_admins() <= 1:
            raise ConflictError("At least one active administrator must remain")
