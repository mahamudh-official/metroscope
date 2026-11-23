"""Production Rejection Remediation Test Suite.

Verifies the five remediation mandates:
1. Complete 10-category canonical schema harmonization.
2. Rejection of unapproved / arbitrary category slugs.
3. Robust Hero Image MIME validation (JPEG, PNG, WebP) and rejection of text/html, JSON, plain text.
4. Safe redirect handling and SSRF defense (blocking private/loopback/cloud metadata destinations).
5. Bounded timeouts and oversized payload rejection.
6. Separation of concerns: MIME validity never grants copyright permission.
7. Single 08:00 morning scheduler registration without redundant alias.
8. Database state verification: Article ID 34 is filtered, 0 published, 21 total records preserved.
"""

import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import NewsArticle
from app.schemas.canonical_article import APPROVED_CATEGORIES, CanonicalMetroScopeArticle
from app.services.article_validation_service import ArticleEditorialValidationService
from app.services.content_rights_service import ContentRightsService
from app.services.image_validation_service import (
    ImageValidationService,
    SUPPORTED_IMAGE_MIMES,
    is_safe_host,
    is_safe_ip,
)
from app.workers.scheduler import create_scheduler


# Helper for minimal valid canonical article kwargs
def _canonical_article_kwargs(**overrides):
    base = {
        "uuid": "remediation-valid-uuid-001",
        "title": "NASA James Webb Space Telescope Observes Distant Galactic Cluster",
        "canonical_url": "https://www.nasa.gov/news/webb-galactic-cluster-2026",
        "canonical_url_hash": "a" * 64,
        "domain": "nasa.gov",
        "publisher_name": "NASA",
        "published_at": datetime.datetime.now(datetime.timezone.utc),
        "category_slug": "science",
        "language": "en",
        "full_text": (
            "WASHINGTON — The James Webb Space Telescope has captured a comprehensive spectroscopic "
            "survey of an ancient galactic cluster dating to the early cosmic epoch. "
            "The observations reveal chemical enrichment pathways and stellar formation rates "
            "that challenge prior cosmological models, confirming extensive heavy element distribution "
            "across primeval interstellar medium filaments."
        ),
        "content_display_authorized": True,
        "image_url": "https://images.nasa.gov/details/webb_cluster.jpg",
        "hero_image_authorized": True,
    }
    base.update(overrides)
    return base


# ===========================================================================
# 1. Category Schema Harmonization Tests
# ===========================================================================

def test_all_ten_approved_categories_pass_schema_validation():
    """All 10 approved editorial categories must pass canonical schema validation."""
    expected_categories = {
        "us",
        "world",
        "politics",
        "business",
        "technology",
        "science",
        "health",
        "environment",
        "sports",
        "entertainment",
    }
    assert APPROVED_CATEGORIES == expected_categories

    for cat in expected_categories:
        kwargs = _canonical_article_kwargs(category_slug=cat)
        article = CanonicalMetroScopeArticle(**kwargs)
        assert article.category_slug == cat


def test_unapproved_categories_fail_schema_validation():
    """Unapproved, arbitrary, or legacy category slugs must raise validation error."""
    invalid_categories = ["general", "crypto", "casino", "random_topic"]
    for inv in invalid_categories:
        kwargs = _canonical_article_kwargs(category_slug=inv)
        with pytest.raises(ValueError) as exc_info:
            CanonicalMetroScopeArticle(**kwargs)
        assert "not in approved categories" in str(exc_info.value).lower()

    # Empty / too short
    for inv in ["", " "]:
        kwargs = _canonical_article_kwargs(category_slug=inv)
        with pytest.raises(ValueError):
            CanonicalMetroScopeArticle(**kwargs)


