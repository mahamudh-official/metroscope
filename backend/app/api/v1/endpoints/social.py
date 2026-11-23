"""Social Media Publishing Endpoints for Meta Graph API (Facebook) and X."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.integrations.screenshotone.client import ScreenshotOneClient
from app.models.social import SocialPost
from app.repositories.social_repository import get_social_post, list_social_posts
from app.social.base import mask_secret
from app.social.facebook_client import FacebookPageClient
from app.social.facebook_service import FacebookPublishingService

router = APIRouter()


def verify_operator_auth(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> bool:
    """Verifies administrative operator authorization for social endpoints.
    
    Accepts:
    - Authorization: Bearer <SECRET_KEY>
    - X-API-Key: <SECRET_KEY>
    - In test/dev environment: 'test-operator-token'
    """
    token = None
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]
    elif x_api_key:
        token = x_api_key.strip()

    valid_tokens = set()
    is_prod = settings.ENVIRONMENT.lower() == "production"
    WEAK_SECRETS = {
        "metroscope_secret_key_default_salt",
        "secret",
        "changeme",
        "admin",
        "password",
        "123456",
        "test-operator-token",
    }

    if settings.SECRET_KEY:
        if is_prod:
            if settings.SECRET_KEY.lower() not in WEAK_SECRETS and len(settings.SECRET_KEY) >= 16:
                valid_tokens.add(settings.SECRET_KEY)
        else:
            valid_tokens.add(settings.SECRET_KEY)

    if getattr(settings, "OPERATOR_API_KEY", None):
        if is_prod:
            if settings.OPERATOR_API_KEY.lower() not in WEAK_SECRETS and len(settings.OPERATOR_API_KEY) >= 16:
                valid_tokens.add(settings.OPERATOR_API_KEY)
        else:
            valid_tokens.add(settings.OPERATOR_API_KEY)

    if settings.ENVIRONMENT in ("test", "testing", "development"):
        valid_tokens.add("test-operator-token")

    if not token or token not in valid_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing operator authorization credentials",
        )
    return True


def get_facebook_service() -> FacebookPublishingService:
    """Dependency providing FacebookPublishingService."""
    return FacebookPublishingService()


@router.get(
    "/facebook/status",
    summary="Facebook Page Publishing Status",
    description="Returns sanitized configuration, Graph API version, and ScreenshotOne dual-key rotation status. Requires operator authorization.",
    dependencies=[Depends(verify_operator_auth)],
)
async def get_facebook_status() -> Dict[str, Any]:
    fb_client = FacebookPageClient()
    s1_client = ScreenshotOneClient()

    return {
        "facebook_enabled": settings.FACEBOOK_ENABLED,
        "facebook_configured": fb_client.is_configured(),
        "page_id": settings.FACEBOOK_PAGE_ID or "[UNSET]",
        "masked_access_token": mask_secret(settings.FACEBOOK_PAGE_ACCESS_TOKEN),
        "graph_api_version": settings.FACEBOOK_GRAPH_API_VERSION or settings.FACEBOOK_API_VERSION,
        "default_post_type": settings.FACEBOOK_DEFAULT_POST_TYPE,
        "post_caption_enabled": settings.FACEBOOK_POST_CAPTION_ENABLED,
        "followup_comment_enabled": settings.FACEBOOK_FOLLOWUP_COMMENT_ENABLED,
        "auto_publish": settings.FACEBOOK_AUTO_PUBLISH,
        "dry_run": settings.SOCIAL_DRY_RUN,
        "screenshotone": s1_client.get_rotation_status(),
    }


@router.post(
    "/facebook/preview/{article_id}",
    summary="Preview Facebook Post Payload",
    description="Generates the exact photo caption, feed message, and follow-up comment without making API calls.",
)
async def preview_facebook_post(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    service: FacebookPublishingService = Depends(get_facebook_service),
    authorized: bool = Depends(verify_operator_auth),
) -> Dict[str, Any]:
    try:
        return await service.preview_payload(db=db, article_id=article_id)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )


@router.post(
    "/facebook/publish/{article_id}",
    summary="Publish Article to Facebook Page",
    description="Executes publication (photo card or text) and optional follow-up comment.",
)
async def publish_to_facebook(
    article_id: int,
    post_type: Optional[str] = Query(None, description="Post type: 'photo' or 'text'"),
    include_comment: Optional[bool] = Query(None, description="Whether to publish follow-up comment"),
    force: bool = Query(False, description="Force republish even if already published"),
    db: AsyncSession = Depends(get_db),
    service: FacebookPublishingService = Depends(get_facebook_service),
    authorized: bool = Depends(verify_operator_auth),
) -> Dict[str, Any]:
    result = await service.publish_article(
        db=db,
        article_id=article_id,
        post_type=post_type,
        include_comment=include_comment,
        force=force,
    )

    if not result.success and result.status == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.error_message or "Facebook publication failed",
        )
    if not result.success and result.status == "REJECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error_message or "Article is not eligible for publication",
        )

    return result.to_dict()


@router.get(
    "/facebook/posts/{article_id}",
    summary="Get Facebook Post Record for Article",
    description="Retrieves publication status, external post ID, photo ID, comment ID, and error messages.",
)
async def get_article_facebook_post(
    article_id: int,
    db: AsyncSession = Depends(get_db),
    authorized: bool = Depends(verify_operator_auth),
) -> Dict[str, Any]:
    post = await get_social_post(db, article_id=article_id, platform="facebook")
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Facebook post tracking record found for article #{article_id}",
        )

    return {
        "id": post.id,
        "article_id": post.article_id,
        "platform": post.platform,
        "status": post.status,
        "post_type": post.post_type,
        "external_post_id": post.external_post_id,
        "external_photo_id": post.external_photo_id,
        "external_comment_id": post.external_comment_id,
        "content": post.content,
        "comment_content": post.comment_content,
        "attempt_count": post.attempt_count,
        "last_error": post.last_error,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
    }


@router.post(
    "/facebook/retry/{social_post_id}",
    summary="Retry Failed or Partially Published Facebook Post",
    description="Retries a failed post or dispatches a missing follow-up comment for PARTIALLY_PUBLISHED posts.",
)
async def retry_facebook_post(
    social_post_id: int,
    db: AsyncSession = Depends(get_db),
    service: FacebookPublishingService = Depends(get_facebook_service),
    authorized: bool = Depends(verify_operator_auth),
) -> Dict[str, Any]:
    try:
        result = await service.retry_post(db=db, social_post_id=social_post_id)
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.error_message or "Retry failed",
            )
        return result.to_dict()
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(val_err),
        )
