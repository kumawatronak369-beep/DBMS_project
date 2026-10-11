from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import CollectorApiKey


class CollectorApiKeyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_by_hash(self, key_hash: str) -> CollectorApiKey | None:
        return self.db.scalar(
            select(CollectorApiKey).where(CollectorApiKey.key_hash == key_hash, CollectorApiKey.status == "ACTIVE")
        )

    def mark_used(self, api_key_id: int, when: datetime) -> None:
        self.db.execute(
            update(CollectorApiKey).where(CollectorApiKey.api_key_id == api_key_id).values(last_used_at=when)
        )
