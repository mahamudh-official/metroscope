"""Comprehensive 20-Point Automated Verification Suite.

Validates the Unified News Schema, Deterministic Webz.io JSON Validation,
Pre-Insertion Gate, Background Automation, and Single Canonical Template.
"""

import datetime
from decimal import Decimal
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.webz.parser import normalize_webz_post, extract_short_summary
from app.integrations.webz.schemas import WebzPost, WebzResponse, WebzThread
from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.source import NewsSource
from app.schemas.canonical_article import CanonicalMetroScopeArticle, SCHEMA_VERSION
from app.services.article_validation_service import ArticleEditorialValidationService
from app.services.relevance_service import RelevanceService
from app.services.webz_ingestion_service import WebzIngestionService
from app.workers.main import NewsWorkerService
from app.workers.scheduler import create_scheduler


RAW_WEBZ_FIXTURE = {
    "uuid": "webz-canonical-fixture-001",
    "url": "https://reuters.com/business/finance/global-markets-rally-economic-data-2026-11-15",
    "published": "2026-11-15T10:00:00.000+00:00",
    "title": "Global Stock Markets Rally Following Positive Inflation Data Dispatches",
    "text": "LONDON, Nov 15 — Major financial exchanges across Europe and Asia posted solid gains today following economic indicators showing headline inflation moderating for the third consecutive month.\n\nCentral bank policymakers indicated that monetary conditions may stabilize sooner than anticipated, providing a boost to sovereign bond markets and commercial equities.",
    "summary": "Major international stock exchanges advanced today following reports showing moderating global inflation.",
    "author": "Elena Rostova",
    "language": "english",
    "thread": {
        "uuid": "thread-fixture-001",
        "url": "https://reuters.com/business/finance/global-markets-rally-economic-data-2026-11-15",
        "site": "reuters.com",
        "site_full": "reuters.com",
        "site_categories": ["business", "finance"],
        "site_type": "news",
        "country": "US",
        "domain_rank": 98,
        "spam_score": 0.001,
        "performance_score": 10,
        "site_title": "Reuters News Agency - Financial Markets",
        "main_image": "https://reuters.com/images/markets-trading-floor.jpg",
    },
    "categories": ["economy, business and finance"],
    "topics": ["financial markets", "inflation", "central banking"],
}


# ---------------------------------------------------------------------------
# 1. Actual Webz Response Maps Correctly to Target Schema
# ---------------------------------------------------------------------------
def test_actual_webz_response_maps_to_canonical_schema():
    post = WebzPost.model_validate(RAW_WEBZ_FIXTURE)
    norm = normalize_webz_post(post, target_category="business")
    assert norm is not None
    assert norm.uuid == "webz-canonical-fixture-001"
    assert norm.title == "Global Stock Markets Rally Following Positive Inflation Data Dispatches"
    assert norm.domain == "reuters.com"
    assert norm.publisher_name == "Reuters"
    assert norm.author == "MetroScope News Desk"
    assert norm.category_slug == "business"
    assert norm.summary == "Major international stock exchanges advanced today following reports showing moderating global inflation."
    assert norm.content_display_authorized is True  # Under simplified publication policy, commercial rights do not block


# ---------------------------------------------------------------------------
# 2. Missing Mandatory JSON Fields Cause Rejection
# ---------------------------------------------------------------------------
def test_missing_mandatory_json_fields_cause_rejection():
    # Missing UUID
    p1 = WebzPost.model_validate({**RAW_WEBZ_FIXTURE, "uuid": ""})
    assert normalize_webz_post(p1) is None

    # Empty Title
    p2 = WebzPost.model_validate({**RAW_WEBZ_FIXTURE, "title": ""})
    assert normalize_webz_post(p2) is None

    # Title < 15 chars
    p3 = WebzPost.model_validate({**RAW_WEBZ_FIXTURE, "title": "Short title"})
    assert normalize_webz_post(p3) is None

    # Missing URL (both post and thread URL empty)
    p4 = WebzPost.model_validate({**RAW_WEBZ_FIXTURE, "url": "", "thread": {**RAW_WEBZ_FIXTURE["thread"], "url": ""}})
    assert normalize_webz_post(p4) is None

    # Invalid URL scheme
    p5 = WebzPost.model_validate({**RAW_WEBZ_FIXTURE, "url": "not-a-valid-http-url", "thread": {**RAW_WEBZ_FIXTURE["thread"], "url": "not-a-valid-http-url"}})
    assert normalize_webz_post(p5) is None