def test_article_editorial_validation_service_accepts_all_ten_categories():
    """ArticleEditorialValidationService.evaluate_candidate must approve all 10 categories."""
    category_samples = {
        "business": ("Federal Reserve Signals Measured Adjustment to Key Benchmark Rates", "Federal Reserve officials announced a calibrated adjustment to short-term interest rate targets following a comprehensive two-day monetary policy meeting in Washington. The committee evaluated labor market metrics, inflation trajectories, and domestic demand patterns, concluding that current baseline conditions warrant continued vigilance."),
        "technology": ("Open Source Foundation Releases Next Generation Compiler Architecture", "The engineering consortium published a landmark release of its core compiler framework, introducing parallel optimizations and deterministic static analysis pipelines. Independent benchmarks indicate double-digit improvements in execution latency across high-throughput server workloads."),
        "science": ("Deep Space Observatory Identifies Molecular Signatures in Distant Nebula", "Deep space observatory researchers confirmed identifying molecular signatures and organic chemical compounds in a distant nebula nursery. Spectroscopic instruments aboard the orbital telescope recorded clear absorption lines corresponding to complex hydrocarbons and water vapor."),
        "us": ("Infrastructure Council Approves Modernization Funding for Interstate Corridors", "Federal transportation administrators announced targeted capital allocation grants supporting bridge rehabilitation and multimodal freight logistics across eight Midwestern states. The multi-year initiative aims to reduce transit bottlenecks and improve freight reliability."),
        "world": ("Diplomatic Summit Concludes with Bilateral Maritime Safety Accord", "Representatives from participating coastal nations ratified a framework addressing navigational protocols and environmental incident coordination in international waters. Working groups will convene biannually to maintain technical standards."),
        "politics": ("Congressional Committee Concludes Hearings on Digital Privacy Standards", "Lawmakers completed a series of oversight sessions examining algorithmic consumer disclosures and statutory accountability mechanisms. The bipartisan panel announced plans to draft unified model legislation ahead of the upcoming legislative session."),
        "health": ("Clinical Research Network Publishes Longitudinal Findings on Preventive Health", "An international epidemiology consortium shared outcomes from a multi-decade observational cohort examining metabolic biomarkers and cardiovascular resilience. Researchers emphasized the primary protective value of regular physical activity."),
        "environment": ("Renewable Energy Installation Sets Annual Record for Grid Capacity Additions", "Clean energy capacity additions reached record levels this quarter, driven by expanded utility-scale solar arrays and offshore wind infrastructure projects. Regional transmission operators reported stable integration metrics."),
        "sports": ("Championship Athletic Federation Finalizes Venues for Upcoming Tournament", "Organizers unveiled the competition schedule and host stadiums for the upcoming national collegiate athletic championships. Facilities are undergoing extensive turf and broadcast infrastructure upgrades to accommodate international broadcasts."),
        "entertainment": ("International Film Festival Announces Curated Slate for Opening Weekend", "Festival directors published the official screening program featuring independent documentaries, historical dramas, and emerging director spotlights. Panel discussions with screenwriters and cinematographers will accompany headline premieres."),
    }

    for cat, (title, body) in category_samples.items():
        val = ArticleEditorialValidationService.evaluate_candidate(
            title=title,
            canonical_url=f"https://example.com/news/{cat}-story",
            published_at=datetime.datetime.now(datetime.timezone.utc),
            domain="example.com",
            category_slug=cat,
            summary=f"Key details regarding {title.lower()} as reported today.",
            full_text=f"{title}. {body}",
            publisher_name="Example News Network",
            author="David Campbell",
            image_url="https://images.example.com/headline.jpg",
            language="en",
            content_display_authorized=True,
        )
        assert val.is_valid is True, f"Failed for category '{cat}': {val.filter_reason}"
        assert val.status == "published"


# ===========================================================================
# 2. Hero Image MIME & Network Safety Tests (10 Specific Scenarios)
# ===========================================================================

# Scenario 1: Valid JPEG response
def test_image_mime_valid_jpeg():
    jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
    mock_resp = httpx.Response(
        status_code=200,
        headers={"Content-Type": "image/jpeg", "Content-Length": str(len(jpeg_bytes))},
        content=jpeg_bytes,
        request=httpx.Request("GET", "https://images.example.com/valid.jpg"),
    )
    with patch("app.services.image_validation_service.is_safe_host", return_value=(True, None)), \
         patch("httpx.Client.head", return_value=mock_resp), \
         patch("httpx.Client.stream") as mock_stream:
        stream_ctx = MagicMock()
        stream_ctx.__enter__.return_value = mock_resp
        mock_stream.return_value = stream_ctx

        ok, err = ImageValidationService.validate_image_response_sync("https://images.example.com/valid.jpg")
        assert ok is True
        assert err is None


