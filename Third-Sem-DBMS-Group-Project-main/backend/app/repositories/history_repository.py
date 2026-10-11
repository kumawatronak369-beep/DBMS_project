from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Destination, Device, NetworkHistory, Node
from app.repositories.filters import contains

_COLUMNS = (
    NetworkHistory.history_id,
    NetworkHistory.observed_at,
    Device.device_id,
    Device.device_identifier,
    Device.device_name,
    Device.ip_address.label("device_ip"),
    Node.node_id,
    Node.node_code,
    Node.node_name,
    Destination.destination_id,
    Destination.ip_address.label("destination_ip"),
    Destination.domain,
    Destination.category,
    NetworkHistory.protocol,
    NetworkHistory.source_port,
    NetworkHistory.destination_port,
)


@dataclass(frozen=True)
class HistoryFilters:
    q: str | None = None
    device: str | None = None
    device_id: int | None = None
    node_id: int | None = None
    destination_id: int | None = None
    domain: str | None = None
    start: datetime | None = None
    end: datetime | None = None


def _joined(stmt):
    return (
        stmt.select_from(NetworkHistory)
        .join(Device, Device.device_id == NetworkHistory.device_id)
        .join(Node, Node.node_id == NetworkHistory.node_id)
        .join(Destination, Destination.destination_id == NetworkHistory.destination_id)
    )


def _conditions(f: HistoryFilters) -> list:
    conditions = []
    if f.device_id is not None:
        conditions.append(NetworkHistory.device_id == f.device_id)
    if f.node_id is not None:
        conditions.append(NetworkHistory.node_id == f.node_id)
    if f.destination_id is not None:
        conditions.append(NetworkHistory.destination_id == f.destination_id)
    if f.device:
        conditions.append(
            or_(
                contains(Device.device_identifier, f.device),
                contains(Device.device_name, f.device),
                contains(Device.ip_address, f.device),
            )
        )
    if f.domain:
        conditions.append(contains(Destination.domain, f.domain))
    if f.q:
        conditions.append(
            or_(
                contains(Device.device_identifier, f.q),
                contains(Device.ip_address, f.q),
                contains(Destination.domain, f.q),
                contains(Destination.ip_address, f.q),
            )
        )
    if f.start is not None:
        conditions.append(NetworkHistory.observed_at >= f.start)
    if f.end is not None:
        conditions.append(NetworkHistory.observed_at <= f.end)
    return conditions


class HistoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, filters: HistoryFilters, *, limit: int, offset: int) -> tuple[list[dict], int]:
        conditions = _conditions(filters)
        rows = (
            self.db.execute(
                _joined(select(*_COLUMNS))
                .where(*conditions)
                .order_by(NetworkHistory.observed_at.desc(), NetworkHistory.history_id.desc())
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        total = self.db.scalar(_joined(select(func.count(NetworkHistory.history_id))).where(*conditions)) or 0
        return [dict(r) for r in rows], total

    def get(self, history_id: int) -> dict | None:
        row = (
            self.db.execute(_joined(select(*_COLUMNS)).where(NetworkHistory.history_id == history_id))
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def activity_counts(
        self,
        start: datetime,
        end: datetime,
        bucket: Literal["hour", "day"],
        *,
        node_id: int | None = None,
        device_id: int | None = None,
    ) -> dict[str, int]:
        pattern = "%Y-%m-%d %H:00:00" if bucket == "hour" else "%Y-%m-%d 00:00:00"
        bucket_col = func.date_format(NetworkHistory.observed_at, pattern).label("bucket")
        stmt = (
            select(bucket_col, func.count(NetworkHistory.history_id).label("event_count"))
            .where(NetworkHistory.observed_at >= start, NetworkHistory.observed_at <= end)
            .group_by(bucket_col)
            .order_by(bucket_col)
        )
        if node_id is not None:
            stmt = stmt.where(NetworkHistory.node_id == node_id)
        if device_id is not None:
            stmt = stmt.where(NetworkHistory.device_id == device_id)
        return {row.bucket: row.event_count for row in self.db.execute(stmt)}

    def find_duplicate(
        self, device_id: int, destination_id: int, window_start: datetime, window_end: datetime
    ) -> tuple[int, datetime] | None:
        """The stored event for this device + destination inside the window, if any."""
        row = self.db.execute(
            select(NetworkHistory.history_id, NetworkHistory.observed_at)
            .where(
                NetworkHistory.device_id == device_id,
                NetworkHistory.destination_id == destination_id,
                NetworkHistory.observed_at >= window_start,
                NetworkHistory.observed_at <= window_end,
            )
            .order_by(NetworkHistory.observed_at.desc())
            .limit(1)
            .with_for_update()
        ).first()
        return (row.history_id, row.observed_at) if row else None

    def add(self, event: NetworkHistory) -> NetworkHistory:
        self.db.add(event)
        self.db.flush()
        return event
