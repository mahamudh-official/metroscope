"""Photo Card Service for MetroScope Editorial News Cards.

Renders user-approved, high-impact 1080x1080 HTML photo cards and orchestrates
image rendering via ScreenshotOne.
"""

import base64
from dataclasses import dataclass
import datetime
import html
import os
from pathlib import Path
import re
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse
from dateutil import parser as date_parser

from app.core.config import settings
from app.core.logging import logger
from app.integrations.screenshotone.client import ScreenshotOneClient

# Approved category presentation mappings
CATEGORY_DISPLAY_MAP: Dict[str, str] = {
    "us": "US News",
    "world": "World News",
    "politics": "Politics",
    "business": "Business",
    "technology": "Technology",
    "science": "Science",
    "health": "Health",
    "environment": "Environment",
    "sports": "Sports",
    "entertainment": "Entertainment",
}

# Template file path
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "photo_card.html"

# Original MetroScope logo asset search locations (prioritizing background-inclusive original asset)
LOGO_PATHS = [
    Path(__file__).resolve().parent.parent / "templates" / "assets" / "stitch-sample.jpg",
    Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "public" / "stitch-sample.jpg",
    Path(__file__).resolve().parent.parent / "templates" / "assets" / "logo.png",
    Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "public" / "logo.png",
]

_TEMPLATE_CACHE: Optional[str] = None
_LOGO_DATA_URI_CACHE: Optional[str] = None


def get_logo_data_uri() -> str:
    """Loads and caches the original MetroScope logo as a base64 data URI.
    
    Guarantees:
    - Sourced strictly from original project asset (stitch-sample.jpg / logo.png).
    - Preserves high-fidelity original visual branding and solid background visibility.
    - Enables self-contained HTML rendering in ScreenshotOne, browsers, and previews.
    - Raises FileNotFoundError if the original logo asset cannot be found.
    """
    global _LOGO_DATA_URI_CACHE
    if _LOGO_DATA_URI_CACHE is None:
        logo_path = None
        for p in LOGO_PATHS:
            if p.exists():
                logo_path = p
                break
        if not logo_path:
            searched = [str(p) for p in LOGO_PATHS]
            raise FileNotFoundError(
                f"Original MetroScope logo asset missing. Searched locations: {searched}"
            )
        raw_bytes = logo_path.read_bytes()
        encoded = base64.b64encode(raw_bytes).decode("ascii")
        ext = logo_path.suffix.lower().lstrip(".")
        mime_type = "image/jpeg" if ext in ["jpg", "jpeg"] else f"image/{ext}"
        _LOGO_DATA_URI_CACHE = f"data:{mime_type};base64,{encoded}"
    return _LOGO_DATA_URI_CACHE


def get_photo_card_template() -> str:
    """Loads and caches the approved photo card HTML template."""
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is None:
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Photo card template not found at {TEMPLATE_PATH}")
        _TEMPLATE_CACHE = TEMPLATE_PATH.read_text(encoding="utf-8")
    return _TEMPLATE_CACHE


def format_category_display(category: Optional[str]) -> str:
    """Formats category slug or name into approved uppercase/title presentation."""
    if not category or not category.strip():
        return "News"
    clean = category.strip().lower()
    if clean in CATEGORY_DISPLAY_MAP:
        return CATEGORY_DISPLAY_MAP[clean]
    # Handle composite or custom categories
    return clean.replace("_", " ").replace("-", " ").title()


def format_date_display(dt_val: Optional[Union[datetime.datetime, datetime.date, str]]) -> str:
    """Formats publication timestamp into approved uppercase 'MONTH DAY, YEAR'.
    
    Rules:
    - Sources exclusively from actual article published_at timestamp.
    - Formats as 'MONTH DAY, YEAR' in uppercase (e.g. 'NOVEMBER 19, 2026').
    - Never hardcodes or fabricates a date.
    - Never substitutes current system date when published_at is missing.
    - If published_at is null, empty, or unparseable, returns 'DATE UNAVAILABLE'.
    - Normalizes timezone-aware timestamps to UTC.
    """
    if not dt_val:
        return "DATE UNAVAILABLE"

    if isinstance(dt_val, datetime.datetime):
        dt_utc = dt_val.astimezone(datetime.timezone.utc) if dt_val.tzinfo else dt_val
        return dt_utc.strftime("%B %d, %Y").upper()

    if isinstance(dt_val, datetime.date):
        return dt_val.strftime("%B %d, %Y").upper()

    clean_str = str(dt_val).strip()
    if not clean_str or clean_str.upper() in ("NONE", "NULL", "UNDEFINED", "DATE UNAVAILABLE"):
        return "DATE UNAVAILABLE"

    try:
        parsed = date_parser.parse(clean_str)
        dt_utc = parsed.astimezone(datetime.timezone.utc) if parsed.tzinfo else parsed
        return dt_utc.strftime("%B %d, %Y").upper()
    except (ValueError, OverflowError, TypeError, date_parser.ParserError):
        return "DATE UNAVAILABLE"


