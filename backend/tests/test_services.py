import pytest
from app.services.url_service import normalize_url, compute_url_hash, extract_domain
from app.services.normalizer_service import clean_title, clean_description, generate_slug
from app.services.classifier_service import classify_article


def test_url_normalization_tracking_params():
    url = "https://www.Reuters.com/world/us/article-1234?utm_source=twitter&utm_medium=social&fbclid=abc123xyz#comments"
    normalized = normalize_url(url)
    assert "utm_source" not in normalized
    assert "utm_medium" not in normalized
    assert "fbclid" not in normalized
    assert "#comments" not in normalized
    assert normalized.startswith("https://www.reuters.com/world/us/article-1234")


def test_url_normalization_trailing_slash_and_params_sort():
    url1 = "https://apnews.com/article/politics/?b=2&a=1"
    url2 = "https://apnews.com/article/politics?a=1&b=2"
    assert normalize_url(url1) == normalize_url(url2)


def test_compute_url_hash():
    url = "https://www.reuters.com/world/us/sample-news"
    h1 = compute_url_hash(url)
    h2 = compute_url_hash(url)
    assert len(h1) == 64
    assert h1 == h2
    assert isinstance(h1, str)


def test_extract_domain():
    assert extract_domain("https://WWW.Bloomberg.COM/news/articles/2026") == "bloomberg.com"
    assert extract_domain("https://sub.domain.co.uk/path") == "sub.domain.co.uk"


def test_clean_title():
    raw_title = "Senate Passes Infrastructure Bill &amp; Economic Package &mdash; Reuters"
    cleaned = clean_title(raw_title)
    assert "&amp;" not in cleaned
    assert "&mdash;" not in cleaned
    assert cleaned == "Senate Passes Infrastructure Bill & Economic Package"


def test_clean_description():
    raw_desc = "<p>Federal authorities confirmed <strong>preliminary</strong> investigations.</p><script>alert('xss')</script>"
    cleaned = clean_description(raw_desc)
    assert "<p>" not in cleaned
    assert "<strong>" not in cleaned
    assert "Federal authorities confirmed preliminary investigations." in cleaned


def test_generate_slug():
    title = "U.S. Inflation Cools to 2.1% in October 2026: Bureau of Labor Statistics"
    slug = generate_slug(title)
    assert slug.startswith("us-inflation-cools")
    assert len(slug) <= 120


def test_classify_article():
    assert classify_article("NASA Space Telescope Discovers New Exoplanet System", "") == "science"
    assert classify_article("Stock Market Rally as Tech Giants Report Earnings", "") == "business"
    assert classify_article("Artificial Intelligence Framework Adopted by Enterprise Software Vendors", "") == "technology"
    assert classify_article("White House and Congress Reach Compromise on Federal Budget", "") == "politics"
    assert classify_article("FDA Approves Breakthrough Oncology Drug After Phase 3 Trial", "") == "health"
    assert classify_article("EPA Enforces New Emission Regulations to Protect Wetlands", "") == "environment"
    assert classify_article("Olympic Games Committee Announces Host City Selection", "") == "sports"
    assert classify_article("Hollywood Guild Reaches Agreement on Streaming Royalties", "") == "entertainment"
    assert classify_article("General Update on Midwestern Highway Maintenance", "") == "us"


def test_classifier_deterministic_tie_breaking():
    # 'market' (+2 business) vs 'climate' (+2 environment) -> 'business' wins alphabetically
    title_tie_1 = "Market Impacts of Climate Policies in 2026"
    assert classify_article(title_tie_1) == "business"

    # 'film' (+2 entertainment) vs 'senate' (+2 politics) -> 'entertainment' wins alphabetically
    title_tie_2 = "Film Industry Testifies Before Senate Committee"
    assert classify_article(title_tie_2) == "entertainment"


def test_classifier_fallback_behavior():
    # No matching keywords -> falls back to 'us'
    assert classify_article("Local Community Center Hosts Annual Fall Festival") == "us"
    # Empty strings -> falls back to 'us'
    assert classify_article("", None, None) == "us"
    # Custom fallback override
    assert classify_article("Local Community Center", default_category="world") == "world"
