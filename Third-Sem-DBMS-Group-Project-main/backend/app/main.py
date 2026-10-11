from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, collector, dashboard, destinations, devices, health, history, nodes, reports, users
from app.core.config import get_settings
from app.core.security import ensure_jwt_secret_configured
from app.exceptions.handlers import register_exception_handlers

@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_jwt_secret_configured()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    docs = settings.enable_api_docs
    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,  # bearer token in a header, no cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    register_exception_handlers(application)

    # health and login are public; the other routers check auth themselves
    api_router = APIRouter(prefix="/api")
    for module in (health, auth, dashboard, nodes, devices, destinations, history, reports, users, collector):
        api_router.include_router(module.router)
    application.include_router(api_router)
    return application


app = create_app()
