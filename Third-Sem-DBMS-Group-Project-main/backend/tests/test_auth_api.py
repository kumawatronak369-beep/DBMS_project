import logging
import re
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.security import ALGORITHM, create_access_token, decode_access_token
from app.main import app
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    ANALYST_EMAIL,
    ANALYST_PASSWORD,
    bearer,
    requires_db,
)

pytestmark = requires_db


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch):
    monkeypatch.setattr(get_settings(), "bcrypt_rounds", 4)


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_successful_login(anon_client, db):
    response = login(anon_client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 3600
    assert decode_access_token(body["access_token"]) == body["user"]["user_id"]
    assert body["user"]["email"] == ADMIN_EMAIL and body["user"]["role"] == "ADMIN"
    assert body["user"]["last_login"] is not None
    assert db.scalar(text("SELECT last_login FROM users WHERE email = :e"), {"e": ADMIN_EMAIL}) is not None


def test_login_never_returns_password_material(anon_client):
    text_body = login(anon_client, ADMIN_EMAIL, ADMIN_PASSWORD).text
    assert "password" not in text_body.lower() and "$2b$" not in text_body
    assert ADMIN_PASSWORD not in text_body


def test_login_email_is_case_and_whitespace_insensitive(anon_client):
    assert login(anon_client, f"  {ADMIN_EMAIL.upper()} ", ADMIN_PASSWORD).status_code == 200


def test_analyst_can_log_in(anon_client):
    body = login(anon_client, ANALYST_EMAIL, ANALYST_PASSWORD).json()
    assert body["user"]["role"] == "ANALYST"


def test_wrong_password_and_unknown_email_look_identical(anon_client):
    wrong = login(anon_client, ADMIN_EMAIL, "not-the-password")
    unknown = login(anon_client, "nobody@netmonitor.local", "not-the-password")
    for response in (wrong, unknown):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json() == {"detail": "Invalid email or password"}
        assert "access_token" not in response.text


def test_login_input_validation(anon_client):
    assert anon_client.post("/api/auth/login", json={"email": ADMIN_EMAIL}).status_code == 422
    assert anon_client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ""}).status_code == 422
    assert anon_client.post("/api/auth/login", json={}).status_code == 422
    too_long = login(anon_client, ADMIN_EMAIL, "x" * 200)
    assert too_long.status_code == 422 and "x" * 20 not in too_long.text


def test_overlong_password_within_field_limit_is_a_normal_401(anon_client):
    assert login(anon_client, ADMIN_EMAIL, "x" * 100).status_code == 401


def test_disabled_account_cannot_log_in(client, anon_client):
    created = client.post(
        "/api/users",
        json={"name": "Temp", "email": "temp@netmonitor.local", "password": "Temp-Pass-123", "role": "ANALYST"},
    ).json()
    client.patch(f"/api/users/{created['user_id']}/status", json={"status": "DISABLED"})

    assert login(anon_client, "temp@netmonitor.local", "Temp-Pass-123").status_code == 403
    assert login(anon_client, "temp@netmonitor.local", "wrong").status_code == 401


def test_passwords_are_never_logged(anon_client, caplog):
    secret = "Log-Me-Not-9x!"
    with caplog.at_level(logging.DEBUG):
        login(anon_client, ADMIN_EMAIL, secret)
        login(anon_client, "nobody@netmonitor.local", secret)
        anon_client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": 5})
    assert secret not in caplog.text


def test_me_returns_the_current_user(client):
    body = client.get("/api/auth/me").json()
    assert body["email"] == ADMIN_EMAIL and body["role"] == "ADMIN"
    assert "password_hash" not in body


def test_full_flow_login_then_use_token(anon_client):
    token = login(anon_client, ANALYST_EMAIL, ANALYST_PASSWORD).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert anon_client.get("/api/auth/me", headers=headers).json()["email"] == ANALYST_EMAIL
    assert anon_client.get("/api/dashboard/summary", headers=headers).status_code == 200


def test_logout(client, anon_client):
    assert client.post("/api/auth/logout").status_code == 204
    assert anon_client.post("/api/auth/logout").status_code == 401


PUBLIC = {("GET", "/api/health"), ("GET", "/api/health/db"), ("POST", "/api/auth/login")}


def _protected_routes():
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api/collector"):
            continue
        for method in operations:
            if (method.upper(), path) not in PUBLIC:
                yield method.upper(), re.sub(r"\{[^}]+\}", "1", path)


def test_every_non_public_route_requires_authentication(anon_client):
    routes = list(_protected_routes())
    assert len(routes) >= 28
    for method, path in routes:
        body = {} if method in {"POST", "PUT", "PATCH"} else None
        response = anon_client.request(method, path, json=body)
        assert response.status_code == 401, f"{method} {path} -> {response.status_code}"
        assert response.headers["www-authenticate"] == "Bearer"


def test_only_liveness_is_public(anon_client, client):
    assert anon_client.get("/api/health").status_code == 200
    assert anon_client.get("/api/health/db").status_code == 401
    assert client.get("/api/health/db").status_code == 200


