"""Unit and integration tests for newsletter article curation, campaign generation, and delivery."""

import datetime
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.newsletter import EmailSubscriber, NewsletterCampaign
from app.models.source import NewsSource
from app.newsletter.campaign_service import NewsletterCampaignService
from app.newsletter.provider import MockEmailProvider, SMTPEmailProvider
from app.newsletter.service import generate_unsubscribe_token, hash_token
from app.newsletter.templates import (
    render_newsletter_email,
    render_unsubscribe_confirmation_email,
    render_verification_email,
)
from app.repositories import newsletter_repository


@pytest.mark.asyncio
async def test_curated_article_selection_and_ranking(db_session: AsyncSession):
    source = NewsSource(name="Reuters", domain="reuters.com")
    cat_us = NewsCategory(name="US News", slug="us-news")
    cat_tech = NewsCategory(name="Technology", slug="tech")
    db_session.add_all([source, cat_us, cat_tech])
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)

    # 1. Low quality (score 55 < 70) -> Should NOT be included
    art_low = NewsArticle(
        title="Low Quality Blog Post",
        slug="low-quality-blog-post",
        original_url="https://reuters.com/low",
        canonical_url="https://reuters.com/low",
        canonical_url_hash="11" * 32,
        source_id=source.id,
        category_id=cat_us.id,
        published_at=now,
        status="published",
        quality_score=55.0,
        is_breaking=False,
        is_trending=False,
    )

    # 2. Standard published story (score 75)
    art_std = NewsArticle(
        title="Federal Reserve Holds Interest Rates Steady",
        slug="fed-holds-rates",
        original_url="https://reuters.com/fed",
        canonical_url="https://reuters.com/fed",
        canonical_url_hash="22" * 32,
        source_id=source.id,
        category_id=cat_us.id,
        published_at=now,
        status="published",
        quality_score=75.0,
        is_breaking=False,
        is_trending=False,
    )

    # 3. Breaking news story (score 82) -> Ranked 1st
    art_breaking = NewsArticle(
        title="Supreme Court Issues Landmark Regulatory Ruling",
        slug="supreme-court-landmark-ruling",
        original_url="https://reuters.com/scotus",
        canonical_url="https://reuters.com/scotus",
        canonical_url_hash="33" * 32,
        source_id=source.id,
        category_id=cat_us.id,
        published_at=now,
        status="published",
        quality_score=82.0,
        is_breaking=True,
        is_trending=False,
    )

    # 4. Trending story (score 80) -> Ranked 2nd
    art_trending = NewsArticle(
        title="New Quantum Computing Architecture Unveiled",
        slug="quantum-computing-breakthrough",
        original_url="https://reuters.com/quantum",
        canonical_url="https://reuters.com/quantum",
        canonical_url_hash="44" * 32,
        source_id=source.id,
        category_id=cat_tech.id,
        published_at=now,
        status="published",
        quality_score=80.0,
        is_breaking=False,
        is_trending=True,
    )

    # 5. Draft story (score 90) -> Excluded (not published)
    art_draft = NewsArticle(
        title="Draft Story Not Ready",
        slug="draft-story",
        original_url="https://reuters.com/draft",
        canonical_url="https://reuters.com/draft",
        canonical_url_hash="55" * 32,
        source_id=source.id,
        category_id=cat_tech.id,
        published_at=now,
        status="draft",
        quality_score=90.0,
        is_breaking=False,
        is_trending=False,
    )

    db_session.add_all([art_low, art_std, art_breaking, art_trending, art_draft])
    await db_session.commit()

    service = NewsletterCampaignService()
    selected = await service.select_curated_articles(db_session, limit=5, min_quality_score=70.0)

    assert len(selected) == 3
    # Breaking news first
    assert selected[0].id == art_breaking.id
    # Trending news second
    assert selected[1].id == art_trending.id
    # Standard news third
    assert selected[2].id == art_std.id


@pytest.mark.asyncio
async def test_campaign_generation_and_deduplication(db_session: AsyncSession):
    source = NewsSource(name="AP", domain="apnews.com")
    cat = NewsCategory(name="National", slug="national")
    db_session.add_all([source, cat])
    await db_session.commit()

    art = NewsArticle(
        title="National Economic Report Released",
        slug="national-economic-report",
        original_url="https://apnews.com/econ",
        canonical_url="https://apnews.com/econ",
        canonical_url_hash="aa" * 32,
        source_id=source.id,
        category_id=cat.id,
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
        quality_score=85.0,
    )
    db_session.add(art)
    await db_session.commit()

    # Create active subscriber
    sub = EmailSubscriber(
        email="reader1@example.com",
        email_normalized="reader1@example.com",
        status="active",
        unsubscribe_token_hash=hash_token(generate_unsubscribe_token("reader1@example.com")),
    )
    db_session.add(sub)
    await db_session.commit()

    service = NewsletterCampaignService()
    today = datetime.datetime.now(datetime.timezone.utc).date()

    # 1. Create first campaign
    c1 = await service.create_daily_campaign(db_session, scheduled_date=today)
    assert c1 is not None
    assert c1.recipient_count == 1
    assert c1.article_ids == [art.id]

    # 2. Second attempt for same date -> returns existing campaign (idempotent deduplication)
    c2 = await service.create_daily_campaign(db_session, scheduled_date=today)
    assert c2 is not None
    assert c2.id == c1.id


