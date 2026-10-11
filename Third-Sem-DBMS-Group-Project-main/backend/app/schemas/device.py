from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import ActivityPoint
from app.schemas.destination import DestinationCategory

DeviceStatus = Literal["ACTIVE", "INACTIVE", "UNKNOWN"]


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: int
    node_id: int
    device_identifier: str
    device_name: str | None = None
    ip_address: str
    mac_address: str | None = None
    hostname: str | None = None
    status: DeviceStatus
    first_seen: datetime
    last_seen: datetime


class DeviceListItem(DeviceOut):
    node_code: str
    node_name: str


class RecentDestination(BaseModel):
    destination_id: int
    domain: str | None = None
    ip_address: str
    category: DestinationCategory
    visits: int
    last_visit: datetime


class DeviceDetail(DeviceListItem):
    total_events: int
    activity_by_day: list[ActivityPoint]
    recent_destinations: list[RecentDestination]