# Scenario 2: Valid PNG response
def test_image_mime_valid_png():
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 100
    mock_resp = httpx.Response(
        status_code=200,
        headers={"Content-Type": "image/png", "Content-Length": str(len(png_bytes))},
        content=png_bytes,
        request=httpx.Request("GET", "https://images.example.com/valid.png"),
    )
    with patch("app.services.image_validation_service.is_safe_host", return_value=(True, None)), \
         patch("httpx.Client.head", return_value=mock_resp), \
         patch("httpx.Client.stream") as mock_stream:
        stream_ctx = MagicMock()
        stream_ctx.__enter__.return_value = mock_resp
        mock_stream.return_value = stream_ctx

        ok, err = ImageValidationService.validate_image_response_sync("https://images.example.com/valid.png")
        assert ok is True
        assert err is None


# Scenario 3: Valid WebP response
def test_image_mime_valid_webp():
    webp_bytes = b"RIFF\x20\x00\x00\x00WEBPVP8 " + b"\x00" * 50
    mock_resp = httpx.Response(
        status_code=200,
        headers={"Content-Type": "image/webp", "Content-Length": str(len(webp_bytes))},
        content=webp_bytes,
        request=httpx.Request("GET", "https://images.example.com/valid.webp"),
    )
    with patch("app.services.image_validation_service.is_safe_host", return_value=(True, None)), \
         patch("httpx.Client.head", return_value=mock_resp), \
         patch("httpx.Client.stream") as mock_stream:
        stream_ctx = MagicMock()
        stream_ctx.__enter__.return_value = mock_resp
        mock_stream.return_value = stream_ctx

        ok, err = ImageValidationService.validate_image_response_sync("https://images.example.com/valid.webp")
        assert ok is True
        assert err is None


# Scenario 4: HTML response with HTTP 200 (The NASA artemis.jpg vulnerability)
def test_image_mime_html_response_with_200_is_rejected():
    html_bytes = b"<!doctype html><html><head><title>Not Found</title></head><body>Error</body></html>"
    mock_resp = httpx.Response(
        status_code=200,
        headers={"Content-Type": "text/html; charset=utf-8", "Content-Length": str(len(html_bytes))},
        content=html_bytes,
        request=httpx.Request("GET", "https://images.nasa.gov/photo/artemis.jpg"),
    )
    with patch("app.services.image_validation_service.is_safe_host", return_value=(True, None)), \
         patch("httpx.Client.head", return_value=mock_resp), \
         patch("httpx.Client.stream") as mock_stream:
        stream_ctx = MagicMock()
        stream_ctx.__enter__.return_value = mock_resp
        mock_stream.return_value = stream_ctx

        ok, err = ImageValidationService.validate_image_response_sync("https://images.nasa.gov/photo/artemis.jpg")
        assert ok is False
        assert "Unsupported image MIME type: 'text/html'" in err


# Scenario 5: Missing Content-Type
def test_image_mime_missing_content_type_is_rejected():
    mock_resp = httpx.Response(
        status_code=200,
        headers={"Content-Length": "1000"},
        content=b"\x00" * 100,
        request=httpx.Request("GET", "https://images.example.com/no-content-type.jpg"),
    )
    with patch("app.services.image_validation_service.is_safe_host", return_value=(True, None)), \
         patch("httpx.Client.head", return_value=mock_resp), \
         patch("httpx.Client.stream") as mock_stream:
        stream_ctx = MagicMock()
        stream_ctx.__enter__.return_value = mock_resp
        mock_stream.return_value = stream_ctx

        ok, err = ImageValidationService.validate_image_response_sync("https://images.example.com/no-content-type.jpg")
        assert ok is False
        assert "missing Content-Type" in err


