import pytest
import asyncio
from unittest.mock import patch, AsyncMock
from app.workers.jobs import (
    collect_webz_sports_morning_job,
    collect_webz_business_evening_job,
    _webz_collection_lock,
)


@pytest.mark.asyncio
async def test_webz_worker_prevents_concurrent_sports_runs():
    """If the execution lock is held, morning sports job exits immediately."""
    async with _webz_collection_lock:
        with patch("app.workers.jobs.WebzIngestionService") as mock_service_cls:
            result = await collect_webz_sports_morning_job()
            assert result["status"] == "skipped"
            assert result["reason"] == "lock_busy"
            mock_service_cls.assert_not_called()


@pytest.mark.asyncio
async def test_webz_worker_prevents_concurrent_business_runs():
    """If the execution lock is held, evening business job exits immediately."""
    async with _webz_collection_lock:
        with patch("app.workers.jobs.WebzIngestionService") as mock_service_cls:
            result = await collect_webz_business_evening_job()
            assert result["status"] == "skipped"
            assert result["reason"] == "lock_busy"
            mock_service_cls.assert_not_called()
