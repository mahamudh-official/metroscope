"""Focused Unit & Regression Tests for Webz.io Schema Wire Variations,
Defensive Coercion, Normalization, Editorial Rights, and Attribution Integrity.
"""
import datetime
from decimal import Decimal
from typing import Any, Dict
import pytest

from app.core.config import settings
from app.integrations.webz.client import CONFIRMED_QUERY, CATEGORY_QUERIES, WebzClient
from app.integrations.webz.parser import normalize_webz_post
from app.integrations.webz.schemas import (
    WebzPost,
    WebzResponse,
    WebzThread,
    NormalizedWebzArticle,
)
from app.services.article_validation_service import ArticleEditorialValidationService
from app.services.content_rights_service import ContentRightsService
from app.services.normalizer_service import EDITORIAL_AUTHOR
from app.schemas.canonical_article import CanonicalMetroScopeArticle


# -----------------------------------------------------------------------------
# 1. Local Fixtures Representing Webz.io Wire Variations
# -----------------------------------------------------------------------------

def make_webz_wire_fixture(
    topics=None,
    categories=None,
    site_categories=None,
    external_links=None,
    external_images=None,
    internal_images=None,
    entities=None,
    thread_override: Dict[str, Any] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Generates a raw dictionary simulating Webz.io JSON payloads with wire variations."""
    thread_data = {
        "uuid": "thread-uuid-001",
        "url": "https://www.nasa.gov/news/webb-deep-field-observation",
        "site": "nasa.gov",
        "site_full": "www.nasa.gov",
        "site_section": "news",
        "site_categories": site_categories,
        "site_title": "NASA",
        "site_type": "news",
        "country": "US",
        "main_image": "https://www.nasa.gov/images/webb-deep-field.jpg",
        "domain_rank": 100,
        "spam_score": 0.0,
        "performance_score": 90,
    }
    if thread_override:
        thread_data.update(thread_override)

    post_data = {
        "uuid": "webz-post-uuid-valid-nasa-001",
        "url": "https://www.nasa.gov/news/webb-deep-field-observation",
        "published": "2026-11-16T18:00:00.000+00:00",
        "title": "NASA James Webb Space Telescope Reveals Ancient Star Clusters in Deep Field",
        "text": (
            "The James Webb Space Telescope has captured unprecedented observations of ancient star clusters "
            "dating back to the earliest epochs of cosmic history. Astronomers utilizing the observatory's near-infrared "
            "spectrograph documented spectroscopic signatures indicating intense star formation and primordial galactic "
            "evolution in unprecedented detail. These discoveries provide crucial empirical benchmarks for cosmological models "
            "and illuminate the mechanisms that drove cosmic reionization."
        ),
        "summary": "NASA's James Webb Space Telescope has uncovered detailed evidence of primordial star clusters.",
        "author": "Dr. Alan Stern",
        "language": "english",
        "thread": thread_data,
        "entities": entities,
        "crawled": "2026-11-16T18:30:00.000+00:00",
        "categories": categories,
        "topics": topics,
        "sentiment": "positive",
        "breaking": False,
        "external_links": external_links,
        "external_images": external_images,
        "internal_images": internal_images,
    }
    post_data.update(kwargs)
    return post_data


# -----------------------------------------------------------------------------
# 2. Schema Coercion & Defensive Wire Parsing Tests
# -----------------------------------------------------------------------------

def test_schema_coercion_when_topics_is_null():
    """Validates fix for wire bug where topics is explicitly null in JSON."""
    raw = make_webz_wire_fixture(topics=None)
    parsed = WebzPost.model_validate(raw)
    assert parsed.topics == []
    assert isinstance(parsed.topics, list)


def test_schema_coercion_when_categories_is_null():
    """Validates fix when categories is null in JSON."""
    raw = make_webz_wire_fixture(categories=None)
    parsed = WebzPost.model_validate(raw)
    assert parsed.categories == []
    assert isinstance(parsed.categories, list)


def test_schema_coercion_when_site_categories_is_null():
    """Validates fix when thread.site_categories is null in JSON."""
    raw = make_webz_wire_fixture(site_categories=None)
    parsed = WebzPost.model_validate(raw)
    assert parsed.thread.site_categories == []
    assert isinstance(parsed.thread.site_categories, list)


def test_schema_coercion_when_links_and_images_are_null():
    """Validates fix when external_links and image arrays are null."""
    raw = make_webz_wire_fixture(
        external_links=None,
        external_images=None,
        internal_images=None,
    )
    parsed = WebzPost.model_validate(raw)
    assert parsed.external_links == []
    assert parsed.external_images == []
    assert parsed.internal_images == []


def test_schema_coercion_when_all_optional_fields_are_null():
    """Validates parsing when every optional field is missing or null."""
    raw_minimal = {
        "uuid": "minimal-uuid-999",
        "url": "https://example.com/story",
        "published": "2026-11-16T12:00:00Z",
        "title": "Minimal Title Meeting Minimum Length Constraint for Testing",
        "text": None,
        "summary": None,
        "author": None,
        "language": None,
        "thread": None,
        "entities": None,
        "crawled": None,
        "categories": None,
        "topics": None,
        "sentiment": None,
        "external_links": None,
        "external_images": None,
        "internal_images": None,
    }
    response_payload = {
        "posts": [raw_minimal],
        "total_results": 1,
        "requests_left": 950,
    }
    response = WebzResponse.model_validate(response_payload)
    assert len(response.posts) == 1
    post = response.posts[0]
    assert post.topics == []
    assert post.categories == []
    assert post.external_links == []
    assert post.external_images == []
    assert post.internal_images == []
    assert post.thread is None


def test_schema_coercion_single_string_to_list():
    """Validates that accidental single strings in list fields are wrapped defensively."""
    raw = make_webz_wire_fixture(
        topics="space exploration",
        categories="science and technology",
        site_categories="science",
        external_links="https://nasa.gov",
    )
    parsed = WebzPost.model_validate(raw)
    assert parsed.topics == ["space exploration"]
    assert parsed.categories == ["science and technology"]
    assert parsed.thread.site_categories == ["science"]
    assert parsed.external_links == ["https://nasa.gov"]


# -----------------------------------------------------------------------------
# 3. Normalization & Editorial Pipeline Tests
# -----------------------------------------------------------------------------

def test_normalization_with_null_wire_fields():
    """Verifies normalize_webz_post handles null wire fields gracefully."""
    raw = make_webz_wire_fixture(
        topics=None,
        categories=None,
        site_categories=None,
        external_links=None,
        external_images=None,
        internal_images=None,
    )
    post = WebzPost.model_validate(raw)
    norm = normalize_webz_post(post, target_category="science")
    assert norm is not None
    assert norm.uuid == raw["uuid"]
    assert norm.title == raw["title"]
    assert norm.domain == "nasa.gov"
    assert norm.author == EDITORIAL_AUTHOR  # Canonical author must be MetroScope News Desk


def test_valid_public_domain_article_passes_all_gates():
    """Verifies that a genuine statutory public domain article from NASA passes publication gates."""
    raw = make_webz_wire_fixture(
        topics=["astronomy", "deep space"],
        categories=["science and technology"],
    )
    post = WebzPost.model_validate(raw)
    norm = normalize_webz_post(post, target_category="science")
    assert norm is not None

    # Rights check: NASA is statutory public domain under 17 U.S.C. § 105
    rights_service = ContentRightsService()
    rights_pkg = rights_service.evaluate_article_rights(domain="nasa.gov", raw_post=post)
    assert rights_pkg.full_text_authorized is True

    # Editorial Validation Gate
    val = ArticleEditorialValidationService.evaluate_candidate(
        title=norm.title,
        canonical_url=norm.canonical_url,
        published_at=norm.published_at,
        domain=norm.domain,
        category_slug=norm.category_slug,
        summary=norm.summary,
        full_text=norm.full_text,
        publisher_name=norm.publisher_name,
        author=norm.author,
        image_url=norm.image_url,
        language=norm.language,
        content_display_authorized=rights_pkg.full_text_authorized,
    )
    assert val.is_valid is True
    assert val.status == "published"
    assert val.filter_reason is None
    assert val.cleaned_author == EDITORIAL_AUTHOR

    # Canonical schema validation
    canonical = CanonicalMetroScopeArticle(
        uuid=norm.uuid,
        title=norm.title,
        canonical_url=norm.canonical_url,
        canonical_url_hash=norm.canonical_url_hash,
        domain=norm.domain,
        publisher_name=val.cleaned_publisher or norm.domain,
        published_at=norm.published_at,
        category_slug=norm.category_slug,
        language=norm.language,
        author=EDITORIAL_AUTHOR,
        summary=val.cleaned_summary,
        full_text=val.cleaned_full_text,
        country=norm.country,
        content_display_authorized=True,
        image_url=norm.image_url,
        hero_image_authorized=True,
    )
    assert canonical.author == "MetroScope News Desk"
    assert canonical.publisher_name == "NASA"


# -----------------------------------------------------------------------------
# 4. Explicit Filter Reasons on Incomplete or Non-Compliant Articles
# -----------------------------------------------------------------------------

def test_commercial_publisher_article_passes_validation_without_rights_blocking():
    """Commercial publisher articles are no longer blocked by rights validation."""
    raw = make_webz_wire_fixture(
        thread_override={
            "site": "wsj.com",
            "site_full": "www.wsj.com",
            "site_title": "The Wall Street Journal",
            "url": "https://www.wsj.com/articles/markets-rally-today",
        },
        url="https://www.wsj.com/articles/markets-rally-today",
        title="Wall Street Rallies as Treasury Yields Decline Across All Benchmark Maturities",
        summary="Wall Street stocks surged as benchmark treasury yields retreated across bond trading desks.",
        text=(
            "Wall Street stocks surged across major equity indices today as benchmark treasury yields retreated "
            "across bond trading desks. Investors responded enthusiastically to moderating wholesale price pressures "
            "and favorable quarterly corporate earnings reports, lifting both the S&P 500 and the Nasdaq composite "
            "to fresh weekly highs amidst broad-based sector participation."
        ),
    )
    post = WebzPost.model_validate(raw)
    norm = normalize_webz_post(post, target_category="business")
    assert norm is not None
    assert norm.image_url is not None

    val = ArticleEditorialValidationService.evaluate_candidate(
        title=norm.title,
        canonical_url=norm.canonical_url,
        published_at=norm.published_at,
        domain=norm.domain,
        category_slug=norm.category_slug,
        summary=norm.summary,
        full_text=norm.full_text,
        publisher_name=norm.publisher_name,
        author=norm.author,
        image_url=norm.image_url,
        language=norm.language,
    )
    assert val.is_valid is True
    assert val.status == "published"
    assert val.filter_reason is None
    assert val.cleaned_author == "MetroScope News Desk"
    assert val.cleaned_publisher == "The Wall Street Journal"


def test_short_body_is_filtered_with_explicit_reason():
    """Article with body under 200 characters is filtered."""
    val = ArticleEditorialValidationService.evaluate_candidate(
        title="Federal Reserve Signals Interest Rate Deliberations for Upcoming December Session",
        canonical_url="https://www.whitehouse.gov/briefing/economic-update",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="whitehouse.gov",
        category_slug="business",
        summary="Federal Reserve policymakers signal new interest rate deliberations ahead of December.",
        full_text="Too short text under 200 characters.",
        publisher_name="The White House",
        author="MetroScope News Desk",
        image_url="https://www.whitehouse.gov/images/briefing.jpg",
        language="en",
        content_display_authorized=True,
    )
    assert val.is_valid is False
    assert val.status == "filtered"
    assert "substantive body text" in val.filter_reason.lower() or "too short" in val.filter_reason.lower()


def test_missing_hero_image_is_filtered_with_explicit_reason():
    """Article lacking mandatory HTTPS hero image is filtered."""
    val = ArticleEditorialValidationService.evaluate_candidate(
        title="Federal Reserve Signals Interest Rate Deliberations for Upcoming December Session",
        canonical_url="https://www.whitehouse.gov/briefing/economic-update",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="whitehouse.gov",
        category_slug="business",
        summary="Federal Reserve policymakers signal new interest rate deliberations ahead of December session.",
        full_text=(
            "Federal Reserve policymakers signaled intensive interest rate deliberations ahead of their upcoming December session today. "
            "The White House Council of Economic Advisers released an update noting that the Federal Reserve remains focused on "
            "achieving sustained price stability while evaluating labor market resilience across all regions of the national economy."
        ),
        publisher_name="The White House",
        author="MetroScope News Desk",
        image_url=None,  # Missing image
        language="en",
        content_display_authorized=True,
    )
    assert val.is_valid is False
    assert val.status == "filtered"
    assert "featured hero image" in val.filter_reason.lower()


def test_prohibited_casino_gambling_content_is_filtered():
    """Commercial gambling/casino content is filtered with explicit reason."""
    val = ArticleEditorialValidationService.evaluate_candidate(
        title="Best Online Casino Sites with Real Money Slots and Free Spins in Canada 2026",
        canonical_url="https://ou.ac.lk/casino-spins-2026",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="ou.ac.lk",
        category_slug="business",
        summary="Claim your free spins and deposit bonus now at the top rated online casino gaming portal.",
        full_text=(
            "Looking for the best real money online casino sites? We have ranked the top 10 casino destinations "
            "featuring slot machines, jackpot city games, free spins, and instant deposit bonuses with low wagering "
            "requirements for all Canadian and international players."
        ),
        publisher_name="The Open University of Sri Lanka",
        author="MetroScope News Desk",
        image_url="https://images.unsplash.com/photo-casino.jpg",
        language="en",
        content_display_authorized=True,
    )
    assert val.is_valid is False
    assert val.status == "filtered"
    assert "gambling" in val.filter_reason.lower() or "casino" in val.filter_reason.lower()


# -----------------------------------------------------------------------------
# 5. Author Attribution & Deduplication Guards
# -----------------------------------------------------------------------------

def test_author_attribution_is_always_metroscope_news_desk():
    """Verifies that regardless of input byline, the author is always MetroScope News Desk."""
    for raw_byline in ["John Doe", "Reuters Wire", "Staff Reporter", "", None]:
        raw = make_webz_wire_fixture(author=raw_byline)
        post = WebzPost.model_validate(raw)
        norm = normalize_webz_post(post, target_category="science")
        assert norm.author == "MetroScope News Desk"

        val = ArticleEditorialValidationService.evaluate_candidate(
            title=norm.title,
            canonical_url=norm.canonical_url,
            published_at=norm.published_at,
            domain=norm.domain,
            category_slug=norm.category_slug,
            summary=norm.summary,
            full_text=norm.full_text,
            publisher_name=norm.publisher_name,
            author=norm.author,
            image_url=norm.image_url,
            language=norm.language,
            content_display_authorized=True,
        )
        assert val.cleaned_author == "MetroScope News Desk"


# -----------------------------------------------------------------------------
# 6. Service Protection Invariants
# -----------------------------------------------------------------------------

def test_social_publishing_remains_strictly_disabled():
    """Confirms social publishing remains disabled and dry-run mode enabled."""
    assert settings.SOCIAL_PUBLISHING_ENABLED is False
    assert settings.SOCIAL_DRY_RUN is True
    assert settings.FACEBOOK_ENABLED is False
    assert settings.X_ENABLED is False
    assert settings.EMAIL_DRY_RUN is True


# -----------------------------------------------------------------------------
# 7. Query Coverage for Approved 10 Categories
# -----------------------------------------------------------------------------

def test_webz_query_scope_matches_10_categories():
    """Inspects the Webz query structure to verify actual coverage of all 10 MetroScope categories."""
    query = CONFIRMED_QUERY.lower()
    
    # 1. Politics
    assert 'category:"politics"' in query
    
    # 2. Business
    assert 'category:"economy, business and finance"' in query
    
    # 3. Technology & 4. Science
    assert 'category:"science and technology"' in query
    
    # 5. Health
    assert 'category:"health"' in query
    
    # 6. Environment
    assert 'category:"environment"' in query
    
    # 7. Sports
    assert 'category:"sport"' in query
    
    # 8. Entertainment
    assert 'category:"arts, culture and entertainment"' in query
    
    # 9. World
    assert 'category:"war, conflict and unrest"' in query
    assert '"international"' in query or '"world"' in query
    
    # 10. US (Geographic focus)
    assert 'country:us' in query
    
    # English language
    assert 'language:english' in query
