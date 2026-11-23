import datetime
from decimal import Decimal
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.webz.client import (
    WebzClient,
    WebzError,
    WebzAuthenticationError,
    WebzRateLimitError,
    WebzRequestError,
    CATEGORY_QUERIES,
)
from app.integrations.webz.parser import (
    normalize_webz_post,
    parse_webz_datetime,
    extract_short_summary,
)
from app.integrations.webz.schemas import (
    WebzPost,
    WebzResponse,
    WebzThread,
    NormalizedWebzArticle,
)
from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.source import NewsSource
from app.models.webz_ledger import WebzUsageLedger
from app.services.budget_service import (
    BudgetPeriodSummary,
    BudgetProtectionService,
    PreflightResult,
)
from app.services.webz_ingestion_service import WebzIngestionService


SAMPLE_POST_RAW = {
    "uuid": "webz-uuid-12345-abcde",
    "url": "https://espn.com/nfl/story/_/id/998877/super-bowl-preview",
    "published": "2026-11-10T08:00:00.000+00:00",
    "title": "Championship Preview: Historic Rivalry Rekindled on National Stage",
    "text": "Full exclusive body text of 2000 words that should never be republished directly on MetroScope without a licensing agreement.",
    "author": "Marcus Thompson",
    "language": "english",
    "thread": {
        "uuid": "webz-thread-12345",
        "url": "https://espn.com/nfl/story/_/id/998877/super-bowl-preview",
        "site": "espn.com",
        "site_full": "espn.com",
        "site_categories": ["sport", "football", "nfl"],
        "site_type": "news",
        "country": "US",
        "domain_rank": 85,
        "spam_score": 0.01,
        "performance_score": 9,
        "main_image": "https://a.espncdn.com/photo/2026/1110/super_bowl.jpg",
    },
    "entities": {
        "organizations": [{"name": "NFL"}],
        "persons": [{"name": "Patrick Mahomes"}],
    },
}


# --- 1. Authentication & Query Construction Tests ---

def test_webz_client_authentication_configured():
    client = WebzClient(api_key="valid_token_xyz")
    assert client.is_configured() is True
    assert client.api_key == "valid_token_xyz"


def test_webz_client_authentication_missing_token():
    client = WebzClient(api_key="")
    assert client.is_configured() is False


def test_webz_query_construction_sports():
    client = WebzClient(api_key="dummy_token")
    query, ts_ms = client.build_query(category="sports", freshness_hours=24)
    # With final unified query, both business/finance and science/technology categories should be present
    assert "economy, business and finance" in query.lower()
    assert "science and technology" in query.lower()
    # Freshness ts should be approximately 24 hours ago in ms
    now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    diff_hours = (now_ms - ts_ms) / (1000 * 3600)
    assert 23.5 <= diff_hours <= 24.5


def test_webz_query_construction_business():
    client = WebzClient(api_key="dummy_token")
    query, ts_ms = client.build_query(category="business", freshness_hours=12)
    # business category uses economy, business and finance category filter
    assert "economy, business and finance" in query.lower()

    # Freshness ts should be approximately 12 hours ago in ms
    now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    diff_hours = (now_ms - ts_ms) / (1000 * 3600)
    assert 11.5 <= diff_hours <= 12.5


def test_webz_freshness_window_caps_prevents_historical_collection():
    client = WebzClient(api_key="dummy_token")
    # Even if an excessive window like 500 hours is requested, capped to max 48h
    query, ts_ms = client.build_query(category="sports", freshness_hours=500)
    now_ms = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    diff_hours = (now_ms - ts_ms) / (1000 * 3600)
    assert diff_hours <= 48.5


# --- 2. API Response Schema & Result Mapping Tests ---

