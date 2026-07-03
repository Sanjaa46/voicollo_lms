# =============================================================================
# purpose:  APScheduler configuration and job registration.
#           Manages the lifecycle of the background job scheduler,
#           integrated with FastAPI's lifespan context manager.
#           The retention job runs nightly at 02:00 Asia/Ulaanbaatar (UTC+8).
# implements: LMS-SDD-002 §3.5 (Retention Job — APScheduler)
#             LMS-SDD-002 §4   (APScheduler 3.x)
#             LMS-BRD-001 §7.1 (Server timezone: Asia/Ulaanbaatar UTC+8)
# =============================================================================

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.jobs.retention import run_retention_job

logger = logging.getLogger(__name__)

# Module-level scheduler singleton — initialised once at startup.
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """
    Returns the scheduler singleton.
    Raises RuntimeError if init_scheduler() has not been called.
    """
    if _scheduler is None:
        raise RuntimeError(
            "Scheduler not initialised. Call init_scheduler() at startup."
        )
    return _scheduler


def init_scheduler() -> AsyncIOScheduler:
    """
    Creates and configures the APScheduler instance.
    Registers all background jobs.
    Does NOT start the scheduler — call start_scheduler() after init.

    Called during application startup (app/main.py lifespan).

    LMS-SDD-002 §3.5: "APScheduler (recommended: 02:00 Asia/Ulaanbaatar)"
    LMS-BRD-001 §7.1: "Server timezone is Asia/Ulaanbaatar (UTC+8)"
    """
    global _scheduler
    settings = get_settings()

    _scheduler = AsyncIOScheduler(
        # Use Asia/Ulaanbaatar timezone for all cron expressions.
        # This ensures the retention job runs at 02:00 local time
        # regardless of the server's system timezone setting.
        timezone="Asia/Ulaanbaatar",
        job_defaults={
            # If a job run is missed (e.g. server was down), do not
            # retroactively execute it when the server comes back up.
            "misfire_grace_time": 300,  # 5-minute window to still run a missed job.
            "coalesce": True,           # If multiple runs were missed, run only once.
            "max_instances": 1,         # Never run two instances of the same job.
        },
    )

    # -------------------------------------------------------------------------
    # Register: Nightly Retention Job
    # LMS-SDD-002 §3.5: "Runs nightly via APScheduler (recommended: 02:00 Asia/Ulaanbaatar)"
    # LMS-BRD-001 FR-12, FR-13: retention enforcement is a MUST requirement.
    # -------------------------------------------------------------------------
    _scheduler.add_job(
        func=run_retention_job,
        trigger=CronTrigger(
            hour=settings.retention_job_hour,
            minute=settings.retention_job_minute,
            timezone="Asia/Ulaanbaatar",
        ),
        id="retention_job",
        name="Nightly Log Retention Purge",
        replace_existing=True,
    )

    logger.info(
        "Scheduler initialised. Retention job scheduled at %02d:%02d Asia/Ulaanbaatar.",
        settings.retention_job_hour,
        settings.retention_job_minute,
    )

    return _scheduler


def start_scheduler() -> None:
    """
    Starts the APScheduler instance.
    Must be called after init_scheduler() and after the event loop is running
    (i.e. inside the FastAPI lifespan async context).
    """
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("Background job scheduler started.")
    else:
        logger.warning("Scheduler start called but scheduler is already running.")


def shutdown_scheduler() -> None:
    """
    Gracefully shuts down the scheduler, waiting for any running jobs to complete.
    Called during application shutdown (app/main.py lifespan).
    """
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=True)
        logger.info("Background job scheduler shut down gracefully.")
