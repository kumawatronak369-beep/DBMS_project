import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.core.security import create_access_token
from app.db.session import engine
from app.main import app

ADMIN_EMAIL = "admin@netmonitor.local"
ADMIN_PASSWORD = "Admin@12345"
ANALYST_EMAIL = "analyst@netmonitor.local"
ANALYST_PASSWORD = "Analyst@12345"


def _db_available() -> bool:
    try:
        with engine.connect():
            return True
    except SQLAlchemyError:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="MySQL not reachable")


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", autoflush=False, expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def bearer(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _user_id(db: Session, email: str) -> int:
    return db.scalar(text("SELECT user_id FROM users WHERE email = :e"), {"e": email})


@pytest.fixture
def _use_test_session(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def anon_client(_use_test_session):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(_use_test_session, db):
    with TestClient(app, headers=bearer(_user_id(db, ADMIN_EMAIL))) as test_client:
        yield test_client


@pytest.fixture
def analyst_client(_use_test_session, db):
    with TestClient(app, headers=bearer(_user_id(db, ANALYST_EMAIL))) as test_client:
        yield test_client
