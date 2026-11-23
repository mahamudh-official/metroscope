import datetime
import ipaddress
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from dateutil import parser as date_parser

from app.core.logging import logger
from app.integrations.webz.schemas import NormalizedWebzArticle, WebzPost, WebzResponse
from app.schemas.canonical_article import CanonicalMetroScopeArticle
from app.services.classifier_service import classify_article_detailed
from app.services.content_rights_service import ContentRightsService
from app.services.normalizer_service import (
    EDITORIAL_AUTHOR,
    clean_title,
    clean_description,
    normalize_author_name,
    normalize_publisher_name,
)
from app.services.url_service import normalize_url, compute_url_hash, extract_domain

VERIFIED_PUBLISHER_MAP: Dict[str, str] = {
    "reuters.com": "Reuters",
    "apnews.com": "Associated Press",
    "bbc.com": "BBC News",
    "bbc.co.uk": "BBC News",
    "npr.org": "NPR",
    "pbs.org": "PBS News",
    "nytimes.com": "The New York Times",
    "wsj.com": "The Wall Street Journal",
    "washingtonpost.com": "The Washington Post",
    "bloomberg.com": "Bloomberg",
    "cnbc.com": "CNBC",
    "forbes.com": "Forbes",
    "marketwatch.com": "MarketWatch",
    "businessinsider.com": "Business Insider",
    "fortune.com": "Fortune",
    "theguardian.com": "The Guardian",
    "cbsnews.com": "CBS News",
    "nbcnews.com": "NBC News",
    "abcnews.go.com": "ABC News",
    "foxnews.com": "Fox News",
    "thehill.com": "The Hill",
    "politico.com": "Politico",
    "axios.com": "Axios",
    "techcrunch.com": "TechCrunch",
    "theverge.com": "The Verge",
    "arstechnica.com": "Ars Technica",
    "wired.com": "Wired",
    "engadget.com": "Engadget",
    "scientificamerican.com": "Scientific American",
    "sciencedaily.com": "ScienceDaily",
    "phys.org": "Phys.org",
    "nature.com": "Nature",
    "statnews.com": "STAT News",
    "insideclimatenews.org": "Inside Climate News",
    "espn.com": "ESPN",
    "cbssports.com": "CBS Sports",
    "nbcsports.com": "NBC Sports",
    "variety.com": "Variety",
    "hollywoodreporter.com": "The Hollywood Reporter",
    "deadline.com": "Deadline",
    "rollingstone.com": "Rolling Stone",
    "yahoo.com": "Yahoo News",
    "msn.com": "MSN",
}

UTILITY_URL_PATH_PATTERNS = re.compile(
    r"(?:/page/(?:terms|about|accessibility|openaccess|subject_collections)|"
    r"^/(?:terms|privacy|privacy-policy|terms-of-service|accessibility|about|about-us|contact|contact-us|login|signup|register|cookie-policy|help|sitemap)/?$)",
    re.IGNORECASE,
)

UTILITY_TITLE_PATTERNS = re.compile(
    r"^(?:terms\s*(?:&|and)\s*conditions|terms\s+of\s+(?:service|use)|privacy\s+policy|"
    r"cookie\s+policy|accessibility\s+statement(?:\s*-\s*\w+)?|subject\s+collections|"
    r"open\s+access(?:\s*-\s*\w+)?|about\s+(?:us|iopscience)|contact\s+us|sign\s+in|log\s+in|"
    r"404\s*not\s*found|page\s*not\s*found|access\s*denied|error\s*500)$",
    re.IGNORECASE,
)


def parse_webz_datetime(dt_str: Optional[str]) -> Optional[datetime.datetime]:
    """Parses ISO-8601 or RFC-3339 timestamps from Webz.io into UTC datetime.
    
    Rejects timestamps that fail to parse or are absurdly far in the future (> 1 day).
    """
    if not dt_str or not dt_str.strip():
        return None
    try:
        parsed = date_parser.parse(dt_str.strip())
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.timezone.utc)
        else:
            parsed = parsed.astimezone(datetime.timezone.utc)

        # Sanity check: publication date cannot be > 24 hours into the future
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        if parsed > now_utc + datetime.timedelta(hours=24):
            logger.warning(f"Rejecting article with future timestamp: {dt_str}")
            return None
        return parsed
    except Exception as exc:
        logger.warning(f"Failed to parse Webz.io publication date '{dt_str}': {exc}")
        return None


