from datetime import datetime
from ipaddress import ip_address
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AfterValidator, BaseModel, Field

T = TypeVar("T")


def _validate_ip(value: str) -> str:
    try:
        parsed = ip_address(value.strip())
    except ValueError:
        raise ValueError("must be a valid IPv4 or IPv6 address") from None
    return str(parsed)  # canonical form, so 2001:DB8::1 and 2001:db8::1 match


IpAddress = Annotated[str, Field(min_length=2, max_length=45), AfterValidator(_validate_ip)]


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ActivityPoint(BaseModel):
    bucket: datetime
    event_count: int


class ActivitySeries(BaseModel):
    start: datetime
    end: datetime
    bucket: Literal["hour", "day"]
    points: list[ActivityPoint]
