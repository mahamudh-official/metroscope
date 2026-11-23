from zoneinfo import ZoneInfo
from app.core.config import settings
from app.workers.scheduler import create_scheduler


def test_create_scheduler_webz_jobs():
    """Verifies scheduler configuration with single-provider Webz.io acquisition:
    - Exactly two collection jobs (08:00 Sports, 20:00 Business) in Asia/Dhaka timezone
    - Zero active GDELT or RSS collection jobs
    - Social and newsletter jobs preserved
    """
    scheduler = create_scheduler()
    assert scheduler is not None

    # Verify Webz.io Morning Collection Job (08:00 Asia/Dhaka)
    morning_job = scheduler.get_job("webz_morning_collection")
    assert morning_job is not None
    assert "Morning" in morning_job.name
    # Trigger verification
    morning_trigger = morning_job.trigger
    assert any(f.name == "hour" and 8 in [e.first for e in f.expressions] for f in morning_trigger.fields)
    assert str(morning_trigger.timezone) == "Asia/Dhaka"

    # Verify redundant alias job is NOT registered (preventing duplicate triggers)
    assert scheduler.get_job("webz_morning_sports") is None

    # Verify Webz.io Evening Business Job (20:00 Asia/Dhaka)
    business_job = scheduler.get_job("webz_evening_business")
    assert business_job is not None
    assert "Business" in business_job.name
    business_trigger = business_job.trigger
    assert any(f.name == "hour" and 20 in [e.first for e in f.expressions] for f in business_trigger.fields)
    assert str(business_trigger.timezone) == "Asia/Dhaka"

    # Verify complete removal of legacy pollers
    assert scheduler.get_job("gdelt_discovery_poller") is None
    assert scheduler.get_job("rss_discovery_poller") is None

    # Verify preservation of social and newsletter scheduled jobs
    assert scheduler.get_job("social_news_publisher") is not None
    assert scheduler.get_job("social_stale_recovery") is not None
    assert scheduler.get_job("newsletter_daily_briefing") is not None