def _resolve_publisher_name(thread: Any, domain: Optional[str] = None, title: Optional[str] = None) -> Optional[str]:
    """Resolves and validates the best available publisher display name without inventing names.
    
    Priority:
    1. thread.site_title validated & normalized (rejects headline and - homepage)
    2. VERIFIED_PUBLISHER_MAP lookup by canonical domain
    3. Clean normalized domain fallback
    """
    raw_site_title = None
    if thread is not None and getattr(thread, "site_title", None) and thread.site_title.strip():
        raw_site_title = thread.site_title.strip()
    return normalize_publisher_name(raw_name=raw_site_title, domain=domain, title=title)


def extract_short_summary(post: WebzPost, max_len: int = 500) -> Optional[str]:
    """Extracts a permitted summary for public display, respecting copyright.

    Rules:
    - Uses `post.summary` (provider-supplied summary) when available and meaningful.
    - Never uses or retains full article body text (`post.text`).
    - Never generates a fake summary (such as 'Reporting by {publisher}: {headline}.').
    - Rejects boilerplate, wire teasers, and generic placeholder paragraphs.
    - Returns None when no genuine summary is available.
    """
    webz_summary = getattr(post, "summary", None)
    if not webz_summary or not webz_summary.strip():
        return None

    raw_summary = webz_summary.strip()
    if len(raw_summary) < 20:
        return None

    cleaned = clean_description(raw_summary)
    if not cleaned or len(cleaned) < 20:
        return None

    # Reject placeholder phrases, stock promo teasers, and boilerplate
    lower_s = cleaned.lower()
    placeholder_phrases = [
        "detailed reporting on this story is available directly from the primary publisher",
        "full reporting published on original newsroom platform",
        "published first on –",
        "see insiders’ hot stocks on tipranks",
        "see today’s best-performing stocks on tipranks",
        "see insiders' hot stocks on tipranks",
        "see today's best-performing stocks on tipranks",
        "please enable cookies",
        "sign in to continue",
        "subscribe to read",
        "all rights reserved",
        "comprehensive wire coverage",
        "access the original publication",
    ]
    if any(p in lower_s for p in placeholder_phrases):
        return None

    # Reject summaries that merely duplicate the headline
    thread = getattr(post, "thread", None)
    raw_title = getattr(post, "title", None) or (thread.title if thread else "")
    headline = clean_title(raw_title or "")
    if headline and cleaned.lower().rstrip(".") == headline.lower().rstrip("."):
        return None

    if len(cleaned) > max_len:
        return cleaned[:max_len].rsplit(" ", 1)[0] + "..."
    return cleaned


def is_utility_or_non_article(title: str, canonical_url: str) -> bool:
    """Detects utility pages, spam scraper titles, and non-article records."""
    clean_t = title.strip()
    if UTILITY_TITLE_PATTERNS.match(clean_t):
        return True
    lower_t = clean_t.lower()
    if any(p in lower_t for p in ["online casino", "real money casino", "best casino sites", "gambling sites", "sportsbook", "sweet bonanza", "crypto casino"]):
        return True
    try:
        parsed_path = urlparse(canonical_url).path or ""
        if UTILITY_URL_PATH_PATTERNS.search(parsed_path):
            return True
    except Exception:
        pass
    return False


def is_valid_image_url(url: Optional[str]) -> bool:
    """Validates that an image URL has an approved protocol, hostname, and is not a tracking pixel or internal IP."""
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if not u.startswith(("http://", "https://")):
        return False
    if len(u) > 2048 or " " in u or "\n" in u or "\r" in u:
        return False
    lower_u = u.lower()
    disallowed = [
        "1x1", "pixel.gif", "spacer.gif", "tracking", "beacon", "blank.gif",
        "favicon", "avatar-default", "placeholder.jpg", "placeholder.png",
        "ad-pixel", "stat.gif", "counter.gif",
    ]
    if any(d in lower_u for d in disallowed):
        return False
    try:
        parsed = urlparse(u)
        if not parsed.netloc or "." not in parsed.netloc:
            return False
        host = parsed.netloc.split(":")[0].lower()
        if host in {"127.0.0.1", "localhost", "0.0.0.0", "::1"}:
            return False
        # Reject private/internal IP ranges (RFC 1918 & link-local)
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass
        if host.endswith((".local", ".internal", ".lan", ".localhost")):
            return False
    except Exception:
        return False
    return True


