import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import FAKE_INGEST_SIGNING_SECRET


async def test_ingest_app_log_returns_201(client, app_log_payload, mock_db):
    # Tell the mock DB what to return when log_service reads back the saved entry
    from app.models.application_log import ApplicationLog
    from datetime import datetime

    fake_log = ApplicationLog()
    fake_log.id = 1
    fake_log.ingested_at = datetime(2025, 6, 11, 6, 30, 0)
    mock_db.refresh = AsyncMock(
        side_effect=lambda obj: setattr(obj, 'id', 1) or setattr(obj, 'ingested_at', fake_log.ingested_at)
    )

    # Patch the service registration check so it doesn't hit the DB
    with patch("app.services.log_service._validate_service", AsyncMock(return_value=None)):
        response = await client.post("/api/v1/logs/app", json=app_log_payload)

    assert response.status_code == 201
    data = response.json()
    assert "log_id" in data
    assert "ingested_at" in data