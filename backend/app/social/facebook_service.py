"""Facebook Publishing Orchestration Service.

Integrates photo card generation via ScreenshotOne (with dual-key rotation),
Meta Graph API photo and feed posting, follow-up comment association,
strict idempotency, and fine-grained database state tracking.
"""

import datetime
import json
from typing import Any, Dict, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.integrations.screenshotone.client import ScreenshotOneClient, ScreenshotOneError
from app.models.article import NewsArticle
from app.models.social import SocialPost
from app.repositories.social_repository import get_social_post
from app.services.photo_card_service import PhotoCardService
from app.social.content_formatter import (
    format_facebook_caption,
    format_facebook_first_comment,
    get_article_url,
)
from app.social.facebook_client import FacebookPageClient


class FacebookPublishingResult:
    """Structured representation of Facebook publishing outcome."""

    def __init__(
        self,
        success: bool,
        status: str,
        article_id: int,
        post_type: str,
        post_id: Optional[str] = None,
        photo_id: Optional[str] = None,
        comment_id: Optional[str] = None,
        error_message: Optional[str] = None,
        dry_run: bool = False,
        social_post_id: Optional[int] = None,
    ):
        self.success = success
        self.status = status
        self.article_id = article_id
        self.post_type = post_type
        self.post_id = post_id
        self.photo_id = photo_id
        self.comment_id = comment_id
        self.error_message = error_message
        self.dry_run = dry_run
        self.social_post_id = social_post_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "article_id": self.article_id,
            "post_type": self.post_type,
            "post_id": self.post_id,
            "photo_id": self.photo_id,
            "comment_id": self.comment_id,
            "error_message": self.error_message,
            "dry_run": self.dry_run,
            "social_post_id": self.social_post_id,
        }


