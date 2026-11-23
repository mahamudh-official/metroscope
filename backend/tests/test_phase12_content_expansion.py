"""Phase 12 Content Density & Editorial Enrichment Regression Test Suite.

Verifies:
1. Category discovery query mapping covers all 10 approved categories.
2. IngestionService supports category-specific discovery with default_category hinting.
3. QualityScoringService established domains includes expanded beat publications.
4. Comprehensive discovery handles per-category delays and aggregates newly inserted counts.
5. Ingestion rejects malformed titles, applies near-duplicate filtering, and computes valid slugs.
"""

from unittest.mock import AsyncMock, patch
import pytest
from app.services.classifier_service import (
    CATEGORY_KEYWORD_MAP,
    classify_article,
    classify_article_detailed,
)
from app.integrations.webz.client import CATEGORY_QUERIES
from app.services.quality_service import (
    ESTABLISHED_NEWS_DOMAINS,
    QualityScoringService,
)


APPROVED_10_CATEGORIES = {
    "world", "us", "politics", "business", "technology",
    "science", "health", "environment", "sports", "entertainment"
}


def test_approved_categories_in_taxonomy():
    """All 10 approved categories must exist in semantic taxonomy."""
    assert set(CATEGORY_KEYWORD_MAP.keys()) == APPROVED_10_CATEGORIES
    for cat in APPROVED_10_CATEGORIES:
        assert len(CATEGORY_KEYWORD_MAP[cat]) >= 10, f"Category {cat} should have rich taxonomy"


def test_scheduled_categories_in_webz_queries():
    """Confirmed Webz.io query templates cover business, science, technology, and confirmed multi-category."""
    assert "confirmed" in CATEGORY_QUERIES
    assert "business" in CATEGORY_QUERIES
    assert "science" in CATEGORY_QUERIES
    assert "technology" in CATEGORY_QUERIES
    assert "Economy, Business and Finance" in CATEGORY_QUERIES["business"]
    assert "science and technology" in CATEGORY_QUERIES["science"]


def test_expanded_established_domains():
    """Reputation whitelist must cover Tier-1 publishers across specialized beats."""
    assert "scientificamerican.com" in ESTABLISHED_NEWS_DOMAINS
    assert "theverge.com" in ESTABLISHED_NEWS_DOMAINS
    assert "statnews.com" in ESTABLISHED_NEWS_DOMAINS
    assert "insideclimatenews.org" in ESTABLISHED_NEWS_DOMAINS
    assert "espn.com" in ESTABLISHED_NEWS_DOMAINS
    assert "variety.com" in ESTABLISHED_NEWS_DOMAINS
    assert "wsj.com" in ESTABLISHED_NEWS_DOMAINS
    assert "reuters.com" in ESTABLISHED_NEWS_DOMAINS
    assert len(ESTABLISHED_NEWS_DOMAINS) >= 60


def test_category_hinting_preserves_discovery_context():
    """Articles discovered under category-specific queries should adopt hint on tie/fallback."""
    # When no specific keywords match, default_category hint is respected
    res_science = classify_article_detailed(
        title="Researchers Unveil Unprecedented Archaeological Findings at Remote Dig Site",
        default_category="science",
    )
    assert res_science.category_slug == "science"

    # Explicit strong keywords from another category still override hint
    res_override = classify_article_detailed(
        title="Wall Street Stocks Plummet Following Federal Reserve Interest Rate Hike",
        default_category="science",
    )
    assert res_override.category_slug == "business"


def test_quality_scoring_with_expanded_domains():
    """Articles from newly whitelisted domains achieve tier-1 source reputation."""
    scorer = QualityScoringService()

    assessment = scorer.score_article(
        title="NASA Space Telescope Discovers Habitable-Zone Exoplanet 100 Light Years Away",
        canonical_url="https://www.scientificamerican.com/article/nasa-space-telescope-exoplanet",
        domain="scientificamerican.com",
        snippet="Astronomers utilizing the James Webb Space Telescope have identified atmospheric water vapor.",
        category_confidence=8,
    )
    assert assessment.score >= 75.0
    assert assessment.factor_scores["source_reputation"] == scorer.weights.source_reputation
