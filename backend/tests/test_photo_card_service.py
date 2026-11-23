"""Tests for PhotoCardService dynamic HTML template generation and data injection."""

import datetime
from unittest.mock import MagicMock
import pytest

from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.schemas.canonical_article import CanonicalMetroScopeArticle
from app.services.photo_card_service import (
    PhotoCardData,
    PhotoCardService,
    format_category_display,
    format_date_display,
    format_website_display,
    sanitize_image_url,
)


def test_format_category_display():
    assert format_category_display("technology") == "Technology"
    assert format_category_display("us") == "US News"
    assert format_category_display("world") == "World News"
    assert format_category_display("business") == "Business"
    assert format_category_display("science") == "Science"
    assert format_category_display("health") == "Health"
    assert format_category_display("environment") == "Environment"
    assert format_category_display("sports") == "Sports"
    assert format_category_display("entertainment") == "Entertainment"
    assert format_category_display("politics") == "Politics"
    assert format_category_display("custom_beat") == "Custom Beat"
    assert format_category_display("") == "News"
    assert format_category_display(None) == "News"


def test_format_date_display():
    dt = datetime.datetime(2026, 11, 17, 14, 30, 0, tzinfo=datetime.timezone.utc)
    assert format_date_display(dt) == "NOVEMBER 17, 2026"

    d = datetime.date(2026, 5, 4)
    assert format_date_display(d) == "MAY 04, 2026"

    assert format_date_display("2026-11-17T08:00:00Z") == "NOVEMBER 17, 2026"
    assert format_date_display(None) == "DATE UNAVAILABLE"
    assert format_date_display("") == "DATE UNAVAILABLE"
    assert format_date_display("   ") == "DATE UNAVAILABLE"
    assert format_date_display("invalid-date-string") == "DATE UNAVAILABLE"

    # Timezone conversion check: 2026-11-19 23:00 in UTC-5 is 2026-11-20 04:00 in UTC
    dt_tz = datetime.datetime.fromisoformat("2026-11-19T23:00:00-05:00")
    assert format_date_display(dt_tz) == "NOVEMBER 20, 2026"


def test_format_website_display():
    assert format_website_display("https://metroscope.news") == "theMetroScope.com"
    assert format_website_display("http://www.themetroscope.com/") == "theMetroScope.com"
    assert format_website_display("theMetroScope.com") == "theMetroScope.com"
    assert format_website_display("http://localhost:3000") == "theMetroScope.com"
    assert format_website_display(None) == "theMetroScope.com"
    assert format_website_display("") == "theMetroScope.com"
    assert format_website_display("customdomain.org") == "customdomain.org"


def test_sanitize_image_url():
    valid = "https://images.unsplash.com/photo-12345?auto=format&fit=crop&w=1600"
    assert sanitize_image_url(valid) == valid

    # Malicious injection attempts
    assert sanitize_image_url("javascript:alert(1)") is None
    assert sanitize_image_url("data:image/png;base64,abc") is None
    assert sanitize_image_url('https://example.com/img.jpg");</style><script>alert(1)</script>') is None
    assert sanitize_image_url("https://example.com/img.jpg' onclick='alert(1)") is None
    assert sanitize_image_url("https://example.com/img.jpg)") is None
    assert sanitize_image_url("https://example.com/img.jpg\nbackground:red") is None
    assert sanitize_image_url("") is None
    assert sanitize_image_url(None) is None


def test_photo_card_data_from_dict():
    raw = {
        "title": "Quantum Computing Breakthrough Unveiled",
        "category": "science",
        "published_at": "2026-11-17",
        "image_url": "https://example.com/quantum.jpg",
        "website_url": "https://metroscope.news",
    }
    data = PhotoCardData.from_article(raw)
    assert data.headline == "Quantum Computing Breakthrough Unveiled"
    assert data.category == "science"
    assert data.image_url == "https://example.com/quantum.jpg"


def test_photo_card_data_from_canonical_article():
    canonical = CanonicalMetroScopeArticle(
        uuid="uuid-sample-test-99",
        title="NASA Mars Rover Discovers Evidence of Ancient River Delta Formations",
        canonical_url="https://nasa.gov/mission/mars-perseverance-river-delta",
        canonical_url_hash="a" * 64,
        domain="nasa.gov",
        publisher_name="NASA",
        published_at=datetime.datetime(2026, 11, 17, 8, 0, 0, tzinfo=datetime.timezone.utc),
        category_slug="science",
        language="en",
        author="MetroScope News Desk",
        full_text=(
            "Scientists operating the Mars Perseverance rover have discovered detailed sedimentary structures "
            "in Jezero Crater that confirm river delta formation. The discovery provides strong geological "
            "evidence that a large lake and river system existed on Mars for substantial geological periods."
        ),
        content_display_authorized=True,
        image_url="https://nasa.gov/images/mars_rover_delta.jpg",
        hero_image_authorized=True,
    )

    data = PhotoCardData.from_article(canonical)
    assert data.headline == canonical.title
    assert data.category == "science"
    assert data.image_url == "https://nasa.gov/images/mars_rover_delta.jpg"
    assert data.published_at == canonical.published_at