@pytest.mark.parametrize(
    "header",
    ["Bearer not-a-real-token", "Bearer ", "Basic YWRtaW46YWRtaW4=", "Token abc", "garbage"],
)
def test_malformed_authorization_headers_are_401(anon_client, header):
    assert anon_client.get("/api/nodes", headers={"Authorization": header}).status_code == 401


def test_expired_token_is_401(anon_client, db):
    admin_id = db.scalar(text("SELECT user_id FROM users WHERE email = :e"), {"e": ADMIN_EMAIL})
    token = create_access_token(admin_id, expires_delta=timedelta(seconds=-1))
    assert anon_client.get("/api/nodes", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_signed_with_another_secret_is_401(anon_client):
    forged = jwt.encode(
        {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "x" * 40, algorithm=ALGORITHM
    )
    assert anon_client.get("/api/nodes", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_for_a_user_that_does_not_exist_is_401(anon_client):
    assert anon_client.get("/api/nodes", headers=bearer(99999999)).status_code == 401


def test_a_forged_role_claim_grants_nothing(anon_client, db):
    analyst_id = db.scalar(text("SELECT user_id FROM users WHERE email = :e"), {"e": ANALYST_EMAIL})
    forged = jwt.encode(
        {"sub": str(analyst_id), "role": "ADMIN", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        get_settings().jwt_secret,
        algorithm=ALGORITHM,
    )
    response = anon_client.get("/api/users", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 403


def test_disabling_a_user_invalidates_their_existing_token(client, anon_client):
    created = client.post(
        "/api/users", json={"name": "Temp", "email": "temp2@netmonitor.local", "password": "Temp-Pass-123"}
    ).json()
    token = login(anon_client, "temp2@netmonitor.local", "Temp-Pass-123").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert anon_client.get("/api/nodes", headers=headers).status_code == 200

    client.patch(f"/api/users/{created['user_id']}/status", json={"status": "DISABLED"})
    assert anon_client.get("/api/nodes", headers=headers).status_code == 401


def test_role_change_takes_effect_immediately(client, anon_client):
    created = client.post(
        "/api/users", json={"name": "Temp", "email": "temp3@netmonitor.local", "password": "Temp-Pass-123"}
    ).json()
    token = login(anon_client, "temp3@netmonitor.local", "Temp-Pass-123").json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert anon_client.get("/api/users", headers=headers).status_code == 403

    client.put(
        f"/api/users/{created['user_id']}",
        json={"name": "Temp", "email": "temp3@netmonitor.local", "role": "ADMIN"},
    )
    assert anon_client.get("/api/users", headers=headers).status_code == 200


READ_ENDPOINTS = [
    "/api/auth/me",
    "/api/dashboard/summary",
    "/api/dashboard/activity",
    "/api/dashboard/top-destinations",
    "/api/dashboard/top-devices",
    "/api/nodes",
    "/api/nodes/1",
    "/api/devices",
    "/api/devices/1",
    "/api/devices/1/history",
    "/api/destinations",
    "/api/destinations/1",
    "/api/destinations/1/history",
    "/api/history",
    "/api/history/1",
    "/api/reports/top-destinations",
    "/api/reports/top-devices",
    "/api/reports/activity-by-node",
    "/api/reports/activity-over-time",
]

NEW_NODE = {"node_code": "ROLE-01", "node_name": "Role Test", "ip_address": "10.77.0.1", "location": "Lab"}


@pytest.mark.parametrize("path", READ_ENDPOINTS)
def test_analyst_can_read_everything_they_should(analyst_client, path):
    assert analyst_client.get(path).status_code == 200


def test_analyst_cannot_modify_nodes(analyst_client, client):
    assert analyst_client.post("/api/nodes", json=NEW_NODE).status_code == 403
    assert analyst_client.put("/api/nodes/1", json=NEW_NODE).status_code == 403
    assert analyst_client.patch("/api/nodes/1/status", json={"status": "INACTIVE"}).status_code == 403
    assert client.get("/api/nodes/1").json()["status"] == "ACTIVE"


def test_analyst_cannot_manage_users(analyst_client):
    new_user = {"name": "X", "email": "x@netmonitor.local", "password": "Xxxxxxx-1234"}
    assert analyst_client.get("/api/users").status_code == 403
    assert analyst_client.get("/api/users/1").status_code == 403
    assert analyst_client.post("/api/users", json=new_user).status_code == 403
    assert analyst_client.put("/api/users/1", json={"name": "X", "email": "x@a.b", "role": "ADMIN"}).status_code == 403
    assert analyst_client.patch("/api/users/1/status", json={"status": "DISABLED"}).status_code == 403


def test_forbidden_is_403_not_401(analyst_client):
    response = analyst_client.get("/api/users")
    assert response.status_code == 403
    assert response.json() == {"detail": "You do not have permission to perform this action"}


def test_admin_has_full_access(client):
    for path in READ_ENDPOINTS + ["/api/users"]:
        assert client.get(path).status_code == 200, path
    assert client.post("/api/nodes", json=NEW_NODE).status_code == 201
    assert client.patch("/api/nodes/1/status", json={"status": "INACTIVE"}).status_code == 200
