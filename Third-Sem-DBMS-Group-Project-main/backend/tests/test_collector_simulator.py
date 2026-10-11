import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from tests.conftest import requires_db

COLLECTOR_DIR = Path(__file__).resolve().parents[2] / "collector"
sys.path.insert(0, str(COLLECTOR_DIR))

import api_client  # noqa: E402
import collector  # noqa: E402
import config as collector_config  # noqa: E402
import event_generator  # noqa: E402

pytestmark = requires_db

KEYS = {"lab-a": "nm_dev_lab-a_key", "lab-b": "nm_dev_lab-b_key", "lib-01": "nm_dev_lib-01_key", "admin-01": "nm_dev_admin-01_key"}
NODE_IDS = {"lab-a": 1, "lab-b": 2, "lib-01": 3, "admin-01": 4}


class Recorder:
    def __init__(self, client):
        self.client, self.log = client, []

    def send_event(self, payload):
        result = self.client.send_event(payload)
        self.log.append((payload, result))
        return result


@pytest.fixture
def backend(_use_test_session):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def real_client(backend, profile="lab-a", key=None):
    return api_client.CollectorClient("http://testserver", key or KEYS[profile], timeout=5, session=backend)


LONG_AGO = datetime(2025, 6, 1, 10, 0, 0)


def simulate(backend, profile="lab-a", count=60, rate=0.25, seed=11, key=None, start=LONG_AGO):
    clock = iter(start + timedelta(seconds=2 * i) for i in range(10_000))
    generator = event_generator.EventGenerator(
        event_generator.PROFILES[profile], random.Random(seed), clock=lambda: next(clock), duplicate_rate=rate
    )
    settings = collector_config.Settings(interval=0, count=count, duplicate_rate=rate)
    recorder = Recorder(real_client(backend, profile, key))
    summary = collector.Simulator(recorder, generator, settings, out=lambda _: None, sleep=lambda _: None).run()
    return summary, recorder.log


def scalar(db, sql, **params):
    return db.scalar(text(sql), params)


def test_generated_events_are_accepted_and_stored_in_mysql(backend, db):
    before = scalar(db, "SELECT COUNT(*) FROM network_history")
    summary, log = simulate(backend, count=60)

    assert summary.sent == 60 and summary.rejected == 0 and summary.errors == 0 and summary.ok
    assert summary.stored + summary.duplicate == 60
    assert summary.stored > 20 and summary.duplicate > 0
    assert scalar(db, "SELECT COUNT(*) FROM network_history") == before + summary.stored

    stored_ids = [result.history_id for _, result in log if result.outcome == api_client.STORED]
    assert len(stored_ids) == len(set(stored_ids)) == summary.stored
    rows = db.execute(text("SELECT history_id FROM network_history WHERE history_id IN :ids").bindparams(
        __import__("sqlalchemy").bindparam("ids", expanding=True)), {"ids": stored_ids}).all()
    assert len(rows) == summary.stored


def test_the_api_key_decides_the_node_and_relationships_are_consistent(backend, db):
    devices_before = scalar(db, "SELECT COUNT(*) FROM devices")
    _, log = simulate(backend, profile="lab-b", count=50)
    stored = [result.history_id for _, result in log if result.outcome == api_client.STORED]

    rows = db.execute(
        text(
            "SELECT h.node_id, dv.node_id AS device_node, dv.device_identifier, d.ip_address, d.domain "
            "FROM network_history h JOIN devices dv ON dv.device_id = h.device_id "
            "JOIN destinations d ON d.destination_id = h.destination_id WHERE h.history_id >= :first"
        ),
        {"first": min(stored)},
    ).mappings().all()
    assert len(rows) >= len(stored)
    ours = [r for r in rows if r["device_identifier"].startswith("PC-LAB-B-")]
    assert len(ours) == len(stored)
    assert {r["node_id"] for r in ours} == {NODE_IDS["lab-b"]}
    assert all(r["node_id"] == r["device_node"] for r in rows)
    assert scalar(db, "SELECT COUNT(*) FROM devices") == devices_before


def test_each_profile_and_key_pair_lands_on_its_own_node(backend, db):
    for profile, node_id in NODE_IDS.items():
        _, log = simulate(backend, profile=profile, count=12, rate=0)
        first = next(r.history_id for _, r in log if r.outcome == api_client.STORED)
        assert scalar(db, "SELECT node_id FROM network_history WHERE history_id = :i", i=first) == node_id


def test_last_seen_values_follow_the_newest_stored_event(backend, db):
    recent = datetime.now().replace(microsecond=0) - timedelta(minutes=30)
    _, log = simulate(backend, count=40, rate=0.2, start=recent)
    assert any(result.outcome == api_client.STORED for _, result in log)

    newest_for_node = scalar(db, "SELECT MAX(observed_at) FROM network_history WHERE node_id = 1")
    assert scalar(db, "SELECT last_seen FROM nodes WHERE node_id = 1") == newest_for_node
    device_rows = db.execute(
        text(
            "SELECT dv.last_seen, MAX(h.observed_at) AS newest FROM devices dv JOIN network_history h ON h.device_id = dv.device_id "
            "WHERE dv.node_id = 1 GROUP BY dv.device_id, dv.last_seen"
        )
    ).all()
    assert device_rows and all(row.last_seen == row.newest for row in device_rows)
    dest_rows = db.execute(
        text(
            "SELECT d.last_seen, MAX(h.observed_at) AS newest FROM destinations d JOIN network_history h ON h.destination_id = d.destination_id "
            "GROUP BY d.destination_id, d.last_seen"
        )
    ).all()
    assert dest_rows and all(row.last_seen == row.newest for row in dest_rows)
    assert scalar(db, "SELECT last_used_at FROM collector_api_keys WHERE node_id = 1") is not None


