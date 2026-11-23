"""Service for generating daily newsletter briefings and executing subscriber deliveries."""

import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import logger
from app.models.article import NewsArticle
from app.models.newsletter import EmailSubscriber, NewsletterCampaign, NewsletterDelivery
from app.newsletter.provider import EmailProvider, SMTPEmailProvider
from app.newsletter.service import generate_unsubscribe_token
from app.newsletter.templates import render_newsletter_email
from app.repositories import newsletter_repository


class NewsletterCampaignService:
    """Orchestrates newsletter article curation, campaign generation, and batch dispatch."""

    def __init__(self, email_provider: Optional[EmailProvider] = None):
        self.email_provider = email_provider or SMTPEmailProvider()

    async def select_curated_articles(
        self,
        db: AsyncSession,
        limit: int = settings.NEWSLETTER_MAX_ARTICLES,
        min_quality_score: float = settings.NEWSLETTER_MIN_QUALITY_SCORE,
    ) -> List[NewsArticle]:
        """Selects high-quality, verified published articles prioritized by editorial significance."""
        now = datetime.datetime.now(datetime.timezone.utc)
        lookback_window = now - datetime.timedelta(hours=48)

        # 1. Fetch recent campaign article IDs to avoid repeated content
        recent_campaigns_stmt = select(NewsletterCampaign.article_ids).where(
            NewsletterCampaign.created_at >= lookback_window
        )
        recent_res = await db.execute(recent_campaigns_stmt)
        excluded_article_ids: set[int] = set()
        for row in recent_res.scalars():
            if isinstance(row, list):
                excluded_article_ids.update(row)

        # 2. Query published articles matching editorial standards
        stmt = (
            select(NewsArticle)
            .options(
                selectinload(NewsArticle.source),
                selectinload(NewsArticle.category),
            )
            .where(
                NewsArticle.status == "published",
                NewsArticle.quality_score >= min_quality_score,
                NewsArticle.published_at >= lookback_window,
            )
        )
        if excluded_article_ids:
            stmt = stmt.where(NewsArticle.id.not_in(list(excluded_article_ids)))

        stmt = stmt.order_by(
            NewsArticle.is_breaking.desc(),
            NewsArticle.is_trending.desc(),
            NewsArticle.quality_score.desc(),
            NewsArticle.published_at.desc(),
        ).limit(limit)

        result = await db.execute(stmt)
        articles = list(result.scalars().all())

        # Fallback if no fresh un-sent articles in past 48h: query top recent without exclusion
        if not articles:
            fallback_stmt = (
                select(NewsArticle)
                .options(
                    selectinload(NewsArticle.source),
                    selectinload(NewsArticle.category),
                )
                .where(
                    NewsArticle.status == "published",
                    NewsArticle.quality_score >= min_quality_score,
                )
                .order_by(
                    NewsArticle.is_breaking.desc(),
                    NewsArticle.is_trending.desc(),
                    NewsArticle.quality_score.desc(),
                    NewsArticle.published_at.desc(),
                )
                .limit(limit)
            )
            fallback_res = await db.execute(fallback_stmt)
            articles = list(fallback_res.scalars().all())

        return articles

    async def create_daily_campaign(
        self,
        db: AsyncSession,
        scheduled_date: Optional[datetime.date] = None,
    ) -> Optional[NewsletterCampaign]:
        """Creates a single daily newsletter briefing campaign record and populates pending deliveries."""
        now = datetime.datetime.now(datetime.timezone.utc)
        target_date = scheduled_date or now.date()
        start_of_day = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=datetime.timezone.utc)
        end_of_day = datetime.datetime.combine(target_date, datetime.time.max, tzinfo=datetime.timezone.utc)

        # Deduplication: Ensure only one campaign is scheduled per calendar day
        existing = await newsletter_repository.get_campaign_by_scheduled_range(
            db, start_time=start_of_day, end_time=end_of_day
        )
        if existing:
            logger.info(f"Campaign already exists for date {target_date} (ID: {existing.id}, Status: {existing.status})")
            return existing

        # Select articles
        articles = await self.select_curated_articles(db)
        if not articles:
            logger.warning("No eligible articles found for newsletter generation. Skipping campaign.")
            return None

        article_ids = [a.id for a in articles]
        date_str = target_date.strftime("%B %d, %Y")
        subject = f"MetroScope Daily Briefing — {date_str}"

        campaign = await newsletter_repository.create_campaign(
            db=db,
            subject=subject,
            scheduled_for=now,
            article_ids=article_ids,
            status="draft",
        )

        # Fetch active subscribers
        active_subscribers = await newsletter_repository.list_active_subscribers(db)
        if not active_subscribers:
            logger.info("No active subscribers registered. Campaign created with 0 recipients.")
            campaign.status = "sent"
            campaign.sent_at = now
            await db.commit()
            await db.refresh(campaign)
            return campaign

        # Create delivery tracking rows
        subscriber_ids = [sub.id for sub in active_subscribers]
        await newsletter_repository.create_deliveries_for_campaign(
            db=db,
            campaign_id=campaign.id,
            subscriber_ids=subscriber_ids,
        )
        campaign.recipient_count = len(subscriber_ids)
        await db.commit()
        await db.refresh(campaign)

        logger.info(
            f"Created newsletter campaign #{campaign.id} with {len(articles)} articles for {len(subscriber_ids)} active subscribers."
        )
        return campaign

    async def deliver_campaign(
        self,
        db: AsyncSession,
        campaign_id: int,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        """Dispatches email deliveries for all pending recipients in a campaign."""
        campaign = await newsletter_repository.get_campaign(db, campaign_id)
        if not campaign:
            return {"success": False, "error": f"Campaign #{campaign_id} not found"}

        if campaign.status in ("sent", "sending") and campaign.delivered_count == campaign.recipient_count:
            logger.info(f"Campaign #{campaign_id} already fully dispatched.")
            return {
                "success": True,
                "campaign_id": campaign.id,
                "recipient_count": campaign.recipient_count,
                "delivered_count": campaign.delivered_count,
                "failed_count": campaign.failed_count,
                "status": campaign.status,
            }

        campaign.status = "sending"
        await db.commit()

        # Load articles for this campaign
        art_stmt = (
            select(NewsArticle)
            .options(
                selectinload(NewsArticle.source),
                selectinload(NewsArticle.category),
            )
            .where(NewsArticle.id.in_(campaign.article_ids))
        )
        art_res = await db.execute(art_stmt)
        articles = list(art_res.scalars().all())

        # Format article data for email template
        articles_data = []
        for art in articles:
            articles_data.append(
                {
                    "title": art.title,
                    "category": art.category.name if art.category else "General",
                    "source": art.source.name if art.source else "MetroScope",
                    "url": f"{settings.SITE_URL.rstrip('/')}/article/{art.slug}",
                    "summary": (getattr(art, "description", None) or getattr(art, "meta_description", None) or "")[:180],
                }
            )

        date_str = campaign.scheduled_for.strftime("%B %d, %Y")
        delivered_count = campaign.delivered_count
        failed_count = campaign.failed_count

        while True:
            pending_batch = await newsletter_repository.get_pending_deliveries(
                db=db,
                campaign_id=campaign.id,
                limit=batch_size,
            )
            if not pending_batch:
                break

            for delivery in pending_batch:
                sub = delivery.subscriber
                if not sub or sub.status != "active":
                    delivery.status = "failed"
                    delivery.error_message = "Subscriber is not active"
                    failed_count += 1
                    continue

                raw_unsub_token = generate_unsubscribe_token(sub.email_normalized)
                unsub_url = f"{settings.SITE_URL.rstrip('/')}/unsubscribe?token={raw_unsub_token}"

                html_body, text_body = render_newsletter_email(
                    campaign_date=date_str,
                    articles=articles_data,
                    unsubscribe_url=unsub_url,
                )

                result = await self.email_provider.send_email(
                    to_email=sub.email,
                    subject=campaign.subject,
                    html_body=html_body,
                    text_body=text_body,
                )

                now = datetime.datetime.now(datetime.timezone.utc)
                if result.success:
                    delivery.status = "sent"
                    delivery.sent_at = now
                    delivery.error_message = None
                    delivered_count += 1
                else:
                    delivery.status = "failed"
                    delivery.error_message = result.error_message
                    failed_count += 1

            campaign.delivered_count = delivered_count
            campaign.failed_count = failed_count
            await db.commit()

        now = datetime.datetime.now(datetime.timezone.utc)
        campaign.sent_at = now
        campaign.status = "sent" if delivered_count > 0 or failed_count == 0 else "failed"
        await db.commit()
        await db.refresh(campaign)

        logger.info(
            f"Campaign #{campaign.id} completed. Delivered: {campaign.delivered_count}, Failed: {campaign.failed_count}"
        )
        return {
            "success": True,
            "campaign_id": campaign.id,
            "recipient_count": campaign.recipient_count,
            "delivered_count": campaign.delivered_count,
            "failed_count": campaign.failed_count,
            "status": campaign.status,
        }
