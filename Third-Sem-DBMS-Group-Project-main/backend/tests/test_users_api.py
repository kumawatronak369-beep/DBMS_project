import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.security import verify_password
from tests.conftest import ADMIN_EMAIL, requires_db

pytestmark = requires_db

NEW_USER = {"name": "Dana Analyst", "email": "Dana@NetMonitor.local", "password": "Dana-Pass-2026", "role": "ANALYST"}


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch):
    monkeypatch.setattr(get_settings(), "bcrypt_rounds", 4)


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_list_users_never_exposes_password_material(client):
    response = client.get("/api/users")
    body = response.json()
    assert body["total"] == 2 and len(body["items"]) == 2
    assert "password" not in response.text.lower() and "$2b$" not in response.text
    assert client.get("/api/users", params={"role": "ANALYST"}).json()["total"] == 1
    assert client.get("/api/users", params={"search": "admin"}).json()["total"] == 1
    assert client.get("/api/users", params={"status": "DISABLED"}).json()["total"] == 0


def test_create_user_hashes_the_password(client, db):
    response = client.post("/api/users", json=NEW_USER)
    assert response.status_code == 201
    user = response.json()
    assert user["email"] == "dana@netmonitor.local"
    assert user["role"] == "ANALYST" and user["status"] == "ACTIVE" and user["last_login"] is None
    assert "password" not in response.text.lower()

    stored = db.scalar(text("SELECT password_hash FROM users WHERE user_id = :i"), {"i": user["user_id"]})
    assert stored.startswith("$2b$") and stored != NEW_USER["password"]
    assert NEW_USER["password"] not in stored
    assert verify_password(NEW_USER["password"], stored)


def test_created_user_can_log_in(client, anon_client):
    client.post("/api/users", json=NEW_USER)
    ok = login(anon_client, "dana@netmonitor.local", NEW_USER["password"])
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "ANALYST"


def test_role_defaults_to_analyst(client):
    body = {k: v for k, v in NEW_USER.items() if k != "role"}
    assert client.post("/api/users", json=body).json()["role"] == "ANALYST"


def test_duplicate_email_is_409_case_insensitively(client):
    assert client.post("/api/users", json=NEW_USER).status_code == 201
    assert client.post("/api/users", json={**NEW_USER, "email": "DANA@netmonitor.local"}).status_code == 409
    other = client.post("/api/users", json={**NEW_USER, "email": "eve@netmonitor.local"}).json()
    clash = client.put(
        f"/api/users/{other['user_id']}", json={"name": "Eve", "email": ADMIN_EMAIL, "role": "ANALYST"}
    )
    assert clash.status_code == 409


@pytest.mark.parametrize(
    "override",
    [
        {"password": "short1!"},
        {"password": "x" * 73},
        {"password": "é" * 40},
        {"email": "not-an-email"},
        {"email": "two@@ats.com"},
        {"role": "SUPERUSER"},
        {"name": ""},
    ],
)
def test_user_validation_errors(client, override):
    response = client.post("/api/users", json={**NEW_USER, **override})
    assert response.status_code == 422
    assert NEW_USER["password"] not in response.text
    if "password" in override:
        assert override["password"] not in response.text


def test_update_user_and_reset_password(client, anon_client):
    user = client.post("/api/users", json=NEW_USER).json()
    uid = user["user_id"]

    renamed = client.put(
        f"/api/users/{uid}", json={"name": "Dana Renamed", "email": "dana@netmonitor.local", "role": "ADMIN"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Dana Renamed" and renamed.json()["role"] == "ADMIN"

    assert login(anon_client, "dana@netmonitor.local", NEW_USER["password"]).status_code == 200

    client.put(
        f"/api/users/{uid}",
        json={"name": "Dana", "email": "dana@netmonitor.local", "role": "ADMIN", "password": "Brand-New-Pass-1"},
    )
    assert login(anon_client, "dana@netmonitor.local", NEW_USER["password"]).status_code == 401
    assert login(anon_client, "dana@netmonitor.local", "Brand-New-Pass-1").status_code == 200


def test_disable_and_reenable_user(client, anon_client):
    uid = client.post("/api/users", json=NEW_USER).json()["user_id"]
    assert client.patch(f"/api/users/{uid}/status", json={"status": "DISABLED"}).json()["status"] == "DISABLED"
    assert login(anon_client, "dana@netmonitor.local", NEW_USER["password"]).status_code == 403

    client.patch(f"/api/users/{uid}/status", json={"status": "ACTIVE"})
    assert login(anon_client, "dana@netmonitor.local", NEW_USER["password"]).status_code == 200


def test_the_last_active_admin_cannot_be_disabled_or_demoted(client, db):
    admin_id = db.scalar(text("SELECT user_id FROM users WHERE email = :e"), {"e": ADMIN_EMAIL})
    disable = client.patch(f"/api/users/{admin_id}/status", json={"status": "DISABLED"})
    assert disable.status_code == 409 and "administrator" in disable.json()["detail"]

    demote = client.put(
        f"/api/users/{admin_id}", json={"name": "Admin", "email": ADMIN_EMAIL, "role": "ANALYST"}
    )
    assert demote.status_code == 409

    client.post("/api/users", json={**NEW_USER, "role": "ADMIN"})
    assert client.put(
        f"/api/users/{admin_id}", json={"name": "Admin", "email": ADMIN_EMAIL, "role": "ANALYST"}
    ).status_code == 200


def test_user_not_found_and_bad_ids(client):
    assert client.get("/api/users/99999").status_code == 404
    assert client.put("/api/users/99999", json={"name": "x", "email": "x@y.z", "role": "ANALYST"}).status_code == 404
    assert client.patch("/api/users/99999/status", json={"status": "DISABLED"}).status_code == 404
    assert client.get("/api/users/0").status_code == 422


def test_users_are_never_deleted(client):
    assert client.delete("/api/users/1").status_code == 405
