import datetime
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.social import SocialPost
from app.models.source import NewsSource
from app.repositories.social_repository import get_eligible_articles_for_social, get_social_post
from app.social.base import SocialPlatformClient, SocialPostResult
from app.social.publishing_service import SocialPublishingService


class MockFailingClient(SocialPlatformClient):
    @property
    def platform_name(self) -> str:
        return "facebook"

    def is_configured(self) -> bool:
        return True

    async def publish(self, text: str, link: str = None, article_id: int = None) -> SocialPostResult:
        return SocialPostResult(
            success=False,
            platform="facebook",
            error_message="Simulated Meta API network failure",
        )


class MockSucceedingClient(SocialPlatformClient):
    @property
    def platform_name(self) -> str:
        return "x"

    def is_configured(self) -> bool:
        return True

    async def publish(self, text: str, link: str = None, article_id: int = None) -> SocialPostResult:
        return SocialPostResult(
            success=True,
            platform="x",
            external_post_id="mock-x-tweet-9999",
            dry_run=False,
        )


@pytest.mark.asyncio
async def test_social_publishing_eligibility_and_ranking(db_session: AsyncSession):
    source = NewsSource(name="AP News", domain="apnews.com")
    cat = NewsCategory(name="Politics", slug="politics")
    db_session.add_all([source, cat])
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Low quality article (score 50 < 70) -> Should NOT be selected
    art_low_quality = NewsArticle(
        title="Low Quality Report",
        slug="low-quality-report",
        original_url="https://apnews.com/low",
        canonical_url="https://apnews.com/low",
        canonical_url_hash="aa" * 32,
        source_id=source.id,
        category_id=cat.id,
        published_at=now,
        status="published",
        quality_score=50.0,
        is_breaking=False,
        is_trending=False,
    )

    # 2. Standard quality article (score 75)
    art_standard = NewsArticle(
        title="Senate Reviews Education Budget",
        slug="senate-reviews-education-budget",
        original_url="https://apnews.com/budget",
        canonical_url="https://apnews.com/budget",
        canonical_url_hash="bb" * 32,
        source_id=source.id,
        category_id=cat.id,
        published_at=now,
        status="published",
        quality_score=75.0,
        is_breaking=False,
        is_trending=False,
    )

    # 3. Breaking news article (score 80) -> Should be ranked FIRST
    art_breaking = NewsArticle(
        title="Major Hurricane Makes Landfall",
        slug="major-hurricane-makes-landfall",
        original_url="https://apnews.com/hurricane",
        canonical_url="https://apnews.com/hurricane",
        canonical_url_hash="cc" * 32,
        source_id=source.id,
        category_id=cat.id,
        published_at=now,
        status="published",
        quality_score=80.0,
        is_breaking=True,
        is_trending=False,
    )

    # 4. Trending article (score 78) -> Should be ranked SECOND
    art_trending = NewsArticle(
        title="Global Trade Negotiations Conclude",
        slug="global-trade-negotiations-conclude",
        original_url="https://apnews.com/trade",
        canonical_url="https://apnews.com/trade",
        canonical_url_hash="dd" * 32,
        source_id=source.id,
        category_id=cat.id,
        published_at=now,
        status="published",
        quality_score=78.0,
        is_breaking=False,
        is_trending=True,
    )

    db_session.add_all([art_low_quality, art_standard, art_breaking, art_trending])
    await db_session.commit()

    # Query eligible articles for facebook
    eligible = await get_eligible_articles_for_social(
        db=db_session,
        platform="facebook",
        min_quality_score=70.0,
        limit=5,
    )

    eligible_slugs = [a.slug for a in eligible]
    assert "low-quality-report" not in eligible_slugs
    assert "major-hurricane-makes-landfall" in eligible_slugs
    assert "global-trade-negotiations-conclude" in eligible_slugs
    assert "senate-reviews-education-budget" in eligible_slugs

    # Verify ranking order: breaking first, then trending, then quality
    assert eligible[0].slug == "major-hurricane-makes-landfall"
    assert eligible[1].slug == "global-trade-negotiations-conclude"
    assert eligible[2].slug == "senate-reviews-education-budget"


