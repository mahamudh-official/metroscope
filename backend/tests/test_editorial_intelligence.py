import datetime
import pytest
from app.services.editorial_intelligence_service import EditorialIntelligenceService


def test_trending_detection_multi_source_coverage():
    service = EditorialIntelligenceService(min_trending_sources=3)
    now = datetime.datetime.now(datetime.timezone.utc)

    # 3 distinct publishers covering the same developing story
    articles = [
        {"id": 1, "title": "Federal Reserve Cuts Benchmark Interest Rates by 25 Basis Points", "domain": "reuters.com", "published_at": now},
        {"id": 2, "title": "Fed Decides to Cut Interest Rates by Quarter Point Amid Cooling Inflation", "domain": "bloomberg.com", "published_at": now},
        {"id": 3, "title": "Central Bank Policy Shift: Federal Reserve Cuts Rates by 25 Basis Points", "domain": "wsj.com", "published_at": now},
        # 1 unrelated story
        {"id": 4, "title": "James Webb Space Telescope Captures Distant Spiral Galaxy in Deep Space", "domain": "nasa.gov", "published_at": now},
    ]

    results = service.analyze_articles(articles, now=now)

    # Articles 1, 2, 3 should be flagged as trending and share the same cluster_id
    assert results[1]["is_trending"] is True
    assert results[2]["is_trending"] is True
    assert results[3]["is_trending"] is True
    assert results[1]["cluster_id"] is not None
    assert results[1]["cluster_id"] == results[2]["cluster_id"] == results[3]["cluster_id"]

    # Article 4 is unrelated and must NOT be trending
    assert results[4]["is_trending"] is False
    assert results[4]["cluster_id"] is None


def test_single_source_story_NOT_flagged_as_trending():
    service = EditorialIntelligenceService(min_trending_sources=3)
    now = datetime.datetime.now(datetime.timezone.utc)

    # Multiple articles from the SAME publisher domain
    articles = [
        {"id": 10, "title": "Local Olympian Offers Book Talk at Moundsville Library Event", "domain": "theintelligencer.net", "published_at": now},
        {"id": 11, "title": "Moundsville Library Welcomes Local Olympian for Community Book Reading", "domain": "theintelligencer.net", "published_at": now},
    ]

    results = service.analyze_articles(articles, now=now)

    # Only 1 distinct domain, does NOT meet the 3-domain threshold
    assert results[10]["is_trending"] is False
    assert results[11]["is_trending"] is False


def test_breaking_news_detection_rapid_multi_source_velocity():
    service = EditorialIntelligenceService(min_breaking_sources=3, max_breaking_age_hours=3.0)
    now = datetime.datetime.now(datetime.timezone.utc)
    recent_time = now - datetime.timedelta(minutes=45)

    # Rapid pickup by 3 major publishers within 45 minutes
    articles = [
        {"id": 20, "title": "Major 7.2 Magnitude Earthquake Strikes Offshore Coastal Region", "domain": "reuters.com", "published_at": recent_time},
        {"id": 21, "title": "Tsunami Warning Issued After 7.2 Magnitude Earthquake Strikes Coast", "domain": "apnews.com", "published_at": recent_time},
        {"id": 22, "title": "Emergency Teams Mobilize Following Massive 7.2 Magnitude Earthquake", "domain": "cnn.com", "published_at": recent_time},
    ]

    results = service.analyze_articles(articles, now=now)

    assert results[20]["is_breaking"] is True
    assert results[21]["is_breaking"] is True
    assert results[22]["is_breaking"] is True


def test_clickbait_breaking_title_from_single_source_rejected():
    service = EditorialIntelligenceService(min_breaking_sources=3, max_breaking_age_hours=3.0)
    now = datetime.datetime.now(datetime.timezone.utc)

    # Single sensational article calling itself 'BREAKING'
    articles = [
        {"id": 30, "title": "BREAKING: Celebrity Sighting Outside Downtown Coffee Shop", "domain": "gossipwire.net", "published_at": now},
        {"id": 31, "title": "Treasury Secretary Testifies Before Senate Finance Committee", "domain": "bloomberg.com", "published_at": now},
    ]

    results = service.analyze_articles(articles, now=now)

    # Without multi-source corroboration, breaking flag must be False
    assert results[30]["is_breaking"] is False
    assert results[31]["is_breaking"] is False


