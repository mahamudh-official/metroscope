import asyncio
import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.integrations.webz.schemas import WebzResponse


class WebzError(Exception):
    """Base exception for Webz.io integration errors."""
    pass


class WebzAuthenticationError(WebzError):
    """Raised when authentication fails (HTTP 401/403 or missing token)."""
    pass


class WebzRateLimitError(WebzError):
    """Raised when rate limits are exceeded (HTTP 429)."""
    pass


class WebzRequestError(WebzError):
    """Raised for malformed requests or unrecoverable client errors (HTTP 400)."""
    pass


class WebzBudgetExceededError(WebzError):
    """Raised when request is blocked by budget protection safeguards."""
    pass


# Confirmed comprehensive 10-category Webz.io news query covering US domestic & significant international reporting
CONFIRMED_QUERY: str = (
    '(category:"politics" OR category:"economy, business and finance" OR category:"science and technology" '
    'OR category:"health" OR category:"environment" OR category:"sport" OR category:"sports" '
    'OR category:"arts, culture and entertainment" OR category:"war, conflict and unrest") '
    'AND (country:US OR "international" OR "global" OR "world") AND language:english'
)

CATEGORY_QUERIES: Dict[str, str] = {
    "default": CONFIRMED_QUERY,
    "confirmed": CONFIRMED_QUERY,
    "all": CONFIRMED_QUERY,
    "general": CONFIRMED_QUERY,
    "business": 'category:"Economy, Business and Finance" AND language:english',
    "science": 'category:"science and technology" AND language:english',
    "technology": 'category:"science and technology" AND language:english',
}


