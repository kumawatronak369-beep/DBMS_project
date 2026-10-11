from sqlalchemy import text
from sqlalchemy.orm import Session


class HealthRepository:
    def __init__(self, db: Session):
        self.db = db

    def ping(self) -> None:
        self.db.execute(text("SELECT 1"))

    def list_tables(self) -> list[str]:
        rows = self.db.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' "
                "ORDER BY table_name"
            )
        )
        return [row[0] for row in rows]
