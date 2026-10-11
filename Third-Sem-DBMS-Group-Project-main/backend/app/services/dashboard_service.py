from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.core.query_params import TimeRange
from app.repositories.stats_repository import StatsRepository
from app.schemas.common import ActivitySeries
from app.schemas.dashboard import DashboardSummary
from app.schemas.report import TopDestination, TopDevice
from app.services.activity_service import ActivityService, resolve_window


class DashboardService:
    def __init__(self, db: Session):
        self.stats = StatsRepository(db)
        self.activity = ActivityService(db)

    def summary(self) -> DashboardSummary:
        day_start = datetime.combine(date.today(), time.min)
        return DashboardSummary.model_validate(self.stats.summary(day_start))

    def activity_series(self, time_range: TimeRange) -> ActivitySeries:
        start, end = resolve_window(time_range, timedelta(hours=24))
        return self.activity.series(start, end)

    def top_destinations(self, time_range: TimeRange, limit: int) -> list[TopDestination]:
        rows = self.stats.top_destinations(time_range.start, time_range.end, limit)
        return [TopDestination.model_validate(r) for r in rows]

    def top_devices(self, time_range: TimeRange, limit: int) -> list[TopDevice]:
        rows = self.stats.top_devices(time_range.start, time_range.end, limit)
        return [TopDevice.model_validate(r) for r in rows]