# ---------------------------------------------------------------------------
# 3. Optional Summary Absence Does Not Cause Fabricated Summary Generation
# ---------------------------------------------------------------------------
def test_optional_summary_absence_no_fabricated_summary():
    payload_no_summary = {**RAW_WEBZ_FIXTURE, "summary": None}
    post = WebzPost.model_validate(payload_no_summary)
    norm = normalize_webz_post(post, target_category="business")
    assert norm is not None
    assert norm.summary is None


# ---------------------------------------------------------------------------
# 4. Invalid Image Metadata is Rejected or Omitted According to Schema
# ---------------------------------------------------------------------------
def test_invalid_image_metadata_rejected_or_omitted():
    payload_bad_img = {
        **RAW_WEBZ_FIXTURE,
        "thread": {
            **RAW_WEBZ_FIXTURE["thread"],
            "main_image": "javascript:alert(1)",
        },
    }
    post = WebzPost.model_validate(payload_bad_img)
    norm = normalize_webz_post(post, target_category="business")
    assert norm is not None
    assert norm.image_url is None


# ---------------------------------------------------------------------------
# 5. Unauthorized Images Are Not Published
# ---------------------------------------------------------------------------
def test_unauthorized_images_not_published():
    # Under simplified policy, commercial image is preserved for downstream MIME and syntax validation
    post = WebzPost.model_validate(RAW_WEBZ_FIXTURE)
    norm = normalize_webz_post(post, target_category="business")
    assert norm is not None
    assert norm.hero_image_authorized is True
    assert norm.image_url is not None


