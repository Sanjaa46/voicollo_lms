"""Uniform error envelope: {error_code, message, details, request_id}."""

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.exceptions import LMSError
from app.core.request_context import get_request_id
from app.services import metrics

logger = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "BAD_REQUEST",
    401: "AUTH_TOKEN_INVALID",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
    429: "RATE_LIMIT_EXCEEDED",
    503: "SERVICE_UNAVAILABLE",
}


def _respond(
    error_code: str,
    message: str,
    status_code: int,
    details: dict | None = None,
    headers: dict | None = None,
) -> JSONResponse:
    show_details = details is not None and not get_settings().is_production
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message": message,
            "details": details if show_details else None,
            "request_id": get_request_id() or str(uuid.uuid4()),
        },
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(LMSError)
    async def _lms_error(request: Request, exc: LMSError) -> JSONResponse:
        log = logger.error if exc.status_code >= 500 else logger.warning
        log("%s %s -> %s: %s", request.method, request.url.path, exc.error_code, exc.message)
        await metrics.record_error(exc.error_code)
        return _respond(exc.error_code, exc.message, exc.status_code, exc.details, exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        field_errors: dict[str, list[str]] = {}
        for err in exc.errors():
            location = ".".join(str(part) for part in err["loc"])
            field_errors.setdefault(location, []).append(err["msg"])
        logger.info("Validation failed on %s: %s", request.url.path, field_errors)
        await metrics.record_error("VALIDATION_ERROR")
        # Field errors are safe to show in every environment; clients need them.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Request body or parameters failed validation.",
                "details": {"field_errors": field_errors},
                "request_id": get_request_id() or str(uuid.uuid4()),
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        if exc.status_code >= 500:
            await metrics.record_error(code)
        return _respond(code, str(exc.detail or "HTTP error"), exc.status_code, headers=exc.headers)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        await metrics.record_error("INTERNAL_ERROR")
        return _respond(
            "INTERNAL_ERROR",
            "An unexpected internal error occurred.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"exception": type(exc).__name__, "detail": str(exc)},
        )
