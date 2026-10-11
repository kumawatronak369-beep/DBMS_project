from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, func
from sqlalchemy.dialects.mysql import BIGINT, SMALLINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NetworkHistory(Base):
    """One observed event. The 30-second rule lives in the service layer, not in a UNIQUE constraint."""

    __tablename__ = "network_history"
    __table_args__ = (
        # a device must belong to the node on the event
        ForeignKeyConstraint(
            ["node_id", "device_id"],
            ["devices.node_id", "devices.device_id"],
            name="fk_history_device_node",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        Index("idx_history_device_time", "device_id", "observed_at"),
        Index("idx_history_node_time", "node_id", "observed_at"),
        Index("idx_history_destination_time", "destination_id", "observed_at"),
        Index("idx_history_time", "observed_at"),
    )

    history_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("devices.device_id", name="fk_history_device", onupdate="CASCADE", ondelete="RESTRICT"),
    )
    node_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("nodes.node_id", name="fk_history_node", onupdate="CASCADE", ondelete="RESTRICT"),
    )
    destination_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "destinations.destination_id", name="fk_history_destination", onupdate="CASCADE", ondelete="RESTRICT"
        ),
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    protocol: Mapped[str | None] = mapped_column(Enum("TCP", "UDP", name="history_protocol"), nullable=True)
    source_port: Mapped[int | None] = mapped_column(SMALLINT(unsigned=True), nullable=True)
    destination_port: Mapped[int | None] = mapped_column(SMALLINT(unsigned=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
