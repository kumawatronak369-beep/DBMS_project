from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ActivityPoint, IpAddress
from app.schemas.history import HistoryOut

NodeStatus = Literal["ACTIVE", "INACTIVE", "OFFLINE"]


class NodeBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    node_code: str = Field(min_length=1, max_length=50)
    node_name: str = Field(min_length=1, max_length=100)
    ip_address: IpAddress
    location: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("description")
    @classmethod
    def _blank_description_is_null(cls, value: str | None) -> str | None:
        return value or None


class NodeCreate(NodeBase):
    pass


class NodeUpdate(NodeBase):
    pass


class NodeStatusUpdate(BaseModel):
    status: NodeStatus


class NodeOut(NodeBase):
    model_config = ConfigDict(from_attributes=True)

    node_id: int
    status: NodeStatus
    registered_at: datetime
    last_seen: datetime | None = None


class NodeListItem(NodeOut):
    device_count: int


class NodeDetail(NodeListItem):
    event_count: int
    recent_activity: list[HistoryOut]
    activity_by_day: list[ActivityPoint]
