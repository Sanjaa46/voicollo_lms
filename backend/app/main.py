# =============================================================================
# purpose:  FastAPI application factory.
#           Responsibilities:
#             - Define the lifespan context (startup + shutdown hooks)
#             - Register global middleware (request-id, logging)
#             - Mount the API v1 router
#             - Register global exception handlers
#             - Expose the `app` instance for Uvicorn
# implements: LMS-SDD-002 §3.1 (app/main.py — App factory, middleware,
#                                lifespan events)
#             LMS-SDD-002 §4   (FastAPI 0.111+, Uvicorn)
#             LMS-SDD-002 §5.1 (Single-node Docker Compose deployment)
# =============================================================================

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.core.database import close_db, init_db
from app.core.error_handler import register_exception_handlers
from app.core.redis_client import close_redis, init_redis
from app.jobs.scheduler import init_scheduler, shutdown_scheduler, start_scheduler

# ---------------------------------------------------------------------------
# Logging configuration — basic setup; extend with structlog in production.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ===========================================================================
# Lifespan context manager
# Manages startup and shutdown of all stateful resources:
#   DB engines, Redis pool, APScheduler.
# FastAPI 0.111+ uses lifespan instead of @app.on_event decorators.
# ===========================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup (before `yield`):
      1. Initialise DB engine pool (primary + retention).
      2. Initialise Redis connection pool.
      3. Initialise and start APScheduler with retention job.

    Shutdown (after `yield`):
      1. Shut down APScheduler (waits for running jobs to finish).
      2. Dispose Redis pool.
      3. Dispose DB engine pool.

    LMS-SDD-002 §3.1: "lifespan events"
    """
    settings = get_settings()
    logger.info(
        "LMS starting up (env=%s, version=%s)",
        settings.app_env,
        settings.app_version,
    )

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------
    try:
        # 1. Database engines.
        init_db()
        logger.info("Database engine pool initialised.")

        # 2. Redis pool.
        init_redis()
        logger.info("Redis connection pool initialised.")

        # 3. APScheduler — init then start.
        init_scheduler()
        start_scheduler()
        logger.info("Background job scheduler started.")

    except Exception as exc:
        logger.critical(
            "Fatal error during startup — application cannot start: %s",
            exc,
            exc_info=True,
        )
        raise

    logger.info("LMS startup complete. Accepting requests.")

    # ------------------------------------------------------------------
    # Application runs here.
    # ------------------------------------------------------------------
    yield

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------
    logger.info("LMS shutting down...")

    try:
        shutdown_scheduler()
    except Exception as exc:
        logger.error("Error shutting down scheduler: %s", exc, exc_info=True)

    try:
        await close_redis()
    except Exception as exc:
        logger.error("Error closing Redis pool: %s", exc, exc_info=True)

    try:
        await close_db()
    except Exception as exc:
        logger.error("Error closing DB engine pool: %s", exc, exc_info=True)

    logger.info("LMS shutdown complete.")


# ===========================================================================
# Application factory
# ===========================================================================

def create_app() -> FastAPI:
    """
    Creates and configures the FastAPI application instance.
    Separated into a factory function to support testing (each test can
    create a fresh app with overridden dependencies).
    """
    settings = get_settings()

    app = FastAPI(
        title="Log Management System (LMS)",
        description=(
            "Centralised log ingestion, querying, and retention backend. "
            "LMS-BRD-001 v1.0 — Custom Log Management System."
        ),
        version=settings.app_version,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        openapi_url="/openapi.json" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # Middleware
    # ------------------------------------------------------------------

    # Request ID middleware — injects a UUID into request.state.request_id
    # for log correlation. LMS-API-004 §1: "request_id always present."
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        """
        Assigns a unique request_id to every incoming request.
        Priority:
          1. X-Request-ID header (if client provides one for tracing).
          2. Fresh UUID generated by the middleware.
        The request_id is stored in request.state and included in all
        error responses by error_handler.py.
        """
        request_id = (
            request.headers.get("X-Request-ID") or str(uuid.uuid4())
        )
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Access logging middleware — logs method, path, status, duration.
    @app.middleware("http")
    async def access_log_middleware(request: Request, call_next):
        """
        Logs every request with method, path, status code, and duration.
        Excludes /health to avoid log spam from probe traffic.
        """
        import time
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 2)

        # Skip health check logging to reduce probe noise.
        if not request.url.path.endswith("/health"):
            logger.info(
                "%s %s → %d (%.1fms) request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
                getattr(request.state, "request_id", "-"),
            )
        return response

    # CORS middleware — internal services only; restrictive by default.
    # TODO: Confirm allowed origins with the infra team before
    #       production deployment. For a government on-prem system, CORS
    #       may be entirely disabled if all clients are server-to-server.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f'{settings.frontend_url}'],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    # ------------------------------------------------------------------
    # Exception handlers
    # ------------------------------------------------------------------
    register_exception_handlers(app)

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(api_v1_router)

    # ------------------------------------------------------------------
    # Root redirect — helpful for developers hitting the bare host.
    # Only active in non-production environments.
    # ------------------------------------------------------------------
    if settings.app_env != "production":
        @app.get("/", include_in_schema=False)
        async def root():
            return JSONResponse(
                content={
                    "service": "LMS API",
                    "version": settings.app_version,
                    "docs": "/docs",
                    "health": "/api/v1/health",
                }
            )

    return app


# ===========================================================================
# Application instance
# Uvicorn entry point: uvicorn app.main:app --workers 2
# LMS-SDD-002 §4: "use with --workers 2 for single-node production"
# ===========================================================================
app = create_app()
