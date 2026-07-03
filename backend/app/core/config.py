# =============================================================================
# purpose:  Runtime configuration. GitHub OAuth single-user auth.
#           No DAN SSO, no roles, no static accounts.
# =============================================================================

import secrets
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_env: str = Field(default="development")
    app_version: str = Field(default="1.0.0")

    # -------------------------------------------------------------------------
    # GitHub OAuth
    # Create your OAuth App at: https://github.com/settings/developers
    # -------------------------------------------------------------------------
    github_client_id: str = Field(
        ...,
        description="GitHub OAuth App Client ID",
    )
    github_client_secret: str = Field(
        ...,
        description="GitHub OAuth App Client Secret",
    )
    github_redirect_uri: str = Field(
        default="http://localhost:8000/api/v1/auth/callback",
        description="Must exactly match the callback URL set in your GitHub OAuth App",
    )

    # -------------------------------------------------------------------------
    # Single allowed user
    # -------------------------------------------------------------------------
    allowed_github_username: str = Field(
        default="Sanjaa46",
        description="Only this GitHub username can log in.",
    )

    # -------------------------------------------------------------------------
    # JWT (HS256, issued by this service)
    # -------------------------------------------------------------------------
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_hex(32),
        description=(
            "HS256 signing secret. Set explicitly — random default "
            "resets on every restart. "
            "Generate: python -c \"import secrets; print(secrets.token_hex(32))\""
        ),
    )
    access_token_expire_minutes: int = Field(default=60, ge=1)
    refresh_token_expire_days: int = Field(default=30, ge=1)

    # -------------------------------------------------------------------------
    # HMAC Signature secret
    # -------------------------------------------------------------------------
    ingest_signing_secret: str

    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str = Field(...)
    retention_database_url: str = Field(...)
    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout: int = Field(default=30, ge=5, le=300)

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str = Field(...)

    # -------------------------------------------------------------------------
    # Cache TTLs
    # -------------------------------------------------------------------------
    query_cache_ttl_seconds: int = Field(default=60, ge=1)
    health_cache_ttl_seconds: int = Field(default=10, ge=1)

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    rate_limit_max: int = Field(default=1000, ge=1)

    # -------------------------------------------------------------------------
    # Retention
    # -------------------------------------------------------------------------
    app_log_retention_days: int = Field(default=90, ge=1)
    audit_log_retention_days: int = Field(default=365, ge=1)
    retention_job_hour: int = Field(default=2, ge=0, le=23)
    retention_job_minute: int = Field(default=0, ge=0, le=59)

    # -------------------------------------------------------------------------
    # Server
    # -------------------------------------------------------------------------
    uvicorn_host: str = Field(default="0.0.0.0")
    uvicorn_port: int = Field(default=8000)
    uvicorn_workers: int = Field(default=1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
