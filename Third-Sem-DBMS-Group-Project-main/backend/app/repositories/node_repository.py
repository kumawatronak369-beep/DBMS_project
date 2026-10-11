from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Device, NetworkHistory, Node
from app.repositories.filters import contains


class NodeRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, *, search: str | None, status: str | None, limit: int, offset: int) -> tuple[list[dict], int]:
        conditions = []
        if search:
            conditions.append(
                or_(
                    contains(Node.node_code, search),
                    contains(Node.node_name, search),
                    contains(Node.location, search),
                    contains(Node.ip_address, search),
                )
            )
        if status:
            conditions.append(Node.status == status)

        device_count = (
            select(func.count(Device.device_id)).where(Device.node_id == Node.node_id).correlate(Node).scalar_subquery()
        )
        rows = (
            self.db.execute(
                select(*Node.__table__.c, device_count.label("device_count"))
                .where(*conditions)
                .order_by(Node.node_name, Node.node_id)
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        total = self.db.scalar(select(func.count()).select_from(Node).where(*conditions)) or 0
        return [dict(r) for r in rows], total

    def get(self, node_id: int) -> Node | None:
        return self.db.get(Node, node_id)

    def get_by_code(self, node_code: str) -> Node | None:
        return self.db.scalar(select(Node).where(Node.node_code == node_code))

    def add(self, node: Node) -> Node:
        self.db.add(node)
        self.db.flush()
        return node

    def device_count(self, node_id: int) -> int:
        return self.db.scalar(select(func.count(Device.device_id)).where(Device.node_id == node_id)) or 0

    def event_count(self, node_id: int) -> int:
        return self.db.scalar(select(func.count(NetworkHistory.history_id)).where(NetworkHistory.node_id == node_id)) or 0

    def lock(self, node: Node) -> None:
        self.db.refresh(node, with_for_update=True)
