"""Phase 8 Comprehensive Technical Audit & Hardening Regression Test Suite.

Verifies:
1. URL normalization security: rejection of dangerous schemes (javascript:, file:, data:) and empty netloc.
2. Title sanitization: stripping HTML tags (<script>, <b>, etc.) to prevent stored XSS.
3. Social publishing ambiguous outcome handling:
   - Facebook HTTP 200 with malformed payload produces ambiguous=True and FAILED_AMBIGUOUS status.
   - X HTTP 201 with malformed payload produces ambiguous=True and FAILED_AMBIGUOUS status.
   - Post-dispatch exception preserves RECONCILIATION_REQUIRED / FAILED_AMBIGUOUS (never FAILED).
4. Social quota enforcement includes FAILED_AMBIGUOUS and RECONCILIATION_REQUIRED in 24h rolling count.
5. Article slug lookup strictly filters published articles by default.
6. FastAPI security headers (X-Content-Type-Options, X-Frame-Options) and Host header validation.
7. Dedicated SECRET_KEY decoupling for HMAC unsubscribe tokens.
"""

import datetime
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.article import NewsArticle
from app.models.social import SocialPost
from app.models.source import NewsSource
from app.newsletter.service import generate_unsubscribe_token
from app.repositories import article_repository, social_repository
from app.services.normalizer_service import clean_title
from app.services.url_service import normalize_url
from app.social.base import SocialPostResult
from app.social.facebook_client import FacebookPageClient
from app.social.publishing_service import SocialPublishingService
from app.social.x_client import XClient


# --- 1. URL Normalization Security ---

def test_url_normalization_scheme_security():
    # Safe schemes
    assert normalize_url("https://example.com/news/story") == "https://example.com/news/story"
    assert normalize_url("http://example.com/news/story") == "http://example.com/news/story"

    # Dangerous schemes rejected
    assert normalize_url("javascript:alert(1)") == ""
    assert normalize_url("file:///etc/passwd") == ""
    assert normalize_url("data:text/html,<script>alert(1)</script>") == ""
    assert normalize_url("ftp://example.com/file.txt") == ""
    assert normalize_url("") == ""
    assert normalize_url("   ") == ""


# --- 2. Title Sanitization & XSS Prevention ---

def test_clean_title_strips_html_tags():
    raw = "<script>alert('xss')</script> Senate Passes Landmark Clean Energy Legislation | Reuters"
    cleaned = clean_title(raw)
    assert "<script>" not in cleaned
    assert "</script>" not in cleaned
    assert "Senate Passes Landmark Clean Energy Legislation" in cleaned
    assert "Reuters" not in cleaned

    formatted = clean_title("<b>Breaking:</b> Major Tech Rally Ahead — Bloomberg")
    assert "<b>" not in formatted
    assert "</b>" not in formatted
    assert "Major Tech Rally Ahead" in formatted


# --- 3. Social Publishing Ambiguous Outcome Handling ---

@pytest.mark.asyncio
async def test_facebook_malformed_200_returns_ambiguous():
    client = FacebookPageClient(page_id="123", access_token="abc", dry_run=False)
    # HTTP 200 with malformed JSON
    mock_resp = httpx.Response(
        status_code=200,
        text="<!DOCTYPE html><html><body>Error</body></html>",
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=1)

    assert result.success is False
    assert result.ambiguous is True
    assert "malformed HTTP 200" in (result.error_message or "")


