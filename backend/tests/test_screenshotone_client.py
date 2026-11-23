"""Tests for ScreenshotOneClient API integration and photo card endpoints."""

from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.integrations.screenshotone.client import (
    ScreenshotOneClient,
    ScreenshotOneConfigurationError,
    ScreenshotOneTimeoutError,
    ScreenshotOneAPIError,
    sign_query_params,
)
from app.main import app
from app.services.photo_card_service import PhotoCardData, PhotoCardService


def test_screenshotone_client_configuration():
    # Unconfigured client
    unconfigured = ScreenshotOneClient(access_key=None)
    assert unconfigured.is_configured() is False

    empty_client = ScreenshotOneClient(access_key="   ")
    assert empty_client.is_configured() is False

    # Configured client
    configured = ScreenshotOneClient(access_key="test_access_key_123")
    assert configured.is_configured() is True
    assert configured.access_key == "test_access_key_123"


def test_sign_query_params():
    params = {
        "access_key": "my_key",
        "viewport_width": 1080,
        "format": "jpeg",
    }
    secret = "my_secret_token"
    sig = sign_query_params(params, secret)
    assert isinstance(sig, str)
    assert len(sig) == 64  # SHA-256 hex string

    # Deterministic output
    assert sign_query_params(params, secret) == sig


@pytest.mark.asyncio
async def test_render_html_unconfigured_raises_error():
    client = ScreenshotOneClient(access_key=None)
    with pytest.raises(ScreenshotOneConfigurationError) as exc_info:
        await client.render_html("<html><body>Test</body></html>")
    assert "not configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_render_html_empty_content_raises_error():
    client = ScreenshotOneClient(access_key="test_key")
    with pytest.raises(ValueError) as exc_info:
        await client.render_html("")
    assert "cannot be empty" in str(exc_info.value)


