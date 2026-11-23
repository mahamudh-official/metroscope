"""Comprehensive Regression Suite for MetroScope Global News Validation Pipeline.

Tests all 16 required verification points:
1. Missing author
2. Headline incorrectly mapped to author
3. Publisher incorrectly mapped from headline
4. Publisher normalization
5. Missing publisher
6. Summary-only article
7. Authorized full-text article
8. Unauthorized full-text article
9. Summary copied into full text
10. Duplicate summary/body handling
11. Placeholder paragraph rejection
12. Missing image
13. Unauthorized image
14. Invalid provider payload
15. Public API leakage prevention
16. RSS and sitemap exclusion of invalid articles
"""

import datetime
import json
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.webz.parser import normalize_webz_post
from app.integrations.webz.schemas import WebzPost, WebzThread
from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.source import NewsSource
from app.schemas.article import ArticleDetail
from app.services.article_validation_service import ArticleEditorialValidationService
from app.services.normalizer_service import (
    normalize_author_name,
    normalize_publisher_name,
    is_spam_or_scraper_domain,
)


# ---------------------------------------------------------------------------
# 1. Missing Author
# ---------------------------------------------------------------------------
def test_missing_author():
    assert normalize_author_name(None) is None
    assert normalize_author_name("") is None
    assert normalize_author_name("   ") is None
    # Generic labels must also become None
    assert normalize_author_name("admin") is None
    assert normalize_author_name("editor") is None
    assert normalize_author_name("staff") is None
    assert normalize_author_name("Unknown (noreply@blogger.com)") is None
    assert normalize_author_name("info@irib-news.ir") is None


# ---------------------------------------------------------------------------
# 2. Headline Incorrectly Mapped to Author
# ---------------------------------------------------------------------------
def test_headline_incorrectly_mapped_to_author():
    title = "NASA Mars Rover Discovers Evidence of Ancient River System"
    # Exact match
    assert normalize_author_name(title, title=title) is None
    # Substring match
    assert normalize_author_name("NASA Mars Rover Discovers Evidence", title=title) is None
    # Case insensitive
    assert normalize_author_name(title.lower(), title=title) is None
    # Valid human author with distinct title
    assert normalize_author_name("Dr. Sarah Johnson", title=title) == "Dr. Sarah Johnson"


# ---------------------------------------------------------------------------
# 3. Publisher Incorrectly Mapped from Headline / Homepage
# ---------------------------------------------------------------------------
def test_publisher_incorrectly_mapped_from_headline():
    title = "The Cost Difference Between One-Story and Multi-Story Commercial Builds"
    site_title_with_homepage = "The Cost Difference Between One-Story and Multi-Story Commercial Builds - homepage"
    domain = "sherwoodparktopcommercia406907.alltdesign.com"

    # Homepage suffix and headline duplicate must be rejected
    clean_pub = normalize_publisher_name(site_title_with_homepage, domain=domain, title=title)
    assert clean_pub is None

    # Editorial candidate evaluation must reject spam/homepage publisher
    val_res = ArticleEditorialValidationService.evaluate_candidate(
        title=title,
        canonical_url="https://sherwoodparktopcommercia406907.alltdesign.com/cost-diff",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain=domain,
        category_slug="business",
        summary="A genuine commercial building summary of reasonable length.",
        publisher_name=site_title_with_homepage,
    )
    assert val_res.is_valid is False
    assert val_res.status == "filtered"
    assert "spam" in val_res.filter_reason.lower() or "publisher" in val_res.filter_reason.lower()


# ---------------------------------------------------------------------------
# 4. Publisher Normalization
# ---------------------------------------------------------------------------
def test_publisher_normalization():
    # Marketing taglines stripped
    assert normalize_publisher_name("Business Insider - Latest News in Tech, Markets, Economy & Innovation", domain="markets.businessinsider.com") == "Business Insider"
    assert normalize_publisher_name("Skook News - Your #1 Source for Schuylkill County News", domain="skooknews.com") == "Skook News"
    assert normalize_publisher_name("Vietnam.vn - Nền tảng quảng bá Việt Nam", domain="vietnam.vn") == "Vietnam.vn"
    # Pipe taglines
    assert normalize_publisher_name("Newsroom | Official site of coverage", domain="newsroom.com") == "Newsroom"


