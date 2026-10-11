from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unknown_route_returns_404():
    assert client.get("/api/does-not-exist").status_code == 404


def test_models_match_the_six_table_schema():
    from app.db.base import Base
    import app.models  # noqa: F401

    assert set(Base.metadata.tables) == {
        "users",
        "nodes",
        "devices",
        "destinations",
        "collector_api_keys",
        "network_history",
    }
