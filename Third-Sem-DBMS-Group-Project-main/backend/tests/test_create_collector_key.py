import pytest
from sqlalchemy import text

from app.core.security import hash_api_key
from create_collector_key import create_key

from .conftest import requires_db

pytestmark = requires_db


def make(db, code="TEST-LOCAL", **over):
    values = dict(node_code=code, node_name="Test Computer", location="Home", ip_address="192.168.1.3", key_name="test key")
    values.update(over)
    return create_key(db, **values)


def test_creates_a_node_and_a_key_that_works(db, anon_client):
    node, key, created = make(db)
    assert created and key.startswith("nm_") and len(key) >= 40

    response = anon_client.post(
        "/api/collector/events",
        headers={"X-API-Key": key},
        json={"deviceIdentifier": "TEST-PC", "deviceIp": "192.168.1.3", "destinationIp": "203.0.113.77", "domain": "keytest.example.org", "timestamp": "2026-09-20T11:08:30"},
    )
    assert response.status_code == 201, response.text
    stored_node = db.scalar(text("SELECT node_id FROM network_history WHERE history_id = :h"), {"h": response.json()["history_id"]})
    assert stored_node == node.node_id


def test_only_the_hash_is_stored(db):
    node, key, _ = make(db)
    rows = db.execute(text("SELECT key_hash FROM collector_api_keys WHERE node_id = :n"), {"n": node.node_id}).scalars().all()
    assert rows == [hash_api_key(key)]
    assert key not in rows[0]


def test_an_existing_node_is_reused_and_left_unchanged(db):
    first, _, created_first = make(db)
    second, _, created_second = make(db, node_name="Renamed", location="Elsewhere")
    assert (created_first, created_second) == (True, False)
    assert second.node_id == first.node_id
    assert db.scalar(text("SELECT node_name FROM nodes WHERE node_id = :n"), {"n": first.node_id}) == "Test Computer"
    assert db.scalar(text("SELECT COUNT(*) FROM collector_api_keys WHERE node_id = :n"), {"n": first.node_id}) == 2


def test_every_key_is_different(db):
    _, one, _ = make(db)
    _, two, _ = make(db)
    assert one != two
