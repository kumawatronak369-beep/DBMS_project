"""Synthetic events for the demo: made-up devices reaching made-up destinations (documentation IP ranges only)."""

import ipaddress
import random
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable


@dataclass(frozen=True)
class SimDevice:
    identifier: str
    ip: str


@dataclass(frozen=True)
class SimDestination:
    ip: str
    domain: str | None
    weight: int


@dataclass(frozen=True)
class Profile:
    name: str
    node_label: str
    prefix: str
    subnet: str
    device_count: int

    def devices(self) -> list[SimDevice]:
        # matches database/seed.sql
        return [
            SimDevice(f"{self.prefix}-{i:03d}", f"{self.subnet}.{20 + i}")
            for i in range(1, self.device_count + 1)
        ]


PROFILES = {
    "lab-a": Profile("lab-a", "Computer Lab A", "PC-LAB-A", "192.168.10", 5),
    "lab-b": Profile("lab-b", "Computer Lab B", "PC-LAB-B", "192.168.20", 5),
    "lib-01": Profile("lib-01", "Library", "PC-LIB", "192.168.30", 4),
    "admin-01": Profile("admin-01", "Administrative Block", "PC-ADMIN", "192.168.40", 3),
}

# fictional destinations (documentation IP ranges)
DESTINATIONS = [
    SimDestination("198.51.100.10", "google.com", 18),
    SimDestination("203.0.113.20", "github.com", 14),
    SimDestination("203.0.113.30", "youtube.com", 12),
    SimDestination("203.0.113.50", "stackoverflow.com", 11),
    SimDestination("203.0.113.10", "example.com", 10),
    SimDestination("203.0.113.40", "wikipedia.org", 9),
    SimDestination("198.51.100.20", "microsoft.com", 7),
    SimDestination("198.51.100.40", "coursera.org", 6),
    SimDestination("198.51.100.30", "reddit.com", 5),
    SimDestination("192.0.2.10", "python.org", 5),
    SimDestination("198.51.100.50", "aws.amazon.com", 4),
    SimDestination("203.0.113.60", "news.example.org", 3),
    SimDestination("192.0.2.20", "docs.python.org", 3),
    SimDestination("192.0.2.77", None, 2),
]

REPEAT_WINDOW = timedelta(seconds=25)

_HOST_LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?$")


@dataclass(frozen=True)
class GeneratedEvent:
    payload: dict
    is_repeat: bool


def validate_event(payload: dict) -> dict:
    allowed = {"deviceIdentifier", "deviceIp", "destinationIp", "domain", "timestamp", "protocol", "sourcePort", "destinationPort"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"unexpected field(s): {', '.join(sorted(unknown))}")
    for name in ("deviceIdentifier", "deviceIp", "destinationIp", "timestamp"):
        if not payload.get(name):
            raise ValueError(f"missing {name}")
    ipaddress.ip_address(payload["deviceIp"])
    ipaddress.ip_address(payload["destinationIp"])
    datetime.fromisoformat(payload["timestamp"])
    protocol = payload.get("protocol")
    if protocol is not None and protocol not in ("TCP", "UDP"):
        raise ValueError("invalid protocol")
    for name in ("sourcePort", "destinationPort"):
        port = payload.get(name)
        if port is None:
            continue
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"invalid {name}")
        if protocol is None:
            raise ValueError("protocol is required when a port is given")
    domain = payload.get("domain")
    if domain is not None and not all(_HOST_LABEL.match(part) for part in domain.split(".")):
        raise ValueError("invalid domain")
    return payload


def build_payload(device: SimDevice, destination: SimDestination, timestamp: datetime) -> dict:
    payload = {
        "deviceIdentifier": device.identifier,
        "deviceIp": device.ip,
        "destinationIp": destination.ip,
        "timestamp": timestamp.replace(microsecond=0).isoformat(),
    }
    if destination.domain:
        payload["domain"] = destination.domain
    return validate_event(payload)


class EventGenerator:
    def __init__(
        self,
        profile: Profile,
        rng: random.Random | None = None,
        clock: Callable[[], datetime] = datetime.now,
        duplicate_rate: float = 0.15,
    ):
        self.profile = profile
        self.devices = profile.devices()
        self.rng = rng or random.Random()
        self.clock = clock
        self.duplicate_rate = duplicate_rate
        self.device_weights = [self.rng.uniform(0.5, 2.0) for _ in self.devices]
        self.destination_weights = [d.weight for d in DESTINATIONS]
        self._recent: deque[tuple[datetime, SimDevice, SimDestination]] = deque(maxlen=50)

    def now(self) -> datetime:
        return self.clock().replace(microsecond=0)

    def build(self, device: SimDevice, destination: SimDestination, timestamp: datetime) -> dict:
        return build_payload(device, destination, timestamp)

    def next_event(self) -> GeneratedEvent:
        now = self.now()
        while self._recent and now - self._recent[0][0] > REPEAT_WINDOW:
            self._recent.popleft()

        if self._recent and self.rng.random() < self.duplicate_rate:
            _, device, destination = self.rng.choice(list(self._recent))
            is_repeat = True
        else:
            device = self.rng.choices(self.devices, weights=self.device_weights)[0]
            destination = self.rng.choices(DESTINATIONS, weights=self.destination_weights)[0]
            is_repeat = False
            self._recent.append((now, device, destination))

        return GeneratedEvent(self.build(device, destination, now), is_repeat)
