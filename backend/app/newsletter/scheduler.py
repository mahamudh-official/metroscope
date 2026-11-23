"""Scheduled background job executing daily newsletter curation and delivery."""

import asyncio
from app.core.config import settings
from app.core.logging import logger
from app.db.session import async_session_factory
from app.newsletter.campaign_service import NewsletterCampaignService

_newsletter_campaign_lock = asyncio.Lock()


async def deliver_newsletter_campaign_job() -> None:
    """Scheduled task for curating and dispatching daily newsletter briefings."""
    if _newsletter_campaign_lock.locked():
        logger.info("[NEWSLETTER SCHEDULER] Daily campaign job already running. Skipping overlapping execution.")
        return

    async with _newsletter_campaign_lock:
        logger.info("[NEWSLETTER SCHEDULER] Starting scheduled daily newsletter campaign job...")
        try:
            async with async_session_factory() as db:
                campaign_service = NewsletterCampaignService()
                campaign = await campaign_service.create_daily_campaign(db)
                if not campaign:
                    logger.info("[NEWSLETTER SCHEDULER] No campaign created (no eligible stories or already created).")
                    return

                if campaign.recipient_count > 0:
                    summary = await campaign_service.deliver_campaign(db, campaign.id)
                    logger.info(
                        f"[NEWSLETTER SCHEDULER] Newsletter briefing #{campaign.id} completed. "
                        f"Delivered: {summary.get('delivered_count')}, Failed: {summary.get('failed_count')}"
                    )
                else:
                    logger.info(f"[NEWSLETTER SCHEDULER] Campaign #{campaign.id} generated with 0 active subscribers.")
        except Exception as exc:
            logger.error(f"[NEWSLETTER SCHEDULER] Unhandled exception in newsletter campaign job: {exc}", exc_info=True)
