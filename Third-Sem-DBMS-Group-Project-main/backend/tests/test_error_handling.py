from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.exceptions.handlers import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    register_exception_handlers,
)


def _client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    router = APIRouter()

    @router.get("/bad")
    def bad():
        raise AppError("bad input")

    @router.get("/missing")
    def missing():
        raise NotFoundError("thing not found")

    @router.get("/conflict")
    def conflict():
        raise ConflictError("already exists")

    @router.get("/unauthorized")
    def unauthorized():
        raise UnauthorizedError("login required")

    @router.get("/forbidden")
    def forbidden():
        raise ForbiddenError("not allowed")

    @router.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail: password=hunter2")

    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_app_errors_map_to_http_status_codes():
    client = _client()
    expected = {"/bad": 400, "/unauthorized": 401, "/forbidden": 403, "/missing": 404, "/conflict": 409}
    for path, status_code in expected.items():
        response = client.get(path)
        assert response.status_code == status_code, path
        assert isinstance(response.json()["detail"], str)


def test_unexpected_errors_return_500_without_leaking_details():
    response = _client().get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "hunter2" not in response.text and "Traceback" not in response.text
