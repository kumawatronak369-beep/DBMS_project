from sqlalchemy import text

from tests.conftest import requires_db

pytestmark = requires_db


def test_list_devices_with_node_info_and_filters(client, db):
    body = client.get("/api/devices", params={"pageSize": 100}).json()
    assert body["total"] == db.scalar(text("SELECT COUNT(*) FROM devices")) == len(body["items"])
    assert all(d["node_name"] and d["node_code"] for d in body["items"])

    assert client.get("/api/devices", params={"nodeId": 1}).json()["total"] == 5
    assert client.get("/api/devices", params={"search": "PC-ADMIN"}).json()["total"] == 3
    assert client.get("/api/devices", params={"search": "192.168.30."}).json()["total"] == 4
    assert client.get("/api/devices", params={"status": "UNKNOWN"}).json()["total"] == 0


def test_device_detail(client, db):
    device = client.get("/api/devices/1").json()
    assert device["device_identifier"] == "PC-LAB-A-001" and device["node_code"] == "LAB-A"
    assert device["total_events"] == db.scalar(text("SELECT COUNT(*) FROM network_history WHERE device_id = 1"))
    assert len(device["activity_by_day"]) == 7
    assert 0 < len(device["recent_destinations"]) <= 10
    assert sum(d["visits"] for d in device["recent_destinations"]) <= device["total_events"]
    last_visits = [d["last_visit"] for d in device["recent_destinations"]]
    assert last_visits == sorted(last_visits, reverse=True)


def test_device_history_endpoint(client, db):
    body = client.get("/api/devices/1/history", params={"pageSize": 5}).json()
    assert body["total"] == db.scalar(text("SELECT COUNT(*) FROM network_history WHERE device_id = 1"))
    assert len(body["items"]) == 5 and all(e["device_id"] == 1 for e in body["items"])
    assert client.get("/api/devices/99999/history").status_code == 404
    assert client.get("/api/devices/99999").status_code == 404


def test_list_destinations_with_counts(client, db):
    body = client.get("/api/destinations", params={"pageSize": 100}).json()
    assert body["total"] == db.scalar(text("SELECT COUNT(*) FROM destinations"))
    assert sum(d["event_count"] for d in body["items"]) == db.scalar(text("SELECT COUNT(*) FROM network_history"))
    assert all("domain_key" not in d for d in body["items"])

    assert client.get("/api/destinations", params={"category": "DEVELOPMENT"}).json()["total"] == 3
    assert client.get("/api/destinations", params={"search": "github"}).json()["total"] == 1
    assert client.get("/api/destinations", params={"search": "203.0.113."}).json()["total"] == 5


def test_destination_detail_for_named_and_null_domain(client, db):
    github = client.get("/api/destinations/2").json()
    assert github["domain"] == "github.com" and github["category"] == "DEVELOPMENT"
    assert github["event_count"] == db.scalar(text("SELECT COUNT(*) FROM network_history WHERE destination_id = 2"))
    assert github["unique_devices"] == db.scalar(
        text("SELECT COUNT(DISTINCT device_id) FROM network_history WHERE destination_id = 2")
    )
    assert sum(n["event_count"] for n in github["nodes"]) == github["event_count"]
    assert sum(d["access_count"] for d in github["devices"]) == github["event_count"]
    assert len(github["devices"]) == github["unique_devices"]
    counts = [d["access_count"] for d in github["devices"]]
    assert counts == sorted(counts, reverse=True)

    unresolved = client.get("/api/destinations/12").json()
    assert unresolved["domain"] is None and unresolved["ip_address"] == "192.0.2.77"
    assert "domain_key" not in unresolved


def test_destination_history_endpoint(client, db):
    body = client.get("/api/destinations/2/history", params={"pageSize": 3}).json()
    assert body["total"] == db.scalar(text("SELECT COUNT(*) FROM network_history WHERE destination_id = 2"))
    assert len(body["items"]) == 3 and all(e["destination_id"] == 2 for e in body["items"])
    assert client.get("/api/destinations/99999").status_code == 404
    assert client.get("/api/destinations/99999/history").status_code == 404
