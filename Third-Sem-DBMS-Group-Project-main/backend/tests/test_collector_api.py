import logging
import threading
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_api_key
from app.db.session import engine
from app.main import app
from app.models import NetworkHistory
from app.repositories.history_repository import HistoryRepository
from app.services.collector_service import CollectorService
from tests.conftest import bearer, requires_db

pytestmark = requires_db

KEY_A = "nm_dev_lab-a_key"
KEY_B = "nm_dev_lab-b_key"
URL = "/api/collector/events"
BASE = datetime(2025, 6, 1, 10, 0, 0)


def event(ts=BASE, device="PC-LAB-A-001", device_ip="192.168.10.21", dest_ip="203.0.113.10", domain="example.com", **extra):
    body = {
        "deviceIdentifier": device,
        "deviceIp": device_ip,
        "destinationIp": dest_ip,
        "timestamp": ts.isoformat(),
        **extra,
    }
    if domain is not None:
        body["domain"] = domain
    return body


def now() -> datetime:
    return datetime.now().replace(microsecond=0)


@pytest.fixture
def collector(_use_test_session):
    with TestClient(app, headers={"X-API-Key": KEY_A}, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def collector_b(_use_test_session):
    with TestClient(app, headers={"X-API-Key": KEY_B}, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def anon_collector(_use_test_session):
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def scalar(db, sql, **params):
    return db.scalar(text(sql), params)


def row(db, sql, **params):
    return db.execute(text(sql), params).mappings().first()


def counts(db) -> dict:
    return {
        t: scalar(db, f"SELECT COUNT(*) FROM {t}")
        for t in ("network_history", "devices", "destinations", "nodes")
    }


def test_valid_authenticated_event_is_stored(collector, db):
    response = collector.post(URL, json=event())
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "STORED" and body["duplicate_of"] is None and body["history_id"]

    stored = row(db, "SELECT * FROM network_history WHERE history_id = :i", i=body["history_id"])
    assert stored["node_id"] == 1
    assert stored["device_id"] == 1
    assert stored["destination_id"] == 1
    assert stored["observed_at"] == BASE
    assert stored["created_at"] is not None


def test_history_record_is_correct_and_visible_through_the_read_api(collector, db):
    history_id = collector.post(URL, json=event(ts=now(), dest_ip="203.0.113.77", domain="fresh.example")).json()["history_id"]
    admin = TestClient(app, headers=bearer(scalar(db, "SELECT user_id FROM users WHERE email='admin@netmonitor.local'")))
    shown = admin.get(f"/api/history/{history_id}").json()
    assert shown["device_identifier"] == "PC-LAB-A-001" and shown["node_code"] == "LAB-A"
    assert shown["domain"] == "fresh.example" and shown["destination_ip"] == "203.0.113.77"
    assert shown["category"] == "UNKNOWN"


def test_only_one_collector_operation_exists():
    operations = {
        (method.upper(), path)
        for path, ops in app.openapi()["paths"].items()
        if path.startswith("/api/collector")
        for method in ops
    }
    assert operations == {("POST", "/api/collector/events")}


def test_missing_key_is_rejected(anon_collector, db):
    before = counts(db)
    response = anon_collector.post(URL, json=event())
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "ApiKey"
    assert response.json() == {"detail": "Invalid or missing API key"}
    assert counts(db) == before


@pytest.mark.parametrize("key", ["wrong-key", "", " ", "nm_dev_lab-a_key ", "NM_DEV_LAB-A_KEY", "x" * 500])
def test_invalid_keys_are_rejected(anon_collector, db, key):
    before = counts(db)
    response = anon_collector.post(URL, json=event(), headers={"X-API-Key": key})
    if key == "nm_dev_lab-a_key ":
        assert response.status_code == 201
        return
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}
    assert counts(db) == before


def test_the_stored_hash_is_not_usable_as_a_key(anon_collector, db):
    stored_hash = scalar(db, "SELECT key_hash FROM collector_api_keys WHERE node_id = 1")
    assert stored_hash == hash_api_key(KEY_A) != KEY_A
    assert anon_collector.post(URL, json=event(), headers={"X-API-Key": stored_hash}).status_code == 401


def test_user_tokens_and_collector_keys_are_not_interchangeable(anon_collector, db):
    admin_id = scalar(db, "SELECT user_id FROM users WHERE email='admin@netmonitor.local'")
    assert anon_collector.post(URL, json=event(), headers=bearer(admin_id)).status_code == 401
    assert anon_collector.get("/api/nodes", headers={"X-API-Key": KEY_A}).status_code == 401
    assert anon_collector.get("/api/nodes", headers={"Authorization": f"Bearer {KEY_A}"}).status_code == 401


def test_revoked_key_is_rejected_but_other_nodes_keep_working(collector, collector_b, db):
    db.execute(text("UPDATE collector_api_keys SET status='REVOKED', revoked_at=NOW() WHERE node_id = 1"))
    before = counts(db)
    response = collector.post(URL, json=event())
    assert response.status_code == 401 and response.json() == {"detail": "Invalid or missing API key"}
    assert counts(db) == before
    assert collector_b.post(URL, json=event(device="PC-LAB-B-001")).status_code == 201


def test_disabled_node_cannot_submit_events(collector, db):
    db.execute(text("UPDATE nodes SET status='INACTIVE' WHERE node_id = 1"))
    before = counts(db)
    response = collector.post(URL, json=event())
    assert response.status_code == 403 and response.json() == {"detail": "This node is disabled"}
    assert counts(db) == before


def test_offline_node_can_still_report(collector, db):
    db.execute(text("UPDATE nodes SET status='OFFLINE' WHERE node_id = 1"))
    assert collector.post(URL, json=event()).status_code == 201


def test_key_usage_is_recorded_only_for_authenticated_requests(collector, anon_collector, db):
    assert scalar(db, "SELECT last_used_at FROM collector_api_keys WHERE node_id = 1") is None
    anon_collector.post(URL, json=event(), headers={"X-API-Key": "wrong"})
    assert scalar(db, "SELECT last_used_at FROM collector_api_keys WHERE node_id = 1") is None
    collector.post(URL, json=event())
    used = scalar(db, "SELECT last_used_at FROM collector_api_keys WHERE node_id = 1")
    assert used is not None and abs(used - datetime.now()) < timedelta(minutes=1)
    assert scalar(db, "SELECT last_used_at FROM collector_api_keys WHERE node_id = 2") is None


@pytest.mark.parametrize("field", ["nodeId", "node_id", "node", "nodeCode"])
def test_a_node_supplied_in_the_payload_is_rejected(collector, db, field):
    before = counts(db)
    response = collector.post(URL, json=event(**{field: 2}))
    assert response.status_code == 422
    assert any(err["type"] == "extra_forbidden" for err in response.json()["detail"])
    assert counts(db) == before


def test_key_for_node_a_never_writes_to_node_b(collector, db):
    b_device = scalar(db, "SELECT device_id FROM devices WHERE device_identifier = 'PC-LAB-B-001'")
    b_last_seen = scalar(db, "SELECT last_seen FROM devices WHERE device_id = :d", d=b_device)
    b_events = scalar(db, "SELECT COUNT(*) FROM network_history WHERE node_id = 2")

    response = collector.post(URL, json=event(ts=now(), device="PC-LAB-B-001"))
    assert response.status_code == 201

    stored = row(db, "SELECT * FROM network_history WHERE history_id = :i", i=response.json()["history_id"])
    assert stored["node_id"] == 1 and stored["device_id"] != b_device
    new_device = row(db, "SELECT * FROM devices WHERE device_id = :d", d=stored["device_id"])
    assert new_device["node_id"] == 1 and new_device["device_identifier"] == "PC-LAB-B-001"

    assert scalar(db, "SELECT COUNT(*) FROM network_history WHERE node_id = 2") == b_events
    assert scalar(db, "SELECT last_seen FROM devices WHERE device_id = :d", d=b_device) == b_last_seen


def test_node_b_key_records_under_node_b(collector_b, db):
    body = collector_b.post(URL, json=event(device="PC-LAB-A-001")).json()
    stored = row(db, "SELECT * FROM network_history WHERE history_id = :i", i=body["history_id"])
    assert stored["node_id"] == 2
    assert scalar(db, "SELECT node_id FROM devices WHERE device_id = :d", d=stored["device_id"]) == 2


def test_existing_device_is_reused(collector, db):
    before = counts(db)
    response = collector.post(URL, json=event())
    assert response.status_code == 201
    after = counts(db)
    assert after["devices"] == before["devices"]
    assert scalar(db, "SELECT device_id FROM network_history WHERE history_id = :i", i=response.json()["history_id"]) == 1


def test_a_changed_ip_is_the_same_device_not_a_new_one(collector, db):
    before = counts(db)
    ts = now()
    collector.post(URL, json=event(ts=ts, device_ip="192.168.10.99"))
    assert counts(db)["devices"] == before["devices"]
    device = row(db, "SELECT * FROM devices WHERE device_id = 1")
    assert device["ip_address"] == "192.168.10.99" and device["last_seen"] == ts


def test_unknown_device_is_created_under_the_authenticated_node(collector, db):
    ts = now()
    body = collector.post(URL, json=event(ts=ts, device="PC-NEW-777", device_ip="192.168.10.200")).json()
    device = row(
        db,
        "SELECT d.* FROM devices d JOIN network_history h USING (device_id) WHERE h.history_id = :i",
        i=body["history_id"],
    )
    assert device["device_identifier"] == "PC-NEW-777" and device["node_id"] == 1
    assert device["ip_address"] == "192.168.10.200" and device["status"] == "ACTIVE"
    assert device["first_seen"] == device["last_seen"] == ts
    assert device["device_name"] is None and device["hostname"] is None


def test_device_identity_is_scoped_to_its_node_in_the_database(db):
    device_of_node_1 = scalar(db, "SELECT device_id FROM devices WHERE node_id = 1 LIMIT 1")
    with pytest.raises(IntegrityError) as raised:
        with db.begin_nested():
            db.add(NetworkHistory(device_id=device_of_node_1, node_id=2, destination_id=1, observed_at=BASE))
            db.flush()
    assert "fk_history_device_node" in str(raised.value)


def test_older_events_do_not_overwrite_a_newer_device_state(collector, db):
    ts = now()
    collector.post(URL, json=event(ts=ts, device_ip="192.168.10.50"))
    collector.post(URL, json=event(ts=ts - timedelta(days=30), device_ip="192.168.10.60"))
    device = row(db, "SELECT * FROM devices WHERE device_id = 1")
    assert device["ip_address"] == "192.168.10.50" and device["last_seen"] == ts
    assert device["first_seen"] == ts - timedelta(days=30)


def test_existing_destination_is_reused_and_domain_is_normalised(collector, db):
    before = counts(db)
    for i, domain in enumerate(("example.com", "EXAMPLE.COM", "Example.com.")):
        body = collector.post(URL, json=event(ts=now() - timedelta(minutes=10 * (i + 1)), domain=domain)).json()
        assert scalar(db, "SELECT destination_id FROM network_history WHERE history_id = :i", i=body["history_id"]) == 1
    assert counts(db)["destinations"] == before["destinations"]

    same_moment = now() - timedelta(minutes=200)
    assert collector.post(URL, json=event(ts=same_moment, domain="example.com")).json()["status"] == "STORED"
    assert collector.post(URL, json=event(ts=same_moment, domain="EXAMPLE.COM.")).json()["status"] == "DUPLICATE"


def test_new_destination_is_created(collector, db):
    before = counts(db)
    ts = now()
    body = collector.post(URL, json=event(ts=ts, dest_ip="203.0.113.201", domain="brand-new.example")).json()
    assert counts(db)["destinations"] == before["destinations"] + 1
    dest = row(
        db,
        "SELECT d.* FROM destinations d JOIN network_history h USING (destination_id) WHERE h.history_id = :i",
        i=body["history_id"],
    )
    assert dest["ip_address"] == "203.0.113.201" and dest["domain"] == "brand-new.example"
    assert dest["category"] == "UNKNOWN"
    assert dest["first_seen"] == dest["last_seen"] == ts

    collector.post(URL, json=event(ts=ts, device="PC-LAB-A-002", dest_ip="203.0.113.201", domain="brand-new.example"))
    assert counts(db)["destinations"] == before["destinations"] + 1


def test_same_ip_with_a_different_domain_is_a_different_destination(collector, db):
    before = counts(db)["destinations"]
    collector.post(URL, json=event(ts=now(), dest_ip="203.0.113.10", domain="other-name.example"))
    collector.post(URL, json=event(ts=now(), dest_ip="203.0.113.250", domain="example.com"))
    assert counts(db)["destinations"] == before + 2


def test_destination_without_a_domain_uses_null_and_is_reused(collector, db):
    before = counts(db)["destinations"]
    ts = now()

    for i, domain_field in enumerate([{}, {"domain": None}, {"domain": ""}]):
        payload = event(ts=ts - timedelta(minutes=i), dest_ip="192.0.2.77", domain=None)
        payload.update(domain_field)
        body = collector.post(URL, json=payload).json()
        assert scalar(db, "SELECT destination_id FROM network_history WHERE history_id = :i", i=body["history_id"]) == 12
    assert counts(db)["destinations"] == before

    for i in range(2):
        collector.post(URL, json=event(ts=ts - timedelta(minutes=i), dest_ip="192.0.2.99", domain=None))
    made = row(db, "SELECT * FROM destinations WHERE ip_address = '192.0.2.99'")
    assert made["domain"] is None and made["domain_key"] == ""
    assert counts(db)["destinations"] == before + 1


def test_ipv6_addresses_are_canonicalised(collector, db):
    a = collector.post(URL, json=event(ts=BASE, dest_ip="2001:DB8:0:0:0:0:0:1", domain=None)).json()
    b = collector.post(URL, json=event(ts=BASE + timedelta(minutes=5), dest_ip="2001:db8::1", domain=None)).json()
    dest = lambda i: scalar(db, "SELECT destination_id FROM network_history WHERE history_id = :i", i=i)  # noqa: E731
    assert dest(a["history_id"]) == dest(b["history_id"])
    assert scalar(db, "SELECT ip_address FROM destinations WHERE destination_id = :d", d=dest(a["history_id"])) == "2001:db8::1"


def offset(seconds):
    return BASE + timedelta(seconds=seconds)


def stored_times(db):
    return [
        r[0]
        for r in db.execute(
            text("SELECT observed_at FROM network_history WHERE device_id = 1 AND destination_id = 1 AND observed_at >= '2025-01-01' AND observed_at < '2026-01-01' ORDER BY observed_at")
        )
    ]


def test_specification_example_sequence(collector, db):
    results = [collector.post(URL, json=event(ts=offset(s))) for s in (0, 5, 12, 25, 40)]
    assert [r.status_code for r in results] == [201, 200, 200, 200, 201]
    assert [r.json()["status"] for r in results] == ["STORED", "DUPLICATE", "DUPLICATE", "DUPLICATE", "STORED"]
    first_id = results[0].json()["history_id"]
    assert all(r.json()["duplicate_of"] == first_id and r.json()["history_id"] is None for r in results[1:4])
    assert stored_times(db) == [offset(0), offset(40)]


def test_a_duplicate_is_handled_as_a_normal_response_not_an_error(collector, db):
    collector.post(URL, json=event(ts=offset(0)))
    before = counts(db)
    response = collector.post(URL, json=event(ts=offset(5)))
    assert response.status_code == 200
    assert response.json()["status"] == "DUPLICATE" and "not stored" in response.json()["message"]
    assert counts(db) == before


def test_event_after_more_than_30_seconds_is_stored(collector, db):
    assert collector.post(URL, json=event(ts=offset(0))).status_code == 201
    later = collector.post(URL, json=event(ts=offset(31)))
    assert later.status_code == 201 and later.json()["status"] == "STORED"
    assert stored_times(db) == [offset(0), offset(31)]


def test_the_boundary_is_inclusive_at_exactly_30_seconds(collector, db):
    collector.post(URL, json=event(ts=offset(0)))
    assert collector.post(URL, json=event(ts=offset(30))).json()["status"] == "DUPLICATE"
    assert collector.post(URL, json=event(ts=offset(31))).json()["status"] == "STORED"


def test_each_event_is_compared_with_stored_events_not_rejected_attempts(collector, db):
    collector.post(URL, json=event(ts=offset(0)))
    collector.post(URL, json=event(ts=offset(31)))
    assert collector.post(URL, json=event(ts=offset(60))).json()["status"] == "DUPLICATE"
    assert collector.post(URL, json=event(ts=offset(62))).json()["status"] == "STORED"


def test_different_destination_device_or_node_is_not_a_duplicate(collector, collector_b, db):
    assert collector.post(URL, json=event(ts=offset(0))).status_code == 201
    other_destination = collector.post(URL, json=event(ts=offset(5), dest_ip="203.0.113.20", domain="github.com"))
    other_device = collector.post(URL, json=event(ts=offset(5), device="PC-LAB-A-002"))
    other_node = collector_b.post(URL, json=event(ts=offset(5), device="PC-LAB-A-001"))
    assert [r.status_code for r in (other_destination, other_device, other_node)] == [201, 201, 201]


def test_late_arriving_events_use_a_symmetric_window(collector, db):
    collector.post(URL, json=event(ts=offset(0)))
    assert collector.post(URL, json=event(ts=offset(-20))).json()["status"] == "DUPLICATE"
    assert collector.post(URL, json=event(ts=offset(-3600))).json()["status"] == "STORED"
    assert collector.post(URL, json=event(ts=BASE - timedelta(days=400))).json()["status"] == "STORED"


def test_duplicates_change_nothing(collector, db):
    ts = now()
    collector.post(URL, json=event(ts=ts, device="PC-DUP-1", dest_ip="203.0.113.150", domain="dup.example"))
    snapshot = (
        counts(db),
        scalar(db, "SELECT last_seen FROM devices WHERE device_identifier = 'PC-DUP-1'"),
        scalar(db, "SELECT last_seen FROM destinations WHERE domain = 'dup.example'"),
        scalar(db, "SELECT last_seen FROM nodes WHERE node_id = 1"),
    )
    dup = collector.post(URL, json=event(ts=ts + timedelta(seconds=10), device="PC-DUP-1", dest_ip="203.0.113.150", domain="dup.example"))
    assert dup.json()["status"] == "DUPLICATE"
    assert snapshot == (
        counts(db),
        scalar(db, "SELECT last_seen FROM devices WHERE device_identifier = 'PC-DUP-1'"),
        scalar(db, "SELECT last_seen FROM destinations WHERE domain = 'dup.example'"),
        scalar(db, "SELECT last_seen FROM nodes WHERE node_id = 1"),
    )


def test_no_two_stored_events_are_within_30_seconds_after_a_burst(collector, db):
    for s in range(0, 200, 4):
        collector.post(URL, json=event(ts=offset(s)))
    violations = scalar(
        db,
        "SELECT COUNT(*) FROM network_history a JOIN network_history b ON a.device_id=b.device_id AND a.destination_id=b.destination_id "
        "AND b.observed_at > a.observed_at AND b.observed_at <= a.observed_at + INTERVAL 30 SECOND",
    )
    assert violations == 0
    times = stored_times(db)
    assert all((b - a).total_seconds() > 30 for a, b in zip(times, times[1:]))
    assert len(times) == 7


def test_last_seen_is_updated_on_device_destination_and_node(collector, db):
    ts = now()
    collector.post(URL, json=event(ts=ts, dest_ip="203.0.113.10", domain="example.com"))
    assert scalar(db, "SELECT last_seen FROM devices WHERE device_id = 1") == ts
    assert scalar(db, "SELECT last_seen FROM destinations WHERE destination_id = 1") == ts
    assert scalar(db, "SELECT last_seen FROM nodes WHERE node_id = 1") == ts
    assert scalar(db, "SELECT last_seen FROM nodes WHERE node_id = 2") != ts


def test_last_seen_never_moves_backwards(collector, db):
    ts = now()
    collector.post(URL, json=event(ts=ts))
    collector.post(URL, json=event(ts=ts - timedelta(hours=5)))
    assert scalar(db, "SELECT last_seen FROM devices WHERE device_id = 1") == ts
    assert scalar(db, "SELECT last_seen FROM destinations WHERE destination_id = 1") == ts
    assert scalar(db, "SELECT last_seen FROM nodes WHERE node_id = 1") == ts


def test_first_seen_of_a_destination_can_move_back(collector, db):
    collector.post(URL, json=event(ts=BASE))
    assert scalar(db, "SELECT first_seen FROM destinations WHERE destination_id = 1") == BASE


def _snapshot(db):
    return (
        counts(db),
        scalar(db, "SELECT last_seen FROM nodes WHERE node_id = 1"),
        scalar(db, "SELECT last_used_at FROM collector_api_keys WHERE node_id = 1"),
        scalar(db, "SELECT last_seen FROM devices WHERE device_id = 1"),
        scalar(db, "SELECT last_seen FROM destinations WHERE destination_id = 1"),
    )


NEW_EVENT = dict(device="PC-ROLLBACK-1", dest_ip="203.0.113.222", domain="rollback.example")


def test_failure_while_inserting_history_rolls_everything_back(collector, db, monkeypatch):
    before = _snapshot(db)

    def boom(self, event):
        raise RuntimeError("secret internal failure detail")

    monkeypatch.setattr(HistoryRepository, "add", boom)
    response = collector.post(URL, json=event(ts=now(), **NEW_EVENT))

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret internal failure detail" not in response.text
    assert _snapshot(db) == before
    assert scalar(db, "SELECT COUNT(*) FROM devices WHERE device_identifier = 'PC-ROLLBACK-1'") == 0
    assert scalar(db, "SELECT COUNT(*) FROM destinations WHERE domain = 'rollback.example'") == 0


def test_failure_after_partial_updates_rolls_back_the_updates(collector, db, monkeypatch):
    before = _snapshot(db)

    def boom(destination, observed_at):
        raise RuntimeError("failed after the device was already updated")

    monkeypatch.setattr(CollectorService, "_touch_destination", staticmethod(boom))
    assert collector.post(URL, json=event(ts=now())).status_code == 500
    assert _snapshot(db) == before


def test_a_real_database_error_rolls_back_and_leaks_no_sql(collector, db, monkeypatch):
    before = _snapshot(db)
    original = HistoryRepository.add

    def add_with_wrong_node(self, record):
        record.node_id = 2
        return original(self, record)

    monkeypatch.setattr(HistoryRepository, "add", add_with_wrong_node)
    response = collector.post(URL, json=event(ts=now(), **NEW_EVENT))

    assert response.status_code == 500 and response.json() == {"detail": "Internal server error"}
    assert "fk_history" not in response.text and "INSERT" not in response.text
    assert _snapshot(db) == before


def test_the_service_is_usable_again_after_a_rollback(collector, db, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(HistoryRepository, "add", lambda self, record: (_ for _ in ()).throw(RuntimeError("x")))
        assert collector.post(URL, json=event(ts=now(), **NEW_EVENT)).status_code == 500
    ok = collector.post(URL, json=event(ts=now(), **NEW_EVENT))
    assert ok.status_code == 201
    assert scalar(db, "SELECT COUNT(*) FROM devices WHERE device_identifier = 'PC-ROLLBACK-1'") == 1


def test_a_lock_timeout_is_a_retryable_503_and_stores_nothing(collector, db, monkeypatch):
    from sqlalchemy.exc import OperationalError

    before = _snapshot(db)

    def timeout(self, node):
        raise OperationalError("SELECT ... FOR UPDATE", {}, Exception("Lock wait timeout exceeded"))

    monkeypatch.setattr("app.repositories.node_repository.NodeRepository.lock", timeout)
    response = collector.post(URL, json=event(ts=now()))
    assert response.status_code == 503 and "retry" in response.json()["detail"]
    assert "Lock wait" not in response.text
    assert _snapshot(db) == before


INVALID_PAYLOADS = [
    pytest.param({}, id="empty"),
    pytest.param({"deviceIdentifier": "x"}, id="missing-fields"),
    pytest.param(event(device=""), id="empty-identifier"),
    pytest.param(event(device="x" * 101), id="identifier-too-long"),
    pytest.param(event(device_ip="not-an-ip"), id="bad-device-ip"),
    pytest.param(event(device_ip="999.1.1.1"), id="out-of-range-device-ip"),
    pytest.param(event(dest_ip="1.2.3"), id="bad-destination-ip"),
    pytest.param(event(dest_ip=""), id="empty-destination-ip"),
    pytest.param(event(domain="bad domain!"), id="domain-with-space"),
    pytest.param(event(domain="a..b"), id="domain-empty-label"),
    pytest.param(event(domain="-bad.com"), id="domain-leading-hyphen"),
    pytest.param(event(domain="a" * 64 + ".com"), id="domain-label-too-long"),
    pytest.param({**event(), "timestamp": "yesterday"}, id="bad-timestamp"),
    pytest.param({**event(), "timestamp": None}, id="null-timestamp"),
    pytest.param(event(unexpected="field"), id="unknown-field"),
]


@pytest.mark.parametrize("payload", INVALID_PAYLOADS)
def test_invalid_payloads_are_rejected_and_nothing_is_stored(collector, db, payload):
    before = _snapshot(db)
    response = collector.post(URL, json=payload)
    assert response.status_code == 422
    assert KEY_A not in response.text
    assert _snapshot(db) == before


def test_a_body_that_is_not_json_is_rejected(collector, db):
    before = _snapshot(db)
    assert collector.post(URL, content=b"not json", headers={"content-type": "application/json"}).status_code == 422
    assert collector.post(URL, json=["a", "list"]).status_code == 422
    assert _snapshot(db) == before


def test_authentication_is_checked_before_the_payload(anon_collector):
    assert anon_collector.post(URL, json={}).status_code == 401


def test_a_timestamp_in_the_future_is_rejected(collector, db):
    before = _snapshot(db)
    response = collector.post(URL, json=event(ts=now() + timedelta(hours=1)))
    assert response.status_code == 422 and "future" in response.json()["detail"]
    assert _snapshot(db) == before
    assert collector.post(URL, json=event(ts=now() + timedelta(minutes=4))).status_code == 201


def test_timezone_aware_and_fractional_timestamps_are_normalised(collector, db):
    aware = datetime(2025, 6, 1, 10, 0, 0).astimezone()
    body = collector.post(URL, json={**event(), "timestamp": aware.isoformat()}).json()
    assert scalar(db, "SELECT observed_at FROM network_history WHERE history_id = :i", i=body["history_id"]) == BASE
    frac = collector.post(URL, json={**event(ts=BASE + timedelta(minutes=10)), "timestamp": "2025-06-01T10:10:00.987654"}).json()
    assert scalar(db, "SELECT observed_at FROM network_history WHERE history_id = :i", i=frac["history_id"]) == BASE + timedelta(minutes=10)


def test_snake_case_field_names_are_also_accepted(collector):
    payload = {
        "device_identifier": "PC-LAB-A-001", "device_ip": "192.168.10.21",
        "destination_ip": "203.0.113.10", "domain": "example.com", "timestamp": BASE.isoformat(),
    }
    assert collector.post(URL, json=payload).status_code == 201


def test_api_keys_and_hashes_never_appear_in_responses_or_logs(collector, anon_collector, caplog, db):
    stored_hash = hash_api_key(KEY_A)
    with caplog.at_level(logging.DEBUG):
        responses = [
            collector.post(URL, json=event()),
            collector.post(URL, json=event(ts=BASE + timedelta(seconds=5))),
            collector.post(URL, json={}),
            anon_collector.post(URL, json=event(), headers={"X-API-Key": "leaky-wrong-key-123"}),
        ]
    for response in responses:
        assert KEY_A not in response.text and stored_hash not in response.text
        assert "key_hash" not in response.text
    for secret in (KEY_A, stored_hash, "leaky-wrong-key-123"):
        assert secret not in caplog.text


def _make_isolated_node():
    suffix = uuid.uuid4().hex[:8]
    key = f"nm_test_concurrency_{suffix}"
    with engine.begin() as conn:
        node_id = conn.execute(
            text(
                "INSERT INTO nodes (node_code, node_name, ip_address, location) "
                "VALUES (:c, 'Concurrency test', '10.250.0.1', 'test')"
            ),
            {"c": f"CONC-{suffix}"},
        ).lastrowid
        conn.execute(
            text("INSERT INTO collector_api_keys (node_id, key_name, key_hash) VALUES (:n, 'concurrency', :h)"),
            {"n": node_id, "h": hash_api_key(key)},
        )
    return node_id, key, f"198.18.{int(suffix[:2], 16) % 250}.{int(suffix[2:4], 16) % 250 + 1}"


def _remove_isolated_node(node_id, dest_ip):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM network_history WHERE node_id = :n"), {"n": node_id})
        conn.execute(text("DELETE FROM devices WHERE node_id = :n"), {"n": node_id})
        conn.execute(text("DELETE FROM collector_api_keys WHERE node_id = :n"), {"n": node_id})
        conn.execute(text("DELETE FROM nodes WHERE node_id = :n"), {"n": node_id})
        conn.execute(text("DELETE FROM destinations WHERE ip_address = :ip"), {"ip": dest_ip})


def _fire_concurrently(key, payloads):
    barrier = threading.Barrier(len(payloads))
    responses = [None] * len(payloads)

    def worker(i):
        with TestClient(app, headers={"X-API-Key": key}, raise_server_exceptions=False) as c:
            barrier.wait(timeout=20)
            responses[i] = c.post(URL, json=payloads[i])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(payloads))]
    [t.start() for t in threads]
    [t.join(timeout=60) for t in threads]
    return responses


