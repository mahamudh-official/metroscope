import pytest
from unittest.mock import AsyncMock, patch
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.social.publishing_scheduler import (
    _social_publishing_lock,
    _social_recovery_lock,
    publish_social_news_job,
    recover_stale_publishing_job,
)
from app.workers.scheduler import create_scheduler


def test_scheduler_registers_social_publishing_job():
    scheduler = create_scheduler()
    jobs = scheduler.get_jobs()
    job_ids = [j.id for j in jobs]

    assert "webz_morning_collection" in job_ids
    assert "webz_morning_sports" not in job_ids
    assert "webz_evening_business" in job_ids
    assert "gdelt_discovery_poller" not in job_ids
    assert "social_news_publisher" in job_ids
    assert "social_stale_recovery" in job_ids

    recovery_job = scheduler.get_job("social_stale_recovery")
    assert isinstance(recovery_job.trigger, IntervalTrigger)
    assert recovery_job.max_instances == 1


@pytest.mark.asyncio
async def test_publish_social_news_job_disabled_skips_cleanly():
    with patch.object(settings, "SOCIAL_PUBLISHING_ENABLED", False):
        with patch("app.social.publishing_scheduler.SocialPublishingService") as mock_service:
            await publish_social_news_job()
            mock_service.assert_not_called()


@pytest.mark.asyncio
async def test_publish_social_news_job_lock_overlap_prevention():
    # Simulate an active running lock
    async with _social_publishing_lock:
        with patch.object(settings, "SOCIAL_PUBLISHING_ENABLED", True):
            with patch("app.social.publishing_scheduler.SocialPublishingService") as mock_service:
                await publish_social_news_job()
                # Should return early due to lock being acquired
                mock_service.assert_not_called()


@pytest.mark.asyncio
async def test_recover_stale_publishing_job_lock_overlap_prevention():
    async with _social_recovery_lock:
        with patch("app.social.publishing_scheduler.SocialPublishingService") as mock_service:
            await recover_stale_publishing_job()
            mock_service.assert_not_called()
