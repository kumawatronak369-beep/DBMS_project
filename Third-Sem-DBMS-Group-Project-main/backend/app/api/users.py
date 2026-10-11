from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, require_admin
from app.core.query_params import Pagination, get_pagination
from app.schemas.auth import UserOut, UserRole, UserStatus
from app.schemas.common import Paginated
from app.schemas.user import UserCreate, UserStatusUpdate, UserUpdate
from app.services.user_service import UserService

# user management is admin only
router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


def get_service(db: Session = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("", response_model=Paginated[UserOut])
def list_users(
    search: str | None = Query(None, max_length=100),
    role: UserRole | None = Query(None),
    status_filter: UserStatus | None = Query(None, alias="status"),
    pagination: Pagination = Depends(get_pagination),
    service: UserService = Depends(get_service),
):
    return service.list_users(search, role, status_filter, pagination)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int = Path(ge=1), service: UserService = Depends(get_service)):
    return service.get_user(user_id)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, service: UserService = Depends(get_service)):
    return service.create_user(data)


@router.put("/{user_id}", response_model=UserOut)
def update_user(data: UserUpdate, user_id: int = Path(ge=1), service: UserService = Depends(get_service)):
    return service.update_user(user_id, data)


@router.patch("/{user_id}/status", response_model=UserOut)
def update_user_status(
    data: UserStatusUpdate, user_id: int = Path(ge=1), service: UserService = Depends(get_service)
):
    return service.update_status(user_id, data.status)
