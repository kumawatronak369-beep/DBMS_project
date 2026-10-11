from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CollectorApiKey(Base):
    __tablename__ = "collector_api_keys"
    __table_args__ = (
        UniqueConstraint("key_hash", name="uq_collector_api_key_hash"),
        Index("idx_collector_api_keys_node_status", "node_id", "status"),
    )

    api_key_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    node_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("nodes.node_id", name="fk_collector_api_keys_node", onupdate="CASCADE", ondelete="RESTRICT"),
    )
    key_name: Mapped[str] = mapped_column(String(100))
    key_hash: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(Enum("ACTIVE", "REVOKED", name="api_key_status"), server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.current_timestamp())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
