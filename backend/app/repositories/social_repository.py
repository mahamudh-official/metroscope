import datetime
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.article import NewsArticle
from app.models.social import SocialPost


async def get_social_post(
    db: AsyncSession, article_id: int, platform: str
) -> Optional[SocialPost]:
    """Retrieves a social post record by article ID and platform."""
    stmt = select(SocialPost).where(
        SocialPost.article_id == article_id,
        SocialPost.platform == platform.lower().strip(),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_or_update_social_post(
    db: AsyncSession,
    article_id: int,
    platform: str,
    status: str = "PENDING",
    external_post_id: Optional[str] = None,
    content: Optional[str] = None,
    scheduled_at: Optional[datetime.datetime] = None,
    published_at: Optional[datetime.datetime] = None,
    error_message: Optional[str] = None,
    increment_attempt: bool = False,
) -> SocialPost:
    """Creates a new social post tracking record or updates an existing one."""
    post = await get_social_post(db, article_id=article_id, platform=platform)

    if not post:
        post = SocialPost(
            article_id=article_id,
            platform=platform.lower().strip(),
            status=status.upper(),
            external_post_id=external_post_id,
            content=content,
            scheduled_at=scheduled_at,
            published_at=published_at,
            attempt_count=1 if increment_attempt else 0,
            last_error=error_message,
        )
        db.add(post)
    else:
        post.status = status.upper()
        if external_post_id is not None:
            post.external_post_id = external_post_id
        if content is not None:
            post.content = content
        if scheduled_at is not None:
            post.scheduled_at = scheduled_at
        if published_at is not None:
            post.published_at = published_at
        if error_message is not None:
            post.last_error = error_message
        if increment_attempt:
            post.attempt_count += 1

    await db.flush()
    return post


async def get_eligible_articles_for_social(
    db: AsyncSession,
    platform: str,
    min_quality_score: float = 70.0,
    limit: int = 2,
) -> List[NewsArticle]:
    """Retrieves high-quality articles eligible for publishing on the specified platform.
    
    Filters out articles that have already been successfully published or are currently
    in-flight (PUBLISHED, PUBLISHING) for this platform.
    Orders by editorial priority: breaking news first, then trending stories,
    then highest quality score, then recency.
    """
    plat = platform.lower().strip()

    # Subquery for article IDs already published, publishing, or ambiguous on this platform.
    # Excludes FAILED_AMBIGUOUS and RECONCILIATION_REQUIRED to prevent accidental duplicate publishing.
    published_subq = (
        select(SocialPost.article_id)
        .where(
            SocialPost.platform == plat,
            SocialPost.status.in_([
                "PUBLISHED",
                "PUBLISHING",
                "FAILED_AMBIGUOUS",
                "RECONCILIATION_REQUIRED",
            ]),
        )
        .scalar_subquery()
    )

    stmt = (
        select(NewsArticle)
        .options(
            selectinload(NewsArticle.source),
            selectinload(NewsArticle.category),
        )
        .where(
            NewsArticle.status == "published",
            NewsArticle.quality_score >= min_quality_score,
            ~NewsArticle.id.in_(published_subq),
        )
        .order_by(
            NewsArticle.is_breaking.desc(),
            NewsArticle.is_trending.desc(),
            NewsArticle.quality_score.desc(),
            NewsArticle.published_at.desc(),
        )
        .limit(limit)
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_social_posts(
    db: AsyncSession,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[SocialPost]:
    """Lists social posts for inspection and auditing."""
    stmt = (
        select(SocialPost)
        .options(selectinload(SocialPost.article))
        .order_by(SocialPost.created_at.desc())
        .limit(limit)
    )
    if platform:
        stmt = stmt.where(SocialPost.platform == platform.lower().strip())
    if status:
        stmt = stmt.where(SocialPost.status == status.upper().strip())

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_stale_publishing_posts(
    db: AsyncSession,
    stale_threshold_minutes: int = 60,
    limit: int = 50,
) -> List[SocialPost]:
    """Retrieves social posts stuck in 'PUBLISHING' state longer than the threshold.

    Uses `with_for_update(skip_locked=True)` on supported backends (PostgreSQL)
    to safely prevent concurrent worker processes from racing on the same records.
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        minutes=stale_threshold_minutes
    )
    stmt = (
        select(SocialPost)
        .where(
            SocialPost.status == "PUBLISHING",
            SocialPost.updated_at <= cutoff,
        )
        .order_by(SocialPost.updated_at.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def recover_stale_publishing_post(
    db: AsyncSession,
    post: SocialPost,
    stale_threshold_minutes: int = 60,
) -> SocialPost:
    """Conservatively marks a stale PUBLISHING record as FAILED_AMBIGUOUS.

    Guarantees duplicate prevention by ensuring the post is never automatically
    re-published without explicit operator verification.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    post.status = "FAILED_AMBIGUOUS"
    post.recovered_at = now
    post.recovery_notes = (
        f"Post was stuck in 'PUBLISHING' state for >{stale_threshold_minutes} minutes "
        f"following worker crash or unhandled termination. Marked as FAILED_AMBIGUOUS "
        f"to guarantee zero duplicate external publishing. Requires manual operator reconciliation."
    )
    post.last_error = (
        f"Stale in PUBLISHING for >{stale_threshold_minutes}m; outcome unknown."
    )
    await db.flush()
    return post


async def get_published_count_in_window(
    db: AsyncSession,
    platform: str,
    window_hours: int = 24,
) -> int:
    """Returns number of posts that consumed platform quota in rolling window.
    
    Includes PUBLISHED, FAILED_AMBIGUOUS, and RECONCILIATION_REQUIRED records to
    conservatively protect external platform rate limits (e.g. X Free tier 15/24h).
    """
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=window_hours)
    stmt = (
        select(func.count(SocialPost.id))
        .where(
            SocialPost.platform == platform.lower().strip(),
            SocialPost.status.in_(["PUBLISHED", "FAILED_AMBIGUOUS", "RECONCILIATION_REQUIRED"]),
            (SocialPost.published_at >= since) | (SocialPost.created_at >= since),
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0