class WebzClient:
    """Dedicated HTTPX-based API client for Webz.io News API.
    
    Provides:
    - Secure token transmission (never logged, exposed, or leaked)
    - Confirmed endpoint: https://api.webz.io/api/news
    - Confirmed query: (category:"economy, business and finance" OR category:"science and technology")
    - Confirmed parameters: sort=crawled, ts=checkpoint, format=json, size=10,
      webz_reporter=true, includeSyndicated=false, allowNewsHistory=false
    - Request parameter validation
    - Dynamic collection checkpoint with freshness window enforcement
    - Strict size limit of 10 articles per request
    - Prohibition of automatic pagination
    - Controlled, minimal retry policy (max 1 retry for transient network errors, zero for 4xx)
    - Timeout and status code handling
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        endpoint: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        raw_key = api_key if api_key is not None else settings.WEBZ_IO_API_KEY
        if raw_key and "&" in raw_key:
            raw_key = raw_key.split("&")[0].strip()
        self.api_key = raw_key.strip() if raw_key else None
        self.base_url = (base_url or settings.WEBZ_IO_BASE_URL).rstrip("/")
        self.endpoint = endpoint or settings.WEBZ_IO_ENDPOINT
        if not self.endpoint.startswith("/"):
            self.endpoint = f"/{self.endpoint}"
        self.timeout = timeout_seconds or settings.WEBZ_IO_REQUEST_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.WEBZ_IO_MAX_RETRIES

    def is_configured(self) -> bool:
        """Checks if a valid, non-empty API token is present."""
        return bool(self.api_key and self.api_key.strip())

    def build_query(
        self,
        category: Optional[str] = None,
        query_override: Optional[str] = None,
        checkpoint_ts_ms: Optional[int] = None,
        freshness_hours: int = 24,
    ) -> tuple[str, int]:
        """Constructs a compliant Webz.io query and dynamic collection checkpoint timestamp.
        
        Enforces:
        - Confirmed query: (category:"economy, business and finance" OR category:"science and technology")
        - Dynamic checkpoint: ts in Unix milliseconds (defaults to checkpoint or recent window)
        - Strictly avoids fetching historical articles (max 48 hours, allowNewsHistory=false)
        
        Returns (query_string, ts_in_milliseconds).
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        now_ms = int(now.timestamp() * 1000)

        # 1. Determine query string
        if query_override and query_override.strip():
            query_str = query_override.strip()
        elif category and category.lower() in CATEGORY_QUERIES and category.lower() not in ("default", "confirmed"):
            query_str = CATEGORY_QUERIES[category.lower()]
        else:
            query_str = getattr(settings, "WEBZ_IO_QUERY", CONFIRMED_QUERY)

        # 2. Determine dynamic checkpoint timestamp
        if checkpoint_ts_ms is not None and checkpoint_ts_ms > 0:
            # Enforce max 48h age to prevent accidental historical requests
            max_age_ms = 48 * 3600 * 1000
            if now_ms - checkpoint_ts_ms > max_age_ms:
                ts_ms = now_ms - max_age_ms
            else:
                ts_ms = checkpoint_ts_ms
        else:
            capped_hours = max(1, min(freshness_hours, 48))
            since_dt = now - datetime.timedelta(hours=capped_hours)
            ts_ms = int(since_dt.timestamp() * 1000)

        return query_str, ts_ms

    async def fetch_news_articles(
        self,
        query: Optional[str] = None,
        checkpoint_ts_ms: Optional[int] = None,
        freshness_hours: int = 24,
        size: int = 10,
    ) -> WebzResponse:
        """Executes a single, non-paginated API call with confirmed parameters to retrieve up to 10 articles.
        
        Confirmed parameters:
        - q=(category:"economy, business and finance" OR category:"science and technology")
        - sort=crawled
        - ts=dynamic checkpoint
        - format=json
        - size=10
        - webz_reporter=true
        - includeSyndicated=false
        - allowNewsHistory=false
        """
        if not self.is_configured():
            raise WebzAuthenticationError("Webz.io API token is not configured in environment.")

        # Hard ceiling on batch size to prevent budget overrun
        bounded_size = min(max(1, size), 10)
        query_str, ts_ms = self.build_query(
            query_override=query,
            checkpoint_ts_ms=checkpoint_ts_ms,
            freshness_hours=freshness_hours,
        )

        url = f"{self.base_url}{self.endpoint}"
        params: Dict[str, Any] = {
            "token": self.api_key,
            "q": query_str,
            "sort": "crawled",
            "ts": ts_ms,
            "format": "json",
            "size": bounded_size,
            "webz_reporter": "true",
            "includeSyndicated": "false",
            "allowNewsHistory": "false",
        }

        headers = {
            "User-Agent": "MetroScope-NewsEngine/1.0 (+https://themetroscope.com)",
            "Accept": "application/json",
        }

        timeout = httpx.Timeout(self.timeout, connect=self.timeout)
        attempts = 0
        max_attempts = 1 + max(0, min(self.max_retries, 1))  # at most 2 attempts total

        while attempts < max_attempts:
            attempts += 1
            try:
                # Security: never log the API token
                logger.info(
                    f"Executing Webz.io request (attempt {attempts}/{max_attempts}) "
                    f"endpoint='{self.endpoint}', query='{query_str}', size={bounded_size}, ts={ts_ms}..."
                )
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(url, params=params, headers=headers)

                status_code = response.status_code

                if status_code == 200:
                    payload = response.json()
                    parsed = WebzResponse.model_validate(payload)
                    logger.info(
                        f"Webz.io API 200 OK: returned {len(parsed.posts)} posts, "
                        f"requests_left={parsed.requests_left}, total_results={parsed.total_results}"
                    )
                    return parsed

                elif status_code in (401, 403):
                    msg = f"Webz.io authentication failed with HTTP {status_code}"
                    logger.error(msg)
                    raise WebzAuthenticationError(msg)

                elif status_code == 429:
                    msg = "Webz.io rate limit exceeded (HTTP 429). Halting collection cycle."
                    logger.warning(msg)
                    # Never retry on 429 rate limit
                    raise WebzRateLimitError(msg)

                elif 400 <= status_code < 500:
                    msg = f"Webz.io client error (HTTP {status_code}): {response.text[:200]}"
                    logger.error(msg)
                    raise WebzRequestError(msg)

                else:
                    # 5xx Server Error: retry if attempts remain
                    msg = f"Webz.io upstream server error (HTTP {status_code})"
                    logger.warning(f"{msg} on attempt {attempts}/{max_attempts}")
                    if attempts < max_attempts:
                        await asyncio.sleep(1.0)
                        continue
                    raise WebzError(msg)

            except (httpx.TimeoutException, httpx.NetworkError) as net_exc:
                logger.warning(f"Webz.io network failure on attempt {attempts}/{max_attempts}: {repr(net_exc)}")
                if attempts < max_attempts:
                    await asyncio.sleep(1.0)
                    continue
                raise WebzError(f"Webz.io connection failed after {attempts} attempts: {repr(net_exc)}")

        raise WebzError(f"Webz.io request failed after {attempts} attempts.")

    async def fetch_category_articles(
        self,
        category: str = "business",
        freshness_hours: int = 24,
        size: int = 10,
    ) -> WebzResponse:
        """Backward-compatible wrapper delegating to fetch_news_articles."""
        query_override = CATEGORY_QUERIES.get(category.lower())
        return await self.fetch_news_articles(
            query=query_override,
            freshness_hours=freshness_hours,
            size=size,
        )
