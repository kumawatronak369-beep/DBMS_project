from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Destination, Device, NetworkHistory, Node
from app.repositories.filters import contains

_COLUMNS = (*Device.__table__.c, Node.node_code, Node.node_name)


class DeviceRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(
        self, *, search: str | None, node_id: int | None, status: str | None, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        conditions = []
        if search:
            conditions.append(
                or_(
                    contains(Device.device_identifier, search),
                    contains(Device.device_name, search),
                    contains(Device.ip_address, search),
                    contains(Device.hostname, search),
                )
            )
        if node_id is not None:
            conditions.append(Device.node_id == node_id)
        if status:
            conditions.append(Device.status == status)

        rows = (
            self.db.execute(
                select(*_COLUMNS)
                .join(Node, Node.node_id == Device.node_id)
                .where(*conditions)
                .order_by(Device.last_seen.desc(), Device.device_id)
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        total = self.db.scalar(select(func.count()).select_from(Device).where(*conditions)) or 0
        return [dict(r) for r in rows], total

    def get(self, device_id: int) -> dict | None:
        row = (
            self.db.execute(
                select(*_COLUMNS).join(Node, Node.node_id == Device.node_id).where(Device.device_id == device_id)
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def exists(self, device_id: int) -> bool:
        return self.db.scalar(select(Device.device_id).where(Device.device_id == device_id)) is not None

    def total_events(self, device_id: int) -> int:
        return self.db.scalar(select(func.count(NetworkHistory.history_id)).where(NetworkHistory.device_id == device_id)) or 0

    def recent_destinations(self, device_id: int, limit: int) -> list[dict]:
        last_visit = func.max(NetworkHistory.observed_at)
        rows = (
            self.db.execute(
                select(
                    Destination.destination_id,
                    Destination.domain,
                    Destination.ip_address,
                    Destination.category,
                    func.count(NetworkHistory.history_id).label("visits"),
                    last_visit.label("last_visit"),
                )
                .join(NetworkHistory, NetworkHistory.destination_id == Destination.destination_id)
                .where(NetworkHistory.device_id == device_id)
                .group_by(Destination.destination_id)
                .order_by(last_visit.desc(), Destination.destination_id)
                .limit(limit)
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def find_by_identifier(self, node_id: int, device_identifier: str, *, lock: bool = False) -> Device | None:
        """Look a device up by node + device_identifier (never by IP)."""
        stmt = select(Device).where(Device.node_id == node_id, Device.device_identifier == device_identifier)
        if lock:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(stmt)

    def add(self, device: Device) -> Device:
        self.db.add(device)
        self.db.flush()
        return device

    def lock(self, device: Device) -> None:
        self.db.refresh(device, with_for_update=True)
