"""Editorial Quality Gate & Content Validation Service.

Validates Webz.io news articles before public publication to enforce
journalistic quality, schema consistency, copyright compliance, and
freedom from boilerplate, navigation menus, login prompts, or corrupted text.
"""

import datetime
import ipaddress
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from pydantic import BaseModel

from app.core.logging import logger
from app.services.normalizer_service import (
    EDITORIAL_AUTHOR,
    normalize_author_name,
    normalize_publisher_name,
    is_spam_or_scraper_domain,
)
from app.services.image_validation_service import ImageValidationService

# Boilerplate patterns commonly scraped from cookie walls, login prompts, and navigation
BOILERPLATE_PATTERNS = [
    re.compile(r"please enable (cookies|javascript)", re.IGNORECASE),
    re.compile(r"sign in to (continue|read|access)", re.IGNORECASE),
    re.compile(r"subscribe to read (the full|more)", re.IGNORECASE),
    re.compile(r"all rights reserved\.? terms of (use|service)", re.IGNORECASE),
    re.compile(r"we use cookies to (ensure|personalize|improve)", re.IGNORECASE),
    re.compile(r"comprehensive wire coverage and primary reporting", re.IGNORECASE),
    re.compile(r"access the original publication for full context", re.IGNORECASE),
    re.compile(r"click here to (read|view|accept)", re.IGNORECASE),
    re.compile(r"^reporting by [^:]+: .+$", re.IGNORECASE),
    re.compile(r"\b(404 not found|page not found|access denied|403 forbidden|error 500)\b", re.IGNORECASE),
    re.compile(r"\blorem ipsum dolor sit amet\b", re.IGNORECASE),
    re.compile(r"^(test article|sample text|untitled|default title|coming soon|under construction)$", re.IGNORECASE),
    re.compile(r"detailed reporting on this story is available directly from the primary publisher", re.IGNORECASE),
    re.compile(r"full reporting published on original newsroom platform", re.IGNORECASE),
    re.compile(r"published first on –", re.IGNORECASE),
    re.compile(r"see (?:insiders['’]|today['’]s) (?:hot|best-performing) stocks on tipranks", re.IGNORECASE),
]

# Prohibited commercial casino, gambling, betting, and slot affiliate patterns
CASINO_GAMBLING_PATTERNS = [
    re.compile(r"\b(online\s*casinos?|casino\s*sites?|real\s*money\s*(?:casino|slots?|gaming)|gambling\s*sites?|top\s*\d+\s*casino)\b", re.IGNORECASE),
    re.compile(r"\b(sportsbook|sports\s*betting|betting\s*sites?|poker\s*online|slot\s*machines?|free\s*spins|deposit\s*bonus|wagering\s*requirements?)\b", re.IGNORECASE),
    re.compile(r"\b(sweet\s*bonanza|gonzo['’]?s\s*quest|cash\s*eruption|jackpot\s*city|crypto\s*casino|betonline)\b", re.IGNORECASE),
    re.compile(r"\b(?:best|top\s*\d+)\s+(?:online\s+)?casinos?\s+(?:in\s+[a-z]+|sites?)\b", re.IGNORECASE),
    re.compile(r"\b(?:top\s*\d+\s*(?:best|real\s*money|casino|gambling)|best\s*\d+\s*casino\s*sites?)\b", re.IGNORECASE),
]

# Commercial affiliate listicles, advertorials, and SEO promotional link spam
PROMOTIONAL_LISTICLE_PATTERNS = [
    re.compile(r"\b(top\s*10\s*real\s*money|best\s*casino\s*sites?|top\s*10\+\s*casino)\b", re.IGNORECASE),
    re.compile(r"\b(affiliate\s*disclosure|we\s*may\s*earn\s*a\s*commission|sponsored\s*(?:post|content|article))\b", re.IGNORECASE),
    re.compile(r"\b(exclusive\s*promo\s*code|get\s*welcome\s*bonus|claim\s*your\s*bonus)\b", re.IGNORECASE),
]

