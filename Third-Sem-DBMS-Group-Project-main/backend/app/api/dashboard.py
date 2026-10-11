from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.core.query_params import TimeRange, get_time_range
from app.schemas.common import ActivitySeries
from app.schemas.dashboard import DashboardSummary
from app.schemas.report import TopDestination, TopDevice
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


def get_service(db: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(db)


@router.get("/summary", response_model=DashboardSummary)
def summary(service: DashboardService = Depends(get_service)):
    return service.summary()


@router.get("/activity", response_model=ActivitySeries)
def activity(time_range: TimeRange = Depends(get_time_range), service: DashboardService = Depends(get_service)):
    """Event volume over time. Defaults to the last 24 hours."""
    return service.activity_series(time_range)


@router.get("/top-destinations", response_model=list[TopDestination])
def top_destinations(
    limit: int = Query(5, ge=1, le=50),
    time_range: TimeRange = Depends(get_time_range),
    service: DashboardService = Depends(get_service),
):
    return service.top_destinations(time_range, limit)


@router.get("/top-devices", response_model=list[TopDevice])
def top_devices(
    limit: int = Query(5, ge=1, le=50),
    time_range: TimeRange = Depends(get_time_range),
    service: DashboardService = Depends(get_service),
):
    return service.top_devices(time_range, limit)
