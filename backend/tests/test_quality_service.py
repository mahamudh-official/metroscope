import datetime
import pytest
from app.services.quality_service import QualityScoringService, QualityWeights


def test_quality_scoring_high_quality_article():
    service = QualityScoringService()
    now = datetime.datetime(2026, 11, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)
    pub_at = datetime.datetime(2026, 11, 7, 10, 30, 0, tzinfo=datetime.timezone.utc)

    assessment = service.score_article(
        title="Senate Approves Bipartisan Infrastructure Investment Package",
        canonical_url="https://www.reuters.com/world/us/senate-infrastructure-package-2026",
        domain="reuters.com",
        snippet="The legislation allocates federal funding for transit networks, clean water facilities, and broadband access.",
        published_at=pub_at,
        category_confidence=6,
        now=now,
    )

    assert assessment.score >= 85.0
    assert assessment.factor_scores["title_completeness"] == 25.0
    assert assessment.factor_scores["source_reputation"] == 20.0
    assert assessment.factor_scores["timestamp_validity"] == 15.0
    assert assessment.factor_scores["url_validity"] == 10.0


def test_quality_scoring_clickbait_and_allcaps_penalized():
    service = QualityScoringService()
    now = datetime.datetime(2026, 11, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)

    assessment = service.score_article(
        title="SHOCKING! YOU WON'T BELIEVE WHAT HAPPENED AT THE MEETING TODAY",
        canonical_url="http://sketchy-deals.biz/index.php?utm_source=spam&sessionid=123",
        domain="sketchy-deals.biz",
        snippet="",
        published_at=now,
        category_confidence=0,
        now=now,
    )

    assert assessment.score < 50.0
    assert any("Excessive capitalization" in r or "Promotional or clickbait" in r for r in assessment.reasons)
    assert any("Insecure HTTP" in r or "Tracking tokens" in r for r in assessment.reasons)


def test_quality_scoring_future_date_penalized():
    service = QualityScoringService()
    now = datetime.datetime(2026, 11, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)
    future_pub = datetime.datetime(2026, 11, 8, 12, 0, 0, tzinfo=datetime.timezone.utc)  # 24h in future

    assessment = service.score_article(
        title="Valid Editorial Headline About State Commerce",
        canonical_url="https://apnews.com/article/state-commerce",
        domain="apnews.com",
        snippet="Valid snippet description of commerce developments.",
        published_at=future_pub,
        category_confidence=4,
        now=now,
    )

    assert assessment.factor_scores["timestamp_validity"] < 5.0
    assert any("Future timestamp detected" in r for r in assessment.reasons)


def test_quality_scoring_custom_weights():
    custom_weights = QualityWeights(
        title_completeness=50.0,
        snippet_availability=10.0,
        source_reputation=10.0,
        timestamp_validity=10.0,
        url_validity=10.0,
        classification_confidence=10.0,
    )
    service = QualityScoringService(weights=custom_weights)
    assessment = service.score_article(
        title="Short",
        canonical_url="https://reuters.com/news",
        domain="reuters.com",
    )
    # 0.2 baseline for title < 15 chars * 50 = 10.0
    assert assessment.factor_scores["title_completeness"] == 10.0
