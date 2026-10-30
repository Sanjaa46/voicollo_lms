"""Time helpers. Rule: the database stores *naive UTC*; the API emits ISO-8601 UTC ("Z")."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import PlainSerializer


def utcnow() -> datetime:
    """Current time as naive UTC (the storage format)."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_utc_naive(value: datetime) -> datetime:
    """Normalise any datetime to naive UTC. Naive input is assumed to already be UTC."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def isoformat_utc(value: datetime) -> str:
    return as_aware_utc(value).isoformat(timespec="milliseconds").replace("+00:00", "Z")


UTCDateTime = Annotated[
    datetime,
    PlainSerializer(isoformat_utc, return_type=str, when_used="json"),
]
"""Datetime field that always serialises as `2026-01-01T00:00:00.000Z`."""