@pytest.mark.asyncio
async def test_duplicate_prevention_on_same_platform(db_session: AsyncSession):
    source = NewsSource(name="Reuters", domain="reuters-dup.com")
    db_session.add(source)
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    article = NewsArticle(
        title="Already Published Story",
        slug="already-published-story",
        original_url="https://reuters-dup.com/story",
        canonical_url="https://reuters-dup.com/story",
        canonical_url_hash="ee" * 32,
        source_id=source.id,
        published_at=now,
        status="published",
        quality_score=85.0,
    )
    db_session.add(article)
    await db_session.commit()

    # Mark as PUBLISHED on Facebook
    fb_post = SocialPost(
        article_id=article.id,
        platform="facebook",
        status="PUBLISHED",
        external_post_id="existing_fb_123",
        published_at=now,
        attempt_count=1,
    )
    db_session.add(fb_post)
    await db_session.commit()

    # Query eligibility for facebook -> Must be excluded!
    fb_eligible = await get_eligible_articles_for_social(
        db=db_session, platform="facebook", min_quality_score=70.0, limit=5
    )
    assert article.id not in [a.id for a in fb_eligible]

    # Query eligibility for x -> Must STILL be eligible (not published on X yet!)
    x_eligible = await get_eligible_articles_for_social(
        db=db_session, platform="x", min_quality_score=70.0, limit=5
    )
    assert article.id in [a.id for a in x_eligible]


@pytest.mark.asyncio
async def test_failure_isolation_between_platforms(db_session: AsyncSession):
    source = NewsSource(name="Bloomberg", domain="bloomberg-iso.com")
    db_session.add(source)
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    article = NewsArticle(
        title="Resilient Economy Grows by Three Percent",
        slug="resilient-economy-grows-by-three-percent",
        original_url="https://bloomberg-iso.com/economy",
        canonical_url="https://bloomberg-iso.com/economy",
        canonical_url_hash="ff" * 32,
        source_id=source.id,
        published_at=now,
        status="published",
        quality_score=88.0,
    )
    db_session.add(article)
    await db_session.commit()

    # Service with failing Facebook client and succeeding X client
    service = SocialPublishingService(
        facebook_client=MockFailingClient(),
        x_client=MockSucceedingClient(),
        facebook_enabled=True,
        x_enabled=True,
        dry_run=False,
        min_quality_score=70.0,
        max_posts_per_run=1,
    )

    summary = await service.run_publishing_cycle(db=db_session)

    # Facebook failed
    assert summary["facebook"]["failed"] == 1
    assert summary["facebook"]["published"] == 0

    # X SUCCEEDED despite Facebook failing (failure isolation)
    assert summary["x"]["published"] == 1
    assert summary["x"]["failed"] == 0

    # Verify DB records
    fb_record = await get_social_post(db_session, article.id, "facebook")
    assert fb_record is not None
    assert fb_record.status == "FAILED"
    assert "Simulated Meta API" in fb_record.last_error

    x_record = await get_social_post(db_session, article.id, "x")
    assert x_record is not None
    assert x_record.status == "PUBLISHED"
    assert x_record.external_post_id == "mock-x-tweet-9999"


@pytest.mark.asyncio
async def test_dry_run_publishing_simulation(db_session: AsyncSession):
    source = NewsSource(name="WSJ", domain="wsj-dry.com")
    db_session.add(source)
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    article = NewsArticle(
        title="Dry Run Test Article Coverage",
        slug="dry-run-test-article-coverage",
        original_url="https://wsj-dry.com/dry",
        canonical_url="https://wsj-dry.com/dry",
        canonical_url_hash="00" * 32,
        source_id=source.id,
        published_at=now,
        status="published",
        quality_score=90.0,
    )
    db_session.add(article)
    await db_session.commit()

    service = SocialPublishingService(dry_run=True, min_quality_score=70.0, max_posts_per_run=1)
    summary = await service.run_publishing_cycle(db=db_session)

    assert summary["dry_run"] is True
    assert summary["facebook"]["published"] == 1
    assert summary["x"]["published"] == 1

    fb_record = await get_social_post(db_session, article.id, "facebook")
    assert fb_record is not None
    assert fb_record.status == "PUBLISHED"
    assert "dryrun-fb-" in fb_record.external_post_id

    x_record = await get_social_post(db_session, article.id, "x")
    assert x_record is not None
    assert x_record.status == "PUBLISHED"
    assert "dryrun-x-" in x_record.external_post_id


# --- Phase 5.1 Recovery & Quota Tests ---

