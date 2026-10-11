from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.security import hash_api_key
from app.exceptions.handlers import ApiKeyUnauthorizedError
from app.repositories.collector_api_key_repository import CollectorApiKeyRepository

MAX_API_KEY_LENGTH = 256


@dataclass(frozen=True)
class CollectorPrincipal:
    api_key_id: int
    node_id: int


class CollectorAuthService:
    def __init__(self, db: Session):
        self.keys = CollectorApiKeyRepository(db)

    def authenticate(self, raw_key: str | None) -> CollectorPrincipal:
        if not raw_key or len(raw_key) > MAX_API_KEY_LENGTH:
            raise ApiKeyUnauthorizedError("Invalid or missing API key")
        key = self.keys.get_active_by_hash(hash_api_key(raw_key.strip()))
        if key is None:
            raise ApiKeyUnauthorizedError("Invalid or missing API key")
        return CollectorPrincipal(api_key_id=key.api_key_id, node_id=key.node_id)