# ---------------------------------------------------------------------------
# 5. Missing Publisher
# ---------------------------------------------------------------------------
def test_missing_publisher():
    val_res = ArticleEditorialValidationService.evaluate_candidate(
        title="Significant Breakthrough in Renewable Clean Energy Systems",
        canonical_url="https://invalid-host/article",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="",
        category_slug="technology",
        summary="A genuine discovery summary of reasonable length.",
        publisher_name=None,
    )
    assert val_res.is_valid is False
    assert val_res.status == "filtered"


# ---------------------------------------------------------------------------
# 6. Summary-Only Article
# ---------------------------------------------------------------------------
def test_summary_only_article():
    summary_text = "Pottsville authority partners with local technology center to restore blighted commercial buildings."
    val_res = ArticleEditorialValidationService.evaluate_candidate(
        title="Pottsville Partnership to Restore Blighted Property and Employ Students",
        canonical_url="https://skooknews.com/pottsville-partnership",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="skooknews.com",
        category_slug="us",
        summary=summary_text,
        full_text=None,
        publisher_name="Skook News",
        content_display_authorized=False,
    )
    # Summary-only articles without full authorized body are strictly filtered
    assert val_res.is_valid is False
    assert val_res.status == "filtered"
    assert "mandatory substantive body" in val_res.filter_reason.lower()


