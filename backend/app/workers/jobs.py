import datetime
from app.core.logging import logger
from app.integrations.gdelt.client import GDELTClient, GDELTAPIError


async def poll_gdelt_news_job() -> None:
    """Scheduled job to check GDELT DOC 2.0 API news signals.
    
    In Phase 1, this foundation polls the endpoint, logs discovery metrics,
    and tests API connectivity. Production pipeline storage and automated
    distribution will be activated in subsequent development phases.
    """
    logger.info("Executing scheduled GDELT news discovery check...")
    client = GDELTClient()

    try:
        data = await client.fetch_articles(query="sourcecountry:US", max_records=5)
        articles = data.get("articles", [])
        logger.info(
            f"GDELT discovery cycle complete at {datetime.datetime.now(datetime.timezone.utc).isoformat()}: "
            f"{len(articles)} candidate articles detected."
        )
        for idx, art in enumerate(articles[:3], 1):
            title = art.get("title", "No Title")
            domain = art.get("domain", "Unknown Source")
            logger.debug(f"Candidate #{idx}: [{domain}] {title}")

    except GDELTAPIError as exc:
        logger.warning(f"GDELT scheduled polling experienced upstream error: {exc}")
    except Exception as exc:
        logger.exception(f"Unexpected error during GDELT worker job: {exc}")
