"""Repository layer for email subscribers, newsletter campaigns, and deliveries."""

import datetime
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.newsletter import EmailSubscriber, NewsletterCampaign, NewsletterDelivery


async def get_subscriber_by_email_normalized(
    db: AsyncSession, email_normalized: str
) -> Optional[EmailSubscriber]:
    """Retrieves a subscriber record by normalized email address."""
    stmt = select(EmailSubscriber).where(
        EmailSubscriber.email_normalized == email_normalized
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_subscriber_by_verification_token_hash(
    db: AsyncSession, token_hash: str
) -> Optional[EmailSubscriber]:
    """Retrieves a subscriber by their SHA-256 hashed verification token."""
    stmt = select(EmailSubscriber).where(
        EmailSubscriber.verification_token_hash == token_hash
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_subscriber_by_unsubscribe_token_hash(
    db: AsyncSession, token_hash: str
) -> Optional[EmailSubscriber]:
    """Retrieves a subscriber by their SHA-256 hashed unsubscribe token."""
    stmt = select(EmailSubscriber).where(
        EmailSubscriber.unsubscribe_token_hash == token_hash
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_subscriber(
    db: AsyncSession,
    email: str,
    email_normalized: str,
    verification_token_hash: str,
    verification_expires_at: datetime.datetime,
    unsubscribe_token_hash: str,
) -> EmailSubscriber:
    """Creates a new pending email subscriber record."""
    now = datetime.datetime.now(datetime.timezone.utc)
    subscriber = EmailSubscriber(
        email=email.strip(),
        email_normalized=email_normalized,
        status="pending",
        verification_token_hash=verification_token_hash,
        verification_sent_at=now,
        verification_expires_at=verification_expires_at,
        unsubscribe_token_hash=unsubscribe_token_hash,
    )
    db.add(subscriber)
    await db.flush()
    return subscriber


async def count_active_subscribers(db: AsyncSession) -> int:
    """Counts the total number of verified, active newsletter subscribers."""
    stmt = (
        select(func.count(EmailSubscriber.id))
        .where(EmailSubscriber.status == "active")
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def count_recent_subscriptions(
    db: AsyncSession, since: datetime.datetime
) -> int:
    """Counts subscriptions created since a given timestamp for rate limiting."""
    stmt = (
        select(func.count(EmailSubscriber.id))
        .where(EmailSubscriber.created_at >= since)
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def list_active_subscribers(
    db: AsyncSession, limit: Optional[int] = None, offset: int = 0
) -> List[EmailSubscriber]:
    """Retrieves a paginated list of active subscribers."""
    stmt = (
        select(EmailSubscriber)
        .where(EmailSubscriber.status == "active")
        .order_by(EmailSubscriber.id.asc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_campaign(
    db: AsyncSession, campaign_id: int
) -> Optional[NewsletterCampaign]:
    """Retrieves a campaign by primary key."""
    stmt = select(NewsletterCampaign).where(NewsletterCampaign.id == campaign_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_campaign_by_scheduled_range(
    db: AsyncSession,
    start_time: datetime.datetime,
    end_time: datetime.datetime,
) -> Optional[NewsletterCampaign]:
    """Retrieves any campaign scheduled within a specific time window to avoid duplicate runs."""
    stmt = select(NewsletterCampaign).where(
        NewsletterCampaign.scheduled_for >= start_time,
        NewsletterCampaign.scheduled_for < end_time,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_campaign(
    db: AsyncSession,
    subject: str,
    scheduled_for: datetime.datetime,
    article_ids: List[int],
    status: str = "draft",
) -> NewsletterCampaign:
    """Creates a new newsletter campaign record."""
    campaign = NewsletterCampaign(
        subject=subject,
        scheduled_for=scheduled_for,
        article_ids=article_ids,
        status=status,
    )
    db.add(campaign)
    await db.flush()
    return campaign


async def create_deliveries_for_campaign(
    db: AsyncSession,
    campaign_id: int,
    subscriber_ids: List[int],
) -> int:
    """Bulk creates pending delivery tracking records for a campaign."""
    deliveries = [
        NewsletterDelivery(
            campaign_id=campaign_id,
            subscriber_id=sub_id,
            status="pending",
        )
        for sub_id in subscriber_ids
    ]
    db.add_all(deliveries)
    await db.flush()
    return len(deliveries)


async def get_pending_deliveries(
    db: AsyncSession,
    campaign_id: int,
    limit: int = 100,
) -> List[NewsletterDelivery]:
    """Retrieves pending delivery records for a campaign with eager-loaded subscriber data."""
    stmt = (
        select(NewsletterDelivery)
        .options(selectinload(NewsletterDelivery.subscriber))
        .where(
            NewsletterDelivery.campaign_id == campaign_id,
            NewsletterDelivery.status == "pending",
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