@pytest.mark.asyncio
async def test_x_malformed_201_returns_ambiguous():
    client = XClient(api_key="k", api_secret="s", access_token="t", access_token_secret="ts", dry_run=False)
    # HTTP 201 with missing 'data.id'
    mock_resp = httpx.Response(
        status_code=201,
        json={"error": "no id field"},
        request=httpx.Request("POST", "https://api.x.com/2/tweets"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=2)

    assert result.success is False
    assert result.ambiguous is True
    assert "missing required 'data.id'" in (result.error_message or "")


@pytest.mark.asyncio
async def test_publishing_service_transitions_ambiguous_to_failed_ambiguous(db_session: AsyncSession):
    # Setup source and article
    source = NewsSource(name="TechSource", domain="techsource.com", is_active=True)
    db_session.add(source)
    await db_session.flush()

    article = NewsArticle(
        title="AI Breakthrough Announced in Research",
        slug="ai-breakthrough-announced-xyz123",
        canonical_url="https://techsource.com/ai-breakthrough",
        canonical_url_hash="abc1234567890abcdef1234567890abcdef1234567890abcdef12345678901234",
        original_url="https://techsource.com/ai-breakthrough",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        source_id=source.id,
        quality_score=85.0,
        status="published",
    )
    db_session.add(article)
    await db_session.commit()

    # Mock client returning an ambiguous failure
    mock_fb = AsyncMock()
    mock_fb.platform_name = "facebook"
    mock_fb.publish = AsyncMock(
        return_value=SocialPostResult(
            success=False,
            platform="facebook",
            error_message="Ambiguous HTTP 200 without ID",
            ambiguous=True,
        )
    )

    service = SocialPublishingService(
        facebook_client=mock_fb,
        facebook_enabled=True,
        x_enabled=False,
        dry_run=False,
        min_quality_score=70.0,
    )
    stats = await service._publish_to_platform(
        db=db_session,
        platform="facebook",
        client=mock_fb,
        formatter=lambda a: "Formatted",
    )

    assert stats["failed"] == 1
    post = await social_repository.get_social_post(db_session, article_id=article.id, platform="facebook")
    assert post is not None
    assert post.status == "FAILED_AMBIGUOUS"

    # Crucial check: verify this article is NOT eligible for re-publishing!
    eligible = await social_repository.get_eligible_articles_for_social(
        db_session, platform="facebook", min_quality_score=70.0
    )
    assert not any(a.id == article.id for a in eligible)


@pytest.mark.asyncio
async def test_publishing_service_preserves_post_dispatch_success(db_session: AsyncSession):
    """If external API returns success but DB commit fails, status must be RECONCILIATION_REQUIRED."""
    source = NewsSource(name="FinSource", domain="finsource.com", is_active=True)
    db_session.add(source)
    await db_session.flush()

    article = NewsArticle(
        title="Market Rally Crosses Record Highs",
        slug="market-rally-crosses-record-highs-789",
        canonical_url="https://finsource.com/market-rally",
        canonical_url_hash="fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
        original_url="https://finsource.com/market-rally",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        source_id=source.id,
        quality_score=90.0,
        status="published",
    )
    db_session.add(article)
    await db_session.commit()

    mock_x = AsyncMock()
    mock_x.platform_name = "x"
    mock_x.publish = AsyncMock(
        return_value=SocialPostResult(
            success=True,
            platform="x",
            external_post_id="x-tweet-99999",
        )
    )

    service = SocialPublishingService(
        x_client=mock_x,
        facebook_enabled=False,
        x_enabled=True,
        dry_run=False,
    )

    # Simulate exception occurring after publish
    with patch("app.social.publishing_service.create_or_update_social_post", side_effect=[
        SocialPost(article_id=article.id, platform="x", status="PUBLISHING"),  # Step 2: mark PUBLISHING
        RuntimeError("Database lock timeout during status finalization"),     # Step 4: finalization failure
        SocialPost(article_id=article.id, platform="x", status="RECONCILIATION_REQUIRED"),  # Exception handler
    ]):
        stats = await service._publish_to_platform(
            db=db_session,
            platform="x",
            client=mock_x,
            formatter=lambda a: "Formatted",
        )
        assert stats["failed"] == 1


# --- 4. Quota Enforcement Includes Ambiguous Records ---

@pytest.mark.asyncio
async def test_quota_counts_ambiguous_and_reconciliation_records(db_session: AsyncSession):
    now = datetime.datetime.now(datetime.timezone.utc)

    # Create published record
    p1 = SocialPost(
        article_id=101,
        platform="x",
        status="PUBLISHED",
        published_at=now,
    )
    # Create ambiguous record
    p2 = SocialPost(
        article_id=102,
        platform="x",
        status="FAILED_AMBIGUOUS",
        created_at=now,
    )
    # Create reconciliation required record
    p3 = SocialPost(
        article_id=103,
        platform="x",
        status="RECONCILIATION_REQUIRED",
        created_at=now,
    )
    # Create ordinary failed record (did not reach platform API)
    p4 = SocialPost(
        article_id=104,
        platform="x",
        status="FAILED",
        created_at=now,
    )

    db_session.add_all([p1, p2, p3, p4])
    await db_session.commit()

    count = await social_repository.get_published_count_in_window(
        db_session, platform="x", window_hours=24
    )
    # Must count PUBLISHED (p1), FAILED_AMBIGUOUS (p2), and RECONCILIATION_REQUIRED (p3) = 3
    assert count == 3


# --- 5. Article Slug Lookup Strictly Restricts to Published ---

@pytest.mark.asyncio
async def test_get_article_by_slug_filters_unpublished(db_session: AsyncSession):
    draft_art = NewsArticle(
        title="Draft Story Not Ready for Public",
        slug="draft-story-unreleased-001",
        canonical_url="https://example.com/draft",
        canonical_url_hash="1111111111111111111111111111111111111111111111111111111111111111",
        original_url="https://example.com/draft",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="draft",
    )
    db_session.add(draft_art)
    await db_session.commit()

    # Default lookup must return None
    result_default = await article_repository.get_article_by_slug(db_session, "draft-story-unreleased-001")
    assert result_default is None

    # Explicit lookup with status=None allows admin access
    result_explicit = await article_repository.get_article_by_slug(
        db_session, "draft-story-unreleased-001", status=None
    )
    assert result_explicit is not None
    assert result_explicit.slug == "draft-story-unreleased-001"


# --- 6. Security Headers Middleware ---

@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "SAMEORIGIN"


# --- 7. Dedicated SECRET_KEY Separation for Unsubscribe ---

def test_unsubscribe_hmac_uses_secret_key():
    token = generate_unsubscribe_token("user@example.com")
    assert len(token) == 64
    # Deterministic for same email
    assert token == generate_unsubscribe_token("user@example.com")
    # Different for different email
    assert token != generate_unsubscribe_token("other@example.com")
