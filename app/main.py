"""FastAPI application entrypoint."""

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError

import app.models  # noqa: F401
from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.devices import router as devices_router
from app.api.v1.common import router as common_router
from app.api.v1.diary import router as diary_router
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.uploads import router as uploads_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)
settings = get_settings()
settings.media_dir.mkdir(parents=True, exist_ok=True)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    for folder in ("avatars", "logs"):
        (settings.media_dir / folder).mkdir(parents=True, exist_ok=True)
    logger.info("Starting %s (%s)", settings.app_name, settings.environment)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    _configure_logging()
    publish_docs = settings.environment != "production"
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        summary="API for the Gut Health Tracker mobile app.",
        debug=settings.debug,
        docs_url="/docs" if publish_docs else None,
        redoc_url="/redoc" if publish_docs else None,
        openapi_url="/openapi.json" if publish_docs else None,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "common", "description": "Service health."},
            {"name": "auth", "description": "Registration, sessions, and profile."},
            {"name": "onboarding", "description": "Goals, concerns, interests, and the 30-day target."},
            {"name": "diary", "description": "Daily gut health diary."},
            {"name": "uploads", "description": "Avatar and diary image uploads."},
            {"name": "devices", "description": "Push-notification device tokens."},
            {"name": "admin", "description": "Admin panel accounts, devices, onboarding, and diary."},
        ],
    )

    @application.middleware("http")
    async def add_security_headers(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
        return response

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials="*" not in settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "code": exc.code},
            headers=exc.headers,
        )

    async def handle_database_unavailable(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Database unavailable")
        return JSONResponse(
            status_code=503,
            content={"detail": "Database unavailable", "code": "database_unavailable"},
        )

    application.add_exception_handler(OperationalError, handle_database_unavailable)
    application.add_exception_handler(InterfaceError, handle_database_unavailable)
    application.add_exception_handler(DBAPIError, handle_database_unavailable)

    application.include_router(common_router, prefix=settings.api_v1_prefix)
    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    application.include_router(onboarding_router, prefix=settings.api_v1_prefix)
    application.include_router(diary_router, prefix=settings.api_v1_prefix)
    application.include_router(uploads_router, prefix=settings.api_v1_prefix)
    application.include_router(devices_router, prefix=settings.api_v1_prefix)
    application.include_router(admin_router, prefix=settings.api_v1_prefix)
    application.mount(
        settings.media_url_prefix,
        StaticFiles(directory=settings.media_dir),
        name="media",
    )

    @application.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": settings.app_name, "version": settings.app_version}

    return application


app = create_app()
