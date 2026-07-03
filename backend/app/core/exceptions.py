# =============================================================================
# purpose:  Custom exception hierarchy for the LMS backend.
#           Each exception carries the machine-readable error_code and
#           HTTP status code defined in LMS-API-004 §1 and §3.
#           The global error handler (error_handler.py) catches these and
#           formats them into the standard error envelope.
# implements: LMS-API-004 §1 (Error Response Format)
#             LMS-API-004 §3 (HTTP Status Code Reference)
#             LMS-SDD-002 §3.1 (app/core/exceptions.py)
# =============================================================================

from typing import Any


class LMSBaseException(Exception):
    """
    Base class for all LMS domain exceptions.

    Attributes:
        error_code: Machine-readable code returned in the API error envelope.
        message:    Human-readable description.
        status_code: HTTP status code to return to the client.
        details:    Optional dict of additional context (omitted in production).
    """

    error_code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


# -----------------------------------------------------------------------------
# 401 — Authentication errors
# -----------------------------------------------------------------------------

class AuthTokenMissingError(LMSBaseException):
    """No Authorization header present on the request."""
    error_code = "AUTH_TOKEN_MISSING"
    status_code = 401

    def __init__(self) -> None:
        super().__init__("Authorization header is missing.")


class AuthTokenInvalidError(LMSBaseException):
    """JWT is present but fails signature validation, is expired, or malformed."""
    error_code = "AUTH_TOKEN_INVALID"
    status_code = 401

    def __init__(self, message: str = "Token is invalid or expired.") -> None:
        super().__init__(message)


class AuthJwksUnavailableError(LMSBaseException):
    """
    DAN SSO JWKS endpoint is unreachable and no cached keys are available.
    LMS-CACHE-005 §6 step 4: return 503 with AUTH_JWKS_UNAVAILABLE.
    """
    error_code = "AUTH_JWKS_UNAVAILABLE"
    status_code = 503

    def __init__(self) -> None:
        super().__init__(
            "Authentication service (DAN SSO) is unreachable and no cached "
            "keys are available. Please retry shortly."
        )



# -----------------------------------------------------------------------------
# 404 — Not found
# -----------------------------------------------------------------------------

class LogEntryNotFoundError(LMSBaseException):
    """
    Log entry not found, or audit log existence must not be revealed
    to non-LOG_ADMIN callers (return 404, not 403).
    LMS-API-004 §2.5: "Returns 404 (not 403) for audit logs when actor
    is not LOG_ADMIN — do not reveal existence."
    """
    error_code = "LOG_NOT_FOUND"
    status_code = 404

    def __init__(self, log_type: str, log_id: int) -> None:
        super().__init__(f"{log_type} log entry {log_id} not found.")


# -----------------------------------------------------------------------------
# 405 — Method not allowed
# -----------------------------------------------------------------------------

class AuditLogDeleteForbiddenError(LMSBaseException):
    """
    DELETE is structurally absent for audit logs.
    LMS-BRD-001 FR-14: "No DELETE route exists for audit logs."
    LMS-API-004 §3: 405 Method Not Allowed.
    LMS-SDD-002 §6: "Audit log DELETE via API is structurally absent."
    """
    error_code = "METHOD_NOT_ALLOWED"
    status_code = 405

    def __init__(self) -> None:
        super().__init__(
            "Audit logs are immutable. DELETE operations are not permitted."
        )


# -----------------------------------------------------------------------------
# 422 — Validation / domain rule failures
# -----------------------------------------------------------------------------

class ValidationError(LMSBaseException):
    """
    Business-rule validation failure (distinct from Pydantic schema errors
    which FastAPI handles automatically as 422).
    """
    error_code = "VALIDATION_ERROR"
    status_code = 422

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)


class ServiceNotRegisteredError(LMSBaseException):
    error_code = "SERVICE_NOT_REGISTERED"
    status_code = 404  # not 422

    def __init__(self, source_service: str) -> None:
        super().__init__(
            f"Service '{source_service}' is not registered in the LMS services registry. (or disabled)"
            "Contact an administrator to register this service before ingesting logs."
        )


class ServiceAlreadyRegisteredError(LMSBaseException):
    error_code = "SERVICE_ALREADY_REGISTERED"
    status_code = 409

    def __init__(self, service: str) -> None:
        super().__init__(
            f"Conflict error. Service {service} is already registered."
        )

class ServiceAlreadyDisabledError(LMSBaseException):
    error_code = "SERVICE_ALREADY_DISABLED"
    status_code = 409  # conflict, not 400

    def __init__(self, service_id: str) -> None:
        super().__init__(f"Service '{service_id}' is already disabled.")


# -----------------------------------------------------------------------------
# 429 — Rate limit
# -----------------------------------------------------------------------------

class RateLimitExceededError(LMSBaseException):
    """
    Per-service ingestion rate limit exceeded.
    LMS-CACHE-005 §7: RATE_LIMIT_MAX requests per 60-second window.
    LMS-API-004 §3: 429 Too Many Requests.
    """
    error_code = "RATE_LIMIT_EXCEEDED"
    status_code = 429

    def __init__(self, source_service: str, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            f"Rate limit exceeded for service '{source_service}'. "
            f"Retry after {retry_after_seconds} second(s)."
        )


# -----------------------------------------------------------------------------
# 503 — Dependency failures
# -----------------------------------------------------------------------------

class DatabaseUnavailableError(LMSBaseException):
    """MariaDB is unreachable or returned an unrecoverable error."""
    error_code = "DATABASE_UNAVAILABLE"
    status_code = 503

    def __init__(self) -> None:
        super().__init__("Database is currently unavailable. Please retry shortly.")


class CacheUnavailableError(LMSBaseException):
    """
    Redis is unreachable.
    LMS-CACHE-005 §10: "The application must not crash or return 500 on
    Redis failure for read operations. Redis is a performance layer, not
    a required dependency for reads."
    This exception is raised only in contexts where Redis IS required
    (e.g., rate limiting on write path). For query caching, failures are
    handled silently with a fallthrough to DB.
    """
    error_code = "CACHE_UNAVAILABLE"
    status_code = 503

    def __init__(self) -> None:
        super().__init__("Cache layer is currently unavailable.")

# -----------------------------------------------------------------------------
# 401 — Signature verification (service-to-service ingest auth)
# -----------------------------------------------------------------------------

class SignatureInvalidError(LMSBaseException):
    """HMAC signature is missing, malformed, or does not match."""
    error_code = "SIGNATURE_INVALID"
    status_code = 401

    def __init__(self, message: str = "Request signature is invalid.") -> None:
        super().__init__(message)


class SignatureExpiredError(LMSBaseException):
    """Request timestamp is outside the acceptable tolerance window."""
    error_code = "SIGNATURE_EXPIRED"
    status_code = 401

    def __init__(self) -> None:
        super().__init__("Request timestamp is expired or too far in the future.")