from pydantic import BaseModel

from app.schemas.destination import DestinationCategory


class TopDestination(BaseModel):
    destination_id: int
    domain: str | None = None
    ip_address: str
    category: DestinationCategory
    event_count: int
    unique_devices: int


class TopDevice(BaseModel):
    device_id: int
    device_identifier: str
    ip_address: str
    node_id: int
    node_name: str
    event_count: int


class NodeActivity(BaseModel):
    node_id: int
    node_code: str
    node_name: str
    event_count: int
    unique_devices: int