@pytest.mark.asyncio
async def test_campaign_batch_delivery(db_session: AsyncSession):
    source = NewsSource(name="Bloomberg", domain="bloomberg.com")
    cat = NewsCategory(name="Markets", slug="markets")
    db_session.add_all([source, cat])
    await db_session.commit()

    art = NewsArticle(
        title="Treasury Yields Stabilize Following Policy Statement",
        slug="treasury-yields-stabilize",
        original_url="https://bloomberg.com/treasury",
        canonical_url="https://bloomberg.com/treasury",
        canonical_url_hash="bb" * 32,
        source_id=source.id,
        category_id=cat.id,
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
        quality_score=88.0,
        description="Bond markets responded steadily to the central bank announcement.",
    )
    db_session.add(art)

    # Add 2 active subscribers
    sub1 = EmailSubscriber(
        email="active1@test.com",
        email_normalized="active1@test.com",
        status="active",
        unsubscribe_token_hash=hash_token(generate_unsubscribe_token("active1@test.com")),
    )
    sub2 = EmailSubscriber(
        email="active2@test.com",
        email_normalized="active2@test.com",
        status="active",
        unsubscribe_token_hash=hash_token(generate_unsubscribe_token("active2@test.com")),
    )
    db_session.add_all([sub1, sub2])
    await db_session.commit()

    mock_provider = MockEmailProvider()
    service = NewsletterCampaignService(email_provider=mock_provider)

    campaign = await service.create_daily_campaign(db_session)
    assert campaign is not None
    assert campaign.recipient_count == 2

    # Execute batch delivery
    summary = await service.deliver_campaign(db_session, campaign.id, batch_size=10)
    assert summary["success"] is True
    assert summary["delivered_count"] == 2
    assert summary["failed_count"] == 0
    assert len(mock_provider.sent_emails) == 2

    # Check recipient 1 email contents
    first_email = mock_provider.sent_emails[0]
    assert "Treasury Yields Stabilize" in first_email["html_body"]
    assert "unsubscribe?token=" in first_email["html_body"]
    assert "METRO" in first_email["html_body"] and "SCOPE" in first_email["html_body"]
    assert "METROSCOPE DAILY BRIEFING" in first_email["text_body"]


@pytest.mark.asyncio
async def test_campaign_delivery_failure_handling(db_session: AsyncSession):
    source = NewsSource(name="WSJ", domain="wsj.com")
    cat = NewsCategory(name="Business", slug="business")
    db_session.add_all([source, cat])
    await db_session.commit()

    art = NewsArticle(
        title="Commercial Real Estate Financing Trends",
        slug="cre-financing-trends",
        original_url="https://wsj.com/cre",
        canonical_url="https://wsj.com/cre",
        canonical_url_hash="cc" * 32,
        source_id=source.id,
        category_id=cat.id,
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
        quality_score=79.0,
    )
    db_session.add(art)

    sub = EmailSubscriber(
        email="failing_subscriber@test.com",
        email_normalized="failing_subscriber@test.com",
        status="active",
        unsubscribe_token_hash=hash_token(generate_unsubscribe_token("failing_subscriber@test.com")),
    )
    db_session.add(sub)
    await db_session.commit()

    failing_provider = MockEmailProvider(should_fail=True, error_message="Upstream SMTP connection dropped")
    service = NewsletterCampaignService(email_provider=failing_provider)

    campaign = await service.create_daily_campaign(db_session)
    summary = await service.deliver_campaign(db_session, campaign.id)

    assert summary["delivered_count"] == 0
    assert summary["failed_count"] == 1

    # Verify delivery record records the error message
    deliveries = await newsletter_repository.get_pending_deliveries(db_session, campaign.id)
    # Status should be "failed", not "pending"
    assert len(deliveries) == 0


@pytest.mark.asyncio
async def test_smtp_dry_run_provider():
    provider = SMTPEmailProvider(dry_run=True)
    res = await provider.send_email(
        to_email="test@metroscope.news",
        subject="Test Dry Run",
        html_body="<p>Test</p>",
        text_body="Test",
    )
    assert res.success is True
    assert res.dry_run is True
    assert res.error_message is None
    assert "dryrun-msg-" in res.message_id


def test_template_rendering_and_escaping():
    # 1. Verification template
    html_v, text_v = render_verification_email("reader@test.com", "https://metroscope.news/verify?token=xyz")
    assert "reader@test.com" in html_v
    assert "https://metroscope.news/verify?token=xyz" in html_v
    assert "Confirm Subscription" in html_v
    assert "https://metroscope.news/verify?token=xyz" in text_v

    # 2. Newsletter template with HTML injection test
    articles = [
        {
            "title": "US Markets Rally <script>alert('xss')</script>",
            "category": "Markets & Economy",
            "source": "AP News",
            "url": "https://metroscope.news/article/us-markets-rally",
            "summary": "Tech shares led gains & investors cheered quarterly reports.",
        }
    ]
    html_n, text_n = render_newsletter_email("November 8, 2026", articles, "https://metroscope.news/unsubscribe?token=abc")
    assert "<script>" not in html_n
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html_n
    assert "November 8, 2026" in html_n
    assert "https://metroscope.news/unsubscribe?token=abc" in html_n
    assert "Unsubscribe from this newsletter" in html_n

    # 3. Unsubscribe confirmation template
    html_u, text_u = render_unsubscribe_confirmation_email("reader@test.com")
    assert "You have been unsubscribed" in html_u
    assert "reader@test.com" in html_u
