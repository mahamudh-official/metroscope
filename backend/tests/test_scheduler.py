from app.workers.scheduler import create_scheduler


def test_create_scheduler():
    scheduler = create_scheduler()
    assert scheduler is not None
    job = scheduler.get_job("gdelt_discovery_poller")
    assert job is not None
    assert job.name == "GDELT DOC 2.0 News Poller"