@pytest.mark.asyncio
async def test_render_html_success_mocked():
    client = ScreenshotOneClient(
        access_key="valid_test_key",
        secret_key="valid_secret_key",
        base_url="https://api.screenshotone.com",
    )

    fake_image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 200

    mock_response = httpx.Response(
        status_code=200,
        content=fake_image_bytes,
        headers={"content-type": "image/jpeg"},
        request=httpx.Request("POST", "https://api.screenshotone.com/take"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response

        image_out = await client.render_html(
            html="<html><body><main class='card'>Card</main></body></html>",
            viewport_width=1080,
            viewport_height=1080,
            image_format="jpeg",
            image_quality=90,
            selector=".card",
        )

        assert image_out == fake_image_bytes
        assert mock_post.called

        # Verify dispatched arguments
        call_args = mock_post.call_args
        params = call_args.kwargs["params"]
        payload = call_args.kwargs.get("json") or call_args.kwargs.get("data")

        assert params["access_key"] == "valid_test_key"
        assert params["viewport_width"] == 1080
        assert params["viewport_height"] == 1080
        assert params["format"] == "jpeg"
        assert params["image_quality"] == 90
        assert params["selector"] == ".card"
        assert "signature" in params  # Signed request
        assert payload["html"] == "<html><body><main class='card'>Card</main></body></html>"


@pytest.mark.asyncio
async def test_render_html_timeout_error():
    client = ScreenshotOneClient(access_key="valid_key", timeout_seconds=5.0)

    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timeout")):
        with pytest.raises(ScreenshotOneTimeoutError) as exc_info:
            await client.render_html("<html><body>Timeout Test</body></html>")
        assert "timed out after 5.0s" in str(exc_info.value)


@pytest.mark.asyncio
async def test_render_html_api_error_401():
    client = ScreenshotOneClient(access_key="invalid_key")

    mock_err_response = httpx.Response(
        status_code=401,
        text='{"error": {"code": "unauthorized", "message": "Invalid access key provided"}}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://api.screenshotone.com/take"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_err_response

        with pytest.raises(ScreenshotOneAPIError) as exc_info:
            await client.render_html("<html><body>Auth Fail</body></html>")

        assert exc_info.value.status_code == 401
        assert "Invalid access key provided" in str(exc_info.value)


@pytest.mark.asyncio
async def test_render_html_api_error_429_rate_limit():
    client = ScreenshotOneClient(access_key="valid_key")

    mock_err_response = httpx.Response(
        status_code=429,
        text='{"message": "Rate limit exceeded. Please upgrade plan."}',
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://api.screenshotone.com/take"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_err_response

        with pytest.raises(ScreenshotOneAPIError) as exc_info:
            await client.render_html("<html><body>Rate limit</body></html>")

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_photo_card_service_render_image_integration():
    mock_client = ScreenshotOneClient(access_key="fake_key")
    service = PhotoCardService(screenshot_client=mock_client)

    fake_bytes = b"PHOTO_CARD_JPEG_DATA"
    with patch.object(mock_client, "render_html", new_callable=AsyncMock) as mock_render:
        mock_render.return_value = fake_bytes

        data = PhotoCardData(
            headline="Breakthrough in Fusion Energy",
            category="Science",
        )
        result = await service.render_image(data, format="jpeg", image_quality=95)

        assert result == fake_bytes
        assert mock_render.called
        call_kwargs = mock_render.call_args.kwargs
        assert call_kwargs["viewport_width"] == 1080
        assert call_kwargs["viewport_height"] == 1080
        assert call_kwargs["selector"] == ".card"
        assert "Fusion Energy" in call_kwargs["html"]
        assert "canvas-fixed" in call_kwargs["html"]


# --- FastAPI Preview Endpoints Integration Tests ---

@pytest.mark.asyncio
async def test_api_photo_card_preview_endpoint_default(client: httpx.AsyncClient):
    response = await client.get("/api/v1/photo-cards/preview")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'class="brand-logo"' in response.text
    assert 'alt="MetroScope"' in response.text
    assert "data:image/" in response.text
    assert "Technology" in response.text
    assert "AI and robotics are reshaping global industry" in response.text
    assert "theMetroScope.com" in response.text


@pytest.mark.asyncio
async def test_api_photo_card_preview_endpoint_custom_query(client: httpx.AsyncClient):
    response = await client.get(
        "/api/v1/photo-cards/preview",
        params={
            "headline": "Electric Vehicle Sales Surge Across North America",
            "category": "business",
            "image_url": "https://images.example.com/ev.jpg",
            "website_url": "https://metroscope.news",
            "canvas_fixed": "true",
        },
    )
    assert response.status_code == 200
    assert "Electric Vehicle Sales Surge" in response.text
    assert "Business" in response.text
    assert "canvas-fixed" in response.text
    assert 'url("https://images.example.com/ev.jpg")' in response.text


@pytest.mark.asyncio
async def test_api_photo_card_article_html_not_found(client: httpx.AsyncClient):
    response = await client.get("/api/v1/photo-cards/articles/9999999/html")
    assert response.status_code == 404
    err_body = response.json()
    err_text = (err_body.get("message") or err_body.get("detail") or "").lower()
    assert "not found" in err_text


@pytest.mark.asyncio
async def test_api_photo_card_article_html_and_render_with_db_article(
    client: httpx.AsyncClient, db_session
):
    import datetime
    from app.models.article import NewsArticle
    from app.models.category import NewsCategory

    cat = NewsCategory(name="Environment", slug="environment")
    db_session.add(cat)
    await db_session.commit()

    art = NewsArticle(
        title="Renewable Energy Capacity Reaches Global Milestone",
        slug="renewable-energy-milestone",
        description="Global wind and solar installations exceed projections.",
        canonical_url="https://reuters.com/green/energy",
        original_url="https://reuters.com/green/energy",
        canonical_url_hash="c" * 64,
        category_id=cat.id,
        image_url="https://images.example.com/wind.jpg",
        published_at=datetime.datetime(2026, 11, 17, 10, 0, 0, tzinfo=datetime.timezone.utc),
        author="MetroScope News Desk",
        status="published",
    )
    db_session.add(art)
    await db_session.commit()

    # 1. HTML generation endpoint
    html_resp = await client.get(f"/api/v1/photo-cards/articles/{art.id}/html")
    assert html_resp.status_code == 200
    assert "Renewable Energy Capacity" in html_resp.text
    assert "Environment" in html_resp.text
    assert 'url("https://images.example.com/wind.jpg")' in html_resp.text

    # 2. Render image endpoint requires operator authentication -> 401 without auth
    unauth_resp = await client.get(f"/api/v1/photo-cards/articles/{art.id}/render")
    assert unauth_resp.status_code == 401

    # 3. Render image endpoint with operator credentials and unconfigured provider -> 503
    with patch("app.services.photo_card_service.ScreenshotOneClient.is_configured", return_value=False):
        render_resp = await client.get(
            f"/api/v1/photo-cards/articles/{art.id}/render",
            headers={"Authorization": "Bearer test-operator-token"},
        )
        assert render_resp.status_code == 503
        err_body = render_resp.json()
        err_text = (err_body.get("message") or err_body.get("detail") or "").lower()
        assert "not configured" in err_text