class FacebookPublishingService:
    """Orchestrates dynamic photo card generation, Facebook posting, and follow-up comments."""

    def __init__(
        self,
        facebook_client: Optional[FacebookPageClient] = None,
        photo_card_service: Optional[PhotoCardService] = None,
        dry_run: Optional[bool] = None,
    ):
        self.dry_run = settings.SOCIAL_DRY_RUN if dry_run is None else dry_run
        self.facebook_client = facebook_client or FacebookPageClient(dry_run=self.dry_run)
        self.photo_card_service = photo_card_service or PhotoCardService(
            screenshot_client=ScreenshotOneClient()
        )

    def generate_caption(self, article: NewsArticle) -> str:
        """Constructs concise editorial caption for photo posts matching approved styling.

        Structure:
        [Article Title]

        Read more in the comments.
        """
        return format_facebook_caption(article)

    def generate_text_message(self, article: NewsArticle) -> str:
        """Constructs feed text message matching approved caption structure."""
        return format_facebook_caption(article)

    def generate_followup_comment(self, article: NewsArticle, base_url: Optional[str] = None) -> str:
        """Constructs dynamic first comment referencing article title and public website URL.

        Structure:
        [Article Title]
        [Website Article URL]
        """
        return format_facebook_first_comment(article, base_url=base_url)

    async def preview_payload(
        self, db: AsyncSession, article_id: int, base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates dry preview of all Facebook content and photo card markup without publishing."""
        article = await db.get(NewsArticle, article_id)
        if not article:
            raise ValueError(f"News article #{article_id} not found")

        caption = self.generate_caption(article)
        text_message = self.generate_text_message(article)
        comment_text = self.generate_followup_comment(article, base_url=base_url)
        card_html = self.photo_card_service.render_html(article, canvas_fixed=True)
        canonical_url = get_article_url(article.slug, base_url=base_url)

        return {
            "article_id": article.id,
            "article_title": article.title,
            "article_status": article.status,
            "canonical_url": canonical_url,
            "photo_caption": caption,
            "text_message": text_message,
            "followup_comment": comment_text,
            "photo_card_preview_endpoint": f"/api/v1/photo-cards/articles/{article.id}/html",
            "default_post_type": settings.FACEBOOK_DEFAULT_POST_TYPE,
            "followup_comment_enabled": settings.FACEBOOK_FOLLOWUP_COMMENT_ENABLED,
            "screenshotone_configured": self.photo_card_service.screenshot_client.is_configured(),
            "facebook_configured": self.facebook_client.is_configured(),
            "dry_run": self.dry_run,
        }

    async def publish_article(
        self,
        db: AsyncSession,
        article_id: int,
        post_type: Optional[str] = None,
        include_comment: Optional[bool] = None,
        force: bool = False,
        base_url: Optional[str] = None,
    ) -> FacebookPublishingResult:
        """Executes full Facebook publishing workflow with idempotency, photo card rendering, and comment."""
        article = await db.get(NewsArticle, article_id)
        if not article:
            return FacebookPublishingResult(
                success=False,
                status="FAILED",
                article_id=article_id,
                post_type=post_type or "photo",
                error_message=f"News article #{article_id} does not exist",
            )

        if article.status != "published":
            return FacebookPublishingResult(
                success=False,
                status="REJECTED",
                article_id=article_id,
                post_type=post_type or "photo",
                error_message=f"Article #{article_id} status is '{article.status}'. Only 'published' articles may be posted to Facebook.",
            )

        if article.quality_score is not None and article.quality_score < settings.INGESTION_MIN_QUALITY_SCORE:
            return FacebookPublishingResult(
                success=False,
                status="REJECTED",
                article_id=article_id,
                post_type=post_type or "photo",
                error_message=f"Article #{article_id} quality score ({article.quality_score}) does not meet the minimum editorial threshold ({settings.INGESTION_MIN_QUALITY_SCORE}).",
            )

        effective_post_type = (
            post_type or settings.FACEBOOK_DEFAULT_POST_TYPE or "photo"
        ).lower().strip()
        effective_comment = (
            settings.FACEBOOK_FOLLOWUP_COMMENT_ENABLED
            if include_comment is None
            else include_comment
        )

        # Idempotency check: verify existing social post
        existing_post = await get_social_post(db, article_id=article_id, platform="facebook")
        if existing_post and existing_post.status == "PUBLISHED" and not force:
            logger.info(
                f"Article #{article_id} was already published to Facebook (post_id={existing_post.external_post_id}). Skipping duplicate."
            )
            return FacebookPublishingResult(
                success=True,
                status="ALREADY_PUBLISHED",
                article_id=article_id,
                post_type=existing_post.post_type or effective_post_type,
                post_id=existing_post.external_post_id,
                photo_id=existing_post.external_photo_id,
                comment_id=existing_post.external_comment_id,
                social_post_id=existing_post.id,
                dry_run=self.dry_run,
            )

        now = datetime.datetime.now(datetime.timezone.utc)

        # Create or update SocialPost record to PROCESSING
        if not existing_post:
            social_post = SocialPost(
                article_id=article_id,
                platform="facebook",
                status="PROCESSING",
                post_type=effective_post_type,
                scheduled_at=now,
                attempt_count=1,
            )
            db.add(social_post)
        else:
            social_post = existing_post
            social_post.status = "PROCESSING"
            social_post.post_type = effective_post_type
            social_post.attempt_count += 1
            social_post.last_error = None

        await db.commit()
        await db.refresh(social_post)

        # Prepare content
        caption = self.generate_caption(article)
        text_message = self.generate_text_message(article)
        comment_text = self.generate_followup_comment(article, base_url=base_url)
        article_url = get_article_url(article.slug, base_url=base_url)

        post_id: Optional[str] = None
        photo_id: Optional[str] = None
        comment_id: Optional[str] = None

        try:
            # Step 1: Dispatch primary post (Photo or Text)
            if effective_post_type == "photo":
                # Render Photo Card (simulate in dry-run if credentials not configured)
                try:
                    if self.dry_run:
                        card_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF_DRY_RUN_PHOTO_CARD"
                    else:
                        card_bytes = await self.photo_card_service.render_image(
                            article,
                            format=settings.SCREENSHOTONE_IMAGE_FORMAT or "jpeg",
                            image_quality=settings.SCREENSHOTONE_IMAGE_QUALITY or 90,
                        )
                except Exception as render_err:
                    err_msg = f"Photo card rendering failed via ScreenshotOne: {render_err}"
                    logger.error(err_msg)
                    social_post.status = "FAILED"
                    social_post.last_error = err_msg
                    await db.commit()
                    return FacebookPublishingResult(
                        success=False,
                        status="FAILED",
                        article_id=article_id,
                        post_type=effective_post_type,
                        error_message=err_msg,
                        social_post_id=social_post.id,
                        dry_run=self.dry_run,
                    )

                # Post photo to Facebook
                photo_res = await self.facebook_client.publish_photo_post(
                    image_bytes=card_bytes,
                    caption=caption,
                    filename=f"card_{article.id}.jpg",
                    article_id=article.id,
                )

                if not photo_res.success:
                    social_post.status = "FAILED"
                    social_post.last_error = photo_res.error_message
                    await db.commit()
                    return FacebookPublishingResult(
                        success=False,
                        status="FAILED",
                        article_id=article_id,
                        post_type=effective_post_type,
                        error_message=photo_res.error_message,
                        social_post_id=social_post.id,
                        dry_run=photo_res.dry_run,
                    )

                post_id = photo_res.external_post_id
                if photo_res.response_data:
                    photo_id = str(photo_res.response_data.get("id") or "")
                social_post.content = caption

            else:
                # Text post
                text_res = await self.facebook_client.publish_text_post(
                    message=text_message,
                    link=article_url,
                    article_id=article.id,
                )

                if not text_res.success:
                    social_post.status = "FAILED"
                    social_post.last_error = text_res.error_message
                    await db.commit()
                    return FacebookPublishingResult(
                        success=False,
                        status="FAILED",
                        article_id=article_id,
                        post_type=effective_post_type,
                        error_message=text_res.error_message,
                        social_post_id=social_post.id,
                        dry_run=text_res.dry_run,
                    )

                post_id = text_res.external_post_id
                social_post.content = text_message

            # Main post succeeded; record IDs
            social_post.external_post_id = post_id
            social_post.external_photo_id = photo_id
            social_post.published_at = datetime.datetime.now(datetime.timezone.utc)

            # Step 2: Follow-up Comment (if enabled)
            if effective_comment and post_id:
                comment_res = await self.facebook_client.publish_comment(
                    post_id=post_id,
                    message=comment_text,
                    article_id=article.id,
                )

                if comment_res.success:
                    comment_id = comment_res.external_post_id
                    social_post.external_comment_id = comment_id
                    social_post.comment_content = comment_text
                    social_post.status = "PUBLISHED"
                    social_post.last_error = None
                    final_status = "PUBLISHED"
                else:
                    social_post.comment_content = comment_text
                    social_post.status = "PARTIALLY_PUBLISHED"
                    social_post.last_error = (
                        f"Post published (post_id={post_id}), but follow-up comment failed: {comment_res.error_message}"
                    )
                    final_status = "PARTIALLY_PUBLISHED"
            else:
                social_post.status = "PUBLISHED"
                social_post.last_error = None
                final_status = "PUBLISHED"

            await db.commit()
            await db.refresh(social_post)

            return FacebookPublishingResult(
                success=True,
                status=final_status,
                article_id=article_id,
                post_type=effective_post_type,
                post_id=post_id,
                photo_id=photo_id,
                comment_id=comment_id,
                error_message=social_post.last_error,
                social_post_id=social_post.id,
                dry_run=self.dry_run,
            )

        except Exception as exc:
            logger.exception(f"Unexpected error publishing article #{article_id} to Facebook: {exc}")
            social_post.status = "FAILED"
            social_post.last_error = f"Unexpected publishing error: {exc}"
            try:
                await db.commit()
            except Exception:
                await db.rollback()

            return FacebookPublishingResult(
                success=False,
                status="FAILED",
                article_id=article_id,
                post_type=effective_post_type,
                error_message=str(exc),
                social_post_id=social_post.id,
                dry_run=self.dry_run,
            )

    async def retry_post(self, db: AsyncSession, social_post_id: int) -> FacebookPublishingResult:
        """Retries a failed or partially published post."""
        post = await db.get(SocialPost, social_post_id)
        if not post:
            raise ValueError(f"Social post record #{social_post_id} not found")

        article = await db.get(NewsArticle, post.article_id)
        if not article:
            raise ValueError(f"Associated news article #{post.article_id} not found")

        # Case 1: Post succeeded but comment failed (PARTIALLY_PUBLISHED)
        if post.status == "PARTIALLY_PUBLISHED" and post.external_post_id and not post.external_comment_id:
            comment_text = post.comment_content or self.generate_followup_comment(article)
            logger.info(
                f"Retrying follow-up comment for social post #{social_post_id} on Facebook post {post.external_post_id}..."
            )
            comment_res = await self.facebook_client.publish_comment(
                post_id=post.external_post_id,
                message=comment_text,
                article_id=article.id,
            )
            if comment_res.success:
                post.external_comment_id = comment_res.external_post_id
                post.comment_content = comment_text
                post.status = "PUBLISHED"
                post.last_error = None
                await db.commit()
                return FacebookPublishingResult(
                    success=True,
                    status="PUBLISHED",
                    article_id=article.id,
                    post_type=post.post_type or "photo",
                    post_id=post.external_post_id,
                    photo_id=post.external_photo_id,
                    comment_id=comment_res.external_post_id,
                    social_post_id=post.id,
                    dry_run=comment_res.dry_run,
                )
            else:
                post.last_error = f"Comment retry failed: {comment_res.error_message}"
                await db.commit()
                return FacebookPublishingResult(
                    success=False,
                    status="PARTIALLY_PUBLISHED",
                    article_id=article.id,
                    post_type=post.post_type or "photo",
                    post_id=post.external_post_id,
                    photo_id=post.external_photo_id,
                    error_message=comment_res.error_message,
                    social_post_id=post.id,
                    dry_run=comment_res.dry_run,
                )

        # Case 2: Full re-publish of failed post
        return await self.publish_article(
            db=db,
            article_id=post.article_id,
            post_type=post.post_type,
            force=True,
        )
