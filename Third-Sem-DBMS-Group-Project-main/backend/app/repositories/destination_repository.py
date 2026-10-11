from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Destination, Device, NetworkHistory, Node
from app.repositories.filters import contains


def _event_count():
    return (
        select(func.count(NetworkHistory.history_id))
        .where(NetworkHistory.destination_id == Destination.destination_id)
        .correlate(Destination)
        .scalar_subquery()
        .label("event_count")
    )


def _unique_devices():
    return (
        select(func.count(func.distinct(NetworkHistory.device_id)))
        .where(NetworkHistory.destination_id == Destination.destination_id)
        .correlate(Destination)
        .scalar_subquery()
        .label("unique_devices")
    )


_BASE_COLUMNS = (
    Destination.destination_id,
    Destination.ip_address,
    Destination.domain,
    Destination.category,
    Destination.first_seen,
    Destination.last_seen,
)


class DestinationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, *, search: str | None, category: str | None, limit: int, offset: int) -> tuple[list[dict], int]:
        conditions = []
        if search:
            conditions.append(or_(contains(Destination.domain, search), contains(Destination.ip_address, search)))
        if category:
            conditions.append(Destination.category == category)

        rows = (
            self.db.execute(
                select(*_BASE_COLUMNS, _event_count(), _unique_devices())
                .where(*conditions)
                .order_by(Destination.last_seen.desc(), Destination.destination_id)
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        total = self.db.scalar(select(func.count()).select_from(Destination).where(*conditions)) or 0
        return [dict(r) for r in rows], total

    def get(self, destination_id: int) -> dict | None:
        row = (
            self.db.execute(
                select(*_BASE_COLUMNS, _event_count(), _unique_devices()).where(
                    Destination.destination_id == destination_id
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def exists(self, destination_id: int) -> bool:
        return (
            self.db.scalar(select(Destination.destination_id).where(Destination.destination_id == destination_id))
            is not None
        )

    def nodes(self, destination_id: int) -> list[dict]:
        event_count = func.count(NetworkHistory.history_id)
        rows = (
            self.db.execute(
                select(Node.node_id, Node.node_code, Node.node_name, event_count.label("event_count"))
                .join(NetworkHistory, NetworkHistory.node_id == Node.node_id)
                .where(NetworkHistory.destination_id == destination_id)
                .group_by(Node.node_id)
                .order_by(event_count.desc(), Node.node_id)
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def devices(self, destination_id: int, limit: int) -> list[dict]:
        access_count = func.count(NetworkHistory.history_id)
        rows = (
            self.db.execute(
                select(
                    Device.device_id,
                    Device.device_identifier,
                    Device.ip_address,
                    Node.node_name,
                    access_count.label("access_count"),
                    func.max(NetworkHistory.observed_at).label("last_access"),
                )
                .join(NetworkHistory, NetworkHistory.device_id == Device.device_id)
                .join(Node, Node.node_id == Device.node_id)
                .where(NetworkHistory.destination_id == destination_id)
                .group_by(Device.device_id, Node.node_name)
                .order_by(access_count.desc(), Device.device_id)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def find_by_ip_and_domain(self, ip_address: str, domain: str | None, *, lock: bool = False) -> Destination | None:
        stmt = select(Destination).where(
            Destination.ip_address == ip_address,
            Destination.domain_key == (domain or ""),
        )
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(stmt)

    def add(self, destination: Destination) -> Destination:
        self.db.add(destination)
        self.db.flush()
        return destination

    def lock(self, destination: Destination) -> None:
        self.db.refresh(destination, with_for_update=True)
