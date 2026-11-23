"""Photo Card API Endpoints for development preview and asset generation."""

from collections import defaultdict
import datetime
import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.social import verify_operator_auth
from app.core.config import settings
from app.db.session import get_db
from app.integrations.screenshotone.client import (
    ScreenshotOneClient,
    ScreenshotOneConfigurationError,
    ScreenshotOneError,
)
from app.models.article import NewsArticle
from app.services.photo_card_service import PhotoCardData, PhotoCardService

router = APIRouter()

# Rate limiting for live ScreenshotOne rendering: max 30 requests per minute
_render_rate_limit_records = defaultdict(list)
PHOTO_CARD_RENDER_RATE_LIMIT = 30
PHOTO_CARD_WINDOW_SECONDS = 60
TRUSTED_PROXY_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def get_trusted_client_ip(request: Request) -> str:
    """Extracts client IP, trusting proxy headers (X-Real-IP) ONLY when forwarded by a trusted proxy."""
    remote_host = request.client.host if request.client else "unknown"
    # Only trust X-Real-IP if the direct TCP peer is a trusted local reverse proxy or Docker network IP
    if remote_host in TRUSTED_PROXY_HOSTS or remote_host.startswith("172.") or remote_host.startswith("10."):
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return remote_host


def check_render_rate_limit(client_ip: str) -> bool:
    now = time.time()
    cutoff = now - PHOTO_CARD_WINDOW_SECONDS
    timestamps = [t for t in _render_rate_limit_records[client_ip] if t > cutoff]
    if len(timestamps) >= PHOTO_CARD_RENDER_RATE_LIMIT:
        _render_rate_limit_records[client_ip] = timestamps
        return False
    timestamps.append(now)
    _render_rate_limit_records[client_ip] = timestamps
    return True


def get_photo_card_service() -> PhotoCardService:
    """Dependency providing a PhotoCardService instance."""
    return PhotoCardService(screenshot_client=ScreenshotOneClient())


@router.get(
    "/preview",
    response_class=HTMLResponse,
    summary="Photo Card HTML Preview",
    description="Renders dynamic HTML for the editorial photo card with variable inputs or realistic defaults.",
)
async def preview_photo_card(
    headline: Optional[str] = Query(None, description="Article headline"),
    category: Optional[str] = Query(None, description="Category name or slug"),
    image_url: Optional[str] = Query(None, description="Hero photograph HTTPS URL"),
    published_at: Optional[str] = Query(None, description="Publication timestamp or formatted date"),
    website_url: Optional[str] = Query(None, description="Website watermark domain"),
    canvas_fixed: bool = Query(
        False, description="If True, renders flush 1080x1080 canvas for screenshot capture; if False, renders responsive centered card"
    ),
    service: PhotoCardService = Depends(get_photo_card_service),
) -> HTMLResponse:
    default_headline = "AI and robotics are reshaping global industry"
    default_image = "https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1600&q=88"
    default_category = "Technology"

    data = PhotoCardData(
        headline=headline or default_headline,
        category=category or default_category,
        published_at=published_at,
        image_url=image_url if image_url is not None else default_image,
        website_url=website_url or settings.SITE_URL,
    )

    rendered_html = service.render_html(data, canvas_fixed=canvas_fixed)
    return HTMLResponse(content=rendered_html, status_code=status.HTTP_200_OK)


@router.get(
    "/articles/{article_id}/html",
    response_class=HTMLResponse,
    summary="Article Photo Card HTML",
    description="Renders the dynamic photo card HTML for a specific database article.",
)
async def get_article_photo_card_html(
    article_id: int,
    canvas_fixed: bool = Query(
        False, description="If True, renders flush 1080x1080 canvas for screenshot capture"
    ),
    db: AsyncSession = Depends(get_db),
    service: PhotoCardService = Depends(get_photo_card_service),
) -> HTMLResponse:
    article = await db.get(NewsArticle, article_id)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"News article #{article_id} not found",
        )

    rendered_html = service.render_html(article, canvas_fixed=canvas_fixed)
    return HTMLResponse(content=rendered_html, status_code=status.HTTP_200_OK)


@router.get(
    "/articles/{article_id}/render",
    summary="Render Article Photo Card Image",
    description="Renders a 1080x1080 image for an article using ScreenshotOne API. Requires operator authentication.",
    dependencies=[Depends(verify_operator_auth)],
    responses={
        200: {"content": {"image/jpeg": {}, "image/png": {}}},
        401: {"description": "Operator authorization required"},
        404: {"description": "Article not found"},
        429: {"description": "Rate limit exceeded"},
        503: {"description": "ScreenshotOne credentials not configured or provider unavailable"},
    },
)
async def render_article_photo_card_image(
    article_id: int,
    request: Request,
    image_format: Optional[str] = Query(None, description="Image format: 'jpeg' or 'png'"),
    image_quality: Optional[int] = Query(None, ge=1, le=100, description="Quality for JPEG (1-100)"),
    db: AsyncSession = Depends(get_db),
    service: PhotoCardService = Depends(get_photo_card_service),
    is_operator: bool = Depends(verify_operator_auth),
) -> Response:
    client_ip = get_trusted_client_ip(request)
    if not check_render_rate_limit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Photo card rendering rate limit exceeded. Please try again later.",
        )

    article = await db.get(NewsArticle, article_id)
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"News article #{article_id} not found",
        )

    try:
        fmt = (image_format or settings.SCREENSHOTONE_IMAGE_FORMAT or "jpeg").lower()
        image_bytes = await service.render_image(
            article,
            format=fmt,
            image_quality=image_quality,
        )
        media_type = f"image/{fmt}"
        return Response(content=image_bytes, media_type=media_type)
    except ScreenshotOneConfigurationError as conf_err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(conf_err),
        )
    except ScreenshotOneError as api_err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Image rendering failed: {api_err}",
        )
