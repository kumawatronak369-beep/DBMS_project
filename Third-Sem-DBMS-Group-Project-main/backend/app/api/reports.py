from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.query_params import TimeRange, get_time_range
from app.schemas.common import ActivitySeries
from app.schemas.report import NodeActivity, TopDestination, TopDevice
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(get_current_user)])


def get_service(db: Session = Depends(get_db)) -> ReportService:
    return ReportService(db)


@router.get("/top-destinations", response_model=list[TopDestination])
def top_destinations(
    limit: int = Query(10, ge=1, le=100),
    time_range: TimeRange = Depends(get_time_range),
    service: ReportService = Depends(get_service),
):
    return service.top_destinations(time_range, limit)


@router.get("/top-devices", response_model=list[TopDevice])
def top_devices(
    limit: int = Query(10, ge=1, le=100),
    time_range: TimeRange = Depends(get_time_range),
    service: ReportService = Depends(get_service),
):
    return service.top_devices(time_range, limit)


@router.get("/activity-by-node", response_model=list[NodeActivity])
def activity_by_node(time_range: TimeRange = Depends(get_time_range), service: ReportService = Depends(get_service)):
    return service.activity_by_node(time_range)


@router.get("/activity-over-time", response_model=ActivitySeries)
def activity_over_time(
    node_id: int | None = Query(None, ge=1, alias="nodeId"),
    time_range: TimeRange = Depends(get_time_range),
    service: ReportService = Depends(get_service),
):
    """Last 24 hours by default; use range=24h|7d|30d or startDate/endDate for a custom range."""
    return service.activity_over_time(time_range, node_id)
