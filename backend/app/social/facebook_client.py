"""Facebook Page publishing adapter utilizing the official Meta Graph API.

Implements complete Facebook Page publishing workflows:
- Feed text posts (/{page_id}/feed)
- Photo posts with binary/multipart image upload and captions (/{page_id}/photos)
- Follow-up comments associated with exact post IDs (/{post_id}/comments)
- Safe response parsing, idempotency handling, secret masking, and retry controls.
"""

import datetime
from typing import Any, Dict, Optional, Tuple
import httpx

from app.core.config import settings
from app.core.logging import logger
from app.social.base import SocialPlatformClient, SocialPostResult, mask_secret, safe_parse_json_response


class FacebookPageClient(SocialPlatformClient):
    """Client for publishing text posts, photo cards, and follow-up comments to a Facebook Page."""

    def __init__(
        self,
        page_id: Optional[str] = None,
        access_token: Optional[str] = None,
        api_version: Optional[str] = None,
        dry_run: Optional[bool] = None,
        timeout_seconds: float = 20.0,
        max_retries: int = 2,
    ):
        self.page_id = (page_id if page_id is not None else (settings.FACEBOOK_PAGE_ID or "")).strip()
        self.access_token = (access_token if access_token is not None else (settings.FACEBOOK_PAGE_ACCESS_TOKEN or "")).strip()
        self.api_version = (
            api_version
            or settings.FACEBOOK_GRAPH_API_VERSION
            or settings.FACEBOOK_API_VERSION
            or "v27.0"
        ).strip()
        self.dry_run = settings.SOCIAL_DRY_RUN if dry_run is None else dry_run
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def platform_name(self) -> str:
        return "facebook"

    def is_configured(self) -> bool:
        """Verifies presence of required Facebook Page ID and Page Access Token."""
        return bool(self.page_id and self.access_token)

    async def publish(
        self,
        text: str,
        link: Optional[str] = None,
        article_id: Optional[int] = None,
    ) -> SocialPostResult:
        """Default entrypoint preserving backward compatibility; delegates to publish_text_post."""
        return await self.publish_text_post(message=text, link=link, article_id=article_id)

    async def publish_text_post(
        self,
        message: str,
        link: Optional[str] = None,
        article_id: Optional[int] = None,
    ) -> SocialPostResult:
        """Publishes a text post with an optional canonical article link to the Facebook Page feed.
        
        Meta Graph API Endpoint: POST https://graph.facebook.com/{version}/{page_id}/feed
        """
        if not message or not message.strip():
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message="Cannot publish empty Facebook text post content",
            )

        # Dry-run execution
        if self.dry_run:
            simulated_id = f"dryrun-fb-feed-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}-{article_id or 0}"
            logger.info(
                f"[DRY-RUN] Facebook feed post simulated for article #{article_id or 'N/A'}. "
                f"Page ID: {self.page_id or '[UNSET]'}, Token: {mask_secret(self.access_token)}. "
                f"Simulated Post ID: {simulated_id}. Content length: {len(message)} chars."
            )
            return SocialPostResult(
                success=True,
                platform=self.platform_name,
                external_post_id=simulated_id,
                dry_run=True,
                response_data={"simulated": True, "message_preview": message[:120], "post_type": "text"},
            )

        if not self.is_configured():
            err = (
                "Facebook Page publishing is not configured. Missing FACEBOOK_PAGE_ID "
                "or FACEBOOK_PAGE_ACCESS_TOKEN."
            )
            logger.error(err)
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message=err,
            )

        url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/feed"
        payload = {
            "message": message,
            "access_token": self.access_token,
        }
        if link:
            payload["link"] = link

        last_error: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, data=payload)

                if response.status_code == 200:
                    data, parse_err = safe_parse_json_response(
                        response.text, response.status_code, "Facebook"
                    )
                    if parse_err:
                        last_error = (
                            f"Facebook returned malformed HTTP 200 success response: {parse_err}. "
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

                    post_id = data.get("id")
                    if not post_id or not str(post_id).strip():
                        last_error = (
                            f"Facebook HTTP 200 response missing required 'id' field in payload. "
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
                        f"Successfully published text post for article #{article_id} to Facebook Page {self.page_id}. Post ID: {post_id}"
                    )
                    return SocialPostResult(
                        success=True,
                        platform=self.platform_name,
                        external_post_id=str(post_id),
                        dry_run=False,
                        response_data=data,
                    )

                last_error, is_auth_error = self._parse_error_response(response, attempt)
                if is_auth_error:
                    break

            except (httpx.RequestError, httpx.TimeoutException) as net_err:
                last_error = f"Network error during Facebook text post: {net_err}"
                logger.warning(
                    f"Facebook feed post attempt {attempt}/{self.max_retries} failed with network error: {net_err}"
                )

        return SocialPostResult(
            success=False,
            platform=self.platform_name,
            error_message=last_error or "Unknown failure during Facebook text post publication",
            dry_run=False,
        )

    async def publish_photo_post(
        self,
        image_bytes: bytes,
        caption: str,
        filename: str = "card.jpg",
        article_id: Optional[int] = None,
    ) -> SocialPostResult:
        """Publishes a photo card to the Facebook Page with multipart upload and dynamic caption.
        
        Meta Graph API Endpoint: POST https://graph.facebook.com/{version}/{page_id}/photos
        Multipart form data:
            - source: image binary
            - caption: string
            - access_token: page token
        """
        if not image_bytes or len(image_bytes) == 0:
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message="Cannot publish empty image binary to Facebook",
            )

        if self.dry_run:
            timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
            simulated_photo_id = f"dryrun-fb-photo-{timestamp_str}-{article_id or 0}"
            simulated_post_id = f"{self.page_id or '643848822147472'}_{simulated_photo_id}"
            logger.info(
                f"[DRY-RUN] Facebook photo post simulated for article #{article_id or 'N/A'}. "
                f"Page ID: {self.page_id or '[UNSET]'}, Token: {mask_secret(self.access_token)}. "
                f"Simulated Photo ID: {simulated_photo_id}, Post ID: {simulated_post_id}. "
                f"Image size: {len(image_bytes)} bytes. Caption length: {len(caption)} chars."
            )
            return SocialPostResult(
                success=True,
                platform=self.platform_name,
                external_post_id=simulated_post_id,
                dry_run=True,
                response_data={
                    "simulated": True,
                    "id": simulated_photo_id,
                    "post_id": simulated_post_id,
                    "caption_preview": caption[:120],
                    "post_type": "photo",
                },
            )

        if not self.is_configured():
            err = (
                "Facebook Page publishing is not configured. Missing FACEBOOK_PAGE_ID "
                "or FACEBOOK_PAGE_ACCESS_TOKEN."
            )
            logger.error(err)
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message=err,
            )

        url = f"https://graph.facebook.com/{self.api_version}/{self.page_id}/photos"
        files = {
            "source": (filename, image_bytes, "image/jpeg"),
        }
        data = {
            "caption": caption or "",
            "access_token": self.access_token,
        }

        last_error: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, data=data, files=files)

                if response.status_code == 200:
                    res_data, parse_err = safe_parse_json_response(
                        response.text, response.status_code, "Facebook"
                    )
                    if parse_err:
                        last_error = (
                            f"Facebook returned malformed HTTP 200 response for photo post: {parse_err}. "
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

                    photo_id = res_data.get("id")
                    # Graph API /photos returns 'post_id' (or falls back to 'id')
                    post_id = res_data.get("post_id") or photo_id
                    if not post_id or not str(post_id).strip():
                        last_error = (
                            f"Facebook HTTP 200 photo response missing required 'id'/'post_id' field. "
                            f"Publishing outcome is unknown; aborting retries."
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
                        f"Successfully published photo post for article #{article_id} to Facebook Page {self.page_id}. "
                        f"Photo ID: {photo_id}, Post ID: {post_id}"
                    )
                    return SocialPostResult(
                        success=True,
                        platform=self.platform_name,
                        external_post_id=str(post_id),
                        dry_run=False,
                        response_data={
                            "id": str(photo_id) if photo_id else None,
                            "post_id": str(post_id),
                            "raw": res_data,
                        },
                    )

                last_error, is_auth_error = self._parse_error_response(response, attempt)
                if is_auth_error:
                    break

            except (httpx.RequestError, httpx.TimeoutException) as net_err:
                last_error = f"Network error during Facebook photo upload: {net_err}"
                logger.warning(
                    f"Facebook photo upload attempt {attempt}/{self.max_retries} failed with network error: {net_err}"
                )

        return SocialPostResult(
            success=False,
            platform=self.platform_name,
            error_message=last_error or "Unknown failure during Facebook photo post publication",
            dry_run=False,
        )

    async def publish_comment(
        self,
        post_id: str,
        message: str,
        article_id: Optional[int] = None,
    ) -> SocialPostResult:
        """Publishes a follow-up comment directly beneath a previously published Facebook post.
        
        Meta Graph API Endpoint: POST https://graph.facebook.com/{version}/{post_id}/comments
        """
        if not post_id or not str(post_id).strip():
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message="Cannot publish Facebook comment without target post_id",
            )

        if not message or not message.strip():
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message="Cannot publish empty Facebook comment content",
            )

        clean_post_id = str(post_id).strip()

        if self.dry_run:
            simulated_comment_id = f"dryrun-fb-comment-{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S')}-{article_id or 0}"
            logger.info(
                f"[DRY-RUN] Facebook follow-up comment simulated for article #{article_id or 'N/A'}. "
                f"Target Post ID: {clean_post_id}. Simulated Comment ID: {simulated_comment_id}. "
                f"Comment length: {len(message)} chars."
            )
            return SocialPostResult(
                success=True,
                platform=self.platform_name,
                external_post_id=simulated_comment_id,
                dry_run=True,
                response_data={
                    "simulated": True,
                    "target_post_id": clean_post_id,
                    "id": simulated_comment_id,
                    "message_preview": message[:120],
                },
            )

        if not self.is_configured():
            err = (
                "Facebook Page publishing is not configured. Missing FACEBOOK_PAGE_ID "
                "or FACEBOOK_PAGE_ACCESS_TOKEN."
            )
            logger.error(err)
            return SocialPostResult(
                success=False,
                platform=self.platform_name,
                error_message=err,
            )

        url = f"https://graph.facebook.com/{self.api_version}/{clean_post_id}/comments"
        payload = {
            "message": message,
            "access_token": self.access_token,
        }

        last_error: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, data=payload)

                if response.status_code == 200:
                    data, parse_err = safe_parse_json_response(
                        response.text, response.status_code, "Facebook"
                    )
                    if parse_err:
                        last_error = (
                            f"Facebook returned malformed HTTP 200 response for comment: {parse_err}. "
                            f"Outcome is unknown; aborting retries."
                        )
                        logger.error(last_error)
                        return SocialPostResult(
                            success=False,
                            platform=self.platform_name,
                            error_message=last_error,
                            dry_run=False,
                            ambiguous=True,
                        )

                    comment_id = data.get("id")
                    if not comment_id or not str(comment_id).strip():
                        last_error = (
                            f"Facebook HTTP 200 comment response missing required 'id' field in payload. "
                            f"Payload preview: {list(data.keys())}."
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
                        f"Successfully published follow-up comment on Facebook post {clean_post_id}. "
                        f"Comment ID: {comment_id}"
                    )
                    return SocialPostResult(
                        success=True,
                        platform=self.platform_name,
                        external_post_id=str(comment_id),
                        dry_run=False,
                        response_data=data,
                    )

                last_error, is_auth_error = self._parse_error_response(response, attempt)
                if is_auth_error:
                    break

            except (httpx.RequestError, httpx.TimeoutException) as net_err:
                last_error = f"Network error during Facebook comment submission: {net_err}"
                logger.warning(
                    f"Facebook comment attempt {attempt}/{self.max_retries} failed with network error: {net_err}"
                )

        return SocialPostResult(
            success=False,
            platform=self.platform_name,
            error_message=last_error or "Unknown failure during Facebook comment publication",
            dry_run=False,
        )

    def _parse_error_response(self, response: httpx.Response, attempt: int) -> Tuple[str, bool]:
        """Parses Meta Graph API error objects and determines if the error is fatal auth/permission failure."""
        error_json, _ = safe_parse_json_response(
            response.text, response.status_code, "Facebook"
        )
        is_auth_error = False
        if error_json and isinstance(error_json.get("error"), dict):
            err_obj = error_json["error"]
            fb_message = err_obj.get("message", "Unknown Meta Graph API error")
            fb_code = err_obj.get("code")
            fb_subcode = err_obj.get("error_subcode")
            last_error = f"Meta Graph API error (code={fb_code}, subcode={fb_subcode}): {fb_message}"
            if fb_code in (190, 200) or response.status_code in (400, 401, 403):
                is_auth_error = True
        else:
            safe_preview = response.text[:200].replace("\n", " ").replace("\r", " ").strip()
            last_error = f"Facebook publishing failed with HTTP {response.status_code}: {safe_preview or '[empty body]'}"
            if response.status_code in (400, 401, 403):
                is_auth_error = True

        logger.warning(
            f"Facebook request attempt {attempt}/{self.max_retries} failed: {last_error}"
        )
        return last_error, is_auth_error
