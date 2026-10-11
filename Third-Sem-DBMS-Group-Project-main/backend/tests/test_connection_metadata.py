from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app

from .conftest import requires_db
from .test_collector_api import KEY_A, URL, event

pytestmark = requires_db

T0 = datetime(2025, 7, 1, 9, 0, 0)
DOMAIN = "ports-test.example"
DEST_IP = "203.0.113.99"


@pytest.fixture
def collector(_use_test_session):
    with TestClient(app, headers={"X-API-Key": KEY_A}, raise_server_exceptions=False) as c:
        yield c


def tcp(ts=T0, **extra):
    return event(ts, dest_ip=DEST_IP, domain=DOMAIN, protocol="TCP", sourcePort=56188, destinationPort=443, **extra)


def stored_row(db, history_id):
    return db.execute(
        text("SELECT protocol, source_port, destination_port FROM network_history WHERE history_id = :h"),
        {"h": history_id},
    ).one()


def test_metadata_is_stored_exactly_as_sent(collector, db):
    response = collector.post(URL, json=tcp())
    assert response.status_code == 201, response.text
    assert tuple(stored_row(db, response.json()["history_id"])) == ("TCP", 56188, 443)


def test_events_without_metadata_still_work_and_store_null(collector, db):
    response = collector.post(URL, json=event(T0, dest_ip=DEST_IP, domain=DOMAIN))
    assert response.status_code == 201
    assert tuple(stored_row(db, response.json()["history_id"])) == (None, None, None)


def test_protocol_alone_is_allowed_and_is_case_insensitive(collector, db):
    response = collector.post(URL, json=event(T0, dest_ip=DEST_IP, domain=DOMAIN, protocol="udp"))
    assert response.status_code == 201
    assert tuple(stored_row(db, response.json()["history_id"])) == ("UDP", None, None)


def test_the_history_api_returns_the_fields(collector, client, db):
    history_id = collector.post(URL, json=tcp()).json()["history_id"]
    detail = client.get(f"/api/history/{history_id}").json()
    assert (detail["protocol"], detail["source_port"], detail["destination_port"]) == ("TCP", 56188, 443)

    listing = client.get("/api/history", params={"q": DOMAIN}).json()["items"]
    assert [(i["protocol"], i["source_port"], i["destination_port"]) for i in listing] == [("TCP", 56188, 443)]


def test_old_events_report_null_metadata(client):
    seeded = client.get("/api/history/1").json()
    assert {k: seeded[k] for k in ("protocol", "source_port", "destination_port")} == {
        "protocol": None,
        "source_port": None,
        "destination_port": None,
    }


def test_device_and_destination_history_include_the_fields(collector, client, db):
    collector.post(URL, json=tcp())
    device_id = db.scalar(text("SELECT device_id FROM devices WHERE device_identifier = 'PC-LAB-A-001'"))
    window = {"startDate": "2025-07-01", "endDate": "2025-07-02"}
    rows = client.get(f"/api/devices/{device_id}/history", params=window).json()["items"]
    assert [(r["domain"], r["protocol"], r["destination_port"]) for r in rows] == [(DOMAIN, "TCP", 443)]
    destination_id = db.scalar(text("SELECT destination_id FROM destinations WHERE domain = :d"), {"d": DOMAIN})
    rows = client.get(f"/api/destinations/{destination_id}/history").json()["items"]
    assert [(r["protocol"], r["source_port"]) for r in rows] == [("TCP", 56188)]


@pytest.mark.parametrize("port", [0, -1, 65536, 999999, "abc", 1.5])
def test_invalid_ports_are_rejected(collector, port):
    for field in ("sourcePort", "destinationPort"):
        body = event(T0, dest_ip=DEST_IP, domain=DOMAIN, protocol="TCP", **{field: port})
        assert collector.post(URL, json=body).status_code == 422


@pytest.mark.parametrize("protocol", ["ICMP", "TCP; DROP TABLE users", "", 6])
def test_unknown_protocols_are_rejected(collector, protocol):
    assert collector.post(URL, json=event(T0, dest_ip=DEST_IP, domain=DOMAIN, protocol=protocol)).status_code == 422


def test_ports_without_a_protocol_are_rejected(collector):
    body = event(T0, dest_ip=DEST_IP, domain=DOMAIN, sourcePort=56188, destinationPort=443)
    assert collector.post(URL, json=body).status_code == 422


def test_boundary_ports_are_accepted(collector, db):
    for ts, (src, dst) in zip((T0, T0 + timedelta(minutes=5)), ((1, 65535), (65535, 1))):
        response = collector.post(URL, json=event(ts, dest_ip=DEST_IP, domain=DOMAIN, protocol="TCP", sourcePort=src, destinationPort=dst))
        assert response.status_code == 201
        assert tuple(stored_row(db, response.json()["history_id"])) == ("TCP", src, dst)


def test_the_node_still_cannot_be_chosen_by_the_payload(collector):
    assert collector.post(URL, json=tcp(nodeId=2)).status_code == 422


def test_the_endpoint_still_requires_an_api_key(_use_test_session):
    with TestClient(app) as anonymous:
        assert anonymous.post(URL, json=tcp()).status_code == 401


def test_different_ports_to_the_same_destination_are_still_a_duplicate(collector, db):
    first = collector.post(URL, json=tcp(T0))
    assert first.status_code == 201
    other = collector.post(URL, json=event(T0 + timedelta(seconds=5), dest_ip=DEST_IP, domain=DOMAIN, protocol="TCP", sourcePort=60000, destinationPort=8443))
    assert other.status_code == 200 and other.json()["status"] == "DUPLICATE"
    assert other.json()["duplicate_of"] == first.json()["history_id"]


def test_a_different_protocol_to_the_same_destination_is_still_a_duplicate(collector):
    assert collector.post(URL, json=tcp(T0)).status_code == 201
    udp = event(T0 + timedelta(seconds=5), dest_ip=DEST_IP, domain=DOMAIN, protocol="UDP", sourcePort=40000, destinationPort=443)
    assert collector.post(URL, json=udp).json()["status"] == "DUPLICATE"


def test_after_thirty_seconds_the_same_destination_is_stored_again(collector):
    assert collector.post(URL, json=tcp(T0)).status_code == 201
    later = event(T0 + timedelta(seconds=31), dest_ip=DEST_IP, domain=DOMAIN, protocol="TCP", sourcePort=56190, destinationPort=443)
    assert collector.post(URL, json=later).status_code == 201


def test_a_duplicate_does_not_overwrite_the_stored_metadata(collector, db):
    first = collector.post(URL, json=tcp(T0)).json()["history_id"]
    collector.post(URL, json=event(T0 + timedelta(seconds=3), dest_ip=DEST_IP, domain=DOMAIN, protocol="UDP", sourcePort=1234, destinationPort=53))
    assert tuple(stored_row(db, first)) == ("TCP", 56188, 443)


def test_history_rows_are_not_updated_by_later_events(collector, db):
    first = collector.post(URL, json=tcp(T0)).json()["history_id"]
    collector.post(URL, json=event(T0 + timedelta(minutes=5), dest_ip=DEST_IP, domain=DOMAIN, protocol="TCP", sourcePort=1111, destinationPort=443))
    assert tuple(stored_row(db, first)) == ("TCP", 56188, 443)