def test_repeats_within_30_seconds_are_deduplicated_and_nothing_breaks_the_rule(backend, db):
    _, log = simulate(backend, count=80, rate=0.4, seed=5)

    for _, result in log:
        if result.outcome == api_client.DUPLICATE:
            assert result.duplicate_of is not None and result.history_id is None
    outcomes = {}
    for payload, result in log:
        key = (payload["deviceIdentifier"], payload["destinationIp"], payload.get("domain"))
        outcomes.setdefault(key, []).append((datetime.fromisoformat(payload["timestamp"]), result.outcome))
    for events in outcomes.values():
        last_stored = None
        for stamp, outcome in events:
            within = last_stored is not None and (stamp - last_stored).total_seconds() <= 30
            assert outcome == (api_client.DUPLICATE if within else api_client.STORED)
            if outcome == api_client.STORED:
                last_stored = stamp

    violations = scalar(
        db,
        "SELECT COUNT(*) FROM network_history a JOIN network_history b ON a.device_id=b.device_id "
        "AND a.destination_id=b.destination_id AND b.observed_at > a.observed_at "
        "AND b.observed_at <= a.observed_at + INTERVAL 30 SECOND",
    )
    assert violations == 0


def test_the_30_second_demo_matches_the_backend_and_stores_three_rows(backend, db):
    lines = []
    assert collector.run_dedup_demo(real_client(backend), event_generator.PROFILES["lab-a"], out=lines.append) is True
    assert sum("ok" == line.split()[-1] for line in lines[2:9]) == 7
    domain = lines[0].rsplit("-> ", 1)[1]
    demo_rows = scalar(db, "SELECT COUNT(*) FROM network_history h JOIN destinations d USING (destination_id) WHERE d.domain = :d", d=domain)
    assert demo_rows == 3


def test_an_event_after_more_than_30_seconds_is_accepted_again(backend):
    client = real_client(backend)
    device, destination = event_generator.PROFILES["lab-a"].devices()[0], event_generator.DESTINATIONS[0]
    base = datetime.now().replace(microsecond=0) - timedelta(hours=1)
    send = lambda seconds: client.send_event(event_generator.build_payload(device, destination, base + timedelta(seconds=seconds)))  # noqa: E731
    assert [send(0).outcome, send(10).outcome, send(31).outcome] == [api_client.STORED, api_client.DUPLICATE, api_client.STORED]


def test_bad_and_revoked_keys_are_rejected_cleanly(backend, db):
    before = scalar(db, "SELECT COUNT(*) FROM network_history")
    summary, log = simulate(backend, count=10, key="not-a-real-key")
    assert len(log) == 1 and "authentication failed (401)" in summary.aborted and not summary.ok
    assert log[0][1].outcome == api_client.AUTH_FAILED

    db.execute(text("UPDATE collector_api_keys SET status='REVOKED', revoked_at=NOW() WHERE node_id = 1"))
    summary, log = simulate(backend, count=10)
    assert len(log) == 1 and log[0][1].outcome == api_client.AUTH_FAILED and log[0][1].status_code == 401
    assert scalar(db, "SELECT COUNT(*) FROM network_history") == before


def test_a_disabled_node_stops_the_simulator(backend, db):
    db.execute(text("UPDATE nodes SET status='INACTIVE' WHERE node_id = 1"))
    summary, log = simulate(backend, count=10)
    assert log[0][1].status_code == 403 and "disabled" in log[0][1].message and summary.aborted


def test_the_backend_refuses_a_smuggled_node_id_and_bad_data_without_crashing_the_client(backend, db):
    client = real_client(backend)
    good = event_generator.build_payload(
        event_generator.PROFILES["lab-a"].devices()[0], event_generator.DESTINATIONS[0], datetime.now().replace(microsecond=0)
    )
    spoofed = client.send_event({**good, "nodeId": 2})
    assert (spoofed.outcome, spoofed.status_code) == (api_client.REJECTED, 422)
    assert "nodeId" in spoofed.message and "not permitted" in spoofed.message

    bad_ip = client.send_event({**good, "deviceIp": "999.1.1.1"})
    assert bad_ip.outcome == api_client.REJECTED and "deviceIp" in bad_ip.message

    future = client.send_event({**good, "timestamp": (datetime.now() + timedelta(hours=2)).isoformat(timespec="seconds")})
    assert future.outcome == api_client.REJECTED and "future" in future.message


def test_check_api_key_stores_nothing(backend, db):
    before = scalar(db, "SELECT COUNT(*) FROM network_history")
    assert real_client(backend).check_api_key().outcome == api_client.KEY_OK
    assert real_client(backend, key="wrong").check_api_key().outcome == api_client.AUTH_FAILED
    assert scalar(db, "SELECT COUNT(*) FROM network_history") == before


def test_secrets_are_not_present_in_anything_the_simulator_reports(backend, capsys):
    settings = collector_config.Settings(api_key=KEYS["lab-a"])
    assert KEYS["lab-a"] not in repr(settings)
    simulate(backend, count=15)
    simulate(backend, count=3, key="leak-me-not")
    captured = capsys.readouterr()
    assert KEYS["lab-a"] not in captured.out + captured.err and "leak-me-not" not in captured.out + captured.err
