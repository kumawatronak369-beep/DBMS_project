from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.exceptions.handlers import ForbiddenError, ServiceUnavailableError, UnprocessableError
from app.models import Destination, Device, NetworkHistory, Node
from app.repositories.collector_api_key_repository import CollectorApiKeyRepository
from app.repositories.destination_repository import DestinationRepository
from app.repositories.device_repository import DeviceRepository
from app.repositories.history_repository import HistoryRepository
from app.repositories.node_repository import NodeRepository
from app.schemas.collector import CollectorEventIn, CollectorEventResult
from app.services.collector_auth_service import CollectorPrincipal

# same device + same destination inside this window is a duplicate
DEDUP_WINDOW = timedelta(seconds=30)
# allowed collector clock skew
MAX_FUTURE_SKEW = timedelta(minutes=5)


class CollectorService:
    """Ingests one collector event in a single transaction.

    Locks are always taken in the same order (node, device, destination) so concurrent events can't deadlock.
    """

    def __init__(self, db: Session):
        self.db = db
        self.api_keys = CollectorApiKeyRepository(db)
        self.nodes = NodeRepository(db)
        self.devices = DeviceRepository(db)
        self.destinations = DestinationRepository(db)
        self.history = HistoryRepository(db)

    def ingest(self, principal: CollectorPrincipal, event: CollectorEventIn) -> CollectorEventResult:
        if event.timestamp > datetime.now() + MAX_FUTURE_SKEW:
            raise UnprocessableError("timestamp is too far in the future")
        try:
            result = self._ingest(principal, event)
            self.db.commit()
            return result
        except OperationalError:
            # lock wait or deadlock: nothing was stored, safe to resend
            self.db.rollback()
            raise ServiceUnavailableError("Temporarily unable to store the event, please retry") from None
        except Exception:
            self.db.rollback()
            raise

    def _ingest(self, principal: CollectorPrincipal, event: CollectorEventIn) -> CollectorEventResult:
        observed_at = event.timestamp

        # the node comes only from the API key
        node = self.nodes.get(principal.node_id)
        if node is None:
            raise ForbiddenError("Unknown node")
        self.nodes.lock(node)
        if node.status == "INACTIVE":
            raise ForbiddenError("This node is disabled")

        self.api_keys.mark_used(principal.api_key_id, datetime.now())

        device = self._resolve_device(node, event)
        destination = self._resolve_destination(event)

        duplicate = self.history.find_duplicate(
            device.device_id,
            destination.destination_id,
            observed_at - DEDUP_WINDOW,
            observed_at + DEDUP_WINDOW,
        )
        if duplicate is not None:
            return CollectorEventResult(
                status="DUPLICATE",
                duplicate_of=duplicate[0],
                message="Same device and destination already recorded within 30 seconds; event not stored",
            )

        self._touch_device(device, event)
        self._touch_destination(destination, observed_at)
        if node.last_seen is None or observed_at > node.last_seen:
            node.last_seen = observed_at

        record = self.history.add(
            NetworkHistory(
                device_id=device.device_id,
                node_id=node.node_id,
                destination_id=destination.destination_id,
                observed_at=observed_at,
                protocol=event.protocol,
                source_port=event.source_port,
                destination_port=event.destination_port,
            )
        )
        return CollectorEventResult(status="STORED", history_id=record.history_id, message="Event stored")

    def _resolve_device(self, node: Node, event: CollectorEventIn) -> Device:
        """Find the device by node + identifier, creating it if unknown."""
        device = self.devices.find_by_identifier(node.node_id, event.device_identifier)
        if device is not None:
            self.devices.lock(device)
            return device

        try:
            with self.db.begin_nested():  # savepoint, so a lost race doesn't poison the transaction
                return self.devices.add(
                    Device(
                        node_id=node.node_id,
                        device_identifier=event.device_identifier,
                        ip_address=event.device_ip,
                        status="ACTIVE",
                        first_seen=event.timestamp,
                        last_seen=event.timestamp,
                    )
                )
        except IntegrityError:
            # another transaction created it first, use theirs
            device = self.devices.find_by_identifier(node.node_id, event.device_identifier, lock=True)
            if device is None:
                raise
            return device

    def _touch_device(self, device: Device, event: CollectorEventIn) -> None:
        if event.timestamp < device.first_seen:
            device.first_seen = event.timestamp
        if event.timestamp >= device.last_seen:
            device.last_seen = event.timestamp
            device.ip_address = event.device_ip

    def _resolve_destination(self, event: CollectorEventIn) -> Destination:
        destination = self.destinations.find_by_ip_and_domain(event.destination_ip, event.domain)
        if destination is not None:
            self.destinations.lock(destination)
            return destination

        try:
            with self.db.begin_nested():
                return self.destinations.add(
                    Destination(
                        ip_address=event.destination_ip,
                        domain=event.domain,
                        category="UNKNOWN",
                        first_seen=event.timestamp,
                        last_seen=event.timestamp,
                    )
                )
        except IntegrityError:
            destination = self.destinations.find_by_ip_and_domain(event.destination_ip, event.domain, lock=True)
            if destination is None:
                raise
            return destination

    @staticmethod
    def _touch_destination(destination: Destination, observed_at: datetime) -> None:
        if observed_at < destination.first_seen:
            destination.first_seen = observed_at
        if observed_at > destination.last_seen:
            destination.last_seen = observed_at
