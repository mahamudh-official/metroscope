import pytest
from unittest.mock import AsyncMock, patch
import httpx
from app.integrations.gdelt.client import GDELTClient


@pytest.mark.asyncio
async def test_gdelt_client_initialization():
    client = GDELTClient(base_url="https://test.api", timeout=10.0, max_retries=2)
    assert client.base_url == "https://test.api"
    assert client.timeout == 10.0
    assert client.max_retries == 2


@pytest.mark.asyncio
async def test_gdelt_client_fetch_articles_success():
    client = GDELTClient()
    mock_payload = {
        "articles": [
            {
                "url": "https://example.com/article-1",
                "title": "US Manufacturing Index Rises",
                "seendate": "20261107T080000Z",
                "domain": "example.com",
            }
        ]
    }

    mock_response = AsyncMock()
    mock_response.text = '{"articles": [{"title": "US Manufacturing Index Rises"}]}'
    mock_response.status_code = 200
    mock_response.json = lambda: mock_payload
    mock_response.raise_for_status = lambda: None

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await client.fetch_articles(query="test", max_records=1)
        assert "articles" in result
        assert len(result["articles"]) == 1
        assert result["articles"][0]["title"] == "US Manufacturing Index Rises"


@pytest.mark.asyncio
async def test_gdelt_client_handles_empty_response():
    client = GDELTClient()

    mock_response = AsyncMock()
    mock_response.text = ""
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        result = await client.fetch_articles(query="test", max_records=1)
        assert result == {"articles": []}
