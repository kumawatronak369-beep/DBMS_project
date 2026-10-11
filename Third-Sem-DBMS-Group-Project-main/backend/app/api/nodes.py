from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db, require_admin
from app.core.query_params import Pagination, get_pagination
from app.schemas.common import Paginated
from app.schemas.node import NodeCreate, NodeDetail, NodeListItem, NodeOut, NodeStatus, NodeStatusUpdate, NodeUpdate
from app.services.node_service import NodeService

# anyone signed in can read; creating, editing and disabling is admin only
router = APIRouter(prefix="/nodes", tags=["nodes"], dependencies=[Depends(get_current_user)])


def get_service(db: Session = Depends(get_db)) -> NodeService:
    return NodeService(db)


@router.get("", response_model=Paginated[NodeListItem])
def list_nodes(
    search: str | None = Query(None, max_length=100),
    status_filter: NodeStatus | None = Query(None, alias="status"),
    pagination: Pagination = Depends(get_pagination),
    service: NodeService = Depends(get_service),
):
    return service.list_nodes(search, status_filter, pagination)


@router.get("/{node_id}", response_model=NodeDetail)
def get_node(node_id: int = Path(ge=1), service: NodeService = Depends(get_service)):
    return service.get_node(node_id)


@router.post("", response_model=NodeOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def create_node(data: NodeCreate, service: NodeService = Depends(get_service)):
    return service.create_node(data)


@router.put("/{node_id}", response_model=NodeOut, dependencies=[Depends(require_admin)])
def update_node(data: NodeUpdate, node_id: int = Path(ge=1), service: NodeService = Depends(get_service)):
    return service.update_node(node_id, data)


@router.patch("/{node_id}/status", response_model=NodeOut, dependencies=[Depends(require_admin)])
def update_node_status(
    data: NodeStatusUpdate, node_id: int = Path(ge=1), service: NodeService = Depends(get_service)
):
    return service.update_status(node_id, data.status)
