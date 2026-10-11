from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.query_params import TimeRange
from app.repositories.history_repository import HistoryRepository
from app.schemas.common import ActivityPoint, ActivitySeries

_HOURLY_MAX_SPAN = timedelta(days=2)
_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def resolve_window(time_range: TimeRange, default_span: timedelta) -> tuple[datetime, datetime]:
    end = time_range.end or datetime.now()
    start = time_range.start or (end - default_span)
    return start, end


class ActivityService:
    def __init__(self, db: Session):
        self.history = HistoryRepository(db)

    def series(
        self, start: datetime, end: datetime, *, node_id: int | None = None, device_id: int | None = None
    ) -> ActivitySeries:
        bucket = "hour" if (end - start) <= _HOURLY_MAX_SPAN else "day"
        counts = self.history.activity_counts(start, end, bucket, node_id=node_id, device_id=device_id)
        by_time = {datetime.strptime(key, _TIMESTAMP_FORMAT): value for key, value in counts.items()}

        if bucket == "hour":
            step = timedelta(hours=1)
            cursor = start.replace(minute=0, second=0, microsecond=0)
        else:
            step = timedelta(days=1)
            cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)

        points: list[ActivityPoint] = []
        while cursor <= end:
            points.append(ActivityPoint(bucket=cursor, event_count=by_time.get(cursor, 0)))
            cursor += step
        return ActivitySeries(start=start, end=end, bucket=bucket, points=points)

    def last_days(self, days: int, *, node_id: int | None = None, device_id: int | None = None) -> list[ActivityPoint]:
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days - 1)
        return self.series(start, now, node_id=node_id, device_id=device_id).points
