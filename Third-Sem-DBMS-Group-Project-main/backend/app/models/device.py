from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        # target of the composite FK from network_history
        UniqueConstraint("node_id", "device_id", name="uq_devices_node_device"),
        UniqueConstraint("node_id", "device_identifier", name="uq_devices_node_identifier"),
        Index("idx_devices_ip", "ip_address"),
        Index("idx_devices_status", "status"),
        Index("idx_devices_last_seen", "last_seen"),
    )

    device_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    node_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("nodes.node_id", name="fk_devices_node", onupdate="CASCADE", ondelete="RESTRICT"),
    )
    device_identifier: Mapped[str] = mapped_column(String(100))
    device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45))
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("ACTIVE", "INACTIVE", "UNKNOWN", name="device_status"), server_default="UNKNOWN"
    )
    first_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    last_seen: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
