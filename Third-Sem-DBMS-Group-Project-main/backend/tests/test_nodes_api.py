from sqlalchemy import text

from tests.conftest import requires_db

pytestmark = requires_db

NEW_NODE = {
    "node_code": "TEST-01",
    "node_name": "Test Node",
    "ip_address": "10.99.0.1",
    "location": "Test Lab",
    "description": "  created by a test  ",
}


def test_list_nodes_with_device_counts(client, db):
    body = client.get("/api/nodes").json()
    assert body["total"] == db.scalar(text("SELECT COUNT(*) FROM nodes"))
    assert sum(n["device_count"] for n in body["items"]) == db.scalar(text("SELECT COUNT(*) FROM devices"))
    assert [n["node_name"] for n in body["items"]] == sorted(n["node_name"] for n in body["items"])


def test_list_nodes_pagination_search_and_status_filter(client):
    page = client.get("/api/nodes", params={"pageSize": 2, "page": 2}).json()
    assert page["page"] == 2 and page["page_size"] == 2 and len(page["items"]) == 2
    assert client.get("/api/nodes", params={"search": "lab"}).json()["total"] == 2
    assert client.get("/api/nodes", params={"status": "OFFLINE"}).json()["total"] == 0
    assert client.get("/api/nodes", params={"status": "BOGUS"}).status_code == 422
    assert client.get("/api/nodes", params={"pageSize": 1000}).status_code == 422


def test_search_treats_like_wildcards_literally(client):
    assert client.get("/api/nodes", params={"search": "%"}).json()["total"] == 0
    assert client.get("/api/nodes", params={"search": "_"}).json()["total"] == 0


def test_node_detail(client, db):
    node = client.get("/api/nodes/1").json()
    assert node["node_code"] == "LAB-A"
    assert node["device_count"] == db.scalar(text("SELECT COUNT(*) FROM devices WHERE node_id = 1"))
    assert node["event_count"] == db.scalar(text("SELECT COUNT(*) FROM network_history WHERE node_id = 1"))
    assert len(node["recent_activity"]) == 10
    times = [e["observed_at"] for e in node["recent_activity"]]
    assert times == sorted(times, reverse=True)
    assert all(e["node_id"] == 1 for e in node["recent_activity"])
    assert len(node["activity_by_day"]) == 7


def test_node_not_found_and_bad_id(client):
    assert client.get("/api/nodes/99999").status_code == 404
    assert client.get("/api/nodes/0").status_code == 422
    assert client.get("/api/nodes/abc").status_code == 422


def test_create_read_update_and_status_change(client):
    created = client.post("/api/nodes", json=NEW_NODE)
    assert created.status_code == 201
    node = created.json()
    assert node["status"] == "ACTIVE" and node["last_seen"] is None
    assert node["description"] == "created by a test"
    node_id = node["node_id"]

    detail = client.get(f"/api/nodes/{node_id}").json()
    assert detail["device_count"] == 0 and detail["event_count"] == 0
    assert detail["recent_activity"] == [] and len(detail["activity_by_day"]) == 7

    updated = client.put(f"/api/nodes/{node_id}", json={**NEW_NODE, "node_name": "Renamed", "description": ""})
    assert updated.status_code == 200
    assert updated.json()["node_name"] == "Renamed" and updated.json()["description"] is None

    disabled = client.patch(f"/api/nodes/{node_id}/status", json={"status": "INACTIVE"})
    assert disabled.status_code == 200 and disabled.json()["status"] == "INACTIVE"
    assert client.get("/api/nodes", params={"status": "INACTIVE"}).json()["total"] == 1


def test_duplicate_node_code_is_409(client):
    assert client.post("/api/nodes", json=NEW_NODE).status_code == 201
    assert client.post("/api/nodes", json=NEW_NODE).status_code == 409
    other = client.post("/api/nodes", json={**NEW_NODE, "node_code": "TEST-02"}).json()
    clash = client.put(f"/api/nodes/{other['node_id']}", json=NEW_NODE)
    assert clash.status_code == 409
    assert client.put(f"/api/nodes/{other['node_id']}", json={**NEW_NODE, "node_code": "TEST-02"}).status_code == 200


def test_validation_errors(client):
    assert client.post("/api/nodes", json={**NEW_NODE, "ip_address": "not-an-ip"}).status_code == 422
    assert client.post("/api/nodes", json={**NEW_NODE, "ip_address": "999.1.1.1"}).status_code == 422
    assert client.post("/api/nodes", json={**NEW_NODE, "node_code": ""}).status_code == 422
    assert client.post("/api/nodes", json={"node_code": "X"}).status_code == 422
    assert client.post("/api/nodes", json={**NEW_NODE, "ip_address": "fe80::1"}).status_code == 201


def test_update_and_status_on_missing_node(client):
    assert client.put("/api/nodes/99999", json=NEW_NODE).status_code == 404
    assert client.patch("/api/nodes/99999/status", json={"status": "OFFLINE"}).status_code == 404
    assert client.patch("/api/nodes/1/status", json={"status": "DELETED"}).status_code == 422


def test_nodes_cannot_be_deleted(client):
    assert client.delete("/api/nodes/1").status_code == 405
