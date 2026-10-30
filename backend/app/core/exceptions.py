"""Domain exceptions. Each maps to one `error_code` + HTTP status in the error envelope."""

from typing import Any


class LMSError(Exception):
    error_code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers


# ---------------------------------------------------------------- 401 / 403
class AuthTokenMissingError(LMSError):
    error_code, status_code = "AUTH_TOKEN_MISSING", 401

    def __init__(self) -> None:
        super().__init__("Authorization header is missing.")


class AuthTokenInvalidError(LMSError):
    error_code, status_code = "AUTH_TOKEN_INVALID", 401

    def __init__(self, message: str = "Token is invalid or expired.") -> None:
        super().__init__(message)


class AuthUserNotAllowedError(LMSError):
    error_code, status_code = "AUTH_USER_NOT_ALLOWED", 403

    def __init__(self, username: str) -> None:
        super().__init__(f"GitHub account '{username}' is not authorized to use this system.")


class AuthProviderError(LMSError):
    error_code, status_code = "AUTH_PROVIDER_ERROR", 502

    def __init__(self, message: str) -> None:
        super().__init__(message)


class SignatureInvalidError(LMSError):
    error_code, status_code = "SIGNATURE_INVALID", 401

    def __init__(self, message: str = "Request signature is invalid.") -> None:
        super().__init__(message)


class SignatureExpiredError(LMSError):
    error_code, status_code = "SIGNATURE_EXPIRED", 401

    def __init__(self) -> None:
        super().__init__("X-Timestamp is outside the accepted window. Check the producer's clock.")


class DuplicateRequestError(LMSError):
    error_code, status_code = "DUPLICATE_REQUEST", 409

    def __init__(self) -> None:
        super().__init__("This signed request was already processed (replay rejected).")


# ---------------------------------------------------------------- 404 / 405 / 409
class LogNotFoundError(LMSError):
    error_code, status_code = "LOG_NOT_FOUND", 404

    def __init__(self, log_type: str, log_id: int) -> None:
        super().__init__(f"{log_type} log {log_id} not found.")


class ServiceNotFoundError(LMSError):
    error_code, status_code = "SERVICE_NOT_FOUND", 404

    def __init__(self, service_id: str) -> None:
        super().__init__(f"Service '{service_id}' does not exist.")


class ServiceAlreadyExistsError(LMSError):
    error_code, status_code = "SERVICE_ALREADY_EXISTS", 409

    def __init__(self, service_id: str) -> None:
        super().__init__(f"Service '{service_id}' is already registered.")


class ServiceProtectedError(LMSError):
    error_code, status_code = "SERVICE_PROTECTED", 409

    def __init__(self, service_id: str) -> None:
        super().__init__(
            f"Service '{service_id}' is reserved by the system and cannot be disabled."
        )


class AuditLogImmutableError(LMSError):
    error_code, status_code = "METHOD_NOT_ALLOWED", 405

    def __init__(self) -> None:
        super().__init__("Audit logs are immutable. DELETE is not permitted.")


class RetentionAlreadyRunningError(LMSError):
    error_code, status_code = "RETENTION_ALREADY_RUNNING", 409

    def __init__(self) -> None:
        super().__init__("A retention run is already in progress.")


# ---------------------------------------------------------------- 403 / 422 ingest
class ServiceNotRegisteredError(LMSError):
    error_code, status_code = "SERVICE_NOT_REGISTERED", 422

    def __init__(self, service_id: str) -> None:
        super().__init__(
            f"source_service '{service_id}' is not registered. Register it in the LMS first."
        )


class ServiceDisabledError(LMSError):
    error_code, status_code = "SERVICE_DISABLED", 403

    def __init__(self, service_id: str) -> None:
        super().__init__(f"source_service '{service_id}' is disabled and cannot ingest logs.")


class ValidationFailedError(LMSError):
    error_code, status_code = "VALIDATION_ERROR", 422


# ---------------------------------------------------------------- 429 / 503
class RateLimitExceededError(LMSError):
    error_code, status_code = "RATE_LIMIT_EXCEEDED", 429

    def __init__(self, service_id: str, retry_after_seconds: int) -> None:
        super().__init__(
            f"Rate limit exceeded for service '{service_id}'. "
            f"Retry after {retry_after_seconds} second(s).",
            headers={"Retry-After": str(retry_after_seconds)},
        )
        self.retry_after_seconds = retry_after_seconds
