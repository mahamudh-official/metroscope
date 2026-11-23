import html
import re
import unicodedata
from typing import Optional, Set

# Known abbreviations and acronyms that should always remain uppercase in headlines
KNOWN_ACRONYMS: Set[str] = {
    "US", "USA", "UK", "EU", "UN", "NATO", "NASA", "FBI", "CIA", "FDA",
    "CDC", "EPA", "SEC", "DOJ", "FTC", "FCC", "IRS", "NTSB", "FAA", "DOD",
    "AI", "CEO", "CFO", "CTO", "COO", "GOP", "DNC", "RNC", "G7", "G20",
    "IMF", "WHO", "COP28", "COP29", "COVID", "COVID-19", "IPO", "EV", "GDP",
    "CPI", "PCE", "LLM", "AP", "AFP", "BBC", "NPR", "PBS", "CBS", "NBC",
    "ABC", "CNN", "MSNBC", "CNBC", "WSJ", "NYT", "MIT", "NIH", "DOA"
}

# Common lowercase words in title case (unless first or last word)
MINOR_WORDS: Set[str] = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "in", "on", "at",
    "to", "from", "by", "of", "with", "as", "into", "over", "after"
}


def fix_all_caps(text: str) -> str:
    """Repairs headlines written in screaming ALL CAPS while preserving standard acronyms."""
    if not text:
        return ""

    # Count letters to determine uppercase ratio
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return text

    upper_count = sum(1 for c in letters if c.isupper())
    ratio = upper_count / len(letters)

    # Only convert if at least 70% of characters are uppercase and length > 12
    if ratio < 0.70 or len(text) < 12:
        return text

    words = text.split()
    converted_words = []

    for idx, word in enumerate(words):
        # Extract leading/trailing punctuation if any
        prefix = ""
        suffix = ""
        core = word

        m_prefix = re.match(r"^([\"\'\(\[\{]+)", core)
        if m_prefix:
            prefix = m_prefix.group(1)
            core = core[len(prefix):]

        m_suffix = re.search(r"([\"\'\)\]\}\:\,\.\;\!\?]+)$", core)
        if m_suffix:
            suffix = m_suffix.group(1)
            core = core[:-len(suffix)]

        core_upper = core.upper()

        if core_upper in KNOWN_ACRONYMS:
            converted_words.append(prefix + core_upper + suffix)
        elif idx > 0 and idx < len(words) - 1 and core.lower() in MINOR_WORDS:
            converted_words.append(prefix + core.lower() + suffix)
        else:
            converted_words.append(prefix + core.capitalize() + suffix)

    return " ".join(converted_words)


