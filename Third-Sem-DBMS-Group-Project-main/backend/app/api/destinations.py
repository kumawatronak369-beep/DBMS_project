from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.query_params import Pagination, TimeRange, get_pagination, get_time_range
from app.schemas.common import Paginated
from app.schemas.destination import DestinationCategory, DestinationDetail, DestinationListItem
from app.schemas.history import HistoryOut
from app.services.destination_service import DestinationService

router = APIRouter(prefix="/destinations", tags=["destinations"], dependencies=[Depends(get_current_user)])


def get_service(db: Session = Depends(get_db)) -> DestinationService:
    return DestinationService(db)


@router.get("", response_model=Paginated[DestinationListItem])
def list_destinations(
    search: str | None = Query(None, max_length=100),
    category: DestinationCategory | None = Query(None),
    pagination: Pagination = Depends(get_pagination),
    service: DestinationService = Depends(get_service),
):
    return service.list_destinations(search, category, pagination)


@router.get("/{destination_id}", response_model=DestinationDetail)
def get_destination(destination_id: int = Path(ge=1), service: DestinationService = Depends(get_service)):
    return service.get_destination(destination_id)


@router.get("/{destination_id}/history", response_model=Paginated[HistoryOut])
def get_destination_history(
    destination_id: int = Path(ge=1),
    time_range: TimeRange = Depends(get_time_range),
    pagination: Pagination = Depends(get_pagination),
    service: DestinationService = Depends(get_service),
):
    return service.get_destination_history(destination_id, time_range, pagination)