def test_transitive_chaining_prevention_distinct_stories():
    """Regression test for Finding M-01: Verifies that single-linkage transitive chaining
    (A ~ B ~ C ~ D) does NOT merge unrelated stories into an oversized cluster.
    """
    service = EditorialIntelligenceService(min_trending_sources=3)
    now = datetime.datetime.now(datetime.timezone.utc)

    # A: Defense spending, B: Farm spending, C: Wisconsin dairy relief, D: Wisconsin milk price crisis
    articles = [
        {"id": 40, "title": "Senate Approves Major Defense Spending Authorization Bill", "domain": "reuters.com", "published_at": now},
        {"id": 41, "title": "Senate Approves Farm Spending Bill in Bipartisan Consensus", "domain": "apnews.com", "published_at": now},
        {"id": 42, "title": "Farm Spending Bill Brings Relief to Wisconsin Dairy Farmers", "domain": "bloomberg.com", "published_at": now},
        {"id": 43, "title": "Wisconsin Dairy Farmers Struggle With Plummeting Milk Prices", "domain": "wsj.com", "published_at": now},
    ]

    results = service.analyze_articles(articles, now=now)

    # Article 40 (Defense Authorization) and Article 43 (Wisconsin Milk Prices) must NOT share a cluster
    cluster_40 = results[40]["cluster_id"]
    cluster_43 = results[43]["cluster_id"]

    assert cluster_40 != cluster_43 or (cluster_40 is None and cluster_43 is None)
    # Neither cluster should have 3 distinct domains, so neither is marked trending
    assert results[40]["is_trending"] is False
    assert results[43]["is_trending"] is False


def test_unrelated_articles_sharing_generic_terms_rejected():
    """Verifies that headlines sharing generic institutional stopwords/terms do not form false clusters."""
    service = EditorialIntelligenceService(min_trending_sources=3)
    now = datetime.datetime.now(datetime.timezone.utc)

    articles = [
        {"id": 50, "title": "Senate Passes Annual Federal Spending Package", "domain": "reuters.com", "published_at": now},
        {"id": 51, "title": "Governor Signs Statewide Transportation Bill", "domain": "apnews.com", "published_at": now},
        {"id": 52, "title": "Mayor Announces City Park Renovation Initiative", "domain": "cnn.com", "published_at": now},
    ]

    results = service.analyze_articles(articles, now=now)
    for art in articles:
        assert results[art["id"]]["cluster_id"] is None
        assert results[art["id"]]["is_trending"] is False


def test_deterministic_clustering_across_repeated_executions():
    """Verifies that cluster IDs and assignments are 100% deterministic across multiple runs."""
    service = EditorialIntelligenceService(min_trending_sources=3)
    now = datetime.datetime.now(datetime.timezone.utc)

    articles = [
        {"id": 60, "title": "Federal Reserve Cuts Benchmark Interest Rates by 25 Basis Points", "domain": "reuters.com", "published_at": now},
        {"id": 61, "title": "Fed Decides to Cut Interest Rates by Quarter Point Amid Cooling Inflation", "domain": "bloomberg.com", "published_at": now},
        {"id": 62, "title": "Central Bank Policy Shift: Federal Reserve Cuts Rates by 25 Basis Points", "domain": "wsj.com", "published_at": now},
    ]

    first_run = service.analyze_articles(articles, now=now)
    cluster_id_first = first_run[60]["cluster_id"]
    assert cluster_id_first is not None

    for _ in range(5):
        run_res = service.analyze_articles(articles, now=now)
        assert run_res[60]["cluster_id"] == cluster_id_first
        assert run_res[61]["cluster_id"] == cluster_id_first
        assert run_res[62]["cluster_id"] == cluster_id_first


def test_cluster_stability_when_new_article_added():
    """Verifies that adding a new related article joins the existing cluster without fragmenting."""
    service = EditorialIntelligenceService(min_trending_sources=3)
    now = datetime.datetime.now(datetime.timezone.utc)

    base_articles = [
        {"id": 70, "title": "NASA James Webb Space Telescope Finds Oldest Known Black Hole", "domain": "reuters.com", "published_at": now},
        {"id": 71, "title": "Webb Telescope Detects Earliest Black Hole Known in Ancient Cosmos", "domain": "apnews.com", "published_at": now},
    ]

    res_base = service.analyze_articles(base_articles, now=now)
    cluster_base_id = res_base[70]["cluster_id"]
    assert cluster_base_id is not None
    assert res_base[70]["cluster_id"] == res_base[71]["cluster_id"]

    # Add 3rd publisher covering the same discovery
    extended_articles = base_articles + [
        {"id": 72, "title": "Astronomers Unveil Oldest Known Black Hole Discovered by James Webb Telescope", "domain": "bbc.com", "published_at": now},
    ]

    res_extended = service.analyze_articles(extended_articles, now=now)
    # The 3rd article joins the cluster
    assert res_extended[72]["cluster_id"] is not None
    assert res_extended[70]["cluster_id"] == res_extended[71]["cluster_id"] == res_extended[72]["cluster_id"]
    # With 3 distinct domains, it is promoted to trending
    assert res_extended[70]["is_trending"] is True
    assert res_extended[72]["is_trending"] is True
