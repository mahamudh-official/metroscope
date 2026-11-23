"""Orchestration service for automated news distribution to Facebook and X."""

import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.article import NewsArticle
from app.models.social import SocialPost
from app.repositories.social_repository import (
    create_or_update_social_post,
    get_eligible_articles_for_social,
    get_published_count_in_window,
    get_stale_publishing_posts,
    recover_stale_publishing_post,
)
from app.social.base import SocialPlatformClient, SocialPostResult
from app.social.content_formatter import format_facebook_post, format_x_post
from app.social.facebook_client import FacebookPageClient
from app.social.x_client import XClient


class SocialPublishingService:
    """Coordinates automated social publishing across Facebook and X."""

    def __init__(
        self,
        facebook_client: Optional[SocialPlatformClient] = None,
        x_client: Optional[SocialPlatformClient] = None,
        dry_run: Optional[bool] = None,
        min_quality_score: Optional[float] = None,
        max_posts_per_run: Optional[int] = None,
        facebook_enabled: Optional[bool] = None,
        x_enabled: Optional[bool] = None,
        stale_timeout_minutes: Optional[int] = None,
        x_max_posts_per_day: Optional[int] = None,
        facebook_max_posts_per_day: Optional[int] = None,
    ):
        self.dry_run = settings.SOCIAL_DRY_RUN if dry_run is None else dry_run
        self.min_quality_score = (
            settings.SOCIAL_MIN_QUALITY_SCORE
            if min_quality_score is None
            else min_quality_score
        )
        self.max_posts_per_run = (
            settings.SOCIAL_MAX_POSTS_PER_RUN
            if max_posts_per_run is None
            else max_posts_per_run
        )
        self.facebook_enabled = settings.FACEBOOK_ENABLED if facebook_enabled is None else facebook_enabled
        self.x_enabled = settings.X_ENABLED if x_enabled is None else x_enabled
        self.stale_timeout_minutes = (
            settings.STALE_PUBLISHING_TIMEOUT_MINUTES
            if stale_timeout_minutes is None
            else stale_timeout_minutes
        )
        self.x_max_posts_per_day = (
            settings.X_MAX_POSTS_PER_DAY
            if x_max_posts_per_day is None
            else x_max_posts_per_day
        )
        self.facebook_max_posts_per_day = (
            settings.FACEBOOK_MAX_POSTS_PER_DAY
            if facebook_max_posts_per_day is None
            else facebook_max_posts_per_day
        )
        self.facebook_client = facebook_client or FacebookPageClient(dry_run=self.dry_run)
        self.x_client = x_client or XClient(dry_run=self.dry_run)

    async def recover_stale_records(self, db: AsyncSession) -> Dict[str, int]:
        """Recovers social posts stuck in 'PUBLISHING' state longer than stale_timeout_minutes.

        Transitions them to 'FAILED_AMBIGUOUS' with audit notes, preventing duplicate external publishing.
        """
        stale_posts = await get_stale_publishing_posts(
            db=db, stale_threshold_minutes=self.stale_timeout_minutes
        )
        recovered_count = 0
        for post in stale_posts:
            await recover_stale_publishing_post(
                db=db, post=post, stale_threshold_minutes=self.stale_timeout_minutes
            )
            recovered_count += 1
            logger.warning(
                f"Recovered stale PUBLISHING record #{post.id} (article #{post.article_id}, platform '{post.platform}'). "
                f"Marked as FAILED_AMBIGUOUS to prevent duplicate publishing."
            )

        if recovered_count > 0:
            await db.commit()
            logger.info(
                f"Stale publishing recovery completed: {recovered_count} records transitioned to FAILED_AMBIGUOUS."
            )

        return {"recovered": recovered_count}

    async def run_publishing_cycle(self, db: AsyncSession) -> Dict[str, Any]:
        """Executes a full social publishing cycle across enabled platforms.
        
        Failure on one platform is strictly isolated and will NOT block or cancel
        publishing on another platform.
        """
        # Step 0: Recover any stale PUBLISHING records first
        recovery_stats = await self.recover_stale_records(db=db)

        summary = {
            "executed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "dry_run": self.dry_run,
            "recovered_stale": recovery_stats.get("recovered", 0),
            "facebook": {"attempted": 0, "published": 0, "failed": 0},
            "x": {"attempted": 0, "published": 0, "failed": 0},
        }

        # 1. Facebook publishing
        if self.facebook_enabled or self.dry_run:
            try:
                fb_stats = await self._publish_to_platform(
                    db=db,
                    platform="facebook",
                    client=self.facebook_client,
                    formatter=format_facebook_post,
                )
                summary["facebook"] = fb_stats
            except Exception as fb_exc:
                logger.exception(f"Unexpected exception during Facebook publishing cycle: {fb_exc}")
                summary["facebook"]["error"] = str(fb_exc)
        else:
            logger.info("Facebook publishing is disabled in configuration; skipping.")

        # 2. X (Twitter) publishing (isolated execution)
        if self.x_enabled or self.dry_run:
            try:
                x_stats = await self._publish_to_platform(
                    db=db,
                    platform="x",
                    client=self.x_client,
                    formatter=format_x_post,
                )
                summary["x"] = x_stats
            except Exception as x_exc:
                logger.exception(f"Unexpected exception during X publishing cycle: {x_exc}")
                summary["x"]["error"] = str(x_exc)
        else:
            logger.info("X publishing is disabled in configuration; skipping.")

        return summary

    async def _publish_to_platform(
        self,
        db: AsyncSession,
        platform: str,
        client: SocialPlatformClient,
        formatter: Any,
    ) -> Dict[str, int]:
        """Publishes eligible articles to a single platform with atomic state updates."""
        stats = {"attempted": 0, "published": 0, "failed": 0}

        # Enforce rolling 24-hour quota limits
        daily_limit = (
            self.x_max_posts_per_day if platform == "x" else self.facebook_max_posts_per_day
        )
        if daily_limit is not None and daily_limit > 0:
            published_24h = await get_published_count_in_window(db, platform, window_hours=24)
            remaining_today = max(0, daily_limit - published_24h)
            if remaining_today <= 0:
                logger.warning(
                    f"Platform '{platform}' reached its rolling 24-hour publishing limit "
                    f"({published_24h}/{daily_limit} published). Skipping publishing run to protect quota."
                )
                stats["skipped_quota"] = 1
                return stats
            effective_limit = min(self.max_posts_per_run, remaining_today)
        else:
            effective_limit = self.max_posts_per_run

        eligible_articles = await get_eligible_articles_for_social(
            db=db,
            platform=platform,
            min_quality_score=self.min_quality_score,
            limit=effective_limit,
        )

        if not eligible_articles:
            logger.info(f"No eligible articles found for platform '{platform}' (threshold >= {self.min_quality_score})")
            return stats

        logger.info(
            f"Found {len(eligible_articles)} eligible articles for platform '{platform}'. "
            f"Beginning publication (dry_run={self.dry_run})..."
        )

        for article in eligible_articles:
            stats["attempted"] += 1
            now = datetime.datetime.now(datetime.timezone.utc)

            try:
                # 1. Format platform-specific content
                formatted_text = formatter(article)

                # 2. Mark state as PUBLISHING
                post_record = await create_or_update_social_post(
                    db=db,
                    article_id=article.id,
                    platform=platform,
                    status="PUBLISHING",
                    content=formatted_text,
                    scheduled_at=now,
                    increment_attempt=True,
                )
                await db.commit()

                # 3. Execute platform API request (or dry-run simulation)
                article_url = f"{settings.SITE_URL}/article/{article.slug}"
                result: SocialPostResult = await client.publish(
                    text=formatted_text,
                    link=article_url,
                    article_id=article.id,
                )

                # 4. Finalize database state
                if result.success:
                    await create_or_update_social_post(
                        db=db,
                        article_id=article.id,
                        platform=platform,
                        status="PUBLISHED",
                        external_post_id=result.external_post_id,
                        content=formatted_text,
                        published_at=now,
                        error_message=None,
                    )
                    stats["published"] += 1
                    logger.info(
                        f"Article #{article.id} successfully recorded as PUBLISHED to '{platform}' "
                        f"(post_id={result.external_post_id}, dry_run={result.dry_run})"
                    )
                elif result.ambiguous:
                    await create_or_update_social_post(
                        db=db,
                        article_id=article.id,
                        platform=platform,
                        status="FAILED_AMBIGUOUS",
                        external_post_id=result.external_post_id,
                        content=formatted_text,
                        error_message=result.error_message,
                    )
                    stats["failed"] += 1
                    logger.warning(
                        f"Article #{article.id} publishing to '{platform}' outcome ambiguous; marked FAILED_AMBIGUOUS: {result.error_message}"
                    )
                else:
                    await create_or_update_social_post(
                        db=db,
                        article_id=article.id,
                        platform=platform,
                        status="FAILED",
                        error_message=result.error_message,
                    )
                    stats["failed"] += 1
                    logger.warning(
                        f"Article #{article.id} publishing to '{platform}' failed: {result.error_message}"
                    )

                await db.commit()

            except Exception as item_exc:
                logger.exception(
                    f"Unhandled error while publishing article #{article.id} to '{platform}': {item_exc}"
                )
                try:
                    fallback_status = "FAILED"
                    fallback_post_id = None
                    if "result" in locals() and result is not None:
                        if result.success:
                            fallback_status = "RECONCILIATION_REQUIRED"
                            fallback_post_id = result.external_post_id
                        elif result.ambiguous:
                            fallback_status = "FAILED_AMBIGUOUS"

                    await create_or_update_social_post(
                        db=db,
                        article_id=article.id,
                        platform=platform,
                        status=fallback_status,
                        external_post_id=fallback_post_id,
                        error_message=f"Unhandled exception post-dispatch: {item_exc}",
                    )
                    await db.commit()
                except Exception:
                    await db.rollback()
                stats["failed"] += 1

        return stats
