from datetime import timedelta

from sqlalchemy import text

from tests.conftest import requires_db

pytestmark = requires_db


def test_history_total_matches_database(client, db):
    body = client.get("/api/history", params={"pageSize": 10}).json()
    assert body["total"] == db.scalar(text("SELECT COUNT(*) FROM network_history"))
    assert len(body["items"]) == 10
    times = [e["observed_at"] for e in body["items"]]
    assert times == sorted(times, reverse=True)
    first = body["items"][0]
    assert {"device_identifier", "device_ip", "node_name", "destination_ip", "domain", "category"} <= set(first)
    assert "domain_key" not in first


def test_history_pages_do_not_overlap_and_cover_everything(client):
    page_size = 100
    seen: list[int] = []
    page = 1
    while True:
        body = client.get("/api/history", params={"page": page, "pageSize": page_size}).json()
        seen.extend(e["history_id"] for e in body["items"])
        if page * page_size >= body["total"]:
            break
        page += 1
    assert len(seen) == len(set(seen)) == body["total"]


def test_history_filters_match_sql(client, db):
    by_device = client.get("/api/history", params={"deviceId": 1}).json()
    assert by_device["total"] == db.scalar(text("SELECT COUNT(*) FROM network_history WHERE device_id = 1"))
    assert all(e["device_id"] == 1 for e in by_device["items"])

    by_node = client.get("/api/history", params={"nodeId": 2}).json()
    assert by_node["total"] == db.scalar(text("SELECT COUNT(*) FROM network_history WHERE node_id = 2"))

    by_domain = client.get("/api/history", params={"domain": "github"}).json()
    expected = db.scalar(
        text(
            "SELECT COUNT(*) FROM network_history h JOIN destinations d USING (destination_id) "
            "WHERE d.domain LIKE '%github%'"
        )
    )
    assert by_domain["total"] == expected > 0
    assert all("github" in e["domain"] for e in by_domain["items"])

    combined = client.get("/api/history", params={"nodeId": 1, "domain": "github"}).json()
    assert 0 < combined["total"] < by_domain["total"]

    by_destination = client.get("/api/history", params={"destinationId": 12}).json()
    assert by_destination["total"] > 0 and all(e["domain"] is None for e in by_destination["items"])


def test_history_text_search(client, db):
    by_device_text = client.get("/api/history", params={"q": "LAB-A-001"}).json()
    assert by_device_text["total"] == db.scalar(
        text("SELECT COUNT(*) FROM network_history WHERE device_id = 1")
    )
    by_ip = client.get("/api/history", params={"q": "192.168.10.21"}).json()
    assert by_ip["total"] > 0
    assert all(e["device_ip"] == "192.168.10.21" for e in by_ip["items"])
    assert client.get("/api/history", params={"q": "no-such-thing"}).json()["total"] == 0
    assert client.get("/api/history", params={"q": "%"}).json()["total"] == 0


def test_history_date_filtering(client, db):
    first_day = db.scalar(text("SELECT DATE(MIN(observed_at)) FROM network_history"))
    d1, d2 = first_day + timedelta(days=1), first_day + timedelta(days=2)

    body = client.get(
        "/api/history", params={"startDate": f"{d1}T00:00:00", "endDate": f"{d2}T23:59:59"}
    ).json()
    expected = db.scalar(
        text("SELECT COUNT(*) FROM network_history WHERE observed_at BETWEEN :a AND :b"),
        {"a": f"{d1} 00:00:00", "b": f"{d2} 23:59:59"},
    )
    assert body["total"] == expected > 0
    assert all(str(d1) <= e["observed_at"][:10] <= str(d2) for e in body["items"])

    day = client.get("/api/history", params={"startDate": str(d1), "endDate": str(d1)}).json()
    expected_day = db.scalar(text("SELECT COUNT(*) FROM network_history WHERE DATE(observed_at) = :d"), {"d": d1})
    assert day["total"] == expected_day > 0

    recent = client.get("/api/history", params={"range": "24h"}).json()
    assert recent["total"] == db.scalar(
        text("SELECT COUNT(*) FROM network_history WHERE observed_at >= NOW() - INTERVAL 24 HOUR")
    )


def test_history_bad_dates_are_400(client):
    assert client.get("/api/history", params={"startDate": "yesterday"}).status_code == 400
    both = client.get("/api/history", params={"startDate": "2026-09-19", "endDate": "2026-09-01"})
    assert both.status_code == 400
    assert "startDate" in both.json()["detail"]


def test_history_event_detail(client):
    event = client.get("/api/history/1").json()
    assert event["history_id"] == 1 and event["node_code"] and event["device_identifier"]
    assert client.get("/api/history/99999999").status_code == 404


def test_error_responses_never_contain_a_stack_trace(client):
    assert "Traceback" not in client.get("/api/history/99999999").text