@pytest.mark.asyncio
async def test_stale_publishing_recovery_logic(db_session: AsyncSession):
    source = NewsSource(name="AP Stale", domain="ap-stale.com")
    db_session.add(source)
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    art1 = NewsArticle(
        title="Crashed Article A",
        slug="crashed-article-a",
        original_url="https://ap-stale.com/a",
        canonical_url="https://ap-stale.com/a",
        canonical_url_hash="aa11" * 16,
        source_id=source.id,
        published_at=now,
        status="published",
        quality_score=85.0,
    )
    art2 = NewsArticle(
        title="In Flight Article B",
        slug="in-flight-article-b",
        original_url="https://ap-stale.com/b",
        canonical_url="https://ap-stale.com/b",
        canonical_url_hash="bb22" * 16,
        source_id=source.id,
        published_at=now,
        status="published",
        quality_score=85.0,
    )
    db_session.add_all([art1, art2])
    await db_session.commit()

    # 1. Stale post (crashed 90 minutes ago)
    stale_time = now - datetime.timedelta(minutes=90)
    post_stale = SocialPost(
        article_id=art1.id,
        platform="facebook",
        status="PUBLISHING",
        attempt_count=1,
        created_at=stale_time,
        updated_at=stale_time,
    )
    # 2. Recent in-flight post (started 5 minutes ago)
    recent_time = now - datetime.timedelta(minutes=5)
    post_recent = SocialPost(
        article_id=art2.id,
        platform="facebook",
        status="PUBLISHING",
        attempt_count=1,
        created_at=recent_time,
        updated_at=recent_time,
    )
    db_session.add_all([post_stale, post_recent])
    await db_session.commit()

    service = SocialPublishingService(stale_timeout_minutes=60)
    recovery_result = await service.recover_stale_records(db=db_session)
    assert recovery_result["recovered"] == 1

    # Reload records
    await db_session.refresh(post_stale)
    await db_session.refresh(post_recent)

    # Stale record must be FAILED_AMBIGUOUS with recovery notes
    assert post_stale.status == "FAILED_AMBIGUOUS"
    assert post_stale.recovered_at is not None
    assert "manual operator reconciliation" in (post_stale.recovery_notes or "")

    # Recent in-flight record must remain untouched
    assert post_recent.status == "PUBLISHING"


@pytest.mark.asyncio
async def test_failed_ambiguous_excluded_from_future_publishing(db_session: AsyncSession):
    source = NewsSource(name="NPR", domain="npr-ambig.com")
    db_session.add(source)
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    article = NewsArticle(
        title="Ambiguous Article Not Republished",
        slug="ambiguous-article-not-republished",
        original_url="https://npr-ambig.com/story",
        canonical_url="https://npr-ambig.com/story",
        canonical_url_hash="cc33" * 16,
        source_id=source.id,
        published_at=now,
        status="published",
        quality_score=90.0,
    )
    db_session.add(article)
    await db_session.commit()

    # Mark as FAILED_AMBIGUOUS on X
    post = SocialPost(
        article_id=article.id,
        platform="x",
        status="FAILED_AMBIGUOUS",
        attempt_count=1,
    )
    db_session.add(post)
    await db_session.commit()

    # Must be excluded from eligible articles for X
    eligible = await get_eligible_articles_for_social(db=db_session, platform="x", min_quality_score=70.0)
    assert article.id not in [a.id for a in eligible]


@pytest.mark.asyncio
async def test_daily_quota_limit_enforcement(db_session: AsyncSession):
    source = NewsSource(name="BBC", domain="bbc-quota.com")
    db_session.add(source)
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    # Create 3 articles
    articles = [
        NewsArticle(
            title=f"Quota Test Article {i}",
            slug=f"quota-test-article-{i}",
            original_url=f"https://bbc-quota.com/{i}",
            canonical_url=f"https://bbc-quota.com/{i}",
            canonical_url_hash=f"{i}{i}" * 32,
            source_id=source.id,
            published_at=now,
            status="published",
            quality_score=85.0 + i,
        )
        for i in range(1, 4)
    ]
    db_session.add_all(articles)
    await db_session.commit()

    # Pre-populate 2 published posts for X within the last 24h
    post1 = SocialPost(
        article_id=articles[0].id,
        platform="x",
        status="PUBLISHED",
        published_at=now - datetime.timedelta(hours=2),
    )
    post2 = SocialPost(
        article_id=articles[1].id,
        platform="x",
        status="PUBLISHED",
        published_at=now - datetime.timedelta(hours=5),
    )
    db_session.add_all([post1, post2])
    await db_session.commit()

    # Configure service with daily cap of 2 for X
    service = SocialPublishingService(
        dry_run=True,
        x_enabled=True,
        facebook_enabled=False,
        x_max_posts_per_day=2,
        max_posts_per_run=2,
    )
    summary = await service.run_publishing_cycle(db=db_session)

    # Since 2 were already published in rolling 24h, X should skip run
    assert summary["x"].get("skipped_quota") == 1
    assert summary["x"]["attempted"] == 0
    assert summary["x"]["published"] == 0
