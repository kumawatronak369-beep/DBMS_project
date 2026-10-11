from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.query_params import Pagination, TimeRange, get_pagination, get_time_range
from app.repositories.history_repository import HistoryFilters
from app.schemas.common import Paginated
from app.schemas.history import HistoryOut
from app.services.history_service import HistoryService

router = APIRouter(prefix="/history", tags=["history"], dependencies=[Depends(get_current_user)])


def get_service(db: Session = Depends(get_db)) -> HistoryService:
    return HistoryService(db)


@router.get("", response_model=Paginated[HistoryOut])
def list_history(
    q: str | None = Query(None, max_length=100, description="Search device / IP / domain"),
    device: str | None = Query(None, max_length=100, description="Device identifier, name or IP"),
    device_id: int | None = Query(None, ge=1, alias="deviceId"),
    node_id: int | None = Query(None, ge=1, alias="nodeId"),
    destination_id: int | None = Query(None, ge=1, alias="destinationId"),
    domain: str | None = Query(None, max_length=255),
    time_range: TimeRange = Depends(get_time_range),
    pagination: Pagination = Depends(get_pagination),
    service: HistoryService = Depends(get_service),
):
    filters = HistoryFilters(
        q=q,
        device=device,
        device_id=device_id,
        node_id=node_id,
        destination_id=destination_id,
        domain=domain,
        start=time_range.start,
        end=time_range.end,
    )
    return service.list_history(filters, pagination)


@router.get("/{history_id}", response_model=HistoryOut)
def get_history_event(history_id: int = Path(ge=1), service: HistoryService = Depends(get_service)):
    return service.get_event(history_id)