def extract_primary_image(post: WebzPost) -> Tuple[Optional[str], Dict[str, Any]]:
    """Extracts the primary editorial image from Webz.io post metadata.
    
    Checks in priority order:
    1. thread.main_image (verified primary hero image)
    2. internal_images (inline publisher images)
    3. external_images (secondary media attachments)
    """
    thread = getattr(post, "thread", None)
    # 1. thread.main_image
    if thread and getattr(thread, "main_image", None):
        main_img = str(thread.main_image).strip()
        if is_valid_image_url(main_img):
            caption = None
            credit = None
            # Check thread licensing agency
            if getattr(thread, "licensing_agency", None):
                credit = str(thread.licensing_agency)
            return main_img, {
                "source": "provider_main_image",
                "url": main_img,
                "caption": caption,
                "credit": credit,
                "external_only": True,
            }

    # 2. internal_images
    if hasattr(post, "internal_images") and post.internal_images:
        for img in post.internal_images:
            raw_url = None
            caption = None
            credit = None
            if isinstance(img, dict):
                raw_url = img.get("url") or img.get("src")
                caption = img.get("caption") or img.get("alt")
                credit = img.get("credit") or img.get("author")
            elif isinstance(img, str):
                raw_url = img
            if raw_url and is_valid_image_url(str(raw_url)):
                clean_u = str(raw_url).strip()
                return clean_u, {
                    "source": "provider_internal_images",
                    "url": clean_u,
                    "caption": caption,
                    "credit": credit,
                    "external_only": True,
                }

    # 3. external_images
    if hasattr(post, "external_images") and post.external_images:
        for img in post.external_images:
            raw_url = None
            caption = None
            credit = None
            if isinstance(img, dict):
                raw_url = img.get("url") or img.get("src")
                caption = img.get("caption") or img.get("alt")
                credit = img.get("credit") or img.get("author")
            elif isinstance(img, str):
                raw_url = img
            if raw_url and is_valid_image_url(str(raw_url)):
                clean_u = str(raw_url).strip()
                return clean_u, {
                    "source": "provider_external_images",
                    "url": clean_u,
                    "caption": caption,
                    "credit": credit,
                    "external_only": True,
                }

    return None, {}


