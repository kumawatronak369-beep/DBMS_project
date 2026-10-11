from sqlalchemy.orm import Session

from app.core.query_params import Pagination, TimeRange
from app.exceptions.handlers import NotFoundError
from app.repositories.device_repository import DeviceRepository
from app.repositories.history_repository import HistoryFilters
from app.schemas.common import Paginated
from app.schemas.device import DeviceDetail, DeviceListItem, RecentDestination
from app.schemas.history import HistoryOut
from app.services.activity_service import ActivityService
from app.services.history_service import HistoryService

RECENT_DESTINATIONS_LIMIT = 10
ACTIVITY_DAYS = 7


class DeviceService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = DeviceRepository(db)

    def list_devices(
        self, search: str | None, node_id: int | None, status: str | None, pagination: Pagination
    ) -> Paginated[DeviceListItem]:
        rows, total = self.repository.list(
            search=search, node_id=node_id, status=status, limit=pagination.page_size, offset=pagination.offset
        )
        return Paginated[DeviceListItem](
            items=[DeviceListItem.model_validate(r) for r in rows],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    def get_device(self, device_id: int) -> DeviceDetail:
        row = self.repository.get(device_id)
        if row is None:
            raise NotFoundError(f"Device {device_id} not found")
        return DeviceDetail(
            **DeviceListItem.model_validate(row).model_dump(),
            total_events=self.repository.total_events(device_id),
            activity_by_day=ActivityService(self.db).last_days(ACTIVITY_DAYS, device_id=device_id),
            recent_destinations=[
                RecentDestination.model_validate(r)
                for r in self.repository.recent_destinations(device_id, RECENT_DESTINATIONS_LIMIT)
            ],
        )

    def get_device_history(
        self, device_id: int, time_range: TimeRange, pagination: Pagination
    ) -> Paginated[HistoryOut]:
        if not self.repository.exists(device_id):
            raise NotFoundError(f"Device {device_id} not found")
        filters = HistoryFilters(device_id=device_id, start=time_range.start, end=time_range.end)
        return HistoryService(self.db).list_history(filters, pagination)
