from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_db
from app.schemas.health import DatabaseHealthResponse, HealthResponse
from app.services.health_service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", app=get_settings().app_name)


@router.get("/db", response_model=DatabaseHealthResponse, dependencies=[Depends(get_current_user)])
def database_health(response: Response, db: Session = Depends(get_db)) -> DatabaseHealthResponse:
    result = HealthService(db).check_database()
    if result.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
