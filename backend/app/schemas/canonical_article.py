"""Canonical MetroScope Article Schema (Version 1.0.0).

Authoritative, version-controlled target schema for all ingested and published news.
Maps deterministically from upstream Webz.io JSON payloads.

Field Classifications:
1. MANDATORY: Required for an acceptable MetroScope article. If missing or invalid, the candidate is rejected.
2. OPTIONAL: May be None/empty without breaking canonical design. Conditionally omitted in UI. Never filled with synthetic fallbacks.
3. RIGHTS-DEPENDENT: Requires separate, explicit copyright authorization before public presentation.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.normalizer_service import EDITORIAL_AUTHOR

SCHEMA_VERSION: str = "1.0.0"

APPROVED_CATEGORIES: set[str] = {
    "us",
    "world",
    "politics",
    "business",
    "technology",
    "science",
    "health",
    "environment",
    "sports",
    "entertainment",
}


class CanonicalMetroScopeArticle(BaseModel):
    """Authoritative canonical schema for a MetroScope news article.
    
    Every article in the production system must satisfy this deterministic contract
    before entering the database or being published to public endpoints.
    """
    model_config = ConfigDict(extra="ignore", from_attributes=True)

    # -------------------------------------------------------------------------
    # 1. MANDATORY IDENTIFIERS & METADATA
    # -------------------------------------------------------------------------
    schema_version: str = Field(default=SCHEMA_VERSION, description="Schema contract version")
    uuid: str = Field(..., min_length=5, description="Provider unique identifier (Webz.io post UUID)")
    title: str = Field(..., min_length=15, max_length=512, description="Clean article headline")
    canonical_url: str = Field(..., min_length=10, description="Normalized canonical source URL")
    canonical_url_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash of canonical URL")
    domain: str = Field(..., min_length=3, max_length=255, description="Primary publisher domain")
    publisher_name: str = Field(..., min_length=2, max_length=255, description="Verified publisher brand name")
    published_at: datetime.datetime = Field(..., description="UTC publication timestamp")
    category_slug: str = Field(..., min_length=2, max_length=50, description="Approved MetroScope category slug")
    language: str = Field(default="en", description="Language code (must be en/english)")

    # -------------------------------------------------------------------------
    # 2. OPTIONAL EDITORIAL FIELDS (Omitted when absent; never synthesized)
    # -------------------------------------------------------------------------
    author: Optional[str] = Field(default=None, max_length=255, description="Verified human journalist name")
    summary: Optional[str] = Field(default=None, max_length=1000, description="Optional genuine provider editorial summary")
    crawled_at: Optional[datetime.datetime] = Field(default=None, description="Timestamp provider crawled the article")
    country: Optional[str] = Field(default=None, max_length=10, description="Country of origin")
    topics: List[str] = Field(default_factory=list, description="Topical classification tags")
    webz_categories: List[str] = Field(default_factory=list, description="Raw provider categories")
    sentiment: Optional[str] = Field(default=None, description="Provider sentiment signal")
    is_breaking: bool = Field(default=False, description="Breaking news flag")
    is_trending: bool = Field(default=False, description="Trending coverage flag")
    classification_confidence: int = Field(default=0, ge=0, le=100, description="Confidence score of category match")

    # -------------------------------------------------------------------------
    # 3. MANDATORY RIGHTS-AUTHORIZED FIELDS (Body & Image are Mandatory)
    # -------------------------------------------------------------------------
    full_text: str = Field(..., min_length=200, description="Mandatory genuine article body text (minimum 200 chars)")
    content_display_authorized: bool = Field(True, description="True if full-text republication is licensed/authorized")
    image_url: str = Field(..., min_length=10, description="Mandatory public hero image HTTPS URL")
    image_caption: Optional[str] = Field(default=None, max_length=512, description="Provider image caption")
    image_credit: Optional[str] = Field(default=None, max_length=255, description="Provider photographer/agency credit")
    hero_image_authorized: bool = Field(True, description="True if featured hero image display is authorized")
    inline_images: List[Dict[str, Any]] = Field(default_factory=list, description="Authorized inline image objects")
    inline_images_authorized: bool = Field(default=False, description="True if inline media display is authorized")
    trust_indicators: Dict[str, Any] = Field(default_factory=dict, description="Domain rank, spam score, provenance indicators")
    image_metadata: Dict[str, Any] = Field(default_factory=dict, description="Internal media rights and audit metadata")

    # -------------------------------------------------------------------------
    # VALIDATION RULES
    # -------------------------------------------------------------------------
    @field_validator("language")
    @classmethod
    def validate_language_english_only(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned not in {"en", "english"}:
            raise ValueError(f"Language '{v}' rejected: MetroScope exclusively publishes English content ('en' or 'english')")
        return "en"

    @field_validator("full_text")
    @classmethod
    def validate_full_text(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Full article body is mandatory")
        cleaned = v.strip()
        if len(cleaned) < 200:
            raise ValueError(f"Article body too short ({len(cleaned)} chars, minimum 200 required)")
        lower = cleaned.lower()
        if "tipranks" in lower or "published first on" in lower:
            raise ValueError("Article body contains wire notice or promotional text rather than substantive reporting")
        return cleaned

    @field_validator("content_display_authorized")
    @classmethod
    def validate_content_display_authorized(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Full text republication is unauthorized")
        return v

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Featured image is mandatory")
        cleaned = v.strip()
        if not cleaned.startswith("https://"):
            raise ValueError(f"Featured image must be a secure HTTPS URL: '{cleaned}'")
        lower = cleaned.lower()
        if any(bad in lower for bad in ["pixel.gif", "1x1", "tracking", "placeholder", "default_image", "blank.png"]):
            raise ValueError(f"Placeholder or tracking pixel image rejected: '{cleaned}'")
        return cleaned

    @field_validator("hero_image_authorized")
    @classmethod
    def validate_hero_image_authorized(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Featured hero image display is unauthorized")
        return v
    @field_validator("title")
    @classmethod
    def validate_title_cleanliness(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 15:
            raise ValueError(f"Headline too short ({len(cleaned)} chars, minimum 15)")
        # Reject generic HTTP or utility titles
        lower = cleaned.lower()
        if lower in {"404 not found", "page not found", "access denied", "terms of service", "privacy policy"}:
            raise ValueError(f"Utility page title rejected: '{cleaned}'")
        return cleaned

    @field_validator("canonical_url")
    @classmethod
    def validate_canonical_url(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned.startswith(("http://", "https://")):
            raise ValueError(f"Invalid canonical URL scheme: '{cleaned}'")
        return cleaned

    @field_validator("published_at")
    @classmethod
    def validate_published_not_future(cls, v: datetime.datetime) -> datetime.datetime:
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if v.tzinfo is None:
            v = v.replace(tzinfo=datetime.timezone.utc)
        else:
            v = v.astimezone(datetime.timezone.utc)
        if v > now_utc + datetime.timedelta(hours=24):
            raise ValueError(f"Publication date too far in future: {v.isoformat()}")
        return v

    @field_validator("category_slug")
    @classmethod
    def validate_category(cls, v: str) -> str:
        slug = v.strip().lower()
        if slug not in APPROVED_CATEGORIES:
            raise ValueError(f"Category '{slug}' not in approved categories: {APPROVED_CATEGORIES}")
        return slug

    @field_validator("author")
    @classmethod
    def validate_author_cleanliness(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        cleaned = v.strip()
        lower = cleaned.lower()
        # Discard generic editorial roles or email handles
        if "@" in lower or "noreply" in lower:
            return None
        if lower in {"admin", "administrator", "editor", "web editor", "staff", "news desk", "author", "unknown"}:
            return None
        if len(cleaned) < 2 or len(cleaned) > 100:
            return None
        return cleaned

    @field_validator("summary")
    @classmethod
    def validate_summary_cleanliness(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        cleaned = v.strip()
        if len(cleaned) < 20:
            return None
        lower = cleaned.lower()
        # Reject boilerplate or error snippets
        if any(bp in lower for bp in [
            "please enable cookies",
            "sign in to continue",
            "all rights reserved",
            "subscribe to read",
            "javascript is disabled",
        ]):
            return None
        return cleaned

    @model_validator(mode="after")
    def validate_cross_field_integrity(self) -> CanonicalMetroScopeArticle:
        # 0. Author is always the MetroScope editorial desk
        self.author = EDITORIAL_AUTHOR

        # 1. Headline cannot match Author
        if self.author:
            if self.author.strip().lower() == self.title.strip().lower():
                self.author = None
            elif len(self.title) > 20 and self.author.strip().lower() in self.title.strip().lower():
                self.author = None

        # 2. Headline cannot match Publisher
        if self.publisher_name:
            pub_clean = self.publisher_name.strip().lower()
            title_clean = self.title.strip().lower()
            if pub_clean == title_clean:
                raise ValueError(f"Publisher name matches article title: '{self.publisher_name}'")
            if len(pub_clean) > 20 and title_clean in pub_clean:
                raise ValueError(f"Publisher name echoes article title: '{self.publisher_name}'")
            if " - homepage" in pub_clean or pub_clean.endswith("- homepage"):
                raise ValueError(f"Publisher name contains crawler suffix: '{self.publisher_name}'")

        # 3. Full text cannot duplicate summary
        if self.full_text and self.summary:
            if self.full_text.strip().lower() == self.summary.strip().lower():
                raise ValueError("Full article body cannot be a duplicate of editorial summary")

        # 4. Mandatory Substantive Body Gate (Minimum 200 chars required)
        if not self.full_text or len(self.full_text.strip()) < 200:
            raise ValueError(
                f"Article lacks substantive body: full_text must be at least 200 characters "
                f"(found {len(self.full_text.strip()) if self.full_text else 0})"
            )

        # 5. Full text republication authorization
        if not self.content_display_authorized:
            raise ValueError("Full article body republication is not authorized")

        # 6. Hero image presence and publication authorization
        if not self.image_url or not self.image_url.startswith("https://"):
            raise ValueError("Mandatory featured hero image must be a valid HTTPS URL")
        if not self.hero_image_authorized:
            raise ValueError("Featured hero image display is not authorized")

        return self
