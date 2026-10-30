from pydantic import BaseModel, Field


class LoginUrlResponse(BaseModel):
    authorization_url: str


class CallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=512)
    state: str = Field(min_length=1, max_length=512)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)
    jti: str | None = Field(
        default=None, description="Deprecated: v2 refresh tokens embed their jti."
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    username: str
    expires_in: int = Field(description="Access token lifetime in seconds.")


class MeResponse(BaseModel):
    username: str
