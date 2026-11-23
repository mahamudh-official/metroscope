import pytest
from unittest.mock import AsyncMock, patch
import httpx
from app.social.base import mask_secret, safe_parse_json_response
from app.social.facebook_client import FacebookPageClient
from app.social.x_client import XClient, generate_oauth1_header


def test_mask_secret():
    assert mask_secret(None) == "[NOT SET]"
    assert mask_secret("") == "[NOT SET]"
    assert mask_secret("short") == "***"
    assert mask_secret("EAABb1234567890xyz") == "EAAB...0xyz"


# --- Facebook Page Client Tests ---

@pytest.mark.asyncio
async def test_facebook_client_dry_run():
    client = FacebookPageClient(
        page_id="123456789",
        access_token="fake_token_abc123",
        dry_run=True,
    )
    assert client.is_configured() is True
    result = await client.publish(
        text="Sample test news headline",
        link="https://metroscope.news/article/sample-headline",
        article_id=55,
    )
    assert result.success is True
    assert result.dry_run is True
    assert result.platform == "facebook"
    assert "dryrun-fb-" in result.external_post_id
    assert result.error_message is None


@pytest.mark.asyncio
async def test_facebook_client_missing_credentials_live():
    client = FacebookPageClient(
        page_id="",
        access_token="",
        dry_run=False,
    )
    assert client.is_configured() is False
    result = await client.publish(text="Hello live world", article_id=56)
    assert result.success is False
    assert "not configured" in result.error_message


@pytest.mark.asyncio
async def test_facebook_client_empty_text():
    client = FacebookPageClient(page_id="123", access_token="abc", dry_run=True)
    result = await client.publish(text="")
    assert result.success is False
    assert "empty" in result.error_message


