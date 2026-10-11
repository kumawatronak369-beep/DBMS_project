from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.query_params import Pagination
from app.exceptions.handlers import ConflictError, NotFoundError
from app.models import Node
from app.repositories.history_repository import HistoryFilters
from app.repositories.node_repository import NodeRepository
from app.schemas.common import Paginated
from app.schemas.node import NodeCreate, NodeDetail, NodeListItem, NodeOut, NodeUpdate
from app.services.activity_service import ActivityService
from app.services.history_service import HistoryService

RECENT_ACTIVITY_LIMIT = 10
ACTIVITY_DAYS = 7


class NodeService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = NodeRepository(db)

    def list_nodes(self, search: str | None, status: str | None, pagination: Pagination) -> Paginated[NodeListItem]:
        rows, total = self.repository.list(
            search=search, status=status, limit=pagination.page_size, offset=pagination.offset
        )
        return Paginated[NodeListItem](
            items=[NodeListItem.model_validate(r) for r in rows],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
        )

    def get_node(self, node_id: int) -> NodeDetail:
        node = self._get_or_404(node_id)
        recent = HistoryService(self.db).list_history(
            HistoryFilters(node_id=node_id), Pagination(page=1, page_size=RECENT_ACTIVITY_LIMIT)
        )
        return NodeDetail(
            **NodeOut.model_validate(node).model_dump(),
            device_count=self.repository.device_count(node_id),
            event_count=self.repository.event_count(node_id),
            recent_activity=recent.items,
            activity_by_day=ActivityService(self.db).last_days(ACTIVITY_DAYS, node_id=node_id),
        )

    def create_node(self, data: NodeCreate) -> NodeOut:
        self._ensure_code_available(data.node_code)
        node = Node(**data.model_dump())
        try:
            self.repository.add(node)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(f"Node code '{data.node_code}' is already in use") from None
        self.db.refresh(node)
        return NodeOut.model_validate(node)

    def update_node(self, node_id: int, data: NodeUpdate) -> NodeOut:
        node = self._get_or_404(node_id)
        if data.node_code != node.node_code:
            self._ensure_code_available(data.node_code)
        for field, value in data.model_dump().items():
            setattr(node, field, value)
        return self._commit(node, data.node_code)

    def update_status(self, node_id: int, status: str) -> NodeOut:
        node = self._get_or_404(node_id)
        node.status = status
        return self._commit(node, node.node_code)

    def _commit(self, node: Node, node_code: str) -> NodeOut:
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(f"Node code '{node_code}' is already in use") from None
        self.db.refresh(node)
        return NodeOut.model_validate(node)

    def _get_or_404(self, node_id: int) -> Node:
        node = self.repository.get(node_id)
        if node is None:
            raise NotFoundError(f"Node {node_id} not found")
        return node

    def _ensure_code_available(self, node_code: str) -> None:
        if self.repository.get_by_code(node_code) is not None:
            raise ConflictError(f"Node code '{node_code}' is already in use")
