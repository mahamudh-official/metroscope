"""News Quality Scoring Service for MetroScope.

Evaluates discovery metadata (title, snippet, publisher domain, publication timestamp,
URL cleanliness, and taxonomy match strength) to compute a normalized quality score (0-100).

IMPORTANT SAFEGUARDS:
- The quality score is a technical metadata heuristic, NOT proof of factual accuracy.
- MetroScope never labels a high quality score as 'verified truth' or 'editorial endorsement'.
"""

import datetime
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# Reputable news agencies, broadcast networks, and journalistic publications
ESTABLISHED_NEWS_DOMAINS: Set[str] = {
    # Core Wire Services & Tier-1 Agencies
    "reuters.com",
    "apnews.com",
    "afp.com",
    "upi.com",
    # Major National & International Dailies
    "nytimes.com",
    "wsj.com",
    "washingtonpost.com",
    "bloomberg.com",
    "usatoday.com",
    "theguardian.com",
    "independent.co.uk",
    "telegraph.co.uk",
    "latimes.com",
    "chicagotribune.com",
    "bostonglobe.com",
    "sfchronicle.com",
    "seattletimes.com",
    "dallasnews.com",
    "denverpost.com",
    "startribune.com",
    "csmonitor.com",
    "newsweek.com",
    # Broadcast & Public Media
    "bbc.com",
    "bbc.co.uk",
    "npr.org",
    "cbsnews.com",
    "nbcnews.com",
    "abcnews.go.com",
    "cnn.com",
    "foxnews.com",
    "pbs.org",
    "aljazeera.com",
    "msnbc.com",
    "c-span.org",
    # Politics & Policy
    "thehill.com",
    "politico.com",
    "axios.com",
    "rollcall.com",
    "nationalreview.com",
    "thebulwark.com",
    "motherjones.com",
    "salon.com",
    "realclearpolitics.com",
    "propublica.org",
    "theatlantic.com",
    "time.com",
    # Business, Markets & Economics
    "economist.com",
    "ft.com",
    "forbes.com",
    "marketwatch.com",
    "barrons.com",
    "cnbc.com",
    "fortune.com",
    "businessinsider.com",
    "investors.com",
    "thestreet.com",
    "kiplinger.com",
    "fastcompany.com",
    "inc.com",
    # Technology & Digital Culture
    "theverge.com",
    "techcrunch.com",
    "wired.com",
    "arstechnica.com",
    "engadget.com",
    "zdnet.com",
    "cnet.com",
    "venturebeat.com",
    "mashable.com",
    "gizmodo.com",
    "tomshardware.com",
    "techradar.com",
    "pcgamer.com",
    # Science & Astronomy
    "scientificamerican.com",
    "space.com",
    "nationalgeographic.com",
    "nature.com",
    "sciencenews.org",
    "newscientist.com",
    "phys.org",
    "eurekalert.org",
    "livescience.com",
    "popularmechanics.com",
    "smithsonianmag.com",
    "nasa.gov",
    # Health, Medicine & Wellness
    "statnews.com",
    "medicalnewstoday.com",
    "healthline.com",
    "webmd.com",
    "medscape.com",
    "nih.gov",
    "cdc.gov",
    "who.int",
    "mayoclinic.org",
    "hopkinsmedicine.org",
    # Environment & Climate
    "insideclimatenews.org",
    "earth.com",
    "mongabay.com",
    "grist.org",
    "yaleclimateconnections.org",
    "epa.gov",
    # Sports
    "espn.com",
    "theathletic.com",
    "cbssports.com",
    "nbcsports.com",
    "si.com",
    "bleacherreport.com",
    "sportingnews.com",
    "nfl.com",
    "nba.com",
    "mlb.com",
    "nhl.com",
    # Entertainment & Culture
    "variety.com",
    "hollywoodreporter.com",
    "deadline.com",
    "rollingstone.com",
    "billboard.com",
    "ew.com",
    "avclub.com",
    "ign.com",
    "pitchfork.com",
    "vulture.com",
}

# Recognized high-trust TLDs
HIGH_TRUST_TLDS: Set[str] = {".gov", ".edu", ".mil"}

