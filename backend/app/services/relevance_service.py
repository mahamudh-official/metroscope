"""News Relevance and Filtering Service for MetroScope.

Ensures the discovery feed remains focused on high-quality news for a US-focused audience
while preserving significant international reporting (geopolitics, global economy, diplomacy)
and strictly rejecting commercial product listings, e-commerce spam, and malformed records.
"""

import re
from dataclasses import dataclass
from typing import Optional, Set

# Commercial e-commerce and shopping spam patterns to filter out
# Contextualized to distinguish commercial intent from legitimate business/retail reporting
COMMERCIAL_SPAM_PATTERNS = [
    # Explicit e-commerce call to action & promotional codes
    re.compile(
        r"\b(buy now|shop now|order today|order now|discount code|promo code|coupon code|voucher code)\b",
        re.IGNORECASE,
    ),
    # Shipping & price promotions (avoiding financial 'save $X billion' phrases)
    re.compile(
        r"\b(free shipping|lowest price|unbeatable price|save up to \$\d+|save \$\d+\s+(?:off|today|on))\b",
        re.IGNORECASE,
    ),
    # Commercial shopping deal markers (avoiding corporate M&A deals)
    re.compile(
        r"\b(best deals? (?:today|now|online|on amazon|this week|for prime day)|shop the best deals?|best shopping deals?)\b",
        re.IGNORECASE,
    ),
    # Foreign or raw product spec catalog strings
    re.compile(
        r"\b(thermom[eè]tre|guidon\s+\d+|waterproof\s+\d+mm|taille\s+[smlxl]+)\b",
        re.IGNORECASE,
    ),
    # E-commerce retail product listings with commercial action/pricing context
    re.compile(
        r"\b(?:buy|shop|order|discount on|sale on|deals? on)\s+(?:t-shirts?|hoodies?|sneakers?|handbags?|shoes?|cases? for iphone)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:t-shirts?|hoodies?|sneakers?|handbags?)\s+(?:for sale|in stock|under \$\d+|at \$\d+|clearance)\b",
        re.IGNORECASE,
    ),
    # Online casino, gambling, betting, and slot affiliate spam
    re.compile(
        r"\b(online\s*casinos?|casino\s*sites?|real\s*money\s*(?:casino|slots?|gaming)|gambling\s*sites?|sportsbook|sports\s*betting|betting\s*sites?|poker\s*online|slot\s*machines?|free\s*spins|deposit\s*bonus|wagering\s*requirements?|sweet\s*bonanza|jackpot\s*city|crypto\s*casino)\b",
        re.IGNORECASE,
    ),
    # Affiliate promotional listicles & advertorials
    re.compile(
        r"\b(?:top\s*\d+\s*(?:best|real\s*money|casino|gambling)|best\s*(?:online\s*)?casino\s*sites?|top\s*10\+\s*casino)\b",
        re.IGNORECASE,
    ),
]

# High-salience US civic, institutional, and geographical keywords
US_RELEVANCE_KEYWORDS: Set[str] = {
    # Federal & Political
    "congress", "senate", "senator", "house of representatives", "white house",
    "capitol hill", "supreme court", "president", "presidential", "pentagon",
    "fbi", "cia", "doj", "state department", "treasury", "federal reserve", "fed",
    "biden", "trump", "harris", "democrat", "democratic", "republican", "gop",
    "bipartisan", "legislation", "executive order", "veto", "governor",
    # Economy & Culture
    "wall street", "nasdaq", "dow jones", "s&p 500", "nyse", "silicon valley",
    "super bowl", "nfl", "nba", "mlb", "nhl", "hollywood", "broadway",
    # States & Major Metros
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio", "oklahoma",
    "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming",
    "los angeles", "chicago", "houston", "phoenix", "philadelphia", "san antonio",
    "san diego", "dallas", "austin", "miami", "atlanta", "seattle", "boston",
}

