from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.destination import DestinationCategory


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    history_id: int
    observed_at: datetime
    device_id: int
    device_identifier: str
    device_name: str | None = None
    device_ip: str
    node_id: int
    node_code: str
    node_name: str
    destination_id: int
    destination_ip: str
    domain: str | None = None
    category: DestinationCategory
    protocol: Literal["TCP", "UDP"] | None = None
    source_port: int | None = None
    destination_port: int | None = None
