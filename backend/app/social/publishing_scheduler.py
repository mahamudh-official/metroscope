"""Scheduled job functions and execution locks for automated social publishing."""

import asyncio
import datetime
from app.core.config import settings
from app.core.logging import logger
from app.db.session import async_session_factory
from app.social.publishing_service import SocialPublishingService

_social_publishing_lock = asyncio.Lock()
_social_recovery_lock = asyncio.Lock()


async def recover_stale_publishing_job() -> None:
    """Scheduled background job to recover stale PUBLISHING records.

    Uses an asyncio lock and database skip-locked transactions to prevent
    overlapping recovery executions.
    """
    if _social_recovery_lock.locked():
        logger.warning(
            "Social stale recovery job is already in progress; skipping this scheduled cycle to prevent overlap."
        )
        return

    async with _social_recovery_lock:
        try:
            async with async_session_factory() as session:
                service = SocialPublishingService()
                stats = await service.recover_stale_records(db=session)
                if stats.get("recovered", 0) > 0:
                    logger.info(
                        f"Stale publishing recovery job successfully recovered {stats['recovered']} records."
                    )
        except Exception as exc:
            logger.exception(f"Unexpected error during stale publishing recovery job: {exc}")


async def publish_social_news_job() -> None:
    """Scheduled background job to publish eligible news articles to Facebook and X.
    
    Uses an asyncio lock to ensure executions never overlap if a batch takes longer
    than the configured publishing interval.
    """
    if not settings.SOCIAL_PUBLISHING_ENABLED:
        logger.debug("Social publishing is disabled globally (SOCIAL_PUBLISHING_ENABLED=False); skipping cycle.")
        return

    if _social_publishing_lock.locked():
        logger.warning(
            "Social publishing job is already in progress; skipping this scheduled cycle to prevent overlap."
        )
        return

    async with _social_publishing_lock:
        start_time = datetime.datetime.now(datetime.timezone.utc)
        logger.info(
            f"Executing scheduled social publishing cycle at {start_time.isoformat()} "
            f"(dry_run={settings.SOCIAL_DRY_RUN})..."
        )

        try:
            async with async_session_factory() as session:
                service = SocialPublishingService()
                summary = await service.run_publishing_cycle(db=session)

                elapsed = (datetime.datetime.now(datetime.timezone.utc) - start_time).total_seconds()
                logger.info(
                    f"Social publishing cycle completed in {elapsed:.2f}s: "
                    f"Facebook: {summary.get('facebook', {})}, X: {summary.get('x', {})}"
                )
        except Exception as exc:
            logger.exception(f"Unexpected error during social publishing job execution: {exc}")
