import uuid
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.exceptions import (
    LMSBaseException,
    RateLimitExceededError,
)

logger = logging.getLogger(__name__)


def _build_error_response(
    request_id: str,
    error_code: str,
    message: str,
    status_code: int,
    details: dict | None = None,
    headers: dict | None = None,
) -> JSONResponse:
    """
    Constructs the standard LMS error envelope.

    LMS-API-004 §1 Error Response Format:
        error_code  — machine-readable string
        message     — human-readable description
        details     — validation errors or debug info (omitted in production)
        request_id  — UUID for log correlation, always present
    """
    settings = get_settings()

    body: dict = {
        "error_code": error_code,
        "message": message,
        "request_id": request_id,
    }

    # Only include details in non-production environments to avoid leaking
    # internal state. LMS-API-004 §1: "omitted in production".
    if details is not None and settings.app_env != "production":
        body["details"] = details
    else:
        body["details"] = None

    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=headers,
    )


def _get_request_id(request: Request) -> str:
    """
    Returns the request_id for this request.
    Uses the value set by the request-id middleware if present,
    otherwise generates a fresh UUID.
    """
    return getattr(request.state, "request_id", str(uuid.uuid4()))


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all exception handlers on the FastAPI application instance.
    Called once during app startup in app/main.py.
    """

    # -------------------------------------------------------------------------
    # LMS domain exceptions (app/core/exceptions.py)
    # -------------------------------------------------------------------------
    @app.exception_handler(LMSBaseException)
    async def lms_exception_handler(
        request: Request, exc: LMSBaseException
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        # Log server-side errors at ERROR level; client errors at WARNING.
        if exc.status_code >= 500:
            logger.error(
                "LMS server error [%s] request_id=%s: %s",
                exc.error_code,
                request_id,
                exc.message,
                exc_info=True,
            )
        else:
            logger.warning(
                "LMS client error [%s] request_id=%s: %s",
                exc.error_code,
                request_id,
                exc.message,
            )

        # Special case: rate limit requires Retry-After header.
        # LMS-CACHE-005 §7: "Retry-After: {seconds_until_next_minute} header"
        extra_headers = None
        if isinstance(exc, RateLimitExceededError):
            extra_headers = {"Retry-After": str(exc.retry_after_seconds)}

        return _build_error_response(
            request_id=request_id,
            error_code=exc.error_code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
            headers=extra_headers,
        )

    # -------------------------------------------------------------------------
    # FastAPI / Pydantic request validation errors (HTTP 422)
    # LMS-API-004 §3: 422 Unprocessable Entity — schema validation failure
    # LMS-BRD-001 FR-04: "reject malformed entries with HTTP 422"
    # -------------------------------------------------------------------------
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        logger.warning(
            "Request validation error request_id=%s path=%s: %s",
            request_id,
            request.url.path,
            exc.errors(),
        )

        # Reformat Pydantic error list into a field-keyed dict for readability.
        field_errors: dict[str, list[str]] = {}
        for error in exc.errors():
            # error["loc"] is a tuple like ("body", "field_name") or ("query", "param")
            location = " -> ".join(str(loc) for loc in error["loc"])
            field_errors.setdefault(location, []).append(error["msg"])

        return _build_error_response(
            request_id=request_id,
            error_code="VALIDATION_ERROR",
            message="Request body or parameters failed schema validation.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"field_errors": field_errors},
        )

    # -------------------------------------------------------------------------
    # Pydantic v2 ValidationError raised outside of request parsing context
    # -------------------------------------------------------------------------
    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        request_id = _get_request_id(request)
        logger.error(
            "Unexpected Pydantic validation error request_id=%s: %s",
            request_id,
            str(exc),
            exc_info=True,
        )
        return _build_error_response(
            request_id=request_id,
            error_code="VALIDATION_ERROR",
            message="Internal data validation error.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"pydantic_errors": exc.errors()},
        )

    # -------------------------------------------------------------------------
    # Starlette / FastAPI HTTP exceptions (404, 405, etc.)
    # -------------------------------------------------------------------------
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        # Map common HTTP status codes to our error_code strings.
        # LMS-API-004 §3 status code reference.
        code_map: dict[int, str] = {
            400: "BAD_REQUEST",
            401: "AUTH_TOKEN_INVALID",
            403: "INSUFFICIENT_ROLE",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            429: "RATE_LIMIT_EXCEEDED",
            503: "SERVICE_UNAVAILABLE",
        }
        error_code = code_map.get(exc.status_code, "HTTP_ERROR")

        return _build_error_response(
            request_id=request_id,
            error_code=error_code,
            message=exc.detail or "An HTTP error occurred.",
            status_code=exc.status_code,
        )

    # -------------------------------------------------------------------------
    # Catch-all for any unhandled Python exception (HTTP 500)
    # -------------------------------------------------------------------------
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = _get_request_id(request)

        logger.critical(
            "Unhandled exception request_id=%s path=%s method=%s: %s",
            request_id,
            request.url.path,
            request.method,
            str(exc),
            exc_info=True,
        )

        # Never expose exception details in production.
        settings = get_settings()
        details = None
        if settings.app_env != "production":
            details = {"exception_type": type(exc).__name__, "detail": str(exc)}

        return _build_error_response(
            request_id=request_id,
            error_code="INTERNAL_ERROR",
            message="An unexpected internal error occurred. Please contact support.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )
