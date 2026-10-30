"""Export matching logs as JSON or CSV (max 10 000 rows per request)."""

import csv
import io
import json
from collections.abc import Iterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import isoformat_utc, utcnow
from app.schemas.logs import AppLogEntry, ExportParams
from app.services.log_query import AnyEntry, build_plan, count_logs, fetch_logs

CSV_COLUMNS = [
    "log_type",
    "id",
    "timestamp",
    "source_service",
    "environment",
    "level",
    "message",
    "trace_id",
    "context_json",
    "actor_type",
    "actor_id",
    "action",
    "target_resource",
    "outcome",
    "ip_address",
    "detail_json",
    "ingested_at",
]
# Spreadsheet apps execute cells that start with these characters.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _row(entry: AnyEntry) -> dict[str, Any]:
    data = entry.model_dump(mode="json")
    if isinstance(entry, AppLogEntry):
        data.pop("created_at", None)
    else:
        data.pop("event_time", None)
    return data


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict | list):
        value = json.dumps(value, ensure_ascii=False)
    text = str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def _csv_lines(rows: list[dict[str, Any]]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow([_csv_cell(row.get(col)) for col in CSV_COLUMNS])
        if buffer.tell() > 64 * 1024:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()
    yield buffer.getvalue()


async def export_logs(db: AsyncSession, params: ExportParams) -> tuple[Iterator[str], str, int]:
    """Return (body chunks, media type, total matching rows)."""
    plan = build_plan(params)
    total = await count_logs(db, plan)
    entries = await fetch_logs(db, plan, params.sort, 0, params.limit) if total else []
    rows = [_row(e) for e in entries]

    if params.format == "csv":
        return _csv_lines(rows), "text/csv; charset=utf-8", total

    document = {
        "exported_at": isoformat_utc(utcnow()),
        "total_matching": total,
        "exported": len(rows),
        "truncated": total > len(rows),
        "filters": params.model_dump(mode="json", exclude={"format", "limit"}, exclude_none=True),
        "data": rows,
    }
    return iter([json.dumps(document, ensure_ascii=False, indent=2)]), "application/json", total
