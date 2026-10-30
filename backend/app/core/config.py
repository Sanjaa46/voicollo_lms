"""Runtime configuration, loaded from environment variables (and `.env` in dev).

Two layers:
  * `DatabaseSettings` — only what Alembic migrations need.
  * `Settings` — everything the API server needs (extends DatabaseSettings).

Database and Redis connection strings can be given as full URLs or assembled
from components (`DB_HOST`, `DB_APP_PASSWORD`, ...). Components are preferred:
the deployment `.env` then contains each password exactly once.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

APP_DB_USER = "lms_app"
RETENTION_DB_USER = "lms_retention"


def _source_version() -> str:
    """VERSION file at the repository root (source checkouts); images bake LMS_BUILD_VERSION."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "VERSION"
        if candidate.is_file():
            return candidate.read_text().strip()
    return "0.0.0-dev"


def build_mysql_url(user: str, password: str, host: str, port: int, database: str) -> str:
    """Build an aiomysql URL with the password safely escaped."""
    url = URL.create(
        "mysql+aiomysql",
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
        query={"charset": "utf8mb4"},
    )
    return url.render_as_string(hide_password=False)


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    db_host: str = "lms-db"
    db_port: int = 3306
    db_name: str = "lms"
    db_app_password: str | None = Field(
        default=None, validation_alias=AliasChoices("DB_APP_PASSWORD", "LMS_APP_DB_PASSWORD")
    )
    db_retention_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DB_RETENTION_PASSWORD", "LMS_RETENTION_DB_PASSWORD"),
    )
    db_root_password: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DB_ROOT_PASSWORD", "MARIADB_ROOT_PASSWORD"),
    )

    # Full URL overrides (take precedence over components when set).
    database_url: str | None = None
    retention_database_url: str | None = None
    root_database_url: str | None = None

    db_pool_size: int = Field(default=10, ge=1, le=100)
    db_max_overflow: int = Field(default=20, ge=0, le=100)
    db_pool_timeout: int = Field(default=30, ge=5, le=300)

    def _component_url(self, user: str, password: str | None, purpose: str) -> str:
        if not password:
            raise ValueError(
                f"No database credentials for the {purpose} connection: set the "
                f"password variable for user '{user}' or the full URL override."
            )
        return build_mysql_url(user, password, self.db_host, self.db_port, self.db_name)

    @property
    def app_db_url(self) -> str:
        return self.database_url or self._component_url(
            APP_DB_USER, self.db_app_password, "application"
        )

    @property
    def retention_db_url(self) -> str:
        return self.retention_database_url or self._component_url(
            RETENTION_DB_USER, self.db_retention_password, "retention"
        )

    @property
    def root_db_url(self) -> str:
        return self.root_database_url or self._component_url(
            "root", self.db_root_password, "migration (root)"
        )


class Settings(DatabaseSettings):
    # ------------------------------------------------------------------ app
    app_env: Literal["development", "staging", "production", "test"] = "production"
    # Build metadata is baked into the image (LMS_BUILD_*) and wins over .env values.
    app_version: str = Field(
        default_factory=_source_version,
        validation_alias=AliasChoices("LMS_BUILD_VERSION", "APP_VERSION"),
    )
    git_sha: str = Field(
        default="unknown", validation_alias=AliasChoices("LMS_BUILD_SHA", "GIT_SHA")
    )
    build_date: str = Field(
        default="unknown", validation_alias=AliasChoices("LMS_BUILD_DATE", "BUILD_DATE")
    )
    public_url: str = Field(
        default="http://localhost:8000",
        validation_alias=AliasChoices("PUBLIC_URL", "FRONTEND_URL"),
        description="Public origin users open in the browser (no trailing slash).",
    )
    cors_extra_origins: list[str] = Field(
        default_factory=list,
        description="Additional browser origins allowed by CORS (e.g. a Vite dev server).",
    )
    log_level: str = "INFO"
    log_format: Literal["text", "json"] = "text"
    scheduler_timezone: str = Field(
        default="Asia/Ulaanbaatar",
        validation_alias=AliasChoices("SCHEDULER_TIMEZONE", "TZ"),
    )
    serve_frontend: bool = True
    frontend_dist_dir: str = "/app/static"

    # ------------------------------------------------------------ GitHub auth
    github_client_id: str
    github_client_secret: str
    github_redirect_uri: str | None = None
    allowed_github_username: str
    allowed_github_user_id: int | None = Field(
        default=None,
        description="Optional numeric GitHub user id. Protects against username re-use.",
    )

    # ------------------------------------------------------------------ JWT
    jwt_secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=60, ge=1, le=24 * 60)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=365)

    # ------------------------------------------------------------- ingestion
    ingest_signing_secret: str = Field(min_length=16)
    signature_tolerance_seconds: int = Field(default=60, ge=5, le=900)
    rate_limit_max: int = Field(default=1000, ge=1, description="Entries / service / minute.")
    max_future_skew_minutes: int = Field(
        default=24 * 60, ge=1, description="Reject event timestamps further in the future."
    )

    # ----------------------------------------------------------------- redis
    redis_url: str | None = None
    redis_host: str = "lms-cache"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_db: int = 0

    # ----------------------------------------------------------------- cache
    query_cache_ttl_seconds: int = Field(default=60, ge=1)
    health_cache_ttl_seconds: int = Field(default=10, ge=1)
    stats_cache_ttl_seconds: int = Field(default=15, ge=1)

    # ------------------------------------------------------------- retention
    retention_enabled: bool = True
    app_log_retention_days: int = Field(default=90, ge=1)
    audit_log_retention_days: int = Field(default=365, ge=1)
    retention_job_hour: int = Field(default=2, ge=0, le=23)
    retention_job_minute: int = Field(default=0, ge=0, le=59)

    @field_validator("public_url")
    @classmethod
    def _strip_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _check_connections(self) -> "Settings":
        # Fail fast at startup instead of on the first request.
        _ = self.app_db_url
        _ = self.retention_db_url
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def oauth_redirect_uri(self) -> str:
        return self.github_redirect_uri or f"{self.public_url}/auth/callback"

    @property
    def redis_dsn(self) -> str:
        if self.redis_url:
            return self.redis_url
        auth = f":{quote(self.redis_password, safe='')}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origins(self) -> list[str]:
        return [self.public_url, *self.cors_extra_origins]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
