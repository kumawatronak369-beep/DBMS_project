from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

DestinationCategory = Literal[
    "SEARCH", "SOCIAL", "DEVELOPMENT", "EDUCATION", "VIDEO", "CLOUD", "OTHER", "UNKNOWN"
]


class DestinationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    destination_id: int
    ip_address: str
    domain: str | None = None
    category: DestinationCategory
    first_seen: datetime
    last_seen: datetime


class DestinationListItem(DestinationOut):
    event_count: int
    unique_devices: int


class DestinationNode(BaseModel):
    node_id: int
    node_code: str
    node_name: str
    event_count: int


class DestinationDevice(BaseModel):
    device_id: int
    device_identifier: str
    ip_address: str
    node_name: str
    access_count: int
    last_access: datetime


class DestinationDetail(DestinationListItem):
    nodes: list[DestinationNode]
    devices: list[DestinationDevice]
