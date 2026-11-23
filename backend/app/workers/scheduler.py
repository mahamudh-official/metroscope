from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from app.core.config import settings
from app.core.logging import logger
from app.newsletter.scheduler import deliver_newsletter_campaign_job
from app.social.publishing_scheduler import (
    publish_social_news_job,
    recover_stale_publishing_job,
)
from app.workers.jobs import (
    collect_webz_morning_job,
    collect_webz_evening_job,
)


def create_scheduler() -> AsyncIOScheduler:
    """Initializes APScheduler with single-provider Webz.io scheduled news collection,
    social publishing, and daily newsletter briefing.
    
    Collection Schedule:
    - 08:00 Asia/Dhaka: Multi-Category Morning Collection (Business, Science, Tech)
    - 20:00 Asia/Dhaka: Business, Finance & Economy Evening Collection
    
    Legacy GDELT and RSS discovery pollers are completely removed.
    """
    scheduler = AsyncIOScheduler()
    collection_tz = ZoneInfo(settings.WEBZ_IO_TIMEZONE)

    # 1a. Morning News Collection: Multi-Category (08:00 Asia/Dhaka)
    morning_trigger = CronTrigger(
        hour=settings.WEBZ_IO_MORNING_SCHEDULE_HOUR,
        minute=settings.WEBZ_IO_MORNING_SCHEDULE_MINUTE,
        timezone=collection_tz,
    )
    scheduler.add_job(
        collect_webz_morning_job,
        trigger=morning_trigger,
        id="webz_morning_collection",
        name="Webz.io Morning Multi-Category News Collection (08:00 Asia/Dhaka)",
        replace_existing=True,
        max_instances=1,
    )

    # 1b. Evening News Collection: Business, Finance & Economy (20:00 Asia/Dhaka)
    business_trigger = CronTrigger(
        hour=settings.WEBZ_IO_EVENING_SCHEDULE_HOUR,
        minute=settings.WEBZ_IO_EVENING_SCHEDULE_MINUTE,
        timezone=collection_tz,
    )
    scheduler.add_job(
        collect_webz_evening_job,
        trigger=business_trigger,
        id="webz_evening_business",
        name="Webz.io Evening Business News Collection (20:00 Asia/Dhaka)",
        replace_existing=True,
        max_instances=1,
    )

    # 2. Automated Social Media Publisher (Facebook & X)
    social_interval = settings.SOCIAL_PUBLISHING_INTERVAL_MINUTES
    social_trigger = IntervalTrigger(minutes=social_interval)

    scheduler.add_job(
        publish_social_news_job,
        trigger=social_trigger,
        id="social_news_publisher",
        name="Automated Social Media Publisher",
        replace_existing=True,
        max_instances=1,
    )

    # 3. Stale Social Publishing Recovery Job
    recovery_interval = settings.STALE_PUBLISHING_TIMEOUT_MINUTES
    recovery_trigger = IntervalTrigger(minutes=recovery_interval)

    scheduler.add_job(
        recover_stale_publishing_job,
        trigger=recovery_trigger,
        id="social_stale_recovery",
        name="Social Stale Publishing Recovery",
        replace_existing=True,
        max_instances=1,
    )

    # 4. Daily Newsletter Briefing Job
    newsletter_trigger = CronTrigger(
        hour=settings.NEWSLETTER_SCHEDULE_HOUR,
        minute=settings.NEWSLETTER_SCHEDULE_MINUTE,
    )

    scheduler.add_job(
        deliver_newsletter_campaign_job,
        trigger=newsletter_trigger,
        id="newsletter_daily_briefing",
        name="Daily Newsletter Briefing Dispatcher",
        replace_existing=True,
        max_instances=1,
    )

    logger.info(
        f"Configured APScheduler with Webz.io News Collection (08:00 Morning, 20:00 Evening {settings.WEBZ_IO_TIMEZONE}), "
        f"Social Publishing ({social_interval}m, enabled={settings.SOCIAL_PUBLISHING_ENABLED}, dry_run={settings.SOCIAL_DRY_RUN}), "
        f"Stale Recovery ({recovery_interval}m), "
        f"and Daily Newsletter Briefing ({settings.NEWSLETTER_SCHEDULE_HOUR:02d}:{settings.NEWSLETTER_SCHEDULE_MINUTE:02d} UTC, dry_run={settings.EMAIL_DRY_RUN})"
    )
    return scheduler