# Utility URL paths indicating non-article utility pages
UTILITY_URL_PATHS = re.compile(
    r"(?:/page/(?:terms|about|accessibility|openaccess|subject_collections)|"
    r"^/(?:terms|privacy|privacy-policy|terms-of-service|accessibility|about|about-us|contact|contact-us|login|signup|register|cookie-policy|sitemap|help)/?$)",
    re.IGNORECASE,
)

APPROVED_CATEGORIES = {
    "us", "world", "politics", "business", "technology",
    "science", "health", "environment", "sports", "entertainment"
}

# Prohibited HTML tags, script injection, closing tag breakouts, and event handler patterns
HTML_INJECTION_PATTERN = re.compile(
    r"</?\s*(?:script|iframe|html|body|svg|img|style|link|meta|object|embed|applet|form|input|button|textarea|select|option|marquee|audio|video|source|track|canvas|math)[^>]*>|"
    r"<\s*/?\s*[a-zA-Z][a-zA-Z0-9]*\b[^>]*>|"
    r"</\s*script\b|"
    r"<\s*script\b|"
    r"\bon[a-zA-Z]{3,15}\s*=|"
    r"javascript:\s*",
    re.IGNORECASE,
)


class ValidationResult(BaseModel):
    is_valid: bool
    status: str  # "published" or "filtered"
    filter_reason: Optional[str] = None
    cleaned_summary: Optional[str] = None
    cleaned_full_text: Optional[str] = None
    cleaned_publisher: Optional[str] = None
    cleaned_author: Optional[str] = None
    has_genuine_summary: bool = False
    has_valid_image: bool = False


