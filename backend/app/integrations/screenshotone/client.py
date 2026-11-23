"""ScreenshotOne API client for server-side HTML-to-image rendering.

Official ScreenshotOne API documentation: https://screenshotone.com/docs/options/
Provides secure, high-fidelity 1080x1080 rendering for MetroScope editorial photo cards
with dual-key round-robin rotation, persistent state, and automatic quota/auth failover.
"""

import hashlib
import hmac
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.integrations.screenshotone.key_manager import ScreenshotOneKeyManager
from app.social.base import mask_secret, safe_parse_json_response


class ScreenshotOneError(Exception):
    """Base exception for ScreenshotOne rendering operations."""
    pass


class ScreenshotOneConfigurationError(ScreenshotOneError):
    """Raised when required ScreenshotOne credentials are not configured."""
    pass


class ScreenshotOneTimeoutError(ScreenshotOneError):
    """Raised when a rendering request times out."""
    pass


class ScreenshotOneAPIError(ScreenshotOneError):
    """Raised when the ScreenshotOne API returns an error response (4xx/5xx)."""

    def __init__(self, message: str, status_code: int = 500, response_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


def sign_query_params(params: Dict[str, Any], secret_key: str) -> str:
    """Computes HMAC-SHA256 signature for ScreenshotOne signed requests.
    
    Parameters are sorted alphabetically by key and encoded into a query string
    before hashing with the secret key.
    """
    filtered = {k: v for k, v in params.items() if v is not None and k != "signature"}
    sorted_items = sorted(filtered.items())
    query_str = urlencode(sorted_items)
    signature = hmac.new(
        secret_key.encode("utf-8"),
        query_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return signature


_USE_SETTINGS = object()


class ScreenshotOneClient:
    """HTTP client for rendering dynamic HTML via ScreenshotOne API.
    
    Guarantees:
    - Never logs or exposes raw access_key or secret_key.
    - Strictly uses ScreenshotOne API (no local headless browsers).
    - Enforces 1080x1080 canvas sizing, web font synchronization, and element cropping.
    - Deterministic round-robin rotation between Key 1 and Key 2 slots.
    - Automatic failover on HTTP 429 quota exhaustion and HTTP 401/403 authorization failures.
    - Graceful fallback to single-key mode if only one key is configured.
    """

    def __init__(
        self,
        access_key: Any = _USE_SETTINGS,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        image_format: Optional[str] = None,
        image_quality: Optional[int] = None,
        key_manager: Optional[ScreenshotOneKeyManager] = None,
    ):
        if key_manager is not None:
            self.key_manager = key_manager
        elif access_key is not _USE_SETTINGS:
            # Explicit single-key initialization
            clean_key = access_key.strip() if (access_key and isinstance(access_key, str)) else None
            self.key_manager = ScreenshotOneKeyManager(
                key_1=clean_key or "",
                key_2="",
                legacy_key="",
            )
        else:
            # Default initialization from environment/settings
            self.key_manager = ScreenshotOneKeyManager()

        raw_secret = secret_key if secret_key is not None else settings.SCREENSHOTONE_SECRET_KEY
        self.secret_key = raw_secret.strip() if raw_secret else None

        self.base_url = (base_url or settings.SCREENSHOTONE_BASE_URL).rstrip("/")
        self.timeout = timeout_seconds if timeout_seconds is not None else settings.SCREENSHOTONE_TIMEOUT_SECONDS
        self.image_format = (image_format or settings.SCREENSHOTONE_IMAGE_FORMAT or "jpeg").lower()
        self.image_quality = image_quality if image_quality is not None else settings.SCREENSHOTONE_IMAGE_QUALITY

    @property
    def access_key(self) -> Optional[str]:
        """Backward-compatible property returning the primary configured access key."""
        if self.key_manager._states:
            return self.key_manager._states[0].key
        return None

    def is_configured(self) -> bool:
        """Checks if at least one valid, non-empty access_key is available."""
        return self.key_manager.is_configured()

    def get_rotation_status(self) -> Dict[str, Any]:
        """Returns sanitized status of managed key slots. Never exposes raw keys."""
        return self.key_manager.get_status()

    async def render_html(
        self,
        html: str,
        viewport_width: int = 1080,
        viewport_height: int = 1080,
        device_scale_factor: int = 1,
        image_format: Optional[str] = None,
        image_quality: Optional[int] = None,
        selector: Optional[str] = ".card",
        wait_until: str = "networkidle0",
        block_ads: bool = True,
        block_trackers: bool = True,
        block_cookie_banners: bool = True,
        cache: bool = True,
    ) -> bytes:
        """Renders raw HTML into image bytes (JPEG/PNG) via ScreenshotOne API.
        
        Dispatches request using deterministic round-robin key selection.
        If the primary key encounters 429 quota exhaustion or 401/403 authorization
        failure, automatically fails over to the alternative key slot.
        """
        if not self.is_configured():
            raise ScreenshotOneConfigurationError(
                "ScreenshotOne access_key is not configured in environment or settings."
            )

        if not html or not html.strip():
            raise ValueError("HTML content to render cannot be empty.")

        fmt = (image_format or self.image_format or "jpeg").lower()
        quality = image_quality if image_quality is not None else self.image_quality

        # Select first eligible key in round-robin rotation
        try:
            slot_id, active_key = self.key_manager.get_next_key()
        except RuntimeError as err:
            raise ScreenshotOneAPIError(
                f"ScreenshotOne key rotation error: {err}", status_code=503
            ) from err

        return await self._dispatch_with_failover(
            html=html,
            initial_slot_id=slot_id,
            initial_key=active_key,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            device_scale_factor=device_scale_factor,
            fmt=fmt,
            quality=quality,
            selector=selector,
            wait_until=wait_until,
            block_ads=block_ads,
            block_trackers=block_trackers,
            block_cookie_banners=block_cookie_banners,
            cache=cache,
        )

    async def _dispatch_with_failover(
        self,
        html: str,
        initial_slot_id: int,
        initial_key: str,
        viewport_width: int,
        viewport_height: int,
        device_scale_factor: int,
        fmt: str,
        quality: Optional[int],
        selector: Optional[str],
        wait_until: str,
        block_ads: bool,
        block_trackers: bool,
        block_cookie_banners: bool,
        cache: bool,
    ) -> bytes:
        """Executes render request with automatic single-failover if current key slot fails."""
        current_slot_id = initial_slot_id
        current_key = initial_key
        attempted_slots = set()

        while True:
            attempted_slots.add(current_slot_id)
            params: Dict[str, Any] = {
                "access_key": current_key,
                "viewport_width": viewport_width,
                "viewport_height": viewport_height,
                "device_scale_factor": device_scale_factor,
                "format": fmt,
                "block_ads": block_ads,
                "block_trackers": block_trackers,
                "block_cookie_banners": block_cookie_banners,
                "cache": cache,
            }

            if wait_until:
                params["wait_until"] = [wait_until] if isinstance(wait_until, str) else list(wait_until)

            if fmt == "jpeg" and quality:
                params["image_quality"] = quality

            if selector:
                params["selector"] = selector

            # Apply HMAC-SHA256 signature if secret_key is configured
            if self.secret_key:
                params["signature"] = sign_query_params(params, self.secret_key)

            endpoint_url = f"{self.base_url}/take"
            masked_key = mask_secret(current_key)
            logger.info(
                f"[SCREENSHOTONE] Dispatching render request: slot={current_slot_id}, "
                f"access_key='{masked_key}', viewport={viewport_width}x{viewport_height}, "
                f"format='{fmt}', quality={quality}, selector='{selector}'"
            )

            timeout = httpx.Timeout(self.timeout, connect=10.0)
            json_payload = {
                "html": html,
                **params,
            }
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        endpoint_url,
                        params=params,
                        json=json_payload,
                    )

                if response.status_code == 200:
                    self.key_manager.mark_success(current_key)
                    content_type = response.headers.get("content-type", "")
                    logger.info(
                        f"[SCREENSHOTONE] Render succeeded on slot {current_slot_id}: HTTP 200, "
                        f"bytes={len(response.content)}, content_type='{content_type}'"
                    )
                    return response.content

                # Non-200 responses: parse error
                error_data, parse_err = safe_parse_json_response(
                    response.text, response.status_code, provider="ScreenshotOne"
                )
                error_msg = None
                if error_data:
                    error_obj = error_data.get("error")
                    if isinstance(error_obj, dict):
                        error_msg = error_obj.get("message")
                    elif isinstance(error_data.get("message"), str):
                        error_msg = error_data.get("message")

                if not error_msg:
                    error_msg = parse_err or f"ScreenshotOne API failed with status {response.status_code}"

                # Handle HTTP 429 Quota Exhaustion / Rate Limit
                if response.status_code == 429:
                    self.key_manager.mark_exhausted(current_key)
                    alt = self.key_manager.get_alternative_key(current_key)
                    if alt and alt[0] not in attempted_slots:
                        logger.warning(
                            f"[SCREENSHOTONE] Key slot {current_slot_id} hit HTTP 429 quota/rate limit: {error_msg}. "
                            f"Failing over to key slot {alt[0]}..."
                        )
                        current_slot_id, current_key = alt
                        continue

                # Handle HTTP 401 / 403 Unauthorized / Forbidden
                if response.status_code in (401, 403):
                    self.key_manager.mark_invalid(current_key)
                    alt = self.key_manager.get_alternative_key(current_key)
                    if alt and alt[0] not in attempted_slots:
                        logger.warning(
                            f"[SCREENSHOTONE] Key slot {current_slot_id} hit HTTP {response.status_code} auth failure: {error_msg}. "
                            f"Failing over to key slot {alt[0]}..."
                        )
                        current_slot_id, current_key = alt
                        continue

                logger.warning(
                    f"[SCREENSHOTONE] Render failed on slot {current_slot_id} (HTTP {response.status_code}): {error_msg}"
                )
                raise ScreenshotOneAPIError(
                    message=f"ScreenshotOne API error (HTTP {response.status_code}): {error_msg}",
                    status_code=response.status_code,
                    response_data=error_data or {},
                )

            except httpx.TimeoutException as exc:
                logger.warning(
                    f"[SCREENSHOTONE] Request timed out on slot {current_slot_id} after {self.timeout}s: {exc}"
                )
                # If alternative key exists and hasn't been tried, attempt failover on timeout
                alt = self.key_manager.get_alternative_key(current_key)
                if alt and alt[0] not in attempted_slots:
                    logger.warning(
                        f"[SCREENSHOTONE] Failing over to slot {alt[0]} following timeout on slot {current_slot_id}..."
                    )
                    current_slot_id, current_key = alt
                    continue

                raise ScreenshotOneTimeoutError(
                    f"ScreenshotOne rendering request timed out after {self.timeout}s"
                ) from exc
            except (ScreenshotOneError, ValueError):
                raise
            except Exception as exc:
                logger.error(f"[SCREENSHOTONE] Unexpected network error on slot {current_slot_id}: {exc}")
                raise ScreenshotOneAPIError(
                    f"ScreenshotOne connection failed: {exc}", status_code=500
                ) from exc
