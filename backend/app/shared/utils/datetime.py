import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ_ENV = os.environ.get("TZ", "Asia/Ulaanbaatar")
UB_TIMEZONE = ZoneInfo(TZ_ENV)

def now_utc() -> datetime:
    """Return the current UTC time."""
    return datetime.now(timezone.utc)

def to_ulaanbaatar(dt: datetime) -> datetime:
    """Convert a UTC datetime to Ulaanbaatar time (UTC+8)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(UB_TIMEZONE)

def now_ulaanbaatar() -> datetime:
    """Return the current time in Ulaanbaatar (UTC+8)."""
    return now_utc().astimezone(UB_TIMEZONE)