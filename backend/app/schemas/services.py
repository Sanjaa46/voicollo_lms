import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.time import UTCDateTime

SERVICE_ID_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$")


class ServiceCreate(BaseModel):
    id: str = Field(
        min_length=1,
        max_length=64,
        description="Lowercase slug: letters, digits, '.', '_' or '-'.",
        examples=["billing-api"],
    )
    name: str = Field(min_length=1, max_length=128, examples=["Billing API"])
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("id", mode="before")
    @classmethod
    def _slug(cls, value: Any) -> Any:
        if isinstance(value, str):
            value = value.strip().lower()
            if not SERVICE_ID_PATTERN.match(value):
                raise ValueError(
                    "id must be a lowercase slug (a-z, 0-9, '.', '_', '-'), "
                    "starting and ending with a letter or digit"
                )
        return value

    @field_validator("name", "description", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name", "description", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class ServiceActivity(BaseModel):
    last_seen_at: UTCDateTime | None = None
    app_logs_24h: int = 0
    errors_24h: int = 0
    audit_logs_24h: int = 0


class ServiceOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    is_active: bool
    is_protected: bool = False
    created_at: UTCDateTime
    updated_at: UTCDateTime
    activity: ServiceActivity | None = None

    model_config = {"from_attributes": True}


class ServiceListResponse(BaseModel):
    data: list[ServiceOut]
    total: int
