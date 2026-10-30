"""FastAPI application factory. Entry point: `uvicorn app.main:app`."""

import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.redis import close_redis, init_redis
from app.core.request_context import set_request_id
from app.jobs.scheduler import shutdown_scheduler, start_scheduler
from app.web import mount_frontend

logger = logging.getLogger("app")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_QUIET_PATHS = ("/api/v1/health", "/assets/")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "Starting LMS %s (%s, sha=%s)", settings.app_version, settings.app_env, settings.git_sha
    )
    init_db()
    init_redis()
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()
        await close_redis()
        await close_db()
        logger.info("LMS stopped.")


def create_app(*, with_lifespan: bool = True) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    expose_docs = not settings.is_production

    app = FastAPI(
        title="Voicollo Log Management System",
        description="Centralised log ingestion, search and retention.",
        version=settings.app_version,
        docs_url="/api/docs" if expose_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if expose_docs else None,
        lifespan=lifespan if with_lifespan else None,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        set_request_id(request_id)
        start = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if not request.url.path.startswith(_QUIET_PATHS):
            logger.info(
                "%s %s -> %d (%.1f ms)",
                request.method,
                request.url.path,
                response.status_code,
                (time.monotonic() - start) * 1000,
            )
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Cache", "X-Total-Count", "Content-Disposition"],
    )

    register_exception_handlers(app)
    app.include_router(api_v1_router)
    if settings.serve_frontend:
        mount_frontend(app, settings.frontend_dist_dir)
    return app


app = create_app()