# ---------------------------------------------------------------------------
# 7. Authorized Full-Text Article
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_authorized_full_text_article(client: AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="NASA", domain="nasa.gov")
    cat = NewsCategory(name="Science", slug="science")
    db_session.add_all([source, cat])
    await db_session.commit()

    body = "PASADENA, Calif. — NASA's Perseverance rover collected geological core samples.\n\nKey Findings\n\nWater minerals identified."
    art = NewsArticle(
        title="NASA Mars Rover Discovers Evidence of Ancient River System",
        slug="nasa-mars-rover-test-authorized",
        description="Perseverance rover identifies geological sediment layers.",
        full_text=body,
        content_display_authorized=True,
        source_id=source.id,
        category_id=cat.id,
        original_url="https://nasa.gov/news/mars",
        canonical_url="https://nasa.gov/news/mars",
        canonical_url_hash="2222222222222222222222222222222222222222222222222222222222222222",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(art)
    await db_session.commit()

    resp = await client.get("/api/v1/articles/nasa-mars-rover-test-authorized")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content_display_authorized"] is True
    assert data["full_text"] == body


# ---------------------------------------------------------------------------
# 8. Unauthorized Full-Text Article
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthorized_full_text_article(client: AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="Commercial Daily", domain="commercialdaily.com")
    cat = NewsCategory(name="Business", slug="business")
    db_session.add_all([source, cat])
    await db_session.commit()

    secret_body = "PROPRIETARY SYNDICATED TEXT: Must never leak to public endpoints without express license."
    art = NewsArticle(
        title="Quarterly Earnings Exceed Estimates Across Semiconductor Sector",
        slug="quarterly-earnings-test-unauthorized",
        description="Chipmakers report robust revenue growth driven by datacenter accelerator sales.",
        full_text=secret_body,
        content_display_authorized=False,
        source_id=source.id,
        category_id=cat.id,
        original_url="https://commercialdaily.com/earnings",
        canonical_url="https://commercialdaily.com/earnings",
        canonical_url_hash="3333333333333333333333333333333333333333333333333333333333333333",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(art)
    await db_session.commit()

    resp = await client.get("/api/v1/articles/quarterly-earnings-test-unauthorized")
    assert resp.status_code == 200
    data = resp.json()
    assert data["content_display_authorized"] is False
    assert data["full_text"] is None, "CRITICAL: Unauthorized full text leaked via public API!"


# ---------------------------------------------------------------------------
# 9. Summary Copied into Full Text
# ---------------------------------------------------------------------------
def test_summary_copied_into_full_text():
    title = "Historic Preservation Board Approves Landmark Building Restoration"
    summary = "The local landmark preservation commission approved complete historic facade restoration."
    # When full_text is identical to summary, validate_body_text must reject it
    cleaned_body, err = ArticleEditorialValidationService.validate_body_text(
        full_text=summary,
        title=title,
        summary=summary,
    )
    assert cleaned_body is None
    assert "duplicates summary" in err


# ---------------------------------------------------------------------------
# 10. Duplicate Summary/Body Handling
# ---------------------------------------------------------------------------
def test_duplicate_paragraphs_deduplication():
    title = "Electric Grid Modernization Initiative Receives Final Approval"
    body_with_repeats = (
        "State regulators authorized transmission upgrades across five counties.\n\n"
        "State regulators authorized transmission upgrades across five counties.\n\n"
        "The project will interconnect 500 MW of regional utility solar facilities."
    )
    cleaned_body, _ = ArticleEditorialValidationService.validate_body_text(
        full_text=body_with_repeats,
        title=title,
    )
    assert cleaned_body is not None
    # Duplicate sequential paragraph must be eliminated
    paragraphs = cleaned_body.split("\n\n")
    assert len(paragraphs) == 2


# ---------------------------------------------------------------------------
# 11. Placeholder Paragraph Rejection
# ---------------------------------------------------------------------------
def test_placeholder_paragraph_rejection():
    title = "Walmart management to meet virtually with Oppenheimer"

    # Known generic placeholders must be rejected by summary validation
    assert ArticleEditorialValidationService.validate_summary(
        "Detailed reporting on this story is available directly from the primary publisher.",
        title,
    )[1] is False

    assert ArticleEditorialValidationService.validate_summary(
        "Full reporting published on original newsroom platform.",
        title,
    )[1] is False

    # Wire teaser snippets must be rejected as full text
    wire_teaser = (
        "Virtual Meeting to be held on November 20 hosted by Oppenheimer.\n"
        "Published first on – the ultimate source for real-time, market-moving breaking financial news.\n"
        "See Insiders’ Hot Stocks on TipRanks >>"
    )
    cleaned_body, err = ArticleEditorialValidationService.validate_body_text(wire_teaser, title)
    assert cleaned_body is None
    assert err is not None


# ---------------------------------------------------------------------------
# 12. Missing Image
# ---------------------------------------------------------------------------
def test_missing_image_handled_gracefully():
    val_res = ArticleEditorialValidationService.evaluate_candidate(
        title="Autonomous Submersible Maps Deep Ocean Trench Topography",
        canonical_url="https://oceanresearch.org/expedition",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="oceanresearch.org",
        category_slug="science",
        summary="Marine biologists complete detailed autonomous sonar mapping of benthic ecosystem.",
        full_text="Submersible exploration vehicle descended into the Mariana Trench collecting high-resolution bathymetric data across benthic geological faults. Telemetry confirms all deep-sea instruments and sensors operated nominally throughout the descent mission.",
        content_display_authorized=True,
        image_url=None,
        publisher_name="Ocean Research Institute",
    )
    # Missing image must be filtered under strict featured image policy
    assert val_res.is_valid is False
    assert val_res.status == "filtered"
    assert "featured hero image" in val_res.filter_reason.lower()


# ---------------------------------------------------------------------------
# 13. Unauthorized Image
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_unauthorized_image_masked_in_api(client: AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="Financial News Wire", domain="financialnews.com")
    cat = NewsCategory(name="Business", slug="business")
    db_session.add_all([source, cat])
    await db_session.commit()

    # Image metadata explicitly indicates unauthorized image
    img_meta = json.dumps({
        "external_only": True,
        "hero": {
            "url": "https://financialnews.com/photo.jpg",
            "authorized": False,
            "reason": "Commercial publisher visual media: copyright reserved",
        },
        "inline_images": [],
        "rights": {"hero_image_authorized": False},
    })

    art = NewsArticle(
        title="Global Central Banks Coordinate Liquidity Facility Agreements",
        slug="central-banks-liquidity-facility-test",
        description="Multilateral central banks announce currency liquidity arrangements.",
        full_text=None,
        content_display_authorized=False,
        source_id=source.id,
        category_id=cat.id,
        original_url="https://financialnews.com/liquidity",
        canonical_url="https://financialnews.com/liquidity",
        canonical_url_hash="4444444444444444444444444444444444444444444444444444444444444444",
        language="en",
        image_url="https://financialnews.com/photo.jpg",
        image_metadata=img_meta,
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(art)
    await db_session.commit()

    resp = await client.get("/api/v1/articles/central-banks-liquidity-facility-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["image_url"] is None, "CRITICAL: Unauthorized image URL leaked via public API!"


# ---------------------------------------------------------------------------
# 14. Invalid Provider Payload
# ---------------------------------------------------------------------------
def test_invalid_provider_payload():
    # 1. Missing UUID
    assert normalize_webz_post(WebzPost.model_validate({
        "uuid": "",
        "url": "https://validnews.com/article",
        "title": "A Valid Headline With Good Character Length",
        "published": "2026-11-15T00:00:00Z",
    })) is None

    # 2. Missing Title
    assert normalize_webz_post(WebzPost.model_validate({
        "uuid": "test-uuid-valid-1",
        "url": "https://validnews.com/article",
        "title": "",
        "published": "2026-11-15T00:00:00Z",
    })) is None

    # 3. Invalid URL protocol
    assert normalize_webz_post(WebzPost.model_validate({
        "uuid": "test-uuid-valid-2",
        "url": "ftp://not-http/article",
        "title": "A Valid Headline With Good Character Length",
        "published": "2026-11-15T00:00:00Z",
    })) is None


# ---------------------------------------------------------------------------
# 15. Public API Leakage Prevention
# ---------------------------------------------------------------------------
def test_public_api_schema_leakage_prevention():
    fields = set(ArticleDetail.model_fields.keys())
    assert "image_metadata" not in fields, "Internal image_metadata must not be exposed in ArticleDetail schema"
    assert "trust_indicators" not in fields, "Internal trust_indicators must not be exposed in ArticleDetail schema"
    assert "filter_reason" not in fields, "Internal filter_reason must not be exposed in ArticleDetail schema"


# ---------------------------------------------------------------------------
# 16. RSS and Sitemap Exclusion of Invalid Articles
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rss_and_sitemap_exclusion_of_invalid_articles(client: AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="Valid News", domain="validnews.com")
    cat = NewsCategory(name="World", slug="world")
    db_session.add_all([source, cat])
    await db_session.commit()

    # Filtered article (must be excluded)
    filtered_art = NewsArticle(
        title="Spam Scraper Notice That Failed Global Editorial Quality Gate",
        slug="spam-scraper-notice-filtered",
        description="A promotional description from an unverifiable scraper site.",
        source_id=source.id,
        category_id=cat.id,
        original_url="https://validnews.com/spam",
        canonical_url="https://validnews.com/spam",
        canonical_url_hash="5555555555555555555555555555555555555555555555555555555555555555",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="filtered",
        filter_reason="Domain is identified as spam or scraper network",
    )
    # Published article (must be included)
    published_art = NewsArticle(
        title="International Summit Reaches Landmark Environmental Protection Treaty",
        slug="international-summit-treaty-published",
        description="Delegates agree on binding multi-nation framework for marine conservation.",
        source_id=source.id,
        category_id=cat.id,
        original_url="https://validnews.com/treaty",
        canonical_url="https://validnews.com/treaty",
        canonical_url_hash="6666666666666666666666666666666666666666666666666666666666666666",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add_all([filtered_art, published_art])
    await db_session.commit()

    # Query public articles listing endpoint (powers homepage, RSS feed, and sitemap)
    resp = await client.get("/api/v1/articles")
    assert resp.status_code == 200
    items = resp.json()["items"]
    slugs = [item["slug"] for item in items]

    assert "international-summit-treaty-published" in slugs
    assert "spam-scraper-notice-filtered" not in slugs, "CRITICAL: Filtered article leaked in public articles list!"


# ---------------------------------------------------------------------------
# 17. Casino & Gambling Promotional Content Rejected (Pre-Insertion Gate)
# ---------------------------------------------------------------------------
def test_casino_gambling_content_rejected():
    # 1. Real Money Online Casinos listicle
    res1 = ArticleEditorialValidationService.evaluate_candidate(
        title="Top 10 Real Money Online Casinos for November",
        canonical_url="https://ou.ac.lk/top-10-real-money-online-casinos",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="ou.ac.lk",
        category_slug="business",
        summary="Once you’ve established that you can legally get your hands on the latest casino free spins and bonus offers, you can begin.",
        full_text="Comprehensive review of top slot machines including Sweet Bonanza, Gonzo's Quest, and live dealer blackjack.",
        publisher_name="The Open University of Sri Lanka",
    )
    assert res1.is_valid is False
    assert res1.status == "filtered"
    assert "gambling" in res1.filter_reason.lower() or "casino" in res1.filter_reason.lower()

    # 2. Canada Casino Sites SEO spam
    res2 = ArticleEditorialValidationService.evaluate_candidate(
        title="Best Online Casino Sites in Canada November 2026",
        canonical_url="https://ou.ac.lk/best-online-casino-sites",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="ou.ac.lk",
        category_slug="world",
        summary="Other top slots include Sweet Bonanza, Gonzo's Quest Megaways, and a selection of Cash Eruption titles.",
        publisher_name="The Open University of Sri Lanka",
    )
    assert res2.is_valid is False
    assert "gambling" in res2.filter_reason.lower() or "casino" in res2.filter_reason.lower()


# ---------------------------------------------------------------------------
# 18. Irrelevant University Content Cannot Pass as Business News
# ---------------------------------------------------------------------------
def test_irrelevant_university_content_rejected_as_business_news():
    res = ArticleEditorialValidationService.evaluate_candidate(
        title="Faculty of Distance Learning Admissions and Student Prospectus 2026",
        canonical_url="https://ou.ac.lk/programmes/distance-learning",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="ou.ac.lk",
        category_slug="business",
        summary="Open and distance learning opportunities to anyone, anywhere, and at any time. Degree programme registration open.",
        publisher_name="The Open University of Sri Lanka",
    )
    assert res.is_valid is False
    assert "university" in res.filter_reason.lower() or "course" in res.filter_reason.lower() or "academic" in res.filter_reason.lower()


# ---------------------------------------------------------------------------
# 19. Headline-Summary Mismatch Rejected
# ---------------------------------------------------------------------------
def test_headline_summary_mismatch_rejected():
    res = ArticleEditorialValidationService.evaluate_candidate(
        title="Federal Reserve Announces Key Interest Rate Decision Following Policy Meeting",
        canonical_url="https://legitnews.com/fed-rate-decision",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="legitnews.com",
        category_slug="business",
        summary="The international gourmet baking championship crowned a new pastry chef from Switzerland today.",
        publisher_name="Legit News Daily",
    )
    assert res.is_valid is False
    assert "mismatch" in res.filter_reason.lower()


# ---------------------------------------------------------------------------
# 20. Strict Pre-Insertion Gate Prevents Database Pollution
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_strict_pre_insertion_gate_rejects_without_insert(db_session: AsyncSession):
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.core.config import settings
    from app.integrations.webz.client import WebzResponse
    from app.services.webz_ingestion_service import WebzIngestionService

    cat = NewsCategory(name="Business", slug="business", description="Business news")
    db_session.add(cat)
    await db_session.commit()

    service = WebzIngestionService()
    mock_client = AsyncMock()
    mock_client.endpoint = "/newsApiLite"
    mock_client.build_query = MagicMock(return_value=("category:business", 1700000000000))

    # Raw spam post (Casino spam)
    spam_post = {
        "uuid": "casino-spam-post-9999",
        "url": "https://ou.ac.lk/top-10-real-money-online-casinos",
        "published": "2026-11-15T10:00:00.000+00:00",
        "title": "Top 10 Real Money Online Casinos for November",
        "text": "Full text promoting slot machines, welcome bonus, and casino free spins.",
        "summary": "Check out the best real money casino sites and claim your bonus today.",
        "author": "Web Editor",
        "language": "english",
        "thread": {
            "uuid": "thread-spam-9999",
            "url": "https://ou.ac.lk/top-10-real-money-online-casinos",
            "site": "ou.ac.lk",
            "site_full": "ou.ac.lk",
            "site_title": "The Open University of Sri Lanka",
            "site_type": "news",
            "country": "LK",
            "domain_rank": 80,
            "spam_score": 0.0,
        },
    }

    mock_resp = WebzResponse.model_validate({
        "posts": [spam_post],
        "requests_left": 990,
        "total_results": 1,
    })
    mock_client.fetch_news_articles.return_value = mock_resp
    service.client = mock_client

    with patch.object(settings, "WEBZ_IO_API_KEY", "valid_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", True):

        res = await service.run_category_collection(db=db_session, category="business")
        assert res["status"] == "success"
        # 0 articles must be inserted
        assert res["inserted"] == 0
        # 1 article was rejected/filtered before insertion
        assert res["filtered"] == 1

        # Verify database has ZERO articles inserted for this spam post
        from sqlalchemy import select
        db_arts = (await db_session.execute(select(NewsArticle).where(NewsArticle.uuid == "casino-spam-post-9999"))).scalars().all()
        assert len(db_arts) == 0, "CRITICAL: Rejected casino spam article was illegally inserted into database!"

