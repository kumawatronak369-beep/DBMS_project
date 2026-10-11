from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import Query

from app.exceptions.handlers import AppError

RANGE_PRESETS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


@dataclass(frozen=True)
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def get_pagination(
    page: int = Query(1, ge=1, le=1_000_000),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
) -> Pagination:
    return Pagination(page=page, page_size=page_size)


@dataclass(frozen=True)
class TimeRange:
    start: datetime | None = None
    end: datetime | None = None


def _parse_bound(value: str, name: str, *, is_end: bool) -> datetime:
    try:
        if len(value) == 10:  # date only: an end date includes the whole day
            day = date.fromisoformat(value)
            return datetime.combine(day, time(23, 59, 59) if is_end else time.min)
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise AppError(f"Invalid {name}: use an ISO date or datetime, e.g. 2026-09-19 or 2026-09-19T20:15:32") from None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def get_time_range(
    range_: Literal["24h", "7d", "30d"] | None = Query(None, alias="range"),
    start_date: str | None = Query(None, alias="startDate", max_length=40),
    end_date: str | None = Query(None, alias="endDate", max_length=40),
) -> TimeRange:
    if start_date is not None or end_date is not None:
        start = _parse_bound(start_date, "startDate", is_end=False) if start_date else None
        end = _parse_bound(end_date, "endDate", is_end=True) if end_date else None
        if start and end and start > end:
            raise AppError("startDate must not be after endDate")
        return TimeRange(start, end)

    if range_ is not None:
        end = datetime.now()
        return TimeRange(end - RANGE_PRESETS[range_], end)

    return TimeRange()