# Clickbait and promotional patterns that reduce quality score
CLICKBAIT_PATTERNS = [
    re.compile(r"\b(you won'?t believe|shocking|mind-blowing|jaw-dropping)\b", re.IGNORECASE),
    re.compile(r"\b(\d+\s+reasons why|\d+\s+things you)\b", re.IGNORECASE),
    re.compile(r"\b(buy now|discount|promo code|sale ends|limited time offer)\b", re.IGNORECASE),
    re.compile(r"\b(act fast|click here|miracle cure|secret revealed)\b", re.IGNORECASE),
    re.compile(r"\b(free shipping|lowest price|cheap|deals? today)\b", re.IGNORECASE),
]


@dataclass
class QualityWeights:
    """Configurable scoring weights summing to 100."""
    title_completeness: float = 25.0
    snippet_availability: float = 15.0
    source_reputation: float = 20.0
    timestamp_validity: float = 15.0
    url_validity: float = 10.0
    classification_confidence: float = 15.0


@dataclass
class QualityAssessment:
    """Result of quality scoring evaluation."""
    score: float  # Normalized 0.0 - 100.0
    factor_scores: Dict[str, float] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


class QualityScoringService:
    """Deterministic, rule-based metadata quality scoring engine."""

    def __init__(self, weights: Optional[QualityWeights] = None):
        self.weights = weights or QualityWeights()

    def score_article(
        self,
        title: str,
        canonical_url: str,
        domain: Optional[str] = None,
        snippet: Optional[str] = None,
        published_at: Optional[datetime.datetime] = None,
        category_confidence: int = 0,
        now: Optional[datetime.datetime] = None,
    ) -> QualityAssessment:
        """Evaluates metadata dimensions and computes a normalized 0-100 score."""
        current_time = now or datetime.datetime.now(datetime.timezone.utc)
        reasons: List[str] = []
        factors: Dict[str, float] = {}

        # 1. Title Completeness & Formatting (max: self.weights.title_completeness)
        title_factor = self._evaluate_title(title, reasons)
        factors["title_completeness"] = title_factor * self.weights.title_completeness

        # 2. Description / Snippet Availability (max: self.weights.snippet_availability)
        snippet_factor = self._evaluate_snippet(snippet, reasons)
        factors["snippet_availability"] = snippet_factor * self.weights.snippet_availability

        # 3. Source Validity & Reputation (max: self.weights.source_reputation)
        source_factor = self._evaluate_source(domain, reasons)
        factors["source_reputation"] = source_factor * self.weights.source_reputation

        # 4. Publication Timestamp Validity (max: self.weights.timestamp_validity)
        ts_factor = self._evaluate_timestamp(published_at, current_time, reasons)
        factors["timestamp_validity"] = ts_factor * self.weights.timestamp_validity

        # 5. URL Validity & Cleanliness (max: self.weights.url_validity)
        url_factor = self._evaluate_url(canonical_url, reasons)
        factors["url_validity"] = url_factor * self.weights.url_validity

        # 6. Category Classification Confidence (max: self.weights.classification_confidence)
        cat_factor = self._evaluate_classification(category_confidence, reasons)
        factors["classification_confidence"] = cat_factor * self.weights.classification_confidence

        raw_score = sum(factors.values())
        normalized_score = max(0.0, min(100.0, round(raw_score, 1)))

        return QualityAssessment(
            score=normalized_score,
            factor_scores=factors,
            reasons=reasons,
        )

    def _evaluate_title(self, title: str, reasons: List[str]) -> float:
        """Scores title quality based on length, caps ratio, and clickbait absence."""
        if not title or not title.strip():
            reasons.append("Missing title")
            return 0.0

        clean = title.strip()
        length = len(clean)

        # Baseline length score
        if length < 15:
            reasons.append(f"Title too short ({length} chars)")
            return 0.2
        elif 25 <= length <= 180:
            score = 1.0
        elif length < 25:
            score = 0.6
        elif length <= 250:
            score = 0.8
        else:
            reasons.append("Title unusually long")
            score = 0.5

        # Check ALL-CAPS screaming titles
        alpha_chars = [c for c in clean if c.isalpha()]
        if len(alpha_chars) >= 15:
            caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if caps_ratio > 0.65:
                reasons.append(f"Excessive capitalization ({caps_ratio:.0%})")
                score = max(0.2, score - 0.4)

        # Check clickbait/promotional markers
        for pattern in CLICKBAIT_PATTERNS:
            if pattern.search(clean):
                reasons.append("Promotional or clickbait phrasing detected")
                score = max(0.1, score - 0.5)
                break

        return score

    def _evaluate_snippet(self, snippet: Optional[str], reasons: List[str]) -> float:
        """Scores snippet presence and depth."""
        if not snippet or not snippet.strip():
            reasons.append("Snippet missing")
            return 0.2

        clean = snippet.strip()
        if len(clean) >= 60:
            return 1.0
        elif len(clean) >= 25:
            return 0.7
        return 0.4

    def _evaluate_source(self, domain: Optional[str], reasons: List[str]) -> float:
        """Scores source publisher validity and reputation."""
        if not domain or not domain.strip():
            reasons.append("Unknown publisher domain")
            return 0.2

        dom = domain.lower().strip()

        # Known established journalistic institutions
        if any(dom == est or dom.endswith(f".{est}") for est in ESTABLISHED_NEWS_DOMAINS):
            return 1.0

        # Government and educational institutions
        if any(dom.endswith(tld) for tld in HIGH_TRUST_TLDS):
            return 0.95

        # Standard commercial or organizational news domain
        if dom.endswith((".com", ".org", ".net", ".edu", ".gov", ".co.uk", ".io", ".news")):
            return 0.75

        # Unknown or unusual TLD
        reasons.append(f"Uncommon TLD for domain: {dom}")
        return 0.5

    def _evaluate_timestamp(
        self,
        published_at: Optional[datetime.datetime],
        current_time: datetime.datetime,
        reasons: List[str],
    ) -> float:
        """Scores timestamp recency and validity."""
        if not published_at:
            reasons.append("Missing publication timestamp")
            return 0.3

        pub_utc = (
            published_at
            if published_at.tzinfo is not None
            else published_at.replace(tzinfo=datetime.timezone.utc)
        )
        now_utc = (
            current_time
            if current_time.tzinfo is not None
            else current_time.replace(tzinfo=datetime.timezone.utc)
        )
        delta_seconds = (now_utc - pub_utc).total_seconds()

        # Timestamp in the future (>10 min drift)
        if delta_seconds < -600:
            reasons.append(f"Future timestamp detected ({delta_seconds:.0f}s ahead)")
            return 0.1

        # Very fresh (within 24 hours)
        if 0 <= delta_seconds <= 86400:
            return 1.0

        # Within 3 days
        if delta_seconds <= 86400 * 3:
            return 0.85

        # Within 7 days
        if delta_seconds <= 86400 * 7:
            return 0.70

        # Stale news (> 7 days)
        reasons.append("Publication date older than 7 days")
        return 0.4

    def _evaluate_url(self, canonical_url: str, reasons: List[str]) -> float:
        """Scores URL safety, HTTPS protocol, and clean pathing."""
        if not canonical_url or not canonical_url.strip():
            reasons.append("Missing canonical URL")
            return 0.0

        url = canonical_url.strip().lower()
        score = 0.5

        if url.startswith("https://"):
            score += 0.4
        elif url.startswith("http://"):
            reasons.append("Insecure HTTP protocol")
            score += 0.1

        # Check for lingering tracking tokens
        if any(token in url for token in ("utm_", "fbclid", "gclid", "sessionid")):
            reasons.append("Tracking tokens present in canonical URL")
            score = max(0.1, score - 0.2)
        else:
            score += 0.1

        return min(1.0, score)

    def _evaluate_classification(self, category_confidence: int, reasons: List[str]) -> float:
        """Scores categorization confidence."""
        if category_confidence >= 6:
            return 1.0
        elif category_confidence >= 4:
            return 0.85
        elif category_confidence >= 2:
            return 0.70
        else:
            reasons.append("Low categorization confidence (fallback applied)")
            return 0.45