PHOTO_CARD_BRAND_WEBSITE: str = "theMetroScope.com"


def format_website_display(site_url: Optional[str] = None) -> str:
    """Formats site URL into clean website branding watermark (e.g. 'theMetroScope.com')."""
    if not site_url or not str(site_url).strip():
        return PHOTO_CARD_BRAND_WEBSITE
    raw = str(site_url).strip()
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    clean = domain.strip().lower()
    # If domain is MetroScope, localhost, loopback, or empty, use canonical brand name
    if not clean or "localhost" in clean or "127.0.0.1" in clean or "metroscope" in clean:
        return PHOTO_CARD_BRAND_WEBSITE
    return domain.strip()


def sanitize_image_url(url: Optional[str]) -> Optional[str]:
    """Validates and sanitizes image URL for safe CSS background injection.
    
    Guarantees:
    - Only allows http:// and https:// schemes.
    - Strips quotes, parentheses, angle brackets, and whitespace to prevent CSS injection.
    - Returns None if invalid or unsafe.
    """
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    if not cleaned.startswith(("http://", "https://")):
        return None
    # Check for disallowed characters that could break out of CSS url("...")
    if re.search(r'["\'()<>\r\n\t\s]', cleaned):
        return None
    return cleaned


@dataclass
class PhotoCardData:
    """Canonical data model for rendering an editorial photo card."""
    headline: str
    category: str = "News"
    published_at: Optional[Union[datetime.datetime, datetime.date, str]] = None
    image_url: Optional[str] = None
    website_url: Optional[str] = None
    edition_text: str = "The latest, in focus"
    logo_src: Optional[str] = None

    @classmethod
    def from_article(cls, article: Any, base_url: Optional[str] = None) -> "PhotoCardData":
        """Factory method constructing PhotoCardData from database or schema models.
        
        Supports:
        - app.models.article.NewsArticle
        - app.schemas.canonical_article.CanonicalMetroScopeArticle
        - app.schemas.article.ArticleDetail / ArticleListItem
        - Generic dict with title, category, published_at, image_url
        """
        # 1. NewsArticle database model
        if hasattr(article, "title") and hasattr(article, "category_id"):
            headline = getattr(article, "title", "")
            cat_name = "News"
            if getattr(article, "category", None) and hasattr(article.category, "name"):
                cat_name = article.category.name
            elif getattr(article, "category", None) and hasattr(article.category, "slug"):
                cat_name = article.category.slug
            return cls(
                headline=headline,
                category=cat_name,
                published_at=getattr(article, "published_at", None),
                image_url=getattr(article, "image_url", None),
                website_url=base_url or settings.SITE_URL,
            )

        # 2. CanonicalMetroScopeArticle Pydantic schema
        if hasattr(article, "title") and hasattr(article, "category_slug"):
            return cls(
                headline=getattr(article, "title", ""),
                category=getattr(article, "category_slug", "News"),
                published_at=getattr(article, "published_at", None),
                image_url=getattr(article, "image_url", None),
                website_url=base_url or settings.SITE_URL,
            )

        # 3. Dict structure
        if isinstance(article, dict):
            return cls(
                headline=article.get("title") or article.get("headline", ""),
                category=article.get("category") or article.get("category_slug", "News"),
                published_at=article.get("published_at") or article.get("date"),
                image_url=article.get("image_url") or article.get("image"),
                website_url=article.get("website_url") or base_url or settings.SITE_URL,
            )

        # 4. Generic duck-typing
        return cls(
            headline=getattr(article, "title", getattr(article, "headline", "")),
            category=getattr(article, "category", getattr(article, "category_slug", "News")),
            published_at=getattr(article, "published_at", None),
            image_url=getattr(article, "image_url", None),
            website_url=base_url or settings.SITE_URL,
        )


