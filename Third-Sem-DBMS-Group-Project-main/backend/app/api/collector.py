from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_collector_principal, get_db
from app.schemas.collector import CollectorEventIn, CollectorEventResult
from app.services.collector_auth_service import CollectorPrincipal
from app.services.collector_service import CollectorService

router = APIRouter(prefix="/collector", tags=["collector"])


@router.post(
    "/events",
    response_model=CollectorEventResult,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "Duplicate within 30 seconds; not stored", "model": CollectorEventResult}},
)
def submit_event(
    event: CollectorEventIn,
    response: Response,
    principal: CollectorPrincipal = Depends(get_collector_principal),
    db: Session = Depends(get_db),
):
    """Submit one network-metadata event. The node comes from the API key.

    Returns 201 when stored, or 200 with status DUPLICATE for a repeat within 30 seconds.
    """
    result = CollectorService(db).ingest(principal, event)
    if result.status == "DUPLICATE":
        response.status_code = status.HTTP_200_OK
    return result
