"""X (Twitter) publishing adapter utilizing the official X API v2."""

import base64
import datetime
import hashlib
import hmac
import secrets
import time
from typing import Dict, Optional
import urllib.parse
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.social.base import SocialPlatformClient, SocialPostResult, mask_secret, safe_parse_json_response
from app.social.content_formatter import validate_x_post_length


def _percent_encode(val: str) -> str:
    """Encodes a string according to RFC 3986 percent-encoding."""
    return urllib.parse.quote(str(val), safe="~-._")


def generate_oauth1_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    token: str,
    token_secret: str,
) -> str:
    """Generates an RFC 5849 OAuth 1.0a Authorization header for X API v2."""
    oauth_params = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }

    # For application/json requests to /2/tweets, body is not included in OAuth 1.0a signature
    # (only query params if any, which are none here)
    sorted_params = sorted(oauth_params.items())
    param_string = "&".join(
        f"{_percent_encode(k)}={_percent_encode(v)}" for k, v in sorted_params
    )

    base_string = f"{method.upper()}&{_percent_encode(url)}&{_percent_encode(param_string)}"
    signing_key = f"{_percent_encode(consumer_secret)}&{_percent_encode(token_secret)}"

    hashed = hmac.new(
        signing_key.encode("utf-8"), base_string.encode("utf-8"), hashlib.sha1
    )
    signature = base64.b64encode(hashed.digest()).decode("utf-8")
    oauth_params["oauth_signature"] = signature

    auth_header_parts = [
        f'{_percent_encode(k)}="{_percent_encode(v)}"'
        for k, v in sorted(oauth_params.items())
    ]
    return f"OAuth {', '.join(auth_header_parts)}"


class XClient(SocialPlatformClient):
    """Client for publishing tweets via the official X API v2 (POST /2/tweets)."""

    API_URL = "https://api.x.com/2/tweets"

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        access_token_secret: Optional[str] = None,
        bearer_token: Optional[str] = None,
        dry_run: Optional[bool] = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ):
        self.api_key = (api_key or settings.X_API_KEY or "").strip()
        self.api_secret = (api_secret or settings.X_API_SECRET or "").strip()
        self.access_token = (access_token or settings.X_ACCESS_TOKEN or "").strip()
        self.access_token_secret = (access_token_secret or settings.X_ACCESS_TOKEN_SECRET or "").strip()
        self.bearer_token = (bearer_token or settings.X_BEARER_TOKEN or "").strip()
        self.dry_run = settings.SOCIAL_DRY_RUN if dry_run is None else dry_run
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def platform_name(self) -> str:
        return "x"

    def is_configured(self) -> bool:
        """Verifies presence of required OAuth 1.0a User Context credentials."""
        return bool(
            self.api_key
            and self.api_secret
            and self.access_token
            and self.access_token_secret
        )

    async def publish(
        self,
        text: str,
        link: Optional[str] = None,
        article_id: Optional[int] = None,
    ) -> SocialPostResult:
        """Publishes post text to X via X API v2 (POST https://api.x.com/2/tweets)."""
        if not text or not text.strip():
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message="Cannot publish empty X post content",
            )

        # Character limit validation (280 characters)
        if not validate_x_post_length(text, max_chars=280):
            err = f"X post exceeds 280 character limit (length: {len(text)} chars)"
            logger.error(err)
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message=err,
            )

        # Dry-run execution
        if self.dry_run:
            simulated_id = f"dryrun-x-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}-{article_id or 0}"
            logger.info(
                f"[DRY-RUN] X publishing simulated for article #{article_id or 'N/A'}. "
                f"API Key: {mask_secret(self.api_key)}, Token: {mask_secret(self.access_token)}. "
                f"Simulated Tweet ID: {simulated_id}. Content length: {len(text)} chars."
            )
            return SocialPostResult(
                success=True,
                platform=self.platform_name,
                external_post_id=simulated_id,
                dry_run=True,
                response_data={"simulated": True, "text": text},
            )

        # Validation for live execution
        if not self.is_configured():
            err = (
                "X publishing is not configured. Missing required OAuth 1.0a credentials "
                "(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET)."
            )
            logger.error(err)
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message=err,
            )

        auth_header = generate_oauth1_header(
            method="POST",
            url=self.API_URL,
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            token=self.access_token,
            token_secret=self.access_token_secret,
        )

        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
        }
        json_payload = {"text": text}
        last_error: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        self.API_URL, headers=headers, json=json_payload
                    )

                if response.status_code == 201:
                    data, parse_err = safe_parse_json_response(
                        response.text, response.status_code, "X API"
                    )
                    if parse_err:
                        last_error = (
                            f"X API returned malformed HTTP 201 success response: {parse_err}. "
                            f"Publishing outcome is unknown; aborting retries to prevent duplicate publishing."
                        )
                        logger.error(last_error)
                        return SocialPostResult(
                            success=False,
                            platform=self.platform_name,
                            error_message=last_error,
                            dry_run=False,
                            ambiguous=True,
                        )

                    data_obj = data.get("data")
                    tweet_id = data_obj.get("id") if isinstance(data_obj, dict) else None
                    if not tweet_id or not str(tweet_id).strip():
                        last_error = (
                            f"X API HTTP 201 response missing required 'data.id' field in payload. "
                            f"Payload preview: {list(data.keys())}. "
                            f"Publishing outcome is unknown; aborting retries to prevent duplicate publishing."
                        )
                        logger.error(last_error)
                        return SocialPostResult(
                            success=False,
                            platform=self.platform_name,
                            error_message=last_error,
                            dry_run=False,
                            ambiguous=True,
                        )

                    logger.info(
                        f"Successfully published article #{article_id} to X. Tweet ID: {tweet_id}"
                    )
                    return SocialPostResult(
                        success=True,
                        platform=self.platform_name,
                        external_post_id=str(tweet_id),
                        dry_run=False,
                        response_data=data,
                    )

                # Handle X API errors
                err_json, _ = safe_parse_json_response(
                    response.text, response.status_code, "X API"
                )
                if err_json and isinstance(err_json, dict):
                    detail = err_json.get("detail") or err_json.get("title") or err_json.get("error")
                    if not detail and "errors" in err_json and isinstance(err_json["errors"], list) and err_json["errors"]:
                        detail = err_json["errors"][0].get("message")
                    last_error = f"X API error (HTTP {response.status_code}): {detail or response.text[:200]}"
                else:
                    safe_preview = response.text[:200].replace("\n", " ").replace("\r", " ").strip()
                    last_error = f"X publishing failed with HTTP {response.status_code}: {safe_preview or '[empty body]'}"

                logger.warning(
                    f"X publishing attempt {attempt}/{self.max_retries} failed: {last_error}"
                )

                # Fatal auth or client errors: do not retry
                if response.status_code in (400, 401, 403):
                    break

            except (httpx.RequestError, httpx.TimeoutException) as net_err:
                last_error = f"Network error during X publishing: {net_err}"
                logger.warning(
                    f"X publishing attempt {attempt}/{self.max_retries} failed with network error: {net_err}"
                )

        return SocialPostResult(
            success=False,
            platform=self.platform_name,
            error_message=last_error or "Unknown failure during X publication",
            dry_run=False,
        )