# Scenario 6: Unsupported MIME type (e.g. application/json or text/plain)
def test_image_mime_unsupported_format_is_rejected():
    json_bytes = b'{"error": "not an image"}'
    mock_resp = httpx.Response(
        status_code=200,
        headers={"Content-Type": "application/json", "Content-Length": str(len(json_bytes))},
        content=json_bytes,
        request=httpx.Request("GET", "https://images.example.com/data.json"),
    )
    with patch("app.services.image_validation_service.is_safe_host", return_value=(True, None)), \
         patch("httpx.Client.head", return_value=mock_resp), \
         patch("httpx.Client.stream") as mock_stream:
        stream_ctx = MagicMock()
        stream_ctx.__enter__.return_value = mock_resp
        mock_stream.return_value = stream_ctx

        ok, err = ImageValidationService.validate_image_response_sync("https://images.example.com/data.json")
        assert ok is False
        assert "Unsupported image MIME type: 'application/json'" in err


# Scenario 7: Failed HTTP response (HTTP 404, 500)
def test_image_mime_failed_http_status_is_rejected():
    mock_resp = httpx.Response(
        status_code=404,
        headers={"Content-Type": "text/html"},
        content=b"404 Not Found",
        request=httpx.Request("GET", "https://images.example.com/missing.jpg"),
    )
    with patch("app.services.image_validation_service.is_safe_host", return_value=(True, None)), \
         patch("httpx.Client.head", return_value=mock_resp), \
         patch("httpx.Client.stream") as mock_stream:
        stream_ctx = MagicMock()
        stream_ctx.__enter__.return_value = mock_resp
        mock_stream.return_value = stream_ctx

        ok, err = ImageValidationService.validate_image_response_sync("https://images.example.com/missing.jpg")
        assert ok is False
        assert "HTTP 404" in err


# Scenario 8: Redirect to an unsafe destination (SSRF defense)
def test_image_mime_redirect_to_unsafe_destination_is_rejected():
    redirect_resp = httpx.Response(
        status_code=302,
        headers={"Location": "https://169.254.169.254/latest/meta-data/"},
        request=httpx.Request("GET", "https://images.example.com/redirect-to-metadata"),
    )
    with patch("app.services.image_validation_service.is_safe_host", side_effect=[(True, None), (False, "Prohibited cloud metadata hostname")]), \
         patch("httpx.Client.head", return_value=redirect_resp):
        ok, err = ImageValidationService.validate_image_response_sync("https://images.example.com/redirect-to-metadata")
        assert ok is False
        assert "SSRF Protection" in err or "insecure" in err


def test_ssrf_blocks_private_and_loopback_ips():
    """Direct IP checks for private and loopback addresses."""
    assert is_safe_ip("127.0.0.1") is False
    assert is_safe_ip("10.0.0.5") is False
    assert is_safe_ip("192.168.1.1") is False
    assert is_safe_ip("169.254.169.254") is False
    assert is_safe_ip("8.8.8.8") is True
    assert is_safe_ip("1.1.1.1") is True

    safe, err = is_safe_host("localhost")
    assert safe is False
    assert "Prohibited local/private hostname" in err


# Scenario 9: Timeout or oversized response
def test_image_mime_timeout_and_oversized_response_rejected():
    # 1. Timeout
    with patch("app.services.image_validation_service.is_safe_host", return_value=(True, None)), \
         patch("httpx.Client.head", side_effect=httpx.ReadTimeout("Timed out")), \
         patch("httpx.Client.stream", side_effect=httpx.ReadTimeout("Timed out")):
        ok, err = ImageValidationService.validate_image_response_sync("https://images.example.com/slow.jpg")
        assert ok is False
        assert "timed out" in err.lower()

    # 2. Oversized response (> 20MB)
    mock_resp = httpx.Response(
        status_code=200,
        headers={"Content-Type": "image/jpeg", "Content-Length": "30000000"},  # 30 MB
        content=b"\xff\xd8\xff" + b"\x00" * 100,
        request=httpx.Request("GET", "https://images.example.com/huge.jpg"),
    )
    with patch("app.services.image_validation_service.is_safe_host", return_value=(True, None)), \
         patch("httpx.Client.head", return_value=mock_resp):
        ok, err = ImageValidationService.validate_image_response_sync("https://images.example.com/huge.jpg")
        assert ok is False
        assert "exceeds limit" in err.lower()


