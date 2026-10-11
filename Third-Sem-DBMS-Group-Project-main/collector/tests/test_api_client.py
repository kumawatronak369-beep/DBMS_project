import requests

import api_client as ac
from tests.conftest import SECRET_KEY, FakeResponse, FakeSession

PAYLOAD = {
    "deviceIdentifier": "PC-LAB-A-001",
    "deviceIp": "192.168.10.21",
    "destinationIp": "203.0.113.10",
    "domain": "example.com",
    "timestamp": "2026-09-20T10:00:00",
}


def client_with(*replies):
    session = FakeSession(replies)
    return ac.CollectorClient("http://backend.test/", SECRET_KEY, timeout=3, session=session), session


def test_a_stored_event_is_reported_as_stored():
    client, _ = client_with(FakeResponse(201, {"status": "STORED", "history_id": 77}))
    result = client.send_event(PAYLOAD)
    assert (result.outcome, result.status_code, result.history_id) == (ac.STORED, 201, 77)


def test_a_duplicate_is_reported_as_a_duplicate_not_an_error():
    client, _ = client_with(FakeResponse(200, {"status": "DUPLICATE", "duplicate_of": 41, "history_id": None}))
    result = client.send_event(PAYLOAD)
    assert (result.outcome, result.duplicate_of) == (ac.DUPLICATE, 41)


def test_the_request_goes_to_the_events_endpoint_with_the_key_header_and_no_node():
    client, session = client_with()
    client.send_event(PAYLOAD)
    sent = session.posts[0]
    assert sent["url"] == "http://backend.test/api/collector/events"
    assert sent["headers"] == {"X-API-Key": SECRET_KEY}
    assert sent["json"] == PAYLOAD and "nodeId" not in sent["json"]
    assert sent["timeout"] == 3


def test_authentication_failures_are_flagged_as_not_retryable():
    for status, detail in ((401, "Invalid or missing API key"), (403, "This node is disabled")):
        client, _ = client_with(FakeResponse(status, {"detail": detail}))
        result = client.send_event(PAYLOAD)
        assert (result.outcome, result.status_code, result.message) == (ac.AUTH_FAILED, status, detail)


def test_validation_errors_are_reported_as_rejected_with_a_readable_reason():
    body = {"detail": [{"loc": ["body", "deviceIp"], "msg": "must be a valid IP", "type": "value_error"}]}
    client, _ = client_with(FakeResponse(422, body))
    result = client.send_event(PAYLOAD)
    assert (result.outcome, result.status_code) == (ac.REJECTED, 422)
    assert result.message == "deviceIp: must be a valid IP"


def test_server_errors_and_unavailability_are_transient_errors():
    for status in (500, 502, 503):
        client, _ = client_with(FakeResponse(status, {"detail": "Temporarily unable, please retry"}))
        assert client.send_event(PAYLOAD).outcome == ac.ERROR


def test_network_failures_never_raise():
    for failure in (requests.ConnectionError("boom"), requests.Timeout("slow"), requests.exceptions.SSLError("tls")):
        client, _ = client_with(failure)
        result = client.send_event(PAYLOAD)
        assert result.outcome == ac.ERROR and result.status_code is None
        assert "cannot reach the backend" in result.message


def test_an_unreadable_body_is_handled():
    client, _ = client_with(FakeResponse(502, None), FakeResponse(400, None))
    assert client.send_event(PAYLOAD).outcome == ac.ERROR
    assert client.send_event(PAYLOAD).outcome == ac.REJECTED


def test_an_unexpected_success_body_is_not_mistaken_for_a_stored_event():
    client, _ = client_with(FakeResponse(201, None))
    assert client.send_event(PAYLOAD).outcome == ac.REJECTED


def test_the_key_is_scrubbed_if_a_message_ever_contains_it():
    client, _ = client_with(FakeResponse(400, {"detail": f"bad key {SECRET_KEY}"}))
    result = client.send_event(PAYLOAD)
    assert SECRET_KEY not in result.message and "***" in result.message


def test_secrets_never_appear_in_any_result_or_repr():
    client, _ = client_with(FakeResponse(401, {"detail": "Invalid or missing API key"}), requests.ConnectionError(SECRET_KEY))
    for result in (client.send_event(PAYLOAD), client.send_event(PAYLOAD)):
        assert SECRET_KEY not in repr(result)


def test_check_api_key_accepts_a_key_when_the_empty_event_is_refused_with_422():
    client, session = client_with(FakeResponse(422, {"detail": [{"loc": ["body"], "msg": "Field required"}]}))
    result = client.check_api_key()
    assert result.outcome == ac.KEY_OK
    assert session.posts[0]["json"] == {}


def test_check_api_key_reports_a_bad_key():
    client, _ = client_with(FakeResponse(401, {"detail": "Invalid or missing API key"}))
    assert client.check_api_key().outcome == ac.AUTH_FAILED


def test_check_health():
    assert client_with(FakeResponse(200, {"status": "ok"}))[0].check_health() is True
    assert client_with(FakeResponse(503))[0].check_health() is False
    assert client_with(requests.ConnectionError("down"))[0].check_health() is False
