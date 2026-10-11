from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Destination, Device, NetworkHistory, Node


def _time_conditions(start: datetime | None, end: datetime | None) -> list:
    conditions = []
    if start is not None:
        conditions.append(NetworkHistory.observed_at >= start)
    if end is not None:
        conditions.append(NetworkHistory.observed_at <= end)
    return conditions


class StatsRepository:
    def __init__(self, db: Session):
        self.db = db

    def summary(self, day_start: datetime) -> dict:
        row = (
            self.db.execute(
                select(
                    select(func.count()).select_from(Node).where(Node.status == "ACTIVE").scalar_subquery().label("active_nodes"),
                    select(func.count()).select_from(Device).scalar_subquery().label("registered_devices"),
                    select(func.count())
                    .select_from(NetworkHistory)
                    .where(NetworkHistory.observed_at >= day_start)
                    .scalar_subquery()
                    .label("todays_events"),
                    select(func.count()).select_from(Destination).scalar_subquery().label("known_destinations"),
                )
            )
            .mappings()
            .one()
        )
        return dict(row)

    def top_destinations(self, start: datetime | None, end: datetime | None, limit: int) -> list[dict]:
        event_count = func.count(NetworkHistory.history_id)
        rows = (
            self.db.execute(
                select(
                    Destination.destination_id,
                    Destination.domain,
                    Destination.ip_address,
                    Destination.category,
                    event_count.label("event_count"),
                    func.count(func.distinct(NetworkHistory.device_id)).label("unique_devices"),
                )
                .join(NetworkHistory, NetworkHistory.destination_id == Destination.destination_id)
                .where(*_time_conditions(start, end))
                .group_by(Destination.destination_id)
                .order_by(event_count.desc(), Destination.destination_id)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def top_devices(self, start: datetime | None, end: datetime | None, limit: int) -> list[dict]:
        event_count = func.count(NetworkHistory.history_id)
        rows = (
            self.db.execute(
                select(
                    Device.device_id,
                    Device.device_identifier,
                    Device.ip_address,
                    Node.node_id,
                    Node.node_name,
                    event_count.label("event_count"),
                )
                .join(NetworkHistory, NetworkHistory.device_id == Device.device_id)
                .join(Node, Node.node_id == Device.node_id)
                .where(*_time_conditions(start, end))
                .group_by(Device.device_id, Node.node_id, Node.node_name)
                .order_by(event_count.desc(), Device.device_id)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def node_activity(self, start: datetime | None, end: datetime | None) -> list[dict]:
        event_count = func.count(NetworkHistory.history_id)
        rows = (
            self.db.execute(
                select(
                    Node.node_id,
                    Node.node_code,
                    Node.node_name,
                    event_count.label("event_count"),
                    func.count(func.distinct(NetworkHistory.device_id)).label("unique_devices"),
                )
                .outerjoin(
                    NetworkHistory,
                    and_(NetworkHistory.node_id == Node.node_id, *_time_conditions(start, end)),
                )
                .group_by(Node.node_id)
                .order_by(event_count.desc(), Node.node_name)
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]
