from typing import Any, Dict, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
from app.core.logging import logger


class GDELTAPIError(Exception):
    """Exception raised when GDELT API returns an error or fails."""
    pass


class GDELTClient:
    """Client for discovering news records via GDELT DOC 2.0 API.
    
    Respects GDELT usage conditions and copyright guidelines:
    Collects metadata, article titles, canonical URLs, and publication dates
    without copying or storing unauthorized full publisher texts or media.
    """

    def __init__(
        self,
        base_url: str = settings.GDELT_BASE_URL,
        timeout: float = settings.GDELT_REQUEST_TIMEOUT_SECONDS,
        max_retries: int = settings.GDELT_MAX_RETRIES,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    async def fetch_articles(
        self,
        query: str = "sourcecountry:US",
        max_records: int = 10,
        sort: str = "DateDesc",
    ) -> Dict[str, Any]:
        """Queries GDELT DOC 2.0 ArtList endpoint with retry and backoff."""
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": str(max_records),
            "format": "json",
            "sort": sort,
        }

        headers = {
            "User-Agent": "MetroScope-News-Discovery-Bot/1.0 (+https://metroscope.news)",
            "Accept": "application/json",
        }

        logger.info(f"Querying GDELT DOC 2.0 API: query='{query}' max_records={max_records}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(self.base_url, params=params, headers=headers)
                response.raise_for_status()

                # GDELT occasionally returns text/html error pages or malformed empty responses
                if not response.text or not response.text.strip():
                    logger.warning("Empty response received from GDELT DOC 2.0 API")
                    return {"articles": []}

                data = response.json()
                articles = data.get("articles", [])
                logger.info(f"Successfully retrieved {len(articles)} article records from GDELT")
                return data
            except httpx.HTTPStatusError as exc:
                logger.error(f"GDELT API HTTP error {exc.response.status_code}: {exc}")
                raise GDELTAPIError(f"GDELT HTTP status error: {exc.response.status_code}") from exc
            except httpx.RequestError as exc:
                logger.error(f"GDELT API request failure: {exc}")
                raise GDELTAPIError(f"GDELT connection error: {exc}") from exc
            except ValueError as exc:
                logger.warning(f"GDELT returned non-JSON payload: {exc}")
                return {"articles": []}
