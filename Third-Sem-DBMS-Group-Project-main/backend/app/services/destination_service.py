from sqlalchemy.orm import Session

from app.core.query_params import Pagination, TimeRange
from app.exceptions.handlers import NotFoundError
from app.repositories.destination_repository import DestinationRepository
from app.repositories.history_repository import HistoryFilters
from app.schemas.common import Paginated
from app.schemas.destination import DestinationDetail, DestinationDevice, DestinationListItem, DestinationNode
from app.schemas.history import HistoryOut
from app.services.history_service import HistoryService

DEVICES_LIMIT = 50


class DestinationService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = DestinationRepository(db)

    def list_destinations(
        self, search: str | None, category: str | None, pagination: Pagination
    ) -> Paginated[DestinationListItem]:
        rows, total = self.repository.list(
            search=search, category=category, limit=pagination.page_size, offset=pagination.offset
        )
        return Paginated[DestinationListItem](
            items=[DestinationListItem.model_validate(r) for r in rows],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    def get_destination(self, destination_id: int) -> DestinationDetail:
        row = self.repository.get(destination_id)
        if row is None:
            raise NotFoundError(f"Destination {destination_id} not found")
        return DestinationDetail(
            **DestinationListItem.model_validate(row).model_dump(),
            nodes=[DestinationNode.model_validate(r) for r in self.repository.nodes(destination_id)],
            devices=[DestinationDevice.model_validate(r) for r in self.repository.devices(destination_id, DEVICES_LIMIT)],
        )

    def get_destination_history(
        self, destination_id: int, time_range: TimeRange, pagination: Pagination
    ) -> Paginated[HistoryOut]:
        if not self.repository.exists(destination_id):
            raise NotFoundError(f"Destination {destination_id} not found")
        filters = HistoryFilters(destination_id=destination_id, start=time_range.start, end=time_range.end)
        return HistoryService(self.db).list_history(filters, pagination)
