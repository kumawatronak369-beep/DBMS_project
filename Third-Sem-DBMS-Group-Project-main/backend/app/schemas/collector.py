import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import IpAddress

_LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?$")


def _normalize_domain(value: str) -> str | None:
    value = value.strip().lower().rstrip(".")
    if not value:
        return None
    if len(value) > 255 or not all(_LABEL.match(label) for label in value.split(".")):
        raise ValueError("must be a valid host name")
    return value


Domain = Annotated[str, AfterValidator(_normalize_domain)]


class CollectorEventIn(BaseModel):
    """Metadata event submitted by a collector. There is no nodeId: the node comes from the API key."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", str_strip_whitespace=True)

    device_identifier: str = Field(alias="deviceIdentifier", min_length=1, max_length=100)
    device_ip: IpAddress = Field(alias="deviceIp")
    destination_ip: IpAddress = Field(alias="destinationIp")
    domain: Domain | None = None
    timestamp: datetime
    protocol: Literal["TCP", "UDP"] | None = None
    source_port: int | None = Field(default=None, alias="sourcePort", ge=1, le=65535)
    destination_port: int | None = Field(default=None, alias="destinationPort", ge=1, le=65535)

    @field_validator("protocol", mode="before")
    @classmethod
    def _protocol_case(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _ports_need_a_protocol(self):
        if (self.source_port is not None or self.destination_port is not None) and self.protocol is None:
            raise ValueError("protocol is required when a port is given")
        return self

    @field_validator("timestamp")
    @classmethod
    def _normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            value = value.astimezone().replace(tzinfo=None)
        return value.replace(microsecond=0)


class CollectorEventResult(BaseModel):
    status: Literal["STORED", "DUPLICATE"]
    history_id: int | None = None
    duplicate_of: int | None = None
    message: str
