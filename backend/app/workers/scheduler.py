from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.core.config import settings
from app.core.logging import logger
from app.workers.jobs import poll_gdelt_news_job


def create_scheduler() -> AsyncIOScheduler:
    """Initializes APScheduler for periodic news discovery execution."""
    scheduler = AsyncIOScheduler()

    interval_minutes = settings.GDELT_POLL_INTERVAL_MINUTES
    trigger = IntervalTrigger(minutes=interval_minutes)

    scheduler.add_job(
        poll_gdelt_news_job,
        trigger=trigger,
        id="gdelt_discovery_poller",
        name="GDELT DOC 2.0 News Poller",
        replace_existing=True,
        max_instances=1,
    )

    logger.info(
        f"Configured APScheduler with GDELT polling interval of {interval_minutes} minutes"
    )
    return scheduler