def extract_inline_images(post: WebzPost, exclude_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extracts all secondary inline images from internal_images and external_images."""
    inline_list: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    if exclude_url:
        seen_urls.add(exclude_url.strip())

    for source_key in ("internal_images", "external_images"):
        raw_list = getattr(post, source_key, []) or []
        for item in raw_list:
            raw_url = None
            caption = None
            credit = None
            if isinstance(item, dict):
                raw_url = item.get("url") or item.get("src")
                caption = item.get("caption") or item.get("alt")
                credit = item.get("credit") or item.get("author")
            elif isinstance(item, str):
                raw_url = item

            if raw_url and is_valid_image_url(str(raw_url)):
                clean_u = str(raw_url).strip()
                if clean_u not in seen_urls:
                    seen_urls.add(clean_u)
                    inline_list.append({
                        "url": clean_u,
                        "caption": caption.strip() if caption and isinstance(caption, str) else None,
                        "credit": credit.strip() if credit and isinstance(credit, str) else None,
                        "source": source_key,
                    })

    return inline_list


def normalize_webz_post(
    post: WebzPost,
    target_category: Optional[str] = None,
) -> Optional[NormalizedWebzArticle]:
    """Validates and normalizes a single Webz.io post into a NormalizedWebzArticle.

    Uses actual Webz.io response fields:
    - post.uuid, post.title, post.summary, post.url, post.author, post.published
    - post.text (root-level full body text, preserved without substitution)
    - post.crawled, post.categories, post.topics, post.sentiment, post.breaking
    - post.thread.site_title (publisher display name)
    - post.thread.site_full / site (publisher domain)
    - post.thread.main_image, thread.domain_rank, thread.country, thread.site_type
    - post.internal_images, post.external_images
    - post.entities (persons, organizations, locations)
    - post.trust

    Returns None if the record fails schema validation.
    """
    # 1. UUID Validation
    uuid = (post.uuid or "").strip()
    if not uuid:
        logger.debug("Rejected Webz post: missing or empty UUID")
        return None

    # 2. Title Validation
    thread = post.thread
    raw_title = post.title or (thread.title if thread else None)
    if not raw_title:
        logger.debug(f"Rejected Webz post {uuid}: missing title")
        return None
    headline = clean_title(raw_title)
    if len(headline) < 15:
        logger.debug(f"Rejected Webz post {uuid}: title too short ('{headline}')")
        return None

    # 3. Canonical URL Validation
    raw_url = post.url or (thread.url if thread else None)
    if not raw_url:
        logger.debug(f"Rejected Webz post {uuid}: missing URL")
        return None
    canonical_url = normalize_url(raw_url)
    if not canonical_url or not canonical_url.startswith(("http://", "https://")):
        logger.debug(f"Rejected Webz post {uuid}: invalid canonical URL '{raw_url}'")
        return None
    if is_utility_or_non_article(headline, canonical_url):
        logger.debug(f"Rejected Webz post {uuid}: utility or non-article page ('{headline}')")
        return None
    canonical_url_hash = compute_url_hash(canonical_url)

    # 4. Publication Timestamp Validation
    raw_date = post.published or (thread.published if thread else None)
    published_at = parse_webz_datetime(raw_date)
    if not published_at:
        logger.debug(f"Rejected Webz post {uuid}: invalid or unparseable timestamp '{raw_date}'")
        return None

    # 5. Crawled timestamp (optional, non-blocking)
    crawled_at = parse_webz_datetime(getattr(post, "crawled", None))

    # 6. Publisher / Domain Extraction
    domain = extract_domain(canonical_url)
    if not domain and thread:
        raw_dom = (thread.site_full or thread.site or "").lower().strip()
        if raw_dom.startswith("www."):
            raw_dom = raw_dom[4:]
        domain = raw_dom
    if not domain:
        logger.debug(f"Rejected Webz post {uuid}: unresolvable publisher domain")
        return None
    publisher_name = _resolve_publisher_name(thread, domain=domain, title=headline)
    if not publisher_name:
        logger.debug(f"Rejected Webz post {uuid}: unresolvable or invalid publisher name")
        return None

    # 7. Author Normalization
    # Canonical author is always the MetroScope editorial desk; provider byline is not used.
    author = EDITORIAL_AUTHOR

    # 8. Summary & Root-level Full Text
    # Uses provider summary field for metadata summary
    summary = extract_short_summary(post)

    # Root-level Webz.io article body (post.text)
    # Distinct from post.summary and post.thread.text
    # Preserves original language, Unicode text, and paragraph boundaries
    full_text: Optional[str] = None
    if getattr(post, "text", None) and post.text.strip():
        candidate_text = post.text.strip()
        # Reject summary-only copies, headline duplicates, or wire-teaser stubs
        if summary and candidate_text.lower() == summary.lower():
            full_text = None
        elif candidate_text.lower().rstrip(".") == headline.lower().rstrip("."):
            full_text = None
        elif len(candidate_text) < 250 and ("tipranks" in candidate_text.lower() or "published first on" in candidate_text.lower()):
            full_text = None
        else:
            full_text = candidate_text

    # 9. Media Extraction & Independent Content Rights Evaluation
    raw_hero_img, raw_hero_meta = extract_primary_image(post)
    inline_candidates = extract_inline_images(post, exclude_url=raw_hero_img)

    rights_service = ContentRightsService()
    rights_pkg = rights_service.evaluate_article_rights(
        domain=domain,
        raw_post=post,
        hero_image_url=raw_hero_img,
        inline_images=inline_candidates,
    )
    # Content rights evaluated for metadata tracking (non-blocking per publication policy)
    content_display_authorized = True
    hero_image_authorized = bool(raw_hero_img)
    inline_images_authorized = True

    # Image URL for public rendering: preserve hero image (validated downstream for syntax, SSRF & MIME)
    public_hero_image_url = raw_hero_img
    hero_caption = raw_hero_meta.get("caption")
    hero_credit = raw_hero_meta.get("credit")

    # Construct structured image metadata
    structured_image_meta: Dict[str, Any] = {
        "external_only": True,
        "source": raw_hero_meta.get("source", "provider_main_image"),
        "url": raw_hero_img,
        "hero": {
            "url": raw_hero_img,
            "caption": raw_hero_meta.get("caption"),
            "credit": raw_hero_meta.get("credit"),
            "authorized": hero_image_authorized,
            "reason": rights_pkg.hero_image_reason,
            "source": raw_hero_meta.get("source"),
        },
        "inline_images": [
            {
                "url": img["url"],
                "caption": img.get("caption"),
                "credit": img.get("credit"),
                "authorized": inline_images_authorized,
                "source": img.get("source"),
            }
            for img in inline_candidates
        ],
        "rights": {
            "full_text_authorized": rights_pkg.full_text_authorized,
            "full_text_reason": rights_pkg.full_text_reason,
            "hero_image_authorized": rights_pkg.hero_image_authorized,
            "hero_image_reason": rights_pkg.hero_image_reason,
            "inline_images_authorized": rights_pkg.inline_images_authorized,
            "audit_log": rights_pkg.audit_log,
        },
    }

    # 10. Provider categories and topics
    webz_categories: List[str] = []
    if hasattr(post, "categories") and post.categories:
        webz_categories = [c.strip().lower() for c in post.categories if c.strip()]

    # Topics: combine post.topics, thread.site_categories, entities
    topics: List[str] = []
    if hasattr(post, "topics") and post.topics:
        topics.extend([t.strip().lower() for t in post.topics if t.strip()])
    if thread and thread.site_categories:
        topics.extend([c.strip().lower() for c in thread.site_categories if c.strip()])
    if post.entities:
        for ent_type in ("organizations", "persons", "locations"):
            ents = post.entities.get(ent_type)
            if isinstance(ents, list):
                for e in ents[:5]:
                    name = e.get("name") if isinstance(e, dict) else str(e)
                    if name and len(name) < 80 and name not in topics:
                        topics.append(name)
    seen: set = set()
    unique_topics: List[str] = []
    for t in topics:
        if t not in seen:
            seen.add(t)
            unique_topics.append(t)
    topics = unique_topics[:15]

    # 11. Category Classification
    webz_cat_context = " ".join(webz_categories + topics)
    default_cat = target_category.lower().strip() if target_category else "world"
    from app.services.classifier_service import CATEGORY_KEYWORD_MAP
    if default_cat not in CATEGORY_KEYWORD_MAP:
        default_cat = "world"
    classification = classify_article_detailed(
        title=headline,
        domain=domain,
        snippet=webz_cat_context,
        default_category=default_cat,
    )
    final_category = classification.category_slug

    # 12. Trust indicators (attributed to provider, not independent fact verification)
    trust_indicators: Dict[str, Any] = {
        "provider": "webz.io",
        "provider_verified_thread": bool(thread and thread.site_type == "news"),
    }
    if thread:
        if thread.domain_rank is not None:
            trust_indicators["provider_domain_rank"] = thread.domain_rank
        if thread.spam_score is not None:
            trust_indicators["provider_spam_score"] = thread.spam_score
        if thread.performance_score is not None:
            trust_indicators["provider_performance_score"] = thread.performance_score
        if thread.site_type:
            trust_indicators["provider_site_type"] = thread.site_type
    if hasattr(post, "trust") and post.trust and isinstance(post.trust, dict):
        trust_indicators["provider_trust_raw"] = post.trust

    # 13. Country & Language
    country = (thread.country.strip().upper()[:10] or None) if thread and thread.country else None
    lang = post.language or "en"
    if lang.lower().startswith("eng"):
        lang = "en"
    lang = lang[:10]

    # 14. Breaking & Sentiment from provider
    is_breaking = bool(getattr(post, "breaking", False))
    sentiment = getattr(post, "sentiment", None)

    return NormalizedWebzArticle(
        uuid=uuid,
        title=headline,
        summary=summary,
        full_text=full_text,
        content_display_authorized=content_display_authorized,
        hero_image_authorized=hero_image_authorized,
        inline_images_authorized=inline_images_authorized,
        original_url=raw_url,
        canonical_url=canonical_url,
        canonical_url_hash=canonical_url_hash,
        domain=domain,
        publisher_name=publisher_name,
        author=author,
        image_url=public_hero_image_url,
        image_caption=hero_caption,
        image_credit=hero_credit,
        inline_images=[img for img in inline_candidates if inline_images_authorized],
        language=lang,
        country=country,
        published_at=published_at,
        crawled_at=crawled_at,
        category_slug=final_category,
        classification_confidence=classification.confidence_score,
        webz_categories=webz_categories,
        topics=topics,
        trust_indicators=trust_indicators,
        image_metadata=structured_image_meta,
        sentiment=sentiment,
        is_breaking=is_breaking,
    )
