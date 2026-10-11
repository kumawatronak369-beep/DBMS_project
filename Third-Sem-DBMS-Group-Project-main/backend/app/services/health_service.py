from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.health_repository import HealthRepository
from app.schemas.health import DatabaseHealthResponse

EXPECTED_TABLES = {
    "users",
    "nodes",
    "devices",
    "destinations",
    "collector_api_keys",
    "network_history",
}


class HealthService:
    def __init__(self, db: Session):
        self.repository = HealthRepository(db)

    def check_database(self) -> DatabaseHealthResponse:
        try:
            self.repository.ping()
            tables = self.repository.list_tables()
        except SQLAlchemyError:
            return DatabaseHealthResponse(status="error", database="unreachable")

        missing = sorted(EXPECTED_TABLES - set(tables))
        return DatabaseHealthResponse(
            status="ok" if not missing else "error",
            database="connected",
            tables=tables,
            missing_tables=missing,
        )