def clean_encoding_artifacts(text: str) -> str:
    """Repairs common mojibake and encoding mangling."""
    if not text:
        return ""

    replacements = {
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€\x9d": '"',
        "â€": '"',
        "â€”": "—",
        "â€“": "–",
        "&nbsp;": " ",
        "\xa0": " ",
        "&#39;": "'",
        "&quot;": '"',
        "&amp;": "&",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


def clean_title(raw_title: str) -> str:
    """Cleans editorial headline titles, normalizes case, removes tags and trailing publisher branding."""
    if not raw_title:
        return ""

    # Unescape HTML entities
    title = html.unescape(raw_title).strip()

    # Repair encoding artifacts
    title = clean_encoding_artifacts(title)

    # Strip HTML script blocks and general HTML tags to eliminate stored XSS vectors
    title = re.sub(r"<script[^>]*>.*?</script>", "", title, flags=re.IGNORECASE | re.DOTALL)
    title = re.sub(r"<[^>]+>", "", title)

    # Strip media/promotional bracket tags: e.g. [VIDEO], (PHOTOS), [WATCH], (LIVE)
    title = re.sub(r"\[(?:video|photos?|watch|live|exclusive|breaking|update)\]", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\((?:video|photos?|watch|live|exclusive|breaking|update)\)", "", title, flags=re.IGNORECASE)

    # Strip common trailing publisher suffixes and promotional trailers:
    # e.g., "Fed Cuts Rates by 25 Bps | The Wall Street Journal"
    # or "Tech Rally Continues - Bloomberg"
    # or "Global Markets Update — Reuters"
    # or "Election Coverage | Watch Live"
    title = re.sub(r"\s+([\|\-\—\–]\s+(?:watch\s+live|watch|read\s+more|full\s+story|analysis|[A-Za-z0-9\.\s\&]+))$", "", title, flags=re.IGNORECASE)

    # Normalize excessive punctuation (e.g. "???" -> "?", "!!!" -> "!")
    title = re.sub(r"\?{2,}", "?", title)
    title = re.sub(r"\!{2,}", "!", title)

    # Fix tokenization spacing around punctuation (e.g. " , " -> ", ")
    title = re.sub(r"\s+([,.;:?!])", r"\1", title)
    title = re.sub(r"\s+'(s|t|re|ve|ll|d)\b", r"'\1", title, flags=re.IGNORECASE)

    # Normalize multiple whitespace characters
    title = re.sub(r"\s+", " ", title)

    # Repair screaming ALL CAPS headlines
    title = fix_all_caps(title.strip())

    return title.strip()


def generate_slug(text: str, max_length: int = 120) -> str:
    """Generates a clean URL slug from article title."""
    if not text:
        return "untitled-article"

    # Strip HTML script blocks first
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # Normalize unicode to ASCII
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")

    # Lowercase and replace non-alphanumeric with hyphen
    slug = re.sub(r"[^\w\s-]", "", ascii_text.lower()).strip()
    slug = re.sub(r"[-\s]+", "-", slug)

    if not slug:
        slug = "article"

    return slug[:max_length].rstrip("-")


def clean_description(raw_desc: Optional[str]) -> Optional[str]:
    """Cleans, sanitizes, and normalizes brief discovery descriptions or snippets."""
    if not raw_desc:
        return None

    desc = html.unescape(raw_desc).strip()
    desc = desc.replace("\u200b", "").replace("\ufeff", "")
    desc = clean_encoding_artifacts(desc)

    # Strip HTML script blocks and tags
    desc = re.sub(r"<script[^>]*>.*?</script>", "", desc, flags=re.IGNORECASE | re.DOTALL)
    desc = re.sub(r"<[^>]+>", "", desc)

    # Normalize RSS ellipsis markers
    desc = desc.replace("[\u2026]", "...").replace("[...]", "...")

    # Remove common read-more or tracker suffixes
    desc = re.sub(r"\s*(?:The post .+ appeared first on .+|Read more\.\.\.|Continue reading\.\.\.|View full post).*$", "", desc, flags=re.IGNORECASE)

    # Normalize whitespace
    desc = re.sub(r"\s+", " ", desc).strip()

    if not desc:
        return None

    # Gracefully truncate if too long (max 400 chars)
    if len(desc) > 400:
        truncated = desc[:400]
        # Try to break at last period or word boundary
        last_period = truncated.rfind(". ")
        if last_period > 200:
            desc = truncated[:last_period + 1]
        else:
            last_space = truncated.rfind(" ")
            if last_space > 200:
                desc = truncated[:last_space] + "..."
            else:
                desc = truncated + "..."

    return desc


# Canonical editorial author for every MetroScope article. Original publisher/source
# attribution is stored separately (publisher_name / source) and is never affected.
EDITORIAL_AUTHOR = "MetroScope News Desk"


VERIFIED_PUBLISHER_MAP = {
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
    "markets.businessinsider.com": "Business Insider",
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
    "skooknews.com": "Skook News",
    "qazinform.com": "Qazinform",
    "inform.kz": "Qazinform",
    "weltwoche.ch": "Die Weltwoche",
    "vietnam.vn": "Vietnam.vn",
    "nasa.gov": "NASA",
    "noaa.gov": "NOAA",
    "cdc.gov": "CDC",
    "whitehouse.gov": "The White House",
}

GENERIC_AUTHOR_NAMES = {
    "admin", "administrator", "editor", "editorial", "editorial desk",
    "editorial team", "staff", "staff writer", "staff reporter", "news",
    "newsroom", "news desk", "desk", "team", "unknown", "anonymous", "by",
    "contributor", "webmaster", "redaktion", "author", "guest", "user",
    "blogger", "mod", "moderator", "system", "info", "support", "tipranks",
    "reuters", "associated press", "ap", "pr newswire", "business wire",
    "globe newswire", "afp", "bloomberg", "dow jones"
}

SPAM_OR_SCRAPER_DOMAINS = {
    "alltdesign.com",
}


def is_spam_or_scraper_domain(domain: Optional[str]) -> bool:
    """Detects spam scraper farms, RSS aggregators, and throwaway subdomains."""
    if not domain or not isinstance(domain, str):
        return True
    dom = domain.lower().strip()
    if dom.startswith("www."):
        dom = dom[4:]
    for spam in SPAM_OR_SCRAPER_DOMAINS:
        if dom == spam or dom.endswith(f".{spam}"):
            return True
    # Subdomains with long alphanumeric randomized prefixes (e.g. sherwoodparktopcommercia406907)
    parts = dom.split(".")
    if len(parts) >= 3 and re.search(r"[a-z]{10,}\d{4,}", parts[0]):
        return True
    return False


def normalize_author_name(
    raw_author: Optional[str],
    title: Optional[str] = None,
    publisher: Optional[str] = None,
    domain: Optional[str] = None,
) -> Optional[str]:
    """Validates and normalizes provider author field.
    
    Rules:
    - Must originate from an actual provider author field.
    - Never uses article title, publisher name, domain, URL, or generic labels as author.
    - Rejects email addresses and handles (noreply@, info@, etc.).
    - Missing or invalid author returns None.
    """
    if not raw_author or not isinstance(raw_author, str) or not raw_author.strip():
        return None

    author = html.unescape(raw_author).strip()
    author = clean_encoding_artifacts(author)

    # Strip leading "By", "by", "Written by", "Author:"
    author = re.sub(r"^(?:by|written by|author:?)\s+", "", author, flags=re.IGNORECASE).strip()

    # Reject if length is out of reasonable range for a human name
    if len(author) < 2 or len(author) > 100:
        return None

    # Reject email addresses or strings containing '@'
    if "@" in author:
        return None

    # Reject URLs, protocols, or top-level domain extensions
    if re.search(r"https?://|www\.|\.(?:com|org|net|gov|edu|io|co|vn|ir|de|uk|ca|info|biz)\b", author, re.I):
        return None

    # Reject if author equals or is contained within the article title (or title within author)
    if title and len(title.strip()) > 10:
        clean_t = title.strip().lower()
        clean_a = author.strip().lower()
        if clean_a == clean_t or (len(clean_a) > 12 and (clean_a in clean_t or clean_t in clean_a)):
            return None

    # Reject if author equals publisher name or domain
    clean_lower = author.lower().strip()
    if publisher and clean_lower == publisher.lower().strip():
        return None
    if domain:
        clean_dom = domain.lower().strip()
        if clean_dom.startswith("www."):
            clean_dom = clean_dom[4:]
        if clean_lower == clean_dom or clean_lower == clean_dom.split(".")[0]:
            return None

    # Reject generic editorial roles, desk handles, or wire service names
    if clean_lower in GENERIC_AUTHOR_NAMES:
        return None

    if re.match(r"^(?:unknown|redaktion|contributor|editorial|staff|team|blogger|web\s*editor|editor|admin|administrator)\b", clean_lower):
        return None

    # Reject strings with parentheses containing email or generic descriptors
    if re.search(r"\(.*(?:@|noreply|editor|centre|center|redaktion|admin).*\)", author, re.I):
        return None

    # Author must contain at least one word character / letter
    if not any(c.isalpha() for c in author):
        return None

    return author.strip()


def normalize_publisher_name(
    raw_name: Optional[str],
    domain: Optional[str] = None,
    title: Optional[str] = None,
) -> Optional[str]:
    """Resolves and normalizes legitimate publisher display names.
    
    Rules:
    - Never uses headline, URL path, homepage label or arbitrary fallback as publisher name.
    - Strips marketing taglines and trailing slogans.
    - Resolves known verified publisher names from domain.
    - Rejects spam/scraper domains and unresolvable publishers (returns None).
    """
    clean_dom = domain.lower().strip() if domain else ""
    if clean_dom.startswith("www."):
        clean_dom = clean_dom[4:]

    # Check if domain is a known spam/scraper network
    if clean_dom and is_spam_or_scraper_domain(clean_dom):
        return None

    candidate = ""
    if raw_name and isinstance(raw_name, str) and raw_name.strip():
        name = html.unescape(raw_name).strip()
        name = clean_encoding_artifacts(name)

        # Check if name contains or ends with homepage suffix (e.g. " - homepage")
        if re.search(r"\s*[-–—|/]\s*home(?:page)?\b", name, flags=re.IGNORECASE) or name.lower().endswith(" homepage"):
            name = ""
        # Check if name duplicates or contains headline
        elif title and len(title.strip()) > 10:
            clean_t = title.strip().lower()
            clean_n = name.strip().lower()
            if clean_n == clean_t or clean_t.startswith(clean_n) or clean_n.startswith(clean_t) or (len(clean_n) > 20 and clean_n in clean_t):
                name = ""
        # Check if name is an RSS/Atom feed label or URL
        elif re.search(r"\b(?:rss\s*feed|atom\s*feed)\b|https?://|www\.", name, flags=re.IGNORECASE):
            name = ""
        else:
            # Handle pipe-separated publisher tags, e.g. "Slogan | Brand" or "Brand | Slogan"
            if "|" in name:
                parts = [p.strip() for p in name.split("|") if p.strip()]
                if len(parts) == 2:
                    p1, p2 = parts[0], parts[1]
                    if len(p2) <= 30 and (len(p1) > len(p2) or re.search(r"\b(?:news|notizie|noticias|новини|новости|ultime)\b", p1, re.I)):
                        name = p2
                    elif len(p1) <= 30:
                        name = p1
                    else:
                        name = p1

            # Strip trailing slogans separated by dash or em-dash (e.g. "The Open University of Sri Lanka – Open and Distance Learning...")
            if re.search(r"\s*[-–—]\s*", name):
                dash_parts = re.split(r"\s*[-–—]\s*", name)
                if len(dash_parts) >= 2 and len(dash_parts[0]) >= 3:
                    if len(dash_parts[1]) > 20 or re.search(r"\b(?:learning|opportunities|source|breaking|latest|home\s*page|official|newspaper)\b", dash_parts[1], re.I):
                        name = dash_parts[0]

            # Strip trailing colon descriptions (e.g. "News Title: самые свежие, актуальные новости...")
            if ":" in name:
                colon_parts = [c.strip() for c in name.split(":") if c.strip()]
                if len(colon_parts) >= 2 and len(colon_parts[0]) >= 3 and len(colon_parts[1]) > 15:
                    name = colon_parts[0]

            # Strip common trailing marketing slogans and taglines
            name = re.sub(
                r"\s*[-–—|]\s*(?:Your #1 Source.*|Latest News.*|Breaking News.*|Nền tảng.*|get the latest news.*|The ultimate source.*|Official site.*|Home of.*|RSS feed.*)$",
                "",
                name,
                flags=re.IGNORECASE,
            ).strip()
            name = re.sub(r"\s*[-–—|]\s*$", "", name).strip()

        if name and len(name) >= 2:
            candidate = name

    # Verified domain lookup takes precedence if available or if candidate is empty
    if clean_dom in VERIFIED_PUBLISHER_MAP:
        return VERIFIED_PUBLISHER_MAP[clean_dom]

    if candidate:
        return candidate

    # If domain is available and valid, format clean domain as publisher
    if clean_dom and "." in clean_dom:
        parts = clean_dom.split(".")
        if len(parts) >= 2 and parts[-2] not in {"co", "com", "net", "org"}:
            return parts[-2].capitalize()

    return None