def test_concurrent_identical_events_store_exactly_one():
    node_id, key, dest_ip = _make_isolated_node()
    try:
        ts = now()
        same = event(ts=ts, device="PC-RACE-1", dest_ip=dest_ip, domain="race.example")
        responses = _fire_concurrently(key, [same] * 8)

        assert all(r is not None and r.status_code in (200, 201) for r in responses), [r.text for r in responses]
        statuses = sorted(r.json()["status"] for r in responses)
        assert statuses == ["DUPLICATE"] * 7 + ["STORED"]
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT COUNT(*) FROM network_history WHERE node_id = :n"), {"n": node_id}) == 1
            assert conn.scalar(text("SELECT COUNT(*) FROM devices WHERE node_id = :n"), {"n": node_id}) == 1
            assert conn.scalar(text("SELECT COUNT(*) FROM destinations WHERE ip_address = :i"), {"i": dest_ip}) == 1
    finally:
        _remove_isolated_node(node_id, dest_ip)


def test_concurrent_events_creating_the_same_new_destination_create_it_once():
    node_id, key, dest_ip = _make_isolated_node()
    try:
        ts = now()
        payloads = [event(ts=ts, device=f"PC-RACE-{i}", dest_ip=dest_ip, domain="shared-race.example") for i in range(8)]
        responses = _fire_concurrently(key, payloads)

        assert all(r is not None and r.status_code == 201 for r in responses), [(r.status_code, r.text) for r in responses]
        with engine.connect() as conn:
            assert conn.scalar(text("SELECT COUNT(*) FROM destinations WHERE ip_address = :i"), {"i": dest_ip}) == 1
            assert conn.scalar(text("SELECT COUNT(*) FROM devices WHERE node_id = :n"), {"n": node_id}) == 8
            assert conn.scalar(text("SELECT COUNT(*) FROM network_history WHERE node_id = :n"), {"n": node_id}) == 8
    finally:
        _remove_isolated_node(node_id, dest_ip)