class PhotoCardService:
    """Service orchestrating dynamic HTML photo card generation and ScreenshotOne image capture."""

    def __init__(self, screenshot_client: Optional[ScreenshotOneClient] = None):
        self.screenshot_client = screenshot_client or ScreenshotOneClient()

    def render_html(
        self,
        data: Union[PhotoCardData, Any],
        canvas_fixed: bool = True,
    ) -> str:
        """Renders dynamic HTML for the photo card, safely escaping all content.
        
        Args:
            data: PhotoCardData or article model instance.
            canvas_fixed: If True, applies 'canvas-fixed' class for 1080x1080 screenshot capture.
                          If False, applies responsive centered preview styling.
                          
        Returns:
            str: Valid, self-contained HTML document.
        """
        if not isinstance(data, PhotoCardData):
            card_data = PhotoCardData.from_article(data)
        else:
            card_data = data

        template = get_photo_card_template()

        # Safe escaping of user/article text content
        safe_headline = html.escape((card_data.headline or "").strip(), quote=True)
        raw_category = format_category_display(card_data.category)
        safe_category = html.escape(raw_category, quote=True)
        raw_date = format_date_display(card_data.published_at)
        safe_date = html.escape(raw_date, quote=True)
        raw_site = format_website_display(card_data.website_url)
        safe_site = html.escape(raw_site, quote=True)
        safe_edition = html.escape(card_data.edition_text or "The latest, in focus", quote=True)

        # Adaptive typography scaling based on headline character length
        headline_len = len(card_data.headline or "")
        if headline_len > 120:
            headline_class = "headline-xlong"
        elif headline_len > 85:
            headline_class = "headline-long"
        else:
            headline_class = ""

        # Original MetroScope logo asset embedding (transparent background and proportional scaling)
        effective_logo = card_data.logo_src or get_logo_data_uri()
        brand_html = f'<img src="{effective_logo}" alt="MetroScope" class="brand-logo">'

        # Photo background CSS generation
        safe_img_url = sanitize_image_url(card_data.image_url)
        if safe_img_url:
            photo_background_css = (
                "background:\n"
                "      linear-gradient(180deg, rgba(7,15,23,.10) 0%, rgba(7,15,23,.02) 35%, rgba(7,15,23,.45) 58%, #101820 100%),\n"
                f'      url("{safe_img_url}") center 42% / cover no-repeat;'
            )
        else:
            # Elegant dark editorial fallback gradient with MetroScope red ambient glow
            photo_background_css = (
                "background:\n"
                "      radial-gradient(circle at 65% 30%, rgba(237, 75, 67, 0.22) 0%, rgba(16, 24, 32, 0) 55%),\n"
                "      linear-gradient(180deg, #18222e 0%, #101820 60%, #0a0f14 100%);"
            )

        body_class = "canvas-fixed" if canvas_fixed else ""

        # Deterministic substitution of template placeholders
        rendered = template.replace("{{ photo_background_css }}", photo_background_css)
        rendered = rendered.replace("{{ body_class }}", body_class)
        rendered = rendered.replace("{{ brand_html }}", brand_html)
        rendered = rendered.replace("{{ edition_text }}", safe_edition)
        rendered = rendered.replace("{{ category }}", safe_category)
        rendered = rendered.replace("{{ headline }}", safe_headline)
        rendered = rendered.replace("{{ headline_class }}", headline_class)
        rendered = rendered.replace("{{ published_at }}", safe_date)
        rendered = rendered.replace("{{ website_url }}", safe_site)

        return rendered

    async def render_image(
        self,
        data: Union[PhotoCardData, Any],
        format: Optional[str] = None,
        image_quality: Optional[int] = None,
    ) -> bytes:
        """Generates dynamic HTML and captures a 1080x1080 image via ScreenshotOne.
        
        Args:
            data: PhotoCardData or article model instance.
            format: 'jpeg' or 'png' (default: settings.SCREENSHOTONE_IMAGE_FORMAT).
            image_quality: Quality 1-100 (default: settings.SCREENSHOTONE_IMAGE_QUALITY).
            
        Returns:
            bytes: Binary image bytes.
        """
        html_markup = self.render_html(data, canvas_fixed=True)
        return await self.screenshot_client.render_html(
            html=html_markup,
            viewport_width=1080,
            viewport_height=1080,
            device_scale_factor=1,
            image_format=format,
            image_quality=image_quality,
            selector=".card",
            wait_until="networkidle0",
        )
