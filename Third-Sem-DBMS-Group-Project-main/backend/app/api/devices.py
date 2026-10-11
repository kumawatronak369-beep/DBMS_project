from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.query_params import Pagination, TimeRange, get_pagination, get_time_range
from app.schemas.common import Paginated
from app.schemas.device import DeviceDetail, DeviceListItem, DeviceStatus
from app.schemas.history import HistoryOut
from app.services.device_service import DeviceService

router = APIRouter(prefix="/devices", tags=["devices"], dependencies=[Depends(get_current_user)])


def get_service(db: Session = Depends(get_db)) -> DeviceService:
    return DeviceService(db)


@router.get("", response_model=Paginated[DeviceListItem])
def list_devices(
    search: str | None = Query(None, max_length=100),
    node_id: int | None = Query(None, ge=1, alias="nodeId"),
    status_filter: DeviceStatus | None = Query(None, alias="status"),
    pagination: Pagination = Depends(get_pagination),
    service: DeviceService = Depends(get_service),
):
    return service.list_devices(search, node_id, status_filter, pagination)


@router.get("/{device_id}", response_model=DeviceDetail)
def get_device(device_id: int = Path(ge=1), service: DeviceService = Depends(get_service)):
    return service.get_device(device_id)


@router.get("/{device_id}/history", response_model=Paginated[HistoryOut])
def get_device_history(
    device_id: int = Path(ge=1),
    time_range: TimeRange = Depends(get_time_range),
    pagination: Pagination = Depends(get_pagination),
    service: DeviceService = Depends(get_service),
):
    return service.get_device_history(device_id, time_range, pagination)
