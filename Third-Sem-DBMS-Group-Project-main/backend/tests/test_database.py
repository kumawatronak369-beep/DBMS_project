import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import engine
from app.models import Destination, Device, NetworkHistory, Node

EXPECTED_TABLES = {"users", "nodes", "devices", "destinations", "collector_api_keys", "network_history"}


def _db_available() -> bool:
    try:
        with engine.connect():
            return True
    except SQLAlchemyError:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="MySQL not reachable")


def test_live_database_has_exactly_the_six_tables():
    assert set(inspect(engine).get_table_names()) - {"alembic_version"} == EXPECTED_TABLES


def test_models_match_live_schema():
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True, "compare_server_default": True})
        assert compare_metadata(ctx, Base.metadata) == []


def test_composite_node_device_foreign_key_exists():
    fks = inspect(engine).get_foreign_keys("network_history")
    composite = [f for f in fks if f["constrained_columns"] == ["node_id", "device_id"]]
    assert composite and composite[0]["referred_columns"] == ["node_id", "device_id"]


def test_orm_reads_and_joins_work():
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Node)) >= 1
        row = db.execute(
            select(NetworkHistory.history_id, Device.device_identifier, Destination.ip_address)
            .join(Device, Device.device_id == NetworkHistory.device_id)
            .join(Destination, Destination.destination_id == NetworkHistory.destination_id)
            .limit(1)
        ).first()
        assert row is not None


def test_null_domain_destination_insert_leaves_domain_key_to_mysql():
    with Session(engine) as db:
        dest = Destination(ip_address="192.0.2.250", domain=None)
        db.add(dest)
        db.flush()
        db.refresh(dest)
        assert dest.domain is None
        assert dest.domain_key == ""
        db.rollback()
