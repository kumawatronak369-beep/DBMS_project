from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, get_settings
from app.core.security import ensure_jwt_secret_configured
from app.db.session import engine
from app.main import create_app

from .conftest import requires_db

INJECTIONS = [
    "' OR '1'='1",
    "'; DROP TABLE users; --",
    '" OR ""="',
    "1 UNION SELECT user_id, password_hash FROM users --",
    "%' OR 1=1 --",
    "\\",
    "'",
    "%",
    "_",
]


@pytest.mark.parametrize(
    "secret",
    [
        "change-me-to-a-long-random-string-of-at-least-32-chars",
        "CHANGEME" + "x" * 30,
        "this-is-an-example-secret-value-0123456789",
    ],
)
def test_placeholder_jwt_secret_is_refused(monkeypatch, secret):
    monkeypatch.setattr(get_settings(), "jwt_secret", secret)
    with pytest.raises(RuntimeError, match="placeholder"):
        ensure_jwt_secret_configured()


def test_the_shipped_env_example_cannot_be_used_as_is(monkeypatch):
    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    secret = next(line.split("=", 1)[1] for line in example.splitlines() if line.startswith("JWT_SECRET="))
    monkeypatch.setattr(get_settings(), "jwt_secret", secret)
    with pytest.raises(RuntimeError):
        ensure_jwt_secret_configured()


def test_bcrypt_work_factor_has_a_floor():
    with pytest.raises(ValidationError):
        Settings(bcrypt_rounds=4)
    assert Settings(bcrypt_rounds=10).bcrypt_rounds == 10


def test_the_database_password_is_masked_in_the_url_repr():
    assert "hunter2" not in repr(Settings(database_password="hunter2").sqlalchemy_url)


@requires_db
def test_sql_errors_do_not_echo_bound_values():
    with pytest.raises(SQLAlchemyError) as caught:
        with engine.connect() as connection:
            connection.execute(
                text("SELECT * FROM table_that_does_not_exist WHERE x = :v"), {"v": "secret@example.org"}
            )
    assert "secret@example.org" not in str(caught.value)


def test_docs_are_on_by_default_and_can_be_switched_off(monkeypatch):
    with TestClient(create_app()) as on:
        assert on.get("/docs").status_code == 200
        assert on.get("/openapi.json").status_code == 200

    monkeypatch.setattr(get_settings(), "enable_api_docs", False)
    with TestClient(create_app()) as off:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert off.get(path).status_code == 404
        assert off.get("/api/health").status_code == 200


def test_api_responses_carry_security_headers(anon_client):
    for response in (anon_client.get("/api/health"), anon_client.get("/api/nodes"), anon_client.get("/api/nope")):
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["cache-control"] == "no-store"


def test_cors_only_allows_the_configured_origin(anon_client):
    origin = get_settings().cors_origin_list[0]
    allowed = anon_client.options("/api/nodes", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})
    assert allowed.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in allowed.headers

    denied = anon_client.options(
        "/api/nodes", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"}
    )
    assert "access-control-allow-origin" not in denied.headers


def test_page_number_has_an_upper_bound(client):
    assert client.get("/api/nodes", params={"page": 1_000_001}).status_code == 422
    assert client.get("/api/nodes", params={"page": 10**30}).status_code == 422
    assert client.get("/api/nodes", params={"pageSize": 101}).status_code == 422


def test_oversized_date_parameters_are_rejected(client):
    assert client.get("/api/history", params={"startDate": "2" * 5000}).status_code == 422


def test_invalid_input_is_not_echoed_back(client):
    response = client.get("/api/history", params={"startDate": "<script>alert(1)</script>"})
    assert response.status_code == 400
    assert "<script>" not in response.text


@requires_db
@pytest.mark.parametrize("payload", INJECTIONS)
@pytest.mark.parametrize(
    "path,param",
    [
        ("/api/history", "q"),
        ("/api/devices", "search"),
        ("/api/destinations", "search"),
        ("/api/nodes", "search"),
        ("/api/users", "search"),
    ],
)
def test_search_parameters_are_treated_as_plain_text(client, db, path, param, payload):
    users_before = db.scalar(text("SELECT COUNT(*) FROM users"))
    response = client.get(path, params={param: payload})
    assert response.status_code == 200, response.text
    for leak in ("password_hash", "$2b$", "SQL syntax", "pymysql", "Traceback"):
        assert leak not in response.text
    assert db.scalar(text("SELECT COUNT(*) FROM users")) == users_before
    if payload in ("' OR '1'='1", "%' OR 1=1 --"):
        assert response.json()["total"] == 0


@requires_db
@pytest.mark.parametrize("payload", INJECTIONS)
def test_login_is_not_injectable(anon_client, payload):
    response = anon_client.post("/api/auth/login", json={"email": payload, "password": payload})
    assert response.status_code in (401, 422)
    assert "access_token" not in response.text


@requires_db
@pytest.mark.parametrize("bad_id", ["1 OR 1=1", "-1", "0", "abc", "1;DROP TABLE nodes", "99999999999999999999"])
def test_path_ids_are_validated(client, bad_id):
    for resource in ("nodes", "devices", "destinations", "history", "users"):
        assert client.get(f"/api/{resource}/{bad_id}").status_code in (404, 422)
