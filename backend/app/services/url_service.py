import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Query parameters commonly used for tracking that should be stripped for canonicalization
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "fbclid",
    "gclid",
    "gclsrc",
    "dclid",
    "msclkid",
    "zanpid",
    "ref",
    "ref_src",
    "ocid",
    "ncid",
    "CMP",
    "at_medium",
    "at_campaign",
    "_hsenc",
    "_hsmi",
    "mc_cid",
    "mc_eid",
}


def normalize_url(url: str) -> str:
    """Normalizes an article URL to its canonical form for deduplication.
    
    - Lowercases scheme and network location (hostname).
    - Removes tracking/ad query parameters (utm_*, fbclid, etc.).
    - Sorts remaining query parameters.
    - Strips fragments and trailing slashes.
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()
    try:
        parsed = urlparse(url)
    except Exception:
        return ""

    # Enforce safe HTTP / HTTPS schemes only (prevent javascript:, file:, data:, etc.)
    scheme = (parsed.scheme or "https").lower()
    if scheme not in ("http", "https"):
        return ""

    netloc = parsed.netloc.lower()
    if not netloc:
        return ""

    # Remove standard port if default for scheme
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    # Clean path (strip redundant trailing slash if path != "/")
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    # Filter tracking query parameters
    query_params = []
    if parsed.query:
        for key, val in parse_qsl(parsed.query, keep_blank_values=False):
            if key.lower() not in TRACKING_PARAMS and not key.lower().startswith("utm_"):
                query_params.append((key, val))
        query_params.sort(key=lambda x: x[0])

    clean_query = urlencode(query_params)

    # Do not include fragments (#...) in canonical URLs
    normalized = urlunparse((scheme, netloc, path, "", clean_query, ""))
    return normalized


def compute_url_hash(url: str) -> str:
    """Returns SHA-256 hex digest of the normalized canonical URL."""
    clean_url = normalize_url(url)
    return hashlib.sha256(clean_url.encode("utf-8")).hexdigest()


def extract_domain(url: str) -> str:
    """Extracts a clean domain name without leading 'www.' or port numbers."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc or parsed.path
        # Strip port
        domain = netloc.split(":")[0].lower()
        # Strip www.
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""
