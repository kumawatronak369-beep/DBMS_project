from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Node(Base):
    __tablename__ = "nodes"
    __table_args__ = (
        UniqueConstraint("node_code", name="uq_nodes_node_code"),
        Index("idx_nodes_status", "status"),
        Index("idx_nodes_last_seen", "last_seen"),
    )

    node_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    node_code: Mapped[str] = mapped_column(String(50))
    node_name: Mapped[str] = mapped_column(String(100))
    ip_address: Mapped[str] = mapped_column(String(45))
    location: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "INACTIVE", "OFFLINE", name="node_status"), server_default="ACTIVE"
    )
    registered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
