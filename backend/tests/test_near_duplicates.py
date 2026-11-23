import datetime
import pytest
from app.services.deduplication_service import (
    calculate_jaccard_similarity,
    find_near_duplicate,
    tokenize_title,
)


def test_tokenize_title_cleans_punctuation_and_stopwords():
    raw = "The Senate Passes an Infrastructure Bill, According to Officials!"
    tokens = tokenize_title(raw)
    assert "senate" in tokens
    assert "passes" in tokens
    assert "infrastructure" in tokens
    assert "bill" in tokens
    assert "the" not in tokens
    assert "an" not in tokens
    assert "to" not in tokens


def test_jaccard_similarity_calculation():
    set_a = {"senate", "passes", "bill", "infrastructure"}
    set_b = {"senate", "passes", "bill", "climate"}
    # intersection: 3 (senate, passes, bill)
    # union: 5 (senate, passes, bill, infrastructure, climate)
    # 3 / 5 = 0.60
    sim = calculate_jaccard_similarity(set_a, set_b)
    assert sim == 0.60


def test_same_domain_headline_update_detected_as_near_duplicate():
    now = datetime.datetime.now(datetime.timezone.utc)
    recent_articles = [
        (101, "Federal Reserve Holds Benchmark Rates Steady at November Meeting", "reuters.com", now),
    ]

    # Reuters slightly updates their headline on the same domain
    updated_title = "Federal Reserve Decides to Hold Benchmark Interest Rates Steady at November Meeting"
    result = find_near_duplicate(
        candidate_title=updated_title,
        candidate_domain="reuters.com",
        candidate_published_at=now,
        recent_articles=recent_articles,
    )

    assert result is not None
    matched_id, score, reason = result
    assert matched_id == 101
    assert "Same-domain headline revision" in reason


def test_cross_domain_syndicated_wire_copy_detected():
    now = datetime.datetime.now(datetime.timezone.utc)
    recent_articles = [
        (201, "Historic Treaty Signed at Geneva Summit on Global Climate Targets", "apnews.com", now),
    ]

    # Another local paper reprints the AP wire story with identical headline
    syndicated_title = "Historic Treaty Signed at Geneva Summit on Global Climate Targets"
    result = find_near_duplicate(
        candidate_title=syndicated_title,
        candidate_domain="dallasnews.com",
        candidate_published_at=now,
        recent_articles=recent_articles,
    )

    assert result is not None
    matched_id, score, reason = result
    assert matched_id == 201
    assert score == 1.0
    assert "Syndicated cross-domain wire copy" in reason


def test_independent_reports_on_same_event_NOT_merged():
    """CRITICAL FALSE-POSITIVE TEST:
    Independent journalists covering the same developing event must NOT be collapsed
    into duplicates.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    recent_articles = [
        (301, "Supreme Court Hears Key Arguments in Landmark First Amendment Free Speech Case", "nytimes.com", now),
    ]

    # Washington Post covers the exact same Supreme Court hearing with their own independent headline
    independent_report = "Supreme Court Justices Express Skepticism Over Digital Speech Restrictions in Oral Arguments"
    result = find_near_duplicate(
        candidate_title=independent_report,
        candidate_domain="washingtonpost.com",
        candidate_published_at=now,
        recent_articles=recent_articles,
    )

    # Must be None: independent reporting preserved!
    assert result is None


def test_temporal_cutoff_prevents_stale_duplicates():
    now = datetime.datetime.now(datetime.timezone.utc)
    stale_date = now - datetime.timedelta(days=3)  # 72 hours ago
    recent_articles = [
        (401, "Severe Blizzard Warnings Issued Across Northern Plains", "weather.com", stale_date),
    ]

    # Similar event 3 days later is a new news development
    new_story = "Severe Blizzard Warnings Issued Across Northern Plains States"
    result = find_near_duplicate(
        candidate_title=new_story,
        candidate_domain="weather.com",
        candidate_published_at=now,
        recent_articles=recent_articles,
        max_time_delta_hours=24,
    )

    assert result is None