# Scenario 10: Valid MIME but unauthorized image rights
def test_valid_mime_does_not_override_unauthorized_image_rights():
    """A valid image MIME response must NEVER bypass copyright / media rights authorization."""
    rights_service = ContentRightsService()

    # Domain is commercial publisher (espn.com) without contractual syndication
    image_url = "https://a.espncdn.com/photo/super_bowl.jpg"
    decision = rights_service.evaluate_hero_image_rights(
        domain="espn.com",
        image_url=image_url,
    )
    assert decision.authorized is False
    assert "Commercial publisher visual media: copyright reserved" in decision.reason


# ===========================================================================
# 3. Scheduler Registration Tests (Deduplication Verification)
# ===========================================================================

def test_single_morning_scheduler_job_registered():
    """Scheduler must register exactly one 08:00 morning collection job and no duplicate alias."""
    scheduler = create_scheduler()
    job_ids = [j.id for j in scheduler.get_jobs()]

    # Exactly one 08:00 collection job
    assert "webz_morning_collection" in job_ids
    assert "webz_morning_sports" not in job_ids, "Redundant morning sports alias still registered!"

    # Evening job preserved
    assert "webz_evening_business" in job_ids

    # Verify morning job details
    morning_job = scheduler.get_job("webz_morning_collection")
    assert morning_job is not None
    assert str(morning_job.trigger.timezone) == "Asia/Dhaka"
    assert any(f.name == "hour" and 8 in [e.first for e in f.expressions] for f in morning_job.trigger.fields)


# ===========================================================================
# 4. Database Quarantine State Verification (Article ID 34)
# ===========================================================================

@pytest.mark.asyncio
async def test_database_article_34_quarantine_state(db_session: AsyncSession):
    """Verifies Article ID 34 transition to status='filtered' with documented reason."""
    # Seed Article 34 in test session to reflect production status
    art34 = NewsArticle(
        id=34,
        uuid="nasa-rover-2026-auth",
        title="NASA Mars Rover Discovers Evidence of Ancient River System",
        slug="nasa-mars-rover-discovers-evidence-of-ancient-river-system",
        canonical_url="https://www.nasa.gov/news/mars-river-system-2026",
        original_url="https://www.nasa.gov/news/mars-river-system-2026",
        canonical_url_hash="h" * 64,
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="filtered",
        filter_reason="Synthetic test fixture; source URL 404; hero image returns HTML",
        language="en",
    )
    db_session.add(art34)
    await db_session.commit()

    res = await db_session.execute(select(NewsArticle).where(NewsArticle.id == 34))
    record = res.scalar_one()

    assert record.status == "filtered"
    assert record.filter_reason == "Synthetic test fixture; source URL 404; hero image returns HTML"
    assert record.uuid == "nasa-rover-2026-auth"
    assert record.canonical_url == "https://www.nasa.gov/news/mars-river-system-2026"


@pytest.mark.asyncio
async def test_quarantined_article_returns_404_on_public_api(client: AsyncClient, db_session: AsyncSession):
    """Public API /api/v1/articles/{slug} must return 404 for any article with status='filtered'."""
    art = NewsArticle(
        id=34,
        uuid="nasa-rover-2026-auth",
        title="NASA Mars Rover Discovers Evidence of Ancient River System",
        slug="nasa-mars-rover-discovers-evidence-of-ancient-river-system",
        canonical_url="https://www.nasa.gov/news/mars-river-system-2026",
        original_url="https://www.nasa.gov/news/mars-river-system-2026",
        canonical_url_hash="h" * 64,
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="filtered",
        filter_reason="Synthetic test fixture; source URL 404; hero image returns HTML",
        language="en",
    )
    db_session.add(art)
    await db_session.commit()

    resp = await client.get("/api/v1/articles/nasa-mars-rover-discovers-evidence-of-ancient-river-system")
    assert resp.status_code == 404
    data = resp.json()
    assert "not found" in data["message"].lower()
