from sqlalchemy.orm import Session

from app.core.query_params import Pagination
from app.exceptions.handlers import NotFoundError
from app.repositories.history_repository import HistoryFilters, HistoryRepository
from app.schemas.common import Paginated
from app.schemas.history import HistoryOut


class HistoryService:
    def __init__(self, db: Session):
        self.repository = HistoryRepository(db)

    def list_history(self, filters: HistoryFilters, pagination: Pagination) -> Paginated[HistoryOut]:
        rows, total = self.repository.list(filters, limit=pagination.page_size, offset=pagination.offset)
        return Paginated[HistoryOut](
            items=[HistoryOut.model_validate(r) for r in rows],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    def get_event(self, history_id: int) -> HistoryOut:
        row = self.repository.get(history_id)
        if row is None:
            raise NotFoundError(f"History event {history_id} not found")
        return HistoryOut.model_validate(row)
