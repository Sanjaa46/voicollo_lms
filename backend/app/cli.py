"""Operational commands, run inside the image: `python -m app.cli <command>`.

migrate        alembic upgrade head, then re-sync DB user passwords from env
check-config   validate the environment without starting the server
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import APP_DB_USER, RETENTION_DB_USER, DatabaseSettings

logger = logging.getLogger("lms.cli")
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _alembic_upgrade() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


async def _sync_users(settings: DatabaseSettings) -> None:
    """Make the DB users' passwords match the current environment (rotation support)."""
    engine = create_async_engine(settings.root_db_url)
    try:
        async with engine.begin() as conn:
            for user, password in (
                (APP_DB_USER, settings.db_app_password),
                (RETENTION_DB_USER, settings.db_retention_password),
            ):
                if not password:
                    continue
                exists = await conn.scalar(
                    text("SELECT COUNT(*) FROM mysql.user WHERE User = :u AND Host = '%'"),
                    {"u": user},
                )
                if exists:
                    await conn.execute(
                        text(f"ALTER USER '{user}'@'%' IDENTIFIED BY :p"), {"p": password}
                    )
                    logger.info("Password synced for DB user %s", user)
    finally:
        await engine.dispose()


def migrate() -> int:
    settings = DatabaseSettings()
    logger.info("Running database migrations against %s:%s", settings.db_host, settings.db_port)
    _alembic_upgrade()
    _setup_logging()  # alembic.ini's logging config replaces ours
    asyncio.run(_sync_users(settings))
    logger.info("Migrations complete.")
    return 0


def check_config() -> int:
    from app.core.config import Settings

    try:
        settings = Settings()
    except Exception as exc:  # pydantic ValidationError lists every bad variable
        print(f"Configuration invalid:\n{exc}", file=sys.stderr)
        return 1
    print(
        f"OK — version {settings.app_version}, env {settings.app_env}, "
        f"public URL {settings.public_url}, OAuth redirect {settings.oauth_redirect_uri}"
    )
    return 0


COMMANDS = {"migrate": migrate, "check-config": check_config}


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", force=True
    )


def main(argv: list[str]) -> int:
    _setup_logging()
    if len(argv) != 1 or argv[0] not in COMMANDS:
        print(f"usage: python -m app.cli [{'|'.join(COMMANDS)}]", file=sys.stderr)
        return 2
    return COMMANDS[argv[0]]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