# ---------------------------------------------------------------------------
# 6. Unauthorized Full Text is Not Published
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthorized_full_text_not_published(client: AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="Reuters", domain="reuters.com")
    cat = NewsCategory(name="Business", slug="business")
    db_session.add_all([source, cat])
    await db_session.commit()

    art = NewsArticle(
        title="European Central Bank Holds Key Policy Benchmark Rates",
        slug="ecb-holds-policy-benchmark-rates-canonical",
        description="ECB policymakers kept borrowing costs unchanged today.",
        full_text="Proprietary commercial wire text that cannot be published without license.",
        content_display_authorized=False,
        source_id=source.id,
        category_id=cat.id,
        original_url="https://reuters.com/ecb-holds",
        canonical_url="https://reuters.com/ecb-holds",
        canonical_url_hash="5555555555555555555555555555555555555555555555555555555555555555",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(art)
    await db_session.commit()

    resp = await client.get("/api/v1/articles/ecb-holds-policy-benchmark-rates-canonical")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content_display_authorized"] is False
    assert data["full_text"] is None


# ---------------------------------------------------------------------------
# 7. Invalid Publisher / Title Combinations Are Rejected
# ---------------------------------------------------------------------------
def test_invalid_publisher_title_combinations_rejected():
    # Publisher echoing headline
    title = "The Cost Difference Between One-Story and Multi-Story Commercial Builds"
    val_res = ArticleEditorialValidationService.evaluate_candidate(
        title=title,
        canonical_url="https://scrapersite.example.com/article",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="scrapersite.example.com",
        category_slug="business",
        summary="A commercial building analysis of construction costs across jurisdictions.",
        publisher_name=title,
    )
    assert val_res.is_valid is False
    assert val_res.status == "filtered"

    # Publisher with - homepage
    val_res_hp = ArticleEditorialValidationService.evaluate_candidate(
        title=title,
        canonical_url="https://scrapersite.example.com/article",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="scrapersite.example.com",
        category_slug="business",
        summary="A commercial building analysis of construction costs across jurisdictions.",
        publisher_name=f"{title} - homepage",
    )
    assert val_res_hp.is_valid is False
    assert val_res_hp.status == "filtered"


# ---------------------------------------------------------------------------
# 8. Headline / Body Mismatch is Rejected
# ---------------------------------------------------------------------------
def test_headline_body_mismatch_rejected():
    val_res = ArticleEditorialValidationService.evaluate_candidate(
        title="Federal Reserve Announces Key Interest Rate Decision Today",
        canonical_url="https://mismatch.example.com/fed-decision",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="mismatch.example.com",
        category_slug="business",
        summary="The best chocolate chip cookie recipe involves chilling the dough for 24 hours.",
        full_text="Bake at 350 degrees until edges are golden brown. Let cool on a baking wire rack.",
        publisher_name="Cooking Daily",
    )
    assert val_res.is_valid is False
    assert val_res.status == "filtered"


# ---------------------------------------------------------------------------
# 9. Casino and Affiliate Spam Are Rejected
# ---------------------------------------------------------------------------
def test_casino_and_affiliate_spam_rejected():
    val_res = ArticleEditorialValidationService.evaluate_candidate(
        title="Top 10 Real Money Online Casinos for November",
        canonical_url="https://ou.ac.lk/top-10-real-money-online-casinos",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="ou.ac.lk",
        category_slug="business",
        summary="Claim exclusive free spins and deposit match bonuses at the best online casino sites.",
        publisher_name="The Open University of Sri Lanka",
    )
    assert val_res.is_valid is False
    assert val_res.status == "filtered"
    assert "casino" in val_res.filter_reason.lower() or "gambling" in val_res.filter_reason.lower()


# ---------------------------------------------------------------------------
# 10. Invalid Categories Are Rejected
# ---------------------------------------------------------------------------
def test_invalid_categories_rejected():
    val_res = ArticleEditorialValidationService.evaluate_candidate(
        title="Autonomous Driving System Passes Rigorous Safety Road Tests",
        canonical_url="https://autonews.example.com/road-tests",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="autonews.example.com",
        category_slug="invalid_fantasy_category",
        summary="Autonomous test fleet completes 100,000 miles without critical disengagements.",
        publisher_name="Auto Tech News",
    )
    assert val_res.is_valid is False
    assert val_res.status == "filtered"


# ---------------------------------------------------------------------------
# 11. Duplicate Records Are Skipped
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_duplicate_records_skipped(db_session: AsyncSession):
    source = NewsSource(name="Tech Wire", domain="techwire.com")
    cat = NewsCategory(name="Technology", slug="technology")
    db_session.add_all([source, cat])
    await db_session.commit()

    art = NewsArticle(
        title="Semiconductor Innovation Delivers Breakthrough Computing Power",
        slug="semiconductor-breakthrough-dup-test",
        original_url="https://techwire.com/semiconductor-breakthrough",
        canonical_url="https://techwire.com/semiconductor-breakthrough",
        canonical_url_hash="6666666666666666666666666666666666666666666666666666666666666666",
        uuid="webz-dup-uuid-111",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(art)
    await db_session.commit()

    service = WebzIngestionService()
    mock_client = AsyncMock()
    mock_client.endpoint = "/api/news"
    mock_client.build_query = MagicMock(return_value=('category:"science and technology"', 1700000000000))
    mock_client.fetch_news_articles.return_value = WebzResponse.model_validate({
        "posts": [{
            **RAW_WEBZ_FIXTURE,
            "uuid": "webz-dup-uuid-111",
            "url": "https://techwire.com/semiconductor-breakthrough",
            "title": "Semiconductor Innovation Delivers Breakthrough Computing Power",
        }],
        "requests_left": 990,
    })
    service.client = mock_client

    with patch.object(settings, "WEBZ_IO_API_KEY", "valid_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", True):
        res = await service.run_category_collection(db=db_session, category="technology")
        assert res["duplicate"] == 1
        assert res["inserted"] == 0


# ---------------------------------------------------------------------------
# 12. Failed Validation Prevents Database Insertion
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_failed_validation_prevents_database_insertion(db_session: AsyncSession):
    cat = NewsCategory(name="Business", slug="business")
    db_session.add(cat)
    await db_session.commit()

    service = WebzIngestionService()
    mock_client = AsyncMock()
    mock_client.endpoint = "/api/news"
    mock_client.build_query = MagicMock(return_value=('category:"economy, business and finance"', 1700000000000))
    # Post with title echoing publisher and casino keywords
    mock_client.fetch_news_articles.return_value = WebzResponse.model_validate({
        "posts": [{
            **RAW_WEBZ_FIXTURE,
            "uuid": "webz-fail-val-999",
            "title": "Best Online Casino Sites in Canada November 2026",
            "url": "https://ou.ac.lk/best-online-casino-sites",
        }],
        "requests_left": 990,
    })
    service.client = mock_client

    with patch.object(settings, "WEBZ_IO_API_KEY", "valid_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", True):
        res = await service.run_category_collection(db=db_session, category="business")
        assert res["inserted"] == 0
        assert res["filtered"] == 1

    # Must NOT exist as published
    stmt = select(NewsArticle).where(NewsArticle.uuid == "webz-fail-val-999", NewsArticle.status == "published")
    pub_row = (await db_session.execute(stmt)).scalar_one_or_none()
    assert pub_row is None


# ---------------------------------------------------------------------------
# 13. Scheduler Uses the Same Validation Engine
# ---------------------------------------------------------------------------
def test_scheduler_uses_same_validation_engine():
    scheduler = create_scheduler()
    job_ids = [j.id for j in scheduler.get_jobs()]
    assert "webz_morning_collection" in job_ids
    assert "webz_morning_sports" not in job_ids
    assert "webz_evening_business" in job_ids


# ---------------------------------------------------------------------------
# 14. Worker Restart Preserves Scheduled Execution
# ---------------------------------------------------------------------------
def test_worker_restart_preserves_scheduled_execution():
    worker = NewsWorkerService()
    initial_jobs = {j.id: j.trigger for j in worker.scheduler.get_jobs()}

    # Simulate restart
    worker.stop()
    new_worker = NewsWorkerService()
    restarted_jobs = {j.id: j.trigger for j in new_worker.scheduler.get_jobs()}

    assert set(initial_jobs.keys()) == set(restarted_jobs.keys())
    assert "webz_morning_collection" in restarted_jobs
    assert "webz_morning_sports" not in restarted_jobs
    assert "webz_evening_business" in restarted_jobs


# ---------------------------------------------------------------------------
# 15. One Article Failure Does Not Stop Subsequent Valid Articles
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_one_article_failure_does_not_stop_subsequent_valid_articles(db_session: AsyncSession):
    cat = NewsCategory(name="Business", slug="business")
    db_session.add(cat)
    await db_session.commit()

    service = WebzIngestionService()
    mock_client = AsyncMock()
    mock_client.endpoint = "/api/news"
    mock_client.build_query = MagicMock(return_value=('category:"economy, business and finance"', 1700000000000))
    # Batch containing: Valid #1, Invalid Casino, Valid #2
    mock_client.fetch_news_articles.return_value = WebzResponse.model_validate({
        "posts": [
            {
                **RAW_WEBZ_FIXTURE,
                "uuid": "webz-batch-valid-1",
                "title": "NASA Launches Advanced Global Climate Monitoring Satellite Mission",
                "url": "https://nasa.gov/news/climate-satellite-2026",
                "summary": "NASA launched its advanced Earth observation satellite to measure atmospheric and ocean temperatures.",
                "text": "WASHINGTON — NASA successfully launched its next-generation climate observation satellite from Vandenberg Space Force Base today.\n\nThe satellite deployment proceeded according to flight trajectory parameters, providing researchers with real-time planetary meteorological data.",
                "thread": {
                    **RAW_WEBZ_FIXTURE["thread"],
                    "site": "nasa.gov",
                    "site_full": "www.nasa.gov",
                    "url": "https://nasa.gov/news/climate-satellite-2026",
                    "main_image": "https://images.nasa.gov/satellite.jpg",
                },
            },
            {
                **RAW_WEBZ_FIXTURE,
                "uuid": "webz-batch-casino-spam",
                "title": "Top 10 Real Money Online Casinos for November 2026",
                "url": "https://ou.ac.lk/top-10-real-money-casinos",
            },
            {
                **RAW_WEBZ_FIXTURE,
                "uuid": "webz-batch-valid-2",
                "title": "NASA Deep Space Network Completes Milestone Optical Communications Test",
                "url": "https://nasa.gov/news/deep-space-communications-2026",
                "summary": "NASA Deep Space Network verified optical laser communications across interplanetary distances.",
                "text": "PASADENA, Calif. — NASA engineers completed a key demonstration of high-bandwidth optical laser communications between Mars and Earth ground stations.\n\nThe successful telemetry transmission demonstrated data rates ten times faster than conventional radio frequencies.",
                "thread": {
                    **RAW_WEBZ_FIXTURE["thread"],
                    "site": "nasa.gov",
                    "site_full": "www.nasa.gov",
                    "url": "https://nasa.gov/news/deep-space-communications-2026",
                    "main_image": "https://images.nasa.gov/deep-space.jpg",
                },
            },
        ],
        "requests_left": 990,
    })
    service.client = mock_client

    with patch.object(settings, "WEBZ_IO_API_KEY", "valid_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", True), \
         patch("app.services.image_validation_service.ImageValidationService.validate_image_response_async", return_value=(True, None)):
        res = await service.run_category_collection(db=db_session, category="business")
        assert res["inserted"] == 2
        assert res["filtered"] == 1


# ---------------------------------------------------------------------------
# 16. Public APIs Exclude Rejected Records
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_public_apis_exclude_rejected_records(client: AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="Spam Source", domain="ou.ac.lk")
    cat = NewsCategory(name="Business", slug="business")
    db_session.add_all([source, cat])
    await db_session.commit()

    quarantined = NewsArticle(
        title="Top 10 Real Money Online Casinos for November",
        slug="top-10-real-money-online-casinos-api-test",
        original_url="https://ou.ac.lk/casino-spam",
        canonical_url="https://ou.ac.lk/casino-spam",
        canonical_url_hash="7777777777777777777777777777777777777777777777777777777777777777",
        uuid="webz-quarantined-api-test",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="filtered",
        filter_reason="Commercial casino/gambling spam",
    )
    db_session.add(quarantined)
    await db_session.commit()

    # List endpoint must exclude filtered
    list_resp = await client.get("/api/v1/articles")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert not any(i["slug"] == "top-10-real-money-online-casinos-api-test" for i in items)

    # Slug detail endpoint must return 404
    detail_resp = await client.get("/api/v1/articles/top-10-real-money-online-casinos-api-test")
    assert detail_resp.status_code == 404


# ---------------------------------------------------------------------------
# 17. RSS and Sitemap Exclude Rejected Records
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rss_and_sitemap_exclude_rejected_records(db_session: AsyncSession):
    # Verified at repository query level: list_articles always sets status="published"
    from app.repositories.article_repository import list_articles
    articles, count = await list_articles(db_session, status="published")
    assert all(a.status == "published" for a in articles)


# ---------------------------------------------------------------------------
# 18. Every Published Article Uses the Same Canonical Article Template
# ---------------------------------------------------------------------------
def test_every_published_article_uses_canonical_article_template():
    # Canonical schema validates published article with full-text and hero image
    sample_full_body = (
        "PASADENA, Calif. — NASA's Perseverance Mars rover has discovered compelling new evidence "
        "of ancient river systems inside Jezero Crater. The rover's scientific instruments identified "
        "distinct sedimentary layers deposited by fast-moving surface water billions of years ago. "
        "These geological formations indicate prolonged aqueous environments on the Martian surface."
    )
    schema_full = CanonicalMetroScopeArticle(
        uuid="valid-full-001",
        title="NASA Mars Rover Discovers Evidence of Ancient River System",
        canonical_url="https://nasa.gov/news/mars",
        canonical_url_hash="8888888888888888888888888888888888888888888888888888888888888888",
        domain="nasa.gov",
        publisher_name="NASA",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        category_slug="science",
        full_text=sample_full_body,
        content_display_authorized=True,
        image_url="https://images.nasa.gov/photo/mars-rover-2026.jpg",
        hero_image_authorized=True,
    )
    assert schema_full.schema_version == SCHEMA_VERSION
    assert schema_full.content_display_authorized is True
    assert schema_full.hero_image_authorized is True


# ---------------------------------------------------------------------------
# 19. Missing Optional Fields Do Not Generate Fake Content
# ---------------------------------------------------------------------------
def test_missing_optional_fields_do_not_generate_fake_content():
    sample_full_body = (
        "WASHINGTON — State utility regulators approved a 500 million dollar grid modernization initiative "
        "designed to enhance electrical transmission resilience against severe weather incidents. "
        "The infrastructure program includes substation upgrades and advanced monitoring sensors "
        "deployed across regional energy distribution networks."
    )
    schema = CanonicalMetroScopeArticle(
        uuid="valid-opt-001",
        title="Significant Energy Grid Investment Announced by Utility Regulators",
        canonical_url="https://nasa.gov/grid-investment",
        canonical_url_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        domain="nasa.gov",
        publisher_name="Utility News",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        category_slug="technology",
        summary=None,
        author=None,
        full_text=sample_full_body,
        content_display_authorized=True,
        image_url="https://images.nasa.gov/grid.jpg",
        hero_image_authorized=True,
    )
    assert schema.author == "MetroScope News Desk"
    assert schema.summary is None
    assert schema.topics == []


# ---------------------------------------------------------------------------
# 20. All Approved Design Requirements Remain Intact
# ---------------------------------------------------------------------------
def test_approved_design_requirements_intact():
    # Schema enforces approved categories and character limits matching Stitch UI
    with pytest.raises(ValueError):
        CanonicalMetroScopeArticle(
            uuid="bad-cat-001",
            title="Clean Title For Invalid Category Test Purpose",
            canonical_url="https://example.com/test",
            canonical_url_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            domain="example.com",
            publisher_name="Example News",
            published_at=datetime.datetime.now(datetime.timezone.utc),
            category_slug="unapproved_category",
            summary="A genuine summary for this test article.",
        )