def test_webz_response_schema_parsing():
    payload = {
        "posts": [SAMPLE_POST_RAW],
        "total_results": 150,
        "more_results_available": 140,
        "next": "/newsApiLite?token=xyz&q=sport&from=10",
        "requests_left": 990,
    }
    response = WebzResponse.model_validate(payload)
    assert len(response.posts) == 1
    assert response.total_results == 150
    assert response.requests_left == 990
    post = response.posts[0]
    assert post.uuid == "webz-uuid-12345-abcde"
    assert post.thread.site == "espn.com"
    assert post.thread.domain_rank == 85


def test_webz_result_mapping_and_copyright_safeguards():
    post = WebzPost.model_validate(SAMPLE_POST_RAW)
    normalized = normalize_webz_post(post, target_category="sports")
    assert normalized is not None
    assert normalized.uuid == "webz-uuid-12345-abcde"
    assert normalized.title == "Championship Preview: Historic Rivalry Rekindled on National Stage"
    assert normalized.domain == "espn.com"
    assert normalized.author == "MetroScope News Desk"
    assert normalized.country == "US"
    assert normalized.category_slug == "sports"

    # Copyright Safeguard: When post.summary is absent, summary is None (never full 2000-word text or fake summary)
    assert normalized.summary is None

    # When post.summary is provided, it is preserved cleanly within 500 chars
    post_with_summary = WebzPost.model_validate({
        **SAMPLE_POST_RAW,
        "summary": "Official NFL championship preview covering team matchups and broadcast schedules.",
    })
    norm_with_summary = normalize_webz_post(post_with_summary, target_category="sports")
    assert norm_with_summary is not None
    assert norm_with_summary.summary == "Official NFL championship preview covering team matchups and broadcast schedules."
    assert len(norm_with_summary.summary) <= 500
    assert "2000 words" not in norm_with_summary.summary

    # Attribution & Trust Indicators
    assert normalized.trust_indicators["provider"] == "webz.io"
    assert normalized.trust_indicators["provider_domain_rank"] == 85
    assert normalized.image_metadata["external_only"] is True


def test_webz_invalid_response_handling():
    # 1. Missing UUID
    invalid_post_1 = WebzPost.model_validate({**SAMPLE_POST_RAW, "uuid": ""})
    assert normalize_webz_post(invalid_post_1) is None

    # 2. Missing/Empty Title
    invalid_post_2 = WebzPost.model_validate({**SAMPLE_POST_RAW, "title": ""})
    assert normalize_webz_post(invalid_post_2) is None

    # 3. Invalid URL
    invalid_post_3 = WebzPost.model_validate({**SAMPLE_POST_RAW, "url": "not-a-valid-url"})
    assert normalize_webz_post(invalid_post_3) is None

    # 4. Future publication timestamp (> 24h ahead)
    future_date = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=5)).isoformat()
    invalid_post_4 = WebzPost.model_validate({**SAMPLE_POST_RAW, "published": future_date})
    assert normalize_webz_post(invalid_post_4) is None


# --- 3. Client Status & Controlled Retry Tests ---

