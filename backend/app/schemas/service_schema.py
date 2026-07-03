from datetime import datetime
from app.shared.utils.datetime import to_ulaanbaatar
from pydantic import BaseModel, Field, field_serializer

class AddServiceRequest(BaseModel):
    id: str = Field(
        ...,
        max_length=64,
        description="Service's id",
        examples=["example-service"]
    )
    name: str = Field(
        ...,
        max_length=128,
        description="Full normal name of service name",
        examples=["Example Service"]
    )
    description: str | None = Field(
        None,
        description="Placeholder service for development and integration testing.",
        examples=["Placeholder service for development and integration testing."]
    )

class AddServiceResponse(BaseModel):
    @field_serializer("created_at", when_used="always")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return to_ulaanbaatar(dt).isoformat()
    
    id: str = Field(
        ...,
        description="Id of service"
    )
    created_at: datetime = Field(
        ..., description="Server created timestamp (UTC)"
    )

    model_config = {"from_attributes": True}

class ServiceQueryParams(BaseModel):
    id: str | None = Field(
        default=None,
        max_length=64,
        description="Exact match of service id"
    )
    name: str | None = Field(
        default=None,
        max_length=128,
        description="Name of service."
    )

class ServiceEntry(BaseModel):
    @field_serializer("created_at", when_used="always")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return to_ulaanbaatar(dt).isoformat()
    id: str
    name: str
    description: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ServiceQueryResponse(BaseModel):
    data: list[ServiceEntry] = Field(
        ..., description="Services"
    )

class ToggleServiceStatus(BaseModel):
    @field_serializer("updated_at", when_used="always")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        if dt is None:
            return None
        return to_ulaanbaatar(dt).isoformat()
    id: str
    is_active: bool
    updated_at: datetime

    model_config = {"from_attributes": True}

class DisableServiceResponse(ToggleServiceStatus):
    is_active: bool = False

class EnableServiceResponse(ToggleServiceStatus):
    is_active: bool = True