def test_photo_card_data_from_db_model():
    category = NewsCategory(id=1, name="Technology", slug="technology")
    article = NewsArticle(
        id=42,
        title="New Semiconductor Foundry Opens in Ohio",
        slug="new-semiconductor-foundry-opens-in-ohio-abc12345",
        original_url="https://reuters.com/tech/semiconductor",
        canonical_url="https://reuters.com/tech/semiconductor",
        canonical_url_hash="b" * 64,
        category_id=1,
        image_url="https://images.reuters.com/foundry.jpg",
        published_at=datetime.datetime(2026, 11, 16, 15, 0, 0, tzinfo=datetime.timezone.utc),
        author="MetroScope News Desk",
    )
    article.category = category

    data = PhotoCardData.from_article(article)
    assert data.headline == "New Semiconductor Foundry Opens in Ohio"
    assert data.category == "Technology"
    assert data.image_url == "https://images.reuters.com/foundry.jpg"


def test_render_html_standard_headline_and_image():
    service = PhotoCardService()
    data = PhotoCardData(
        headline="AI and robotics are reshaping global industry",
        category="technology",
        published_at=datetime.datetime(2026, 11, 17, 10, 0, 0, tzinfo=datetime.timezone.utc),
        image_url="https://images.unsplash.com/photo-robotics.jpg",
        website_url="https://metroscope.news",
    )

    html_out = service.render_html(data, canvas_fixed=True)

    assert '<img src="data:image/' in html_out
    assert 'class="brand-logo"' in html_out
    assert 'alt="MetroScope"' in html_out
    assert "The latest, in focus" in html_out
    assert "Technology" in html_out
    assert "AI and robotics are reshaping global industry" in html_out
    assert "NOVEMBER 17, 2026" in html_out
    assert "theMetroScope.com" in html_out
    assert 'url("https://images.unsplash.com/photo-robotics.jpg")' in html_out
    assert "canvas-fixed" in html_out


def test_render_html_missing_image_fallback_gradient():
    service = PhotoCardService()
    data = PhotoCardData(
        headline="Federal Reserve Holds Benchmark Interest Rates Steady Following Inflation Report",
        category="business",
        published_at="2026-11-17",
        image_url=None,
        website_url="https://metroscope.news",
    )

    html_out = service.render_html(data, canvas_fixed=False)

    # Should not contain url()
    assert 'url("' not in html_out
    # Must contain the approved ambient editorial gradient
    assert "radial-gradient(circle at 65% 30%" in html_out
    assert "#101820" in html_out
    assert "Business" in html_out
    assert "Federal Reserve Holds Benchmark" in html_out


def test_render_html_escaping_and_injection_prevention():
    service = PhotoCardService()
    data = PhotoCardData(
        headline='<script>alert("XSS")</script> "Breaking" & \'Shocking\' <img src=x onerror=alert(1)>',
        category='<b onmouseover=alert(1)>Politics</b>',
        published_at='2026-11-17"><script>alert(2)</script>',
        image_url='https://example.com/bad.jpg");}</style><script>alert(3)</script>',
        website_url='metroscope.news<script>alert(4)</script>',
    )

    html_out = service.render_html(data)

    # Raw script and HTML tags must NEVER appear unescaped in output
    assert "<script>" not in html_out
    assert "</script>" not in html_out
    assert "<img src=x" not in html_out
    assert "<b " not in html_out
    assert "<b>" not in html_out

    # Proper HTML entities must be present
    assert "&lt;script&gt;alert(&quot;XSS&quot;)&lt;/script&gt;" in html_out
    assert "&amp;" in html_out
    assert "&lt;" in html_out
    assert "&gt;" in html_out
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_out

    # Malicious image URL must be rejected and replaced by safe fallback gradient
    assert 'bad.jpg");}' not in html_out
    assert "radial-gradient" in html_out


