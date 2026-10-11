from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.query_params import TimeRange
from app.exceptions.handlers import NotFoundError
from app.repositories.node_repository import NodeRepository
from app.repositories.stats_repository import StatsRepository
from app.schemas.common import ActivitySeries
from app.schemas.report import NodeActivity, TopDestination, TopDevice
from app.services.activity_service import ActivityService, resolve_window


class ReportService:
    def __init__(self, db: Session):
        self.stats = StatsRepository(db)
        self.nodes = NodeRepository(db)
        self.activity = ActivityService(db)

    def top_destinations(self, time_range: TimeRange, limit: int) -> list[TopDestination]:
        rows = self.stats.top_destinations(time_range.start, time_range.end, limit)
        return [TopDestination.model_validate(r) for r in rows]

    def top_devices(self, time_range: TimeRange, limit: int) -> list[TopDevice]:
        rows = self.stats.top_devices(time_range.start, time_range.end, limit)
        return [TopDevice.model_validate(r) for r in rows]

    def activity_by_node(self, time_range: TimeRange) -> list[NodeActivity]:
        rows = self.stats.node_activity(time_range.start, time_range.end)
        return [NodeActivity.model_validate(r) for r in rows]

    def activity_over_time(self, time_range: TimeRange, node_id: int | None) -> ActivitySeries:
        if node_id is not None and self.nodes.get(node_id) is None:
            raise NotFoundError(f"Node {node_id} not found")
        start, end = resolve_window(time_range, timedelta(hours=24))
        return self.activity.series(start, end, node_id=node_id)
