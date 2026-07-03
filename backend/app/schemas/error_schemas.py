# =============================================================================
# purpose:  Pydantic model for the standard LMS error response envelope.
#           Every non-2xx response from the API uses this exact shape.
#           Used by error_handler.py and as the response_model on endpoints
#           where an error schema is needed for OpenAPI documentation.
# implements: LMS-API-004 §1 (Error Response Format)
# =============================================================================

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """
    Standard LMS error envelope.

    LMS-API-004 §1 fields:
      error_code  — Machine-readable code, e.g. VALIDATION_ERROR, AUTH_TOKEN_INVALID
      message     — Human-readable description
      details     — Validation field errors or debug info (None in production)
      request_id  — UUID for log correlation. Always present.
    """

    error_code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["VALIDATION_ERROR", "AUTH_TOKEN_INVALID", "LOG_NOT_FOUND"],
    )
    message: str = Field(
        ...,
        description="Human-readable error description",
        examples=["Request body or parameters failed schema validation."],
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Validation field errors or debug context. "
            "Omitted (null) in production environments. "
            "LMS-API-004 §1."
        ),
    )
    request_id: str = Field(
        ...,
        description="UUID for log correlation. Always present on every response.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "error_code": "VALIDATION_ERROR",
                "message": "Request body or parameters failed schema validation.",
                "details": {
                    "field_errors": {
                        "body -> level": [
                            "Input should be 'DEBUG', 'INFO', 'WARN', 'ERROR' or 'FATAL'"
                        ]
                    }
                },
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        }
    }