@pytest.mark.asyncio
async def test_webz_client_http_429_rate_limit():
    client = WebzClient(api_key="valid_token")
    mock_resp = httpx.Response(
        status_code=429,
        text="Rate limit exceeded",
        request=httpx.Request("GET", "https://api.webz.io"),
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        with pytest.raises(WebzRateLimitError):
            await client.fetch_category_articles("sports")
        # Rate limit must NOT retry
        assert mock_get.await_count == 1


@pytest.mark.asyncio
async def test_webz_client_timeout_and_controlled_retry():
    client = WebzClient(api_key="valid_token", max_retries=1)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ReadTimeout("Timeout from Webz.io")
        with pytest.raises(WebzError) as exc_info:
            await client.fetch_category_articles("sports")
        assert "connection failed" in str(exc_info.value).lower()
        # Initial attempt + 1 controlled retry = exactly 2 attempts
        assert mock_get.await_count == 2


# --- 4. Budget Protection Service Tests ---

@pytest.mark.asyncio
async def test_budget_preflight_allows_within_ceiling(db_session: AsyncSession):
    budget_service = BudgetProtectionService()
    with patch.object(settings, "WEBZ_IO_API_KEY", "test_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", True):
        result = await budget_service.preflight_check(db=db_session)
        assert result.allowed is True
        assert result.stop_reason is None
        assert result.remaining_allowance == Decimal("4.0000")


@pytest.mark.asyncio
async def test_budget_preflight_monthly_hard_stop(db_session: AsyncSession):
    budget_service = BudgetProtectionService()
    period = budget_service.get_current_billing_period()

    # Insert existing usage consuming the $4.00 ceiling
    prior_entry = WebzUsageLedger(
        billing_period=period,
        job_name="prior_collection",
        endpoint="/newsApiLite",
        success=True,
        returned_count=10,
        billable_count=10,
        estimated_cost=Decimal("4.0000"),
        actual_cost=Decimal("4.0000"),
        reserved_cost=Decimal("4.0000"),
        remaining_allowance=Decimal("0.0000"),
    )
    db_session.add(prior_entry)
    await db_session.commit()

    with patch.object(settings, "WEBZ_IO_API_KEY", "test_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", True):
        result = await budget_service.preflight_check(db=db_session)
        assert result.allowed is False
        assert result.stop_reason == "MONTHLY_COLLECTION_CEILING_REACHED"
        assert result.remaining_allowance == Decimal("0.0000")


@pytest.mark.asyncio
async def test_budget_preflight_preserves_emergency_reserve(db_session: AsyncSession):
    budget_service = BudgetProtectionService()
    period = budget_service.get_current_billing_period()

    # Spend $3.9980 leaving only $0.0020
    prior_entry = WebzUsageLedger(
        billing_period=period,
        job_name="prior_collection",
        endpoint="/newsApiLite",
        success=True,
        returned_count=10,
        billable_count=10,
        estimated_cost=Decimal("3.9980"),
        actual_cost=Decimal("3.9980"),
        reserved_cost=Decimal("3.9980"),
        remaining_allowance=Decimal("0.0020"),
    )
    db_session.add(prior_entry)
    await db_session.commit()

    with patch.object(settings, "WEBZ_IO_API_KEY", "test_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", True):
        # Trying to reserve $0.0050 when only $0.0020 remains
        result = await budget_service.preflight_check(db=db_session, estimated_cost=Decimal("0.0050"))
        assert result.allowed is False
        assert result.stop_reason == "INSUFFICIENT_COLLECTION_ALLOWANCE"


@pytest.mark.asyncio
async def test_budget_preflight_owner_disabled_switch(db_session: AsyncSession):
    budget_service = BudgetProtectionService()
    with patch.object(settings, "WEBZ_IO_API_KEY", "test_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", False):
        result = await budget_service.preflight_check(db=db_session)
        assert result.allowed is False
        assert result.stop_reason == "COLLECTION_DISABLED_BY_OWNER"


@pytest.mark.asyncio
async def test_budget_request_reservation_and_finalization(db_session: AsyncSession):
    budget_service = BudgetProtectionService()
    entry = await budget_service.reserve_request(
        db=db_session,
        job_name="test_sports_reserve",
        endpoint="/newsApiLite",
        estimated_cost=Decimal("0.0050"),
    )
    assert entry.id is not None
    assert entry.success is False
    assert entry.reserved_cost == Decimal("0.0050")

    mock_resp = WebzResponse.model_validate({
        "posts": [SAMPLE_POST_RAW],
        "requests_left": 985,
        "cost": Decimal("0.0050"),
    })

    finalized = await budget_service.finalize_ledger_entry(
        db=db_session,
        entry=entry,
        status_code=200,
        response=mock_resp,
    )
    assert finalized.success is True
    assert finalized.returned_count == 1
    assert finalized.requests_left == 985
    assert finalized.actual_cost == Decimal("0.0050")


# --- 5. Ingestion Service Deduplication & Persistence Tests ---

@pytest.mark.asyncio
async def test_webz_ingestion_service_deduplication(db_session: AsyncSession):
    # Setup categories
    cat = NewsCategory(name="Sports", slug="sports", description="Sports coverage")
    db_session.add(cat)
    await db_session.commit()

    service = WebzIngestionService()
    mock_client = AsyncMock()
    mock_client.endpoint = "/newsApiLite"
    mock_client.build_query = MagicMock(return_value=("category:sport", 1700000000000))

    valid_authorized_post = {
        **SAMPLE_POST_RAW,
        "uuid": "webz-uuid-12345-abcde",
        "url": "https://nasa.gov/news/sports-science-evaluation-iss",
        "title": "NASA Evaluates Astronaut Physical Conditioning Protocols in Microgravity",
        "text": (
            "NASA exercise physiology researchers aboard the International Space Station have "
            "concluded a comprehensive study evaluating cardiovascular stamina and musculoskeletal "
            "resilience during long-duration orbital missions. The findings provide critical baseline "
            "metrics for athletic training regimens adapted to microgravity environments, demonstrating "
            "significant improvements in recovery intervals and neuromuscular endurance among crew members."
        ),
        "author": "Dr. Sarah Mitchell",
        "language": "english",
        "thread": {
            **SAMPLE_POST_RAW["thread"],
            "site": "nasa.gov",
            "site_full": "www.nasa.gov",
            "country": "US",
            "main_image": "https://images.nasa.gov/photo/iss_crew_fitness.jpg",
        },
    }

    mock_resp = WebzResponse.model_validate({
        "posts": [valid_authorized_post],
        "requests_left": 995,
        "total_results": 1,
    })
    mock_client.fetch_news_articles.return_value = mock_resp
    service.client = mock_client

    with patch.object(settings, "WEBZ_IO_API_KEY", "valid_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", True), \
         patch("app.services.image_validation_service.ImageValidationService.validate_image_response_async", return_value=(True, None)):

        # First run: should successfully insert 1 article
        res1 = await service.run_category_collection(db=db_session, category="sports")
        assert res1["status"] == "success"
        assert res1["inserted"] == 1
        assert res1["duplicate"] == 0

        # Verify the actual API dispatch receives the category query and checkpoint.
        mock_client.fetch_news_articles.assert_awaited_once_with(
            query="category:sport",
            checkpoint_ts_ms=1700000000000,
            freshness_hours=24,
            size=10,
        )

        # Second run: same UUID and canonical URL hash -> duplicate, 0 inserted
        res2 = await service.run_category_collection(db=db_session, category="sports")
        assert res2["status"] == "success"
        assert res2["inserted"] == 0
        assert res2["duplicate"] == 1


# --- 6. Public API Copyright Protection & Historical Preservation Tests ---

@pytest.mark.asyncio
async def test_public_api_excludes_unauthorized_full_text(client: httpx.AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="ESPN", domain="espn.com")
    cat = NewsCategory(name="Sports", slug="sports")
    db_session.add_all([source, cat])
    await db_session.commit()

    article = NewsArticle(
        title="Super Bowl LIX Championship Coverage",
        slug="super-bowl-lix-championship-coverage",
        description="Concise permitted summary under fair use.",
        source_id=source.id,
        category_id=cat.id,
        original_url="https://espn.com/nfl/story/super-bowl",
        canonical_url="https://espn.com/nfl/story/super-bowl",
        canonical_url_hash="2222222222222222222222222222222222222222222222222222222222222222",
        uuid="uuid-webz-super-bowl-01",
        author="Jane Reporter",
        language="en",
        country="US",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(article)
    await db_session.commit()

    # 1. Check article list endpoint
    resp_list = await client.get("/api/v1/articles")
    assert resp_list.status_code == 200
    list_json = resp_list.json()
    assert len(list_json["items"]) >= 1
    for item in list_json["items"]:
        # Strict Copyright check: full text body MUST NOT be present
        assert "text" not in item
        assert "content" not in item
        assert "body" not in item

    # 2. Check article detail endpoint
    resp_detail = await client.get(f"/api/v1/articles/{article.slug}")
    assert resp_detail.status_code == 200
    detail_json = resp_detail.json()
    assert "text" not in detail_json
    assert "content" not in detail_json
    assert "body" not in detail_json
    assert "uuid" not in detail_json
    assert "canonical_url_hash" not in detail_json
    assert "trust_indicators" not in detail_json
    assert "filter_reason" not in detail_json
    assert detail_json["author"] == "MetroScope News Desk"


@pytest.mark.asyncio
async def test_existing_historical_articles_preserved_without_uuid(client: httpx.AsyncClient, db_session: AsyncSession):
    """Historical articles collected prior to Webz.io migration have uuid=None and remain fully queryable."""
    source = NewsSource(name="Legacy Daily", domain="legacydaily.com")
    cat = NewsCategory(name="US News", slug="us")
    db_session.add_all([source, cat])
    await db_session.commit()

    historical = NewsArticle(
        title="Legacy Archive Historic Discovery Report",
        slug="legacy-archive-historic-discovery-report",
        description="Preserved historical coverage from archive.",
        source_id=source.id,
        category_id=cat.id,
        original_url="https://legacydaily.com/archive/historic-news",
        canonical_url="https://legacydaily.com/archive/historic-news",
        canonical_url_hash="3333333333333333333333333333333333333333333333333333333333333333",
        uuid=None,  # Legacy article has no Webz UUID
        language="en",
        country="US",
        published_at=datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=10),
        status="published",
    )
    db_session.add(historical)
    await db_session.commit()

    resp = await client.get(f"/api/v1/articles/{historical.slug}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Legacy Archive Historic Discovery Report"
    assert "uuid" not in data


def test_webz_utility_page_rejection():
    """Utility pages such as Terms & Conditions or /page/terms must be rejected during normalization."""
    util_post = WebzPost.model_validate({
        **SAMPLE_POST_RAW,
        "uuid": "webz-util-001",
        "title": "Terms & Conditions",
        "url": "https://iopscience.iop.org/page/terms",
    })
    assert normalize_webz_post(util_post) is None


@pytest.mark.asyncio
async def test_webz_ingestion_quality_and_relevance_gate(db_session: AsyncSession):
    """Commercial spam posts must be filtered by the quality/relevance gate and recorded as status='filtered'."""
    cat = NewsCategory(name="Business", slug="business", description="Business coverage")
    db_session.add(cat)
    await db_session.commit()

    spam_post = {
        **SAMPLE_POST_RAW,
        "uuid": "webz-spam-99999",
        "title": "Buy Now! Best Discount Code and Free Shipping on Hoodies Today",
        "url": "https://spamshop.example.com/deals/hoodies-sale",
    }

    service = WebzIngestionService()
    mock_client = AsyncMock()
    mock_client.endpoint = "/api/news"
    mock_client.build_query = MagicMock(return_value=('category:"Economy, Business and Finance"', 1700000000000))
    mock_client.fetch_news_articles.return_value = WebzResponse.model_validate({
        "posts": [spam_post],
        "requests_left": 990,
        "total_results": 1,
    })
    service.client = mock_client

    with patch.object(settings, "WEBZ_IO_API_KEY", "valid_key"), \
         patch.object(settings, "WEBZ_IO_COLLECTION_ENABLED", True), \
         patch("app.services.image_validation_service.ImageValidationService.validate_image_response_async", return_value=(True, None)):
        res = await service.run_category_collection(db=db_session, category="business")
        assert res["status"] == "success"
        assert res["inserted"] == 0
        assert res["filtered"] == 1

    stmt = select(NewsArticle).where(NewsArticle.uuid == "webz-spam-99999")
    filtered_row = (await db_session.execute(stmt)).scalar_one_or_none()
    assert filtered_row is not None
    assert filtered_row.status == "filtered"
    assert filtered_row.filter_reason is not None