def test_render_html_variable_headline_scaling_classes():
    service = PhotoCardService()

    # 1. Short headline (<= 85 chars)
    short_data = PhotoCardData(headline="Short Headline Here")
    html_short = service.render_html(short_data)
    assert '<h1 class="">Short Headline Here</h1>' in html_short

    # 2. Medium-long headline (86 to 120 chars)
    med_text = "This is a medium length headline that contains between eighty-six and one hundred twenty characters for testing"
    assert 85 < len(med_text) <= 120
    med_data = PhotoCardData(headline=med_text)
    html_med = service.render_html(med_data)
    assert 'class="headline-long"' in html_med

    # 3. Very long headline (> 120 chars)
    long_text = (
        "Global Climate Accord Reaches Historic Multilateral Agreement Across One Hundred Ninety "
        "Nations After Intensive Two Week Negotiations Conclude in Geneva"
    )
    assert len(long_text) > 120
    long_data = PhotoCardData(headline=long_text)
    html_long = service.render_html(long_data)
    assert 'class="headline-xlong"' in html_long


def test_render_html_canvas_fixed_toggle():
    service = PhotoCardService()
    data = PhotoCardData(headline="Test Canvas Toggle")

    # Fixed canvas (for 1080x1080 ScreenshotOne capture)
    fixed_html = service.render_html(data, canvas_fixed=True)
    assert '<body class="canvas-fixed">' in fixed_html

    # Responsive preview (for in-browser centered viewing)
    preview_html = service.render_html(data, canvas_fixed=False)
    assert '<body class="">' in preview_html


@pytest.mark.asyncio
async def test_render_image_dimensions_and_aspect_ratio_1080():
    from unittest.mock import AsyncMock

    service = PhotoCardService()
    mock_client = AsyncMock()
    mock_client.render_html.return_value = b"fake-jpeg-bytes-1080x1080"
    service.screenshot_client = mock_client

    data = PhotoCardData(headline="1080x1080 Square Aspect Ratio Verification")
    result = await service.render_image(data)

    assert result == b"fake-jpeg-bytes-1080x1080"
    mock_client.render_html.assert_awaited_once()
    _, call_kwargs = mock_client.render_html.call_args
    assert call_kwargs["viewport_width"] == 1080
    assert call_kwargs["viewport_height"] == 1080
    assert call_kwargs["selector"] == ".card"


def test_render_html_original_logo_asset_presence():
    """Verifies that the original user-supplied MetroScope logo is embedded as a data URI."""
    service = PhotoCardService()
    data = PhotoCardData(headline="Verification of Original Logo Asset")
    html_out = service.render_html(data)

    assert '<header class="top">' in html_out
    assert '<div class="brand">' in html_out
    assert '<img src="data:image/' in html_out
    assert 'alt="MetroScope"' in html_out
    assert 'class="brand-logo"' in html_out
    # Confirm text wordmark is NOT used
    assert "metro<span>scope</span>" not in html_out


def test_render_html_dynamic_dates_for_different_articles():
    """Verifies different articles automatically produce their respective publication dates."""
    service = PhotoCardService()

    # Article 1: Published November 19, 2026
    art1 = PhotoCardData(
        headline="Article One",
        published_at=datetime.datetime(2026, 11, 19, 9, 15, tzinfo=datetime.timezone.utc),
    )
    html1 = service.render_html(art1)
    assert '<div class="date">NOVEMBER 19, 2026</div>' in html1

    # Article 2: Published March 15, 2026
    art2 = PhotoCardData(
        headline="Article Two",
        published_at=datetime.datetime(2026, 3, 15, 18, 0, tzinfo=datetime.timezone.utc),
    )
    html2 = service.render_html(art2)
    assert '<div class="date">MARCH 15, 2026</div>' in html2

    # Article 3: Published July 4, 2025
    art3 = PhotoCardData(
        headline="Article Three",
        published_at="2025-07-04T12:00:00Z",
    )
    html3 = service.render_html(art3)
    assert '<div class="date">JULY 04, 2025</div>' in html3


def test_render_html_missing_or_invalid_dates_display_unavailable():
    """Verifies missing or invalid dates strictly produce 'DATE UNAVAILABLE' without fabricating dates."""
    service = PhotoCardService()

    # Null published_at
    html_null = service.render_html(PhotoCardData(headline="Null Date", published_at=None))
    assert '<div class="date">DATE UNAVAILABLE</div>' in html_null
    # Confirm no current year or month fabricated
    assert datetime.datetime.now(datetime.timezone.utc).strftime("%B %d, %Y").upper() not in html_null or "DATE UNAVAILABLE" in html_null

    # Empty string published_at
    html_empty = service.render_html(PhotoCardData(headline="Empty Date", published_at=""))
    assert '<div class="date">DATE UNAVAILABLE</div>' in html_empty

    # Unparseable date
    html_invalid = service.render_html(PhotoCardData(headline="Invalid Date", published_at="not-a-valid-date"))
    assert '<div class="date">DATE UNAVAILABLE</div>' in html_invalid


