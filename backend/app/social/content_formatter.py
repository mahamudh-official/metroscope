"""Platform-specific content formatting for automated social publishing.

Adheres strictly to editorial and legal constraints:
- Uses only existing article metadata (headline, summary, source attribution).
- Outbound link back to the canonical MetroScope discovery page.
- No scraping or reproduction of full article bodies.
- Deterministic text composition with zero hallucinated facts or invented quotes.
- Strict X (Twitter) URL-weighting (23 chars per URL) and Twitter Text v3 character
  weighting rules.
"""

import re
from typing import Optional
import unicodedata
from app.core.config import settings
from app.models.article import NewsArticle
from app.services.normalizer_service import EDITORIAL_AUTHOR

# Twitter Text v3 Configuration constants (from official config/v3.json)
TWITTER_TEXT_MAX_WEIGHTED_LENGTH: int = 280
TWITTER_TEXT_TRANSFORMED_URL_LENGTH: int = 23
TWITTER_TEXT_DEFAULT_WEIGHT: int = 2
TWITTER_TEXT_SCALE: int = 100

TWITTER_TEXT_V3_RANGES = [
    (0, 4351, 1),        # Basic Latin, Latin-1, Greek, Cyrillic, Hebrew, Arabic, Indic (Bengali, Devanagari, etc.)
    (8192, 8205, 1),    # General Punctuation (spaces, ZWNJ, ZWJ)
    (8208, 8223, 1),    # Dashes, quotes
    (8242, 8247, 1),    # Primes
]

# Standard URL regex matching http:// or https:// schemes
_URL_REGEX = re.compile(
    r'(?:https?://)'
    r'(?:[a-zA-Z0-9-]+\.)+[a-zA-Z0-9]{2,}'
    r'(?::\d+)?'
    r'(?:/[^\s<>"\']*)*',
    re.IGNORECASE
)


def calculate_x_post_weighted_length(text: str) -> int:
    """Calculates effective tweet length according to the official Twitter Text v3 specification.

    Rules:
    - Normalizes text via Unicode NFC.
    - Matches all valid HTTP/HTTPS URLs; each distinct URL is counted as exactly 23 weighted units.
    - Non-URL characters are weighted according to official Unicode range tables:
      - Code points in 0..4351, 8192..8205, 8208..8223, 8242..8247 weight = 1.
      - All other characters (CJK, Emojis, supplementary symbols) weight = 2.
    """
    if not text:
        return 0

    normalized = unicodedata.normalize("NFC", text)
    matches = list(_URL_REGEX.finditer(normalized))

    total_weight = 0
    last_idx = 0

    for m in matches:
        start, end = m.span()
        url_text = normalized[start:end]
        # Strip trailing punctuation often attached to URLs in prose
        while url_text and url_text[-1] in ".,!?:;)":
            url_text = url_text[:-1]
            end -= 1

        # Weight non-URL text before this URL
        for ch in normalized[last_idx:start]:
            cp = ord(ch)
            weight = TWITTER_TEXT_DEFAULT_WEIGHT
            for r_start, r_end, r_w in TWITTER_TEXT_V3_RANGES:
                if r_start <= cp <= r_end:
                    weight = r_w
                    break
            total_weight += weight

        # Fixed URL weight
        total_weight += TWITTER_TEXT_TRANSFORMED_URL_LENGTH
        last_idx = end

    # Weight remaining non-URL text
    for ch in normalized[last_idx:]:
        cp = ord(ch)
        weight = TWITTER_TEXT_DEFAULT_WEIGHT
        for r_start, r_end, r_w in TWITTER_TEXT_V3_RANGES:
            if r_start <= cp <= r_end:
                weight = r_w
                break
        total_weight += weight

    return total_weight


def validate_x_post_length(text: str, max_chars: int = 280) -> bool:
    """Validates that an X post does not exceed the allowed weighted limit (280)."""
    return calculate_x_post_weighted_length(text) <= max_chars


def get_article_url(slug: str, base_url: Optional[str] = None) -> str:
    """Constructs the canonical MetroScope article URL."""
    root = (base_url or settings.SITE_URL or "https://themetroscope.com").rstrip("/")
    if not root or "localhost" in root.lower() or "127.0.0.1" in root:
        root = "https://themetroscope.com"
    return f"{root}/article/{slug}"


def format_category_hashtag(category_name: Optional[str]) -> str:
    """Formats category name into a clean PascalCase hashtag."""
    if not category_name:
        return "#News"
    clean = "".join(word.capitalize() for word in category_name.split())
    return f"#{clean}"


def format_facebook_caption(article: NewsArticle) -> str:
    """Formats the Facebook post caption strictly according to the required structure:

    [Article Title]

    Read more in the comments.
    """
    headline = (article.title or "").strip()
    return f"{headline}\n\nRead more in the comments."


def format_facebook_first_comment(
    article: NewsArticle, base_url: Optional[str] = None
) -> str:
    """Formats the first comment for a Facebook post:

    [Article Title]
    [Website Article URL]
    """
    headline = (article.title or "").strip()
    article_url = get_article_url(article.slug, base_url)
    return f"{headline}\n{article_url}"


def format_facebook_post(
    article: NewsArticle, base_url: Optional[str] = None
) -> str:
    """Formats news discovery metadata for a Facebook post caption.

    Structure:
    [Article Title]

    Read more in the comments.
    """
    return format_facebook_caption(article)


def format_x_post(
    article: NewsArticle,
    base_url: Optional[str] = None,
    max_chars: int = 280,
) -> str:
    """Formats news discovery metadata for an X (Twitter) post.

    Strictly calculates length using official Twitter Text v3 URL and character
    weighting rules. Preserves the canonical MetroScope discovery URL (weighted at 23)
    and pascal-case hashtags, dynamically budgeting and truncating the headline
    to ensure the combined post never exceeds max_chars weighted characters.
    """
    article_url = get_article_url(article.slug, base_url)
    category_tag = format_category_hashtag(
        article.category.name if article.category else None
    )

    prefix = ""
    if article.is_breaking:
        prefix = "🚨 BREAKING: "
    elif article.is_trending:
        prefix = "🔥 TRENDING: "

    suffix = f"\n\nBy {EDITORIAL_AUTHOR}\n{article_url} {category_tag} #News"
    headline = article.title.strip()

    post = f"{prefix}{headline}{suffix}".strip()
    if calculate_x_post_weighted_length(post) <= max_chars:
        return post

    # Truncate headline until weighted length conforms to max_chars
    ellipsis = "..."
    while headline and calculate_x_post_weighted_length(f"{prefix}{headline}{ellipsis}{suffix}".strip()) > max_chars:
        headline = headline[:-1]

    headline = headline.rstrip()
    return f"{prefix}{headline}{ellipsis}{suffix}".strip()
