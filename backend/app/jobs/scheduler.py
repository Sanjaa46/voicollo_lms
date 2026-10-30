"""APScheduler wiring for background jobs."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.jobs.retention import scheduled_retention

logger = logging.getLogger(__name__)

RETENTION_JOB_ID = "retention"
_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.retention_enabled:
        logger.info("Retention job disabled (RETENTION_ENABLED=false).")
        return
    _scheduler = AsyncIOScheduler(
        timezone=settings.scheduler_timezone,
        job_defaults={"misfire_grace_time": 3600, "coalesce": True, "max_instances": 1},
    )
    _scheduler.add_job(
        scheduled_retention,
        CronTrigger(
            hour=settings.retention_job_hour,
            minute=settings.retention_job_minute,
            timezone=settings.scheduler_timezone,
        ),
        id=RETENTION_JOB_ID,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Retention scheduled daily at %02d:%02d %s",
        settings.retention_job_hour,
        settings.retention_job_minute,
        settings.scheduler_timezone,
    )


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def next_retention_run() -> datetime | None:
    if _scheduler is None:
        return None
    job = _scheduler.get_job(RETENTION_JOB_ID)
    return job.next_run_time if job else None
