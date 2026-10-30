from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error_code: str = Field(examples=["VALIDATION_ERROR"])
    message: str
    details: dict[str, Any] | None = None
    request_id: str


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Not authenticated"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}