# High-salience International keywords of vital interest to US readers
INTERNATIONAL_SIGNIFICANCE_KEYWORDS: Set[str] = {
    "united nations", "un security council", "nato", "g7", "g20", "european union",
    "imf", "world bank", "who", "world trade organization", "wto",
    "ukraine", "russia", "china", "taiwan", "middle east", "israel", "gaza",
    "iran", "north korea", "south korea", "britain", "uk", "france", "germany",
    "japan", "india", "canada", "mexico", "syria", "yemen",
    "foreign policy", "diplomacy", "ambassador", "treaty", "sanctions",
    "ceasefire", "peace talks", "summit", "geopolitics", "bilateral", "global trade",
    "opec", "crude oil", "central bank", "tariffs", "war", "military strike",
}


@dataclass
class FilterDecision:
    """Outcome of relevance and quality admissibility screening."""
    is_admissible: bool
    filter_reason: Optional[str] = None
    relevance_type: str = "us_domestic"  # "us_domestic", "international_significance", "filtered"


class RelevanceService:
    """Evaluates discovery records for audience relevance, filtering spam and noise."""

    def __init__(self, min_quality_threshold: float = 30.0):
        self.min_quality_threshold = min_quality_threshold

    def evaluate_article(
        self,
        title: str,
        country: Optional[str] = None,
        language: Optional[str] = None,
        domain: Optional[str] = None,
        snippet: Optional[str] = None,
        quality_score: float = 50.0,
    ) -> FilterDecision:
        """Determines if a candidate discovery article meets MetroScope publication standards."""
        # 1. Structural checks
        clean_title = (title or "").strip()
        if len(clean_title) < 15:
            return FilterDecision(
                is_admissible=False,
                filter_reason="Title too short or malformed (<15 characters)",
                relevance_type="filtered",
            )

        # 2. Quality threshold check
        if quality_score < self.min_quality_threshold:
            return FilterDecision(
                is_admissible=False,
                filter_reason=f"Quality score ({quality_score:.1f}) below threshold ({self.min_quality_threshold:.1f})",
                relevance_type="filtered",
            )

        # 3. Commercial product / e-commerce spam filtering
        text_corpus = f"{clean_title} {snippet or ''}".lower()
        for pattern in COMMERCIAL_SPAM_PATTERNS:
            if pattern.search(text_corpus):
                return FilterDecision(
                    is_admissible=False,
                    filter_reason="Commercial advertisement or product listing detected",
                    relevance_type="filtered",
                )

        # 4. Check for International significance first (preserve vital world news)
        for kw in INTERNATIONAL_SIGNIFICANCE_KEYWORDS:
            if " " in kw:
                if kw in text_corpus:
                    return FilterDecision(
                        is_admissible=True,
                        filter_reason=None,
                        relevance_type="international_significance",
                    )
            else:
                if re.search(rf"\b{re.escape(kw)}\b", text_corpus):
                    return FilterDecision(
                        is_admissible=True,
                        filter_reason=None,
                        relevance_type="international_significance",
                    )

        # 5. Check for US audience relevance
        is_us_country = (country or "").upper() == "US"
        has_us_keyword = False

        for kw in US_RELEVANCE_KEYWORDS:
            if " " in kw:
                if kw in text_corpus:
                    has_us_keyword = True
                    break
            else:
                if re.search(rf"\b{re.escape(kw)}\b", text_corpus):
                    has_us_keyword = True
                    break

        # If sourcecountry is US, accept as domestic news
        if is_us_country:
            return FilterDecision(
                is_admissible=True,
                filter_reason=None,
                relevance_type="us_domestic",
            )

        # If sourcecountry is outside US but mentions US keywords, accept
        if has_us_keyword:
            return FilterDecision(
                is_admissible=True,
                filter_reason=None,
                relevance_type="us_domestic",
            )

        # Non-US story without US or international editorial significance
        return FilterDecision(
            is_admissible=False,
            filter_reason="Foreign local report without US or international editorial relevance",
            relevance_type="filtered",
        )
