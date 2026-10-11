from pydantic import BaseModel


class DashboardSummary(BaseModel):
    active_nodes: int
    registered_devices: int
    todays_events: int
    known_destinations: int