class ArticleEditorialValidationService:
    """Enforces strict pre-publication quality gates across all articles."""

    @classmethod
    def validate_title(cls, title: Optional[str]) -> tuple[bool, Optional[str]]:
        if not title or not isinstance(title, str):
            return False, "Missing or non-string title"
        cleaned = title.strip()
        if len(cleaned) < 15:
            return False, f"Title too short ({len(cleaned)} chars, minimum 15 required)"
        if len(cleaned) > 512:
            return False, "Title exceeds maximum length of 512 characters"
        if HTML_INJECTION_PATTERN.search(cleaned):
            return False, "Title contains illegal HTML tags or script injection"
        for pat in BOILERPLATE_PATTERNS:
            if pat.search(cleaned):
                return False, f"Title matches boilerplate or utility pattern: {cleaned[:40]}"
        return True, None

    @classmethod
    def validate_url(cls, url: Optional[str]) -> tuple[bool, Optional[str]]:
        if not url or not isinstance(url, str):
            return False, "Missing URL"
        clean = url.strip()
        if not clean.startswith(("http://", "https://")):
            return False, "URL does not have http/https protocol"
        try:
            parsed = urlparse(clean)
            if not parsed.netloc or "." not in parsed.netloc:
                return False, "URL missing valid domain netloc"
            host = parsed.netloc.split(":")[0].lower()
            if host in {"127.0.0.1", "localhost", "0.0.0.0", "::1"}:
                return False, "URL points to private/loopback network"
            try:
                ip = ipaddress.ip_address(host)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return False, "URL points to private or link-local IP range"
            except ValueError:
                pass
            if UTILITY_URL_PATHS.search(parsed.path or ""):
                return False, f"URL path matches utility page: {parsed.path}"
        except Exception as e:
            return False, f"Malformed URL: {e}"
        return True, None

    @classmethod
    def validate_published_date(cls, published_at: Optional[datetime.datetime]) -> tuple[bool, Optional[str]]:
        if not published_at:
            return False, "Missing publication timestamp"
        now = datetime.datetime.now(datetime.timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=datetime.timezone.utc)
        if published_at > now + datetime.timedelta(hours=24):
            return False, "Publication date is in the distant future (> 24 hours ahead)"
        if published_at < datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc):
            return False, "Publication date is older than year 2000"
        return True, None

    @classmethod
    def validate_language(cls, language: Optional[str]) -> tuple[bool, Optional[str]]:
        if not language or not isinstance(language, str) or not language.strip():
            return False, "Missing language specification"
        clean_lang = language.strip().lower()
        if clean_lang not in {"en", "english"}:
            return False, f"Language '{language}' rejected: MetroScope exclusively publishes English content ('en' or 'english')"
        return True, None

    @classmethod
    def validate_publisher(
        cls,
        publisher_name: Optional[str],
        domain: str,
        title: str,
    ) -> tuple[bool, Optional[str], Optional[str]]:
        if not domain or len(domain.strip()) < 3 or "." not in domain:
            return False, None, "Unresolvable publisher domain"
        if is_spam_or_scraper_domain(domain):
            return False, None, "Domain is identified as spam or scraper network"

        if publisher_name and HTML_INJECTION_PATTERN.search(publisher_name):
            return False, None, "Publisher name contains illegal HTML tags or script injection"

        # Explicit rejection if provider publisher echoes headline
        if publisher_name and title:
            raw_p = publisher_name.strip().lower()
            raw_t = title.strip().lower()
            if raw_p == raw_t or (len(raw_t) > 20 and raw_t in raw_p):
                return False, None, "Publisher name cannot duplicate or derive from article headline"
            if " - homepage" in raw_p or raw_p.endswith("- homepage"):
                return False, None, "Publisher name contains forbidden homepage label"

        cleaned_pub = normalize_publisher_name(publisher_name, domain=domain, title=title)
        if not cleaned_pub or len(cleaned_pub.strip()) < 2:
            return False, None, "Publisher identity invalid or derived from article title/homepage"

        lower_pub = cleaned_pub.lower().strip()
        if "homepage" in lower_pub:
            return False, None, "Publisher name contains forbidden homepage label"

        if title and len(title.strip()) > 10:
            clean_t = title.strip().lower()
            if lower_pub == clean_t or (len(lower_pub) > 15 and lower_pub in clean_t) or (len(clean_t) > 15 and clean_t in lower_pub):
                return False, None, "Publisher name cannot duplicate or derive from article headline"

        # Check if publisher name is an academic university domain claiming to publish commercial news
        if re.search(r"\b(?:university|college|school|faculty)\b", lower_pub) and title:
            lower_t = title.lower()
            if any(term in lower_t for term in ["casino", "slots", "gambling", "betting", "top 10", "bonus"]):
                return False, None, "Unrelated publisher attribution: educational institution attached to commercial gambling content"

        return True, cleaned_pub, None

    @classmethod
    def validate_relevance(
        cls,
        title: str,
        domain: str,
        category_slug: Optional[str] = None,
        summary: Optional[str] = None,
        full_text: Optional[str] = None,
        publisher_name: Optional[str] = None,
    ) -> tuple[bool, Optional[str]]:
        """Strict pre-insertion editorial relevance validation.
        
        Rejects:
        - Casino, gambling, betting, sportsbooks, slot machines, crypto casinos.
        - Commercial affiliate listicles, advertorials, and SEO promotional link spam.
        - University / academic domains hosting hijacked commercial spam.
        - Academic admissions / course registrations miscategorized as business/world news.
        - Contradictory headline-source-category combinations.
        """
        lower_title = title.lower()
        lower_summary = (summary or "").lower()
        body_sample = (full_text or "")[:2000].lower()
        combined = f"{lower_title} {lower_summary} {body_sample}"
        
        clean_dom = (domain or "").lower().strip()
        if clean_dom.startswith("www."):
            clean_dom = clean_dom[4:]

        # 1. Reject Casino, Gambling, Betting, Slot Games, and Crypto Casinos
        for pat in CASINO_GAMBLING_PATTERNS:
            if pat.search(lower_title):
                return False, f"Headline matches prohibited gambling/casino pattern: {pat.pattern}"
            if lower_summary and pat.search(lower_summary):
                return False, f"Summary matches prohibited gambling/casino pattern: {pat.pattern}"
            if pat.search(body_sample):
                return False, "Content contains prohibited online gambling, casino, or betting promotions"

        # 2. Reject Promotional Listicles, Affiliate SEO Spam, Advertorials
        for pat in PROMOTIONAL_LISTICLE_PATTERNS:
            if pat.search(lower_title):
                return False, f"Headline matches promotional affiliate listicle pattern: {pat.pattern}"
            if lower_summary and pat.search(lower_summary):
                return False, "Summary matches promotional affiliate listicle pattern"

        # 3. Reject Academic / University Domain Hijacking & Brochure Miscategorization
        is_academic = bool(re.search(r"\.(?:edu|ac\.[a-z]{2}|edu\.[a-z]{2})$", clean_dom)) or clean_dom.endswith(("ou.ac.lk", ".edu", ".ac.uk", ".edu.au"))
        if is_academic:
            commercial_indicators = ["casino", "betting", "gambling", "slots", "real money", "free spins", "sportsbook", "cash eruption", "deposit bonus"]
            if any(term in combined for term in commercial_indicators):
                return False, "Academic university domain hosting hijacked commercial casino or gambling affiliate spam"

            academic_brochure_terms = [
                "learning opportunities to anyone", "distance learning", "admissions 2026",
                "course registration", "degree programme", "faculty of", "student prospectus",
                "undergraduate admissions", "postgraduate admissions", "academic calendar"
            ]
            if category_slug in {"business", "world", "politics", "technology", "sports"} and any(term in combined for term in academic_brochure_terms):
                return False, "University course brochure or admissions catalog falsely categorized as general news"

        # 4. Category-Content Consistency
        if category_slug == "business":
            if any(w in lower_title for w in ["online casino", "casino sites", "real money casino", "best slot sites"]):
                return False, "Commercial gambling promotion cannot be categorized as Business News"
            if clean_dom in {"ou.ac.lk"} or "university" in (publisher_name or "").lower():
                if any(w in lower_title for w in ["casino", "gambling", "slots", "loans"]):
                    return False, "Contradictory publisher and content: educational publisher cannot publish commercial loans/gambling"

        # 5. Headline-Summary Topic Mismatch
        if summary and len(summary.strip()) >= 30 and re.match(r"^[A-Za-z0-9\s.,'\"\-:;!?]+$", title) and re.match(r"^[A-Za-z0-9\s.,'\"\-:;!?]+$", summary):
            t_words = set(re.findall(r"\b[A-Za-z]{4,}\b", lower_title))
            stop = {"this", "that", "with", "from", "have", "more", "will", "about", "their", "after", "which", "news", "first", "today", "report", "says", "year"}
            sig_t = t_words - stop
            if len(sig_t) >= 2:
                s_words = set(re.findall(r"\b[A-Za-z]{4,}\b", lower_summary))
                if not (sig_t & s_words):
                    return False, "Headline/summary mismatch: summary does not reference core headline topic or entities"

        return True, None

    @classmethod
    def validate_author(
        cls,
        author: Optional[str],
        title: str,
        publisher_name: Optional[str],
        domain: str,
    ) -> Optional[str]:
        return normalize_author_name(author, title=title, publisher=publisher_name, domain=domain)

    @classmethod
    def validate_body_text(
        cls,
        full_text: Optional[str],
        title: str,
        summary: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """Validates body text for Unicode cleanliness, paragraph structure, boilerplate, and headline mismatch."""
        if not full_text or not isinstance(full_text, str) or not full_text.strip():
            return None, None

        cleaned = full_text.strip()

        # Reject if body is merely duplicate of headline
        if cleaned.lower().rstrip(".") == title.lower().rstrip("."):
            return None, "Body merely duplicates headline"

        # Reject if body merely duplicates summary
        if summary and cleaned.lower().rstrip(".") == summary.strip().lower().rstrip("."):
            return None, "Body merely duplicates summary"

        # Reject HTML tags or script injection
        if HTML_INJECTION_PATTERN.search(cleaned):
            return None, "Body contains illegal HTML tags or script injection"

        # Check for boilerplate patterns
        for pat in BOILERPLATE_PATTERNS:
            if pat.search(cleaned[:500]):
                return None, "Body contains cookie, paywall, error, or navigation boilerplate"

        # Reject wire-notice or stock tip snippets disguised as full text (< 250 chars)
        if len(cleaned) < 250 and ("tipranks" in cleaned.lower() or "published first on" in cleaned.lower()):
            return None, "Body is wire notice or promotional text rather than full article body"

        # Validate paragraph structure (must have reasonable paragraph count / length)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", cleaned) if p.strip()]
        if not paragraphs:
            return None, "Body has no readable paragraphs"

        # Deduplicate sequential duplicate paragraphs in full text
        unique_paragraphs = []
        for p in paragraphs:
            if not unique_paragraphs or p.lower() != unique_paragraphs[-1].lower():
                unique_paragraphs.append(p)
        cleaned = "\n\n".join(unique_paragraphs)

        # Check headline/body mismatch: if body has significant length (> 200 chars), verify topic consistency
        # Avoid false positives for non-Latin / Unicode scripts by checking Latin words only when title is Latin
        if len(cleaned) > 200 and re.match(r"^[A-Za-z0-9\s.,'\"\-:;!?]+$", title):
            title_words = set(re.findall(r"\b[A-Za-z]{4,}\b", title.lower()))
            # Remove common stop words from check
            stop_words = {"this", "that", "with", "from", "have", "more", "will", "about", "their", "after", "which", "news", "first"}
            meaningful_title_words = title_words - stop_words
            if meaningful_title_words:
                body_lower = cleaned.lower()
                matches = sum(1 for w in meaningful_title_words if w in body_lower)
                if matches == 0:
                    return None, "Headline/body mismatch: body text does not reference key headline entities"

        return cleaned, None

    @classmethod
    def validate_summary(
        cls,
        summary: Optional[str],
        title: str,
    ) -> tuple[Optional[str], bool]:
        """Validates whether summary is genuine, distinct from headline, and non-boilerplate."""
        if not summary or not isinstance(summary, str) or not summary.strip():
            return None, False

        cleaned = summary.strip()
        if len(cleaned) < 20:
            return None, False

        if HTML_INJECTION_PATTERN.search(cleaned):
            return None, False

        # Reject if duplicate of headline
        if cleaned.lower().rstrip(".") == title.lower().rstrip("."):
            return None, False

        # Reject boilerplate
        for pat in BOILERPLATE_PATTERNS:
            if pat.search(cleaned):
                return None, False

        return cleaned, True

    @classmethod
    def validate_category(cls, category_slug: Optional[str]) -> str:
        if not category_slug or category_slug.lower() not in APPROVED_CATEGORIES:
            return "world"
        return category_slug.lower()

    @classmethod
    def evaluate_candidate(
        cls,
        title: str,
        canonical_url: str,
        published_at: Optional[datetime.datetime],
        domain: str,
        category_slug: Optional[str],
        summary: Optional[str] = None,
        full_text: Optional[str] = None,
        publisher_name: Optional[str] = None,
        author: Optional[str] = None,
        image_url: Optional[str] = None,
        language: Optional[str] = "en",
        content_display_authorized: bool = True,
        probe_image_mime: bool = False,
        http_client: Optional[Any] = None,
    ) -> ValidationResult:
        """Evaluates complete article candidate against editorial quality gates."""
        # 1. Title
        title_ok, title_err = cls.validate_title(title)
        if not title_ok:
            return ValidationResult(
                is_valid=False,
                status="filtered",
                filter_reason=title_err,
            )

        # 2. Canonical URL
        url_ok, url_err = cls.validate_url(canonical_url)
        if not url_ok:
            return ValidationResult(
                is_valid=False,
                status="filtered",
                filter_reason=url_err,
            )

        # 3. Domain & Publisher
        pub_ok, clean_pub, pub_err = cls.validate_publisher(publisher_name, domain, title)
        if not pub_ok:
            return ValidationResult(
                is_valid=False,
                status="filtered",
                filter_reason=pub_err,
            )

        # 4. Publication Date
        date_ok, date_err = cls.validate_published_date(published_at)
        if not date_ok:
            return ValidationResult(
                is_valid=False,
                status="filtered",
                filter_reason=date_err,
            )

        # 5. Language
        lang_ok, lang_err = cls.validate_language(language)
        if not lang_ok:
            return ValidationResult(
                is_valid=False,
                status="filtered",
                filter_reason=lang_err,
            )

        # 6. Category Approval (Complete 10-Category Approved Taxonomy)
        approved_cats = APPROVED_CATEGORIES
        if not category_slug or category_slug.lower().strip() not in approved_cats:
            return ValidationResult(
                is_valid=False,
                status="filtered",
                filter_reason=f"Category '{category_slug}' is invalid or unapproved",
            )

        # 7. Editorial Relevance Gate (Casino, Gambling, Listicles, Academic Domain Spam)
        rel_ok, rel_err = cls.validate_relevance(
            title=title,
            domain=domain,
            category_slug=category_slug,
            summary=summary,
            full_text=full_text,
            publisher_name=clean_pub,
        )
        if not rel_ok:
            return ValidationResult(
                is_valid=False,
                status="filtered",
                filter_reason=rel_err,
                cleaned_publisher=clean_pub,
            )

        # 7. Author Validation
        # Canonical author is always the MetroScope editorial desk (provider byline ignored)
        clean_author = EDITORIAL_AUTHOR

        # 8. Clean Summary
        cleaned_summary, has_genuine_summary = cls.validate_summary(summary, title)

        # 9. Clean Body Text
        cleaned_body, body_err = cls.validate_body_text(full_text, title, summary=cleaned_summary)
        if not cleaned_body or len(cleaned_body.strip()) < 200:
            return ValidationResult(
                is_valid=False,
                status="filtered",
                filter_reason=body_err or "Article lacks mandatory substantive body text (min 200 chars)",
                cleaned_summary=cleaned_summary,
                cleaned_publisher=clean_pub,
                cleaned_author=clean_author,
            )

        # 10. Mandatory Featured Hero Image Gate:
        # Every published article must have a verified, authorized HTTPS hero image
        img_syntax_ok, img_syntax_err = ImageValidationService.validate_url_syntax(image_url)
        if not img_syntax_ok:
            return ValidationResult(
                is_valid=False,
                status="filtered",
                filter_reason=f"Missing or invalid mandatory HTTPS featured hero image: {img_syntax_err}",
                cleaned_summary=cleaned_summary,
                cleaned_full_text=cleaned_body,
                cleaned_publisher=clean_pub,
                cleaned_author=clean_author,
            )

        if probe_image_mime and image_url:
            mime_ok, mime_err = ImageValidationService.validate_image_response_sync(
                image_url=image_url,
                client=http_client,
            )
            if not mime_ok:
                return ValidationResult(
                    is_valid=False,
                    status="filtered",
                    filter_reason=f"Featured hero image response failed validation: {mime_err}",
                    cleaned_summary=cleaned_summary,
                    cleaned_full_text=cleaned_body,
                    cleaned_publisher=clean_pub,
                    cleaned_author=clean_author,
                )

        return ValidationResult(
            is_valid=True,
            status="published",
            filter_reason=None,
            cleaned_summary=cleaned_summary,
            cleaned_full_text=cleaned_body,
            cleaned_publisher=clean_pub,
            cleaned_author=clean_author,
            has_genuine_summary=has_genuine_summary,
            has_valid_image=True,
        )

    @classmethod
    def validate_image_mime(
        cls,
        image_url: str,
        client: Optional[Any] = None,
    ) -> tuple[bool, Optional[str]]:
        """Validates image MIME type, HTTP status, and network SSRF safety synchronously."""
        return ImageValidationService.validate_image_response_sync(image_url, client=client)

    @classmethod
    async def validate_image_mime_async(
        cls,
        image_url: str,
        client: Optional[Any] = None,
    ) -> tuple[bool, Optional[str]]:
        """Validates image MIME type, HTTP status, and network SSRF safety asynchronously."""
        return await ImageValidationService.validate_image_response_async(image_url, client=client)
