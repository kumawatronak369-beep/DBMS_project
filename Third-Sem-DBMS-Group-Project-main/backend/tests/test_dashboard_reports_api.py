from sqlalchemy import text

from tests.conftest import requires_db

pytestmark = requires_db


def _total_events(db) -> int:
    return db.scalar(text("SELECT COUNT(*) FROM network_history"))


def test_dashboard_summary_matches_database(client, db):
    summary = client.get("/api/dashboard/summary").json()
    assert summary == {
        "active_nodes": db.scalar(text("SELECT COUNT(*) FROM nodes WHERE status = 'ACTIVE'")),
        "registered_devices": db.scalar(text("SELECT COUNT(*) FROM devices")),
        "todays_events": db.scalar(text("SELECT COUNT(*) FROM network_history WHERE observed_at >= CURDATE()")),
        "known_destinations": db.scalar(text("SELECT COUNT(*) FROM destinations")),
    }


def test_summary_reflects_a_status_change(client):
    before = client.get("/api/dashboard/summary").json()["active_nodes"]
    client.patch("/api/nodes/1/status", json={"status": "INACTIVE"})
    assert client.get("/api/dashboard/summary").json()["active_nodes"] == before - 1


def test_dashboard_top_lists(client):
    destinations = client.get("/api/dashboard/top-destinations").json()
    assert len(destinations) == 5
    counts = [d["event_count"] for d in destinations]
    assert counts == sorted(counts, reverse=True)
    assert destinations[0]["domain"] == "google.com"

    devices = client.get("/api/dashboard/top-devices", params={"limit": 3}).json()
    assert len(devices) == 3
    assert [d["event_count"] for d in devices] == sorted((d["event_count"] for d in devices), reverse=True)
    assert client.get("/api/dashboard/top-devices", params={"limit": 0}).status_code == 422


def test_dashboard_activity_defaults_to_last_24_hours_hourly(client, db):
    series = client.get("/api/dashboard/activity").json()
    assert series["bucket"] == "hour"
    assert 24 <= len(series["points"]) <= 26
    total_24h = db.scalar(text("SELECT COUNT(*) FROM network_history WHERE observed_at >= NOW() - INTERVAL 24 HOUR"))
    assert sum(p["event_count"] for p in series["points"]) == total_24h


def test_report_top_destinations_and_devices(client, db):
    rows = client.get("/api/reports/top-destinations", params={"limit": 100}).json()
    assert len(rows) == db.scalar(text("SELECT COUNT(DISTINCT destination_id) FROM network_history"))
    assert sum(r["event_count"] for r in rows) == _total_events(db)
    top = rows[0]
    assert top["unique_devices"] == db.scalar(
        text("SELECT COUNT(DISTINCT device_id) FROM network_history WHERE destination_id = :d"),
        {"d": top["destination_id"]},
    )

    devices = client.get("/api/reports/top-devices", params={"limit": 100}).json()
    assert len(devices) == 17 and sum(r["event_count"] for r in devices) == _total_events(db)
    assert all(r["node_name"] for r in devices)


def test_report_activity_by_node(client, db):
    rows = client.get("/api/reports/activity-by-node").json()
    assert len(rows) == 4 and sum(r["event_count"] for r in rows) == _total_events(db)
    assert [r["event_count"] for r in rows] == sorted((r["event_count"] for r in rows), reverse=True)
    assert rows[0]["unique_devices"] <= 5

    empty = client.get("/api/reports/activity-by-node", params={"startDate": "2000-01-01", "endDate": "2000-01-02"}).json()
    assert len(empty) == 4 and all(r["event_count"] == 0 and r["unique_devices"] == 0 for r in empty)


def test_report_activity_over_time_ranges(client, db):
    day = client.get("/api/reports/activity-over-time", params={"range": "24h"}).json()
    assert day["bucket"] == "hour"

    week = client.get("/api/reports/activity-over-time", params={"range": "7d"}).json()
    assert week["bucket"] == "day" and 7 <= len(week["points"]) <= 9
    assert sum(p["event_count"] for p in week["points"]) == db.scalar(
        text("SELECT COUNT(*) FROM network_history WHERE observed_at >= NOW() - INTERVAL 7 DAY")
    )

    month = client.get("/api/reports/activity-over-time", params={"range": "30d"}).json()
    assert month["bucket"] == "day" and 30 <= len(month["points"]) <= 32
    assert any(p["event_count"] == 0 for p in month["points"])

    first_day = db.scalar(text("SELECT DATE(MIN(observed_at)) FROM network_history"))
    custom = client.get(
        "/api/reports/activity-over-time", params={"startDate": str(first_day), "endDate": str(first_day)}
    ).json()
    assert custom["bucket"] == "hour" and len(custom["points"]) == 24
    assert sum(p["event_count"] for p in custom["points"]) == db.scalar(
        text("SELECT COUNT(*) FROM network_history WHERE DATE(observed_at) = :d"), {"d": first_day}
    )


def test_report_activity_over_time_for_one_node(client, db):
    body = client.get("/api/reports/activity-over-time", params={"range": "30d", "nodeId": 3}).json()
    assert sum(p["event_count"] for p in body["points"]) == db.scalar(
        text("SELECT COUNT(*) FROM network_history WHERE node_id = 3 AND observed_at >= NOW() - INTERVAL 30 DAY")
    )
    assert client.get("/api/reports/activity-over-time", params={"nodeId": 99999}).status_code == 404


def test_invalid_range_preset_is_rejected(client):
    assert client.get("/api/reports/top-devices", params={"range": "1y"}).status_code == 422