@pytest.mark.asyncio
async def test_facebook_client_live_success_mocked():
    client = FacebookPageClient(
        page_id="123456789",
        access_token="valid_page_token",
        dry_run=False,
    )

    mock_resp = httpx.Response(
        status_code=200,
        json={"id": "123456789_9876543210"},
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(
            text="Breaking Tech News",
            link="https://metroscope.news/article/tech-news",
            article_id=1,
        )

    assert result.success is True
    assert result.external_post_id == "123456789_9876543210"
    assert result.dry_run is False


@pytest.mark.asyncio
async def test_facebook_client_live_auth_error_mocked():
    client = FacebookPageClient(
        page_id="123456789",
        access_token="expired_token",
        dry_run=False,
    )

    mock_resp = httpx.Response(
        status_code=400,
        json={"error": {"message": "Session has expired", "type": "OAuthException", "code": 190}},
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Test", article_id=2)

    assert result.success is False
    assert "code=190" in result.error_message
    assert "Session has expired" in result.error_message


# --- X (Twitter) Client Tests ---

def test_x_client_oauth1_header_generation():
    header = generate_oauth1_header(
        method="POST",
        url="https://api.x.com/2/tweets",
        consumer_key="test_api_key",
        consumer_secret="test_api_secret",
        token="test_access_token",
        token_secret="test_access_token_secret",
    )
    assert header.startswith("OAuth ")
    assert 'oauth_consumer_key="test_api_key"' in header
    assert 'oauth_signature_method="HMAC-SHA1"' in header
    assert 'oauth_signature="' in header


@pytest.mark.asyncio
async def test_x_client_dry_run():
    client = XClient(
        api_key="key123",
        api_secret="sec456",
        access_token="tok789",
        access_token_secret="toksec000",
        dry_run=True,
    )
    assert client.is_configured() is True
    result = await client.publish(
        text="Concise breaking update on X https://metroscope.news/article/update",
        article_id=77,
    )
    assert result.success is True
    assert result.dry_run is True
    assert result.platform == "x"
    assert "dryrun-x-" in result.external_post_id


@pytest.mark.asyncio
async def test_x_client_character_limit_rejection():
    client = XClient(dry_run=True)
    over_limit_text = "A" * 281
    result = await client.publish(text=over_limit_text, article_id=78)
    assert result.success is False
    assert "exceeds 280 character limit" in result.error_message


@pytest.mark.asyncio
async def test_x_client_missing_credentials_live():
    client = XClient(
        api_key="",
        api_secret="",
        access_token="",
        access_token_secret="",
        dry_run=False,
    )
    assert client.is_configured() is False
    result = await client.publish(text="Valid tweet under limit", article_id=79)
    assert result.success is False
    assert "not configured" in result.error_message


@pytest.mark.asyncio
async def test_x_client_live_success_mocked():
    client = XClient(
        api_key="key",
        api_secret="secret",
        access_token="token",
        access_token_secret="token_secret",
        dry_run=False,
    )

    mock_resp = httpx.Response(
        status_code=201,
        json={"data": {"id": "1892837465928374650", "text": "Headline"}},
        request=httpx.Request("POST", "https://api.x.com/2/tweets"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Live Tweet Update", article_id=3)

    assert result.success is True
    assert result.external_post_id == "1892837465928374650"


@pytest.mark.asyncio
async def test_x_client_live_rate_limit_error_mocked():
    client = XClient(
        api_key="key",
        api_secret="secret",
        access_token="token",
        access_token_secret="token_secret",
        dry_run=False,
    )

    mock_resp = httpx.Response(
        status_code=429,
        json={"title": "Too Many Requests", "detail": "Rate limit exceeded on tweets endpoint"},
        request=httpx.Request("POST", "https://api.x.com/2/tweets"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Live Tweet Rate Limit", article_id=4)

    assert result.success is False
    assert "HTTP 429" in result.error_message
    assert "Rate limit exceeded" in result.error_message


# --- M-01 Safe JSON Parsing Tests ---

def test_safe_parse_json_response_helper():
    # 1. Empty body
    data, err = safe_parse_json_response("", 200, "TestProvider")
    assert data is None
    assert "empty response body" in err

    # 2. Malformed JSON
    data, err = safe_parse_json_response("<HTML>Gateway Timeout</HTML>", 504, "TestProvider")
    assert data is None
    assert "malformed JSON" in err
    assert "HTTP 504" in err

    # 3. Non-object JSON (list or integer)
    data, err = safe_parse_json_response("[1, 2, 3]", 200, "TestProvider")
    assert data is None
    assert "non-object" in err

    # 4. Valid object JSON
    data, err = safe_parse_json_response('{"id": "12345", "status": "ok"}', 200, "TestProvider")
    assert err is None
    assert data == {"id": "12345", "status": "ok"}


@pytest.mark.asyncio
async def test_facebook_client_http_200_invalid_json():
    client = FacebookPageClient(page_id="123", access_token="tok", dry_run=False)
    mock_resp = httpx.Response(
        status_code=200,
        text="<HTML>Service degradation - upstream proxy</HTML>",
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=201)

    assert result.success is False
    assert "malformed HTTP 200 success response" in result.error_message
    assert "outcome is unknown" in result.error_message.lower()
    # Should not attempt multiple retries on ambiguous success
    assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_facebook_client_http_200_empty_response():
    client = FacebookPageClient(page_id="123", access_token="tok", dry_run=False)
    mock_resp = httpx.Response(
        status_code=200,
        text="",
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=202)

    assert result.success is False
    assert "empty response body" in result.error_message


@pytest.mark.asyncio
async def test_facebook_client_http_200_missing_id():
    client = FacebookPageClient(page_id="123", access_token="tok", dry_run=False)
    mock_resp = httpx.Response(
        status_code=200,
        json={"status": "acknowledged"},  # Missing 'id'
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=203)

    assert result.success is False
    assert "missing required 'id' field" in result.error_message
    assert "outcome is unknown" in result.error_message.lower()


@pytest.mark.asyncio
async def test_facebook_client_error_with_malformed_json():
    client = FacebookPageClient(page_id="123", access_token="tok", dry_run=False, max_retries=1)
    mock_resp = httpx.Response(
        status_code=500,
        text="Internal Server Error: Backend unreachable",
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=204)

    assert result.success is False
    assert "HTTP 500" in result.error_message
    assert "Internal Server Error" in result.error_message


@pytest.mark.asyncio
async def test_x_client_http_201_invalid_json():
    client = XClient(api_key="k", api_secret="s", access_token="t", access_token_secret="ts", dry_run=False)
    mock_resp = httpx.Response(
        status_code=201,
        text="<html>Created but malformed json from proxy</html>",
        request=httpx.Request("POST", "https://api.x.com/2/tweets"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=205)

    assert result.success is False
    assert "malformed HTTP 201 success response" in result.error_message
    assert "outcome is unknown" in result.error_message.lower()
    assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_x_client_http_201_empty_response():
    client = XClient(api_key="k", api_secret="s", access_token="t", access_token_secret="ts", dry_run=False)
    mock_resp = httpx.Response(
        status_code=201,
        text="   ",
        request=httpx.Request("POST", "https://api.x.com/2/tweets"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=206)

    assert result.success is False
    assert "empty response body" in result.error_message


@pytest.mark.asyncio
async def test_x_client_http_201_missing_id():
    client = XClient(api_key="k", api_secret="s", access_token="t", access_token_secret="ts", dry_run=False)
    mock_resp = httpx.Response(
        status_code=201,
        json={"data": {}},  # Missing 'data.id'
        request=httpx.Request("POST", "https://api.x.com/2/tweets"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=207)

    assert result.success is False
    assert "missing required 'data.id' field" in result.error_message
    assert "outcome is unknown" in result.error_message.lower()


@pytest.mark.asyncio
async def test_x_client_error_with_malformed_json():
    client = XClient(api_key="k", api_secret="s", access_token="t", access_token_secret="ts", dry_run=False, max_retries=1)
    mock_resp = httpx.Response(
        status_code=502,
        text="Bad Gateway: upstream connect error",
        request=httpx.Request("POST", "https://api.x.com/2/tweets"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=208)

    assert result.success is False
    assert "HTTP 502" in result.error_message
    assert "Bad Gateway" in result.error_message


@pytest.mark.asyncio
async def test_secret_masking_during_parsing_failures():
    secret_token = "SECRET_TOKEN_XYZ_1234567890_VERY_SENSITIVE"
    client = FacebookPageClient(page_id="123", access_token=secret_token, dry_run=False)
    mock_resp = httpx.Response(
        status_code=500,
        text="Error 500 without json",
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish(text="Headline", article_id=209)

    assert secret_token not in (result.error_message or "")

