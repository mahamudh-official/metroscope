import datetime
import pytest
from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.source import NewsSource
from app.social.content_formatter import (
    calculate_x_post_weighted_length,
    format_category_hashtag,
    format_facebook_caption,
    format_facebook_first_comment,
    format_facebook_post,
    format_x_post,
    get_article_url,
    validate_x_post_length,
)


@pytest.fixture
def sample_article():
    source = NewsSource(id=1, name="Reuters", domain="reuters.com")
    category = NewsCategory(id=1, name="Technology", slug="technology")
    return NewsArticle(
        id=101,
        title="Researchers Unveil Next-Generation Quantum Computing Processor",
        slug="researchers-unveil-next-generation-quantum-computing-processor",
        description="A major breakthrough in quantum coherence achieved at room temperature.",
        source=source,
        category=category,
        original_url="https://reuters.com/quantum",
        canonical_url="https://reuters.com/quantum",
        canonical_url_hash="11" * 32,
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
        quality_score=85.0,
        is_trending=False,
        is_breaking=False,
    )


def test_get_article_url():
    url = get_article_url("test-slug", base_url="https://metroscope.news")
    assert url == "https://metroscope.news/article/test-slug"


def test_format_category_hashtag():
    assert format_category_hashtag("Technology") == "#Technology"
    assert format_category_hashtag("World News") == "#WorldNews"
    assert format_category_hashtag(None) == "#News"


def test_format_facebook_caption_exact_structure(sample_article):
    caption = format_facebook_post(sample_article)
    expected = f"{sample_article.title}\n\nRead more in the comments."
    assert caption == expected
    # Verify title is the only article-specific content
    assert sample_article.title in caption
    assert "Read more in the comments." in caption
    # Verify article URL is NOT in caption
    assert "https://" not in caption
    assert sample_article.slug not in caption
    # Verify no promotional or extra tags
    assert "#MetroScope" not in caption
    assert "Reuters" not in caption
    assert "By " not in caption


def test_format_facebook_caption_breaking_and_trending_pure_english(sample_article):
    # Even if article is breaking or trending, caption must strictly adhere to the exact structure
    sample_article.is_breaking = True
    caption_breaking = format_facebook_post(sample_article)
    assert caption_breaking == f"{sample_article.title}\n\nRead more in the comments."
    assert "🚨" not in caption_breaking

    sample_article.is_breaking = False
    sample_article.is_trending = True
    caption_trending = format_facebook_post(sample_article)
    assert caption_trending == f"{sample_article.title}\n\nRead more in the comments."
    assert "🔥" not in caption_trending


def test_format_facebook_first_comment_exact_structure(sample_article):
    comment = format_facebook_first_comment(sample_article, base_url="https://metroscope.news")
    expected_url = "https://metroscope.news/article/researchers-unveil-next-generation-quantum-computing-processor"
    expected = f"{sample_article.title}\n{expected_url}"
    assert comment == expected
    # Verify exact 2 lines: Title and URL
    lines = comment.split("\n")
    assert len(lines) == 2
    assert lines[0] == sample_article.title
    assert lines[1] == expected_url
    # Verify English only, no Bengali text, no unnecessary promotional copy
    assert "বাংলা" not in comment
    assert "Read full coverage" not in comment
    assert "Briefing" not in comment
    assert "Source:" not in comment


def test_format_x_post_within_limit(sample_article):
    post = format_x_post(sample_article, base_url="https://metroscope.news")
    assert sample_article.title in post
    assert "https://metroscope.news/article/researchers-unveil-next-generation-quantum-computing-processor" in post
    assert "#Technology" in post
    assert len(post) <= 280
    assert validate_x_post_length(post, max_chars=280) is True


def test_format_x_post_breaking_prefix(sample_article):
    sample_article.is_breaking = True
    post = format_x_post(sample_article)
    assert post.startswith("🚨 BREAKING:")
    assert validate_x_post_length(post, max_chars=280) is True


def test_format_x_post_truncates_long_headline():
    long_title = (
        "Super Long Breaking Headline About Federal Reserve Monetary Policy Committee Deciding "
        "To Lower The Benchmark Federal Funds Rate By Exactly Twenty-Five Basis Points Following "
        "Extensive Two-Day Deliberations in Washington DC With Global Market Implications"
    )
    article = NewsArticle(
        id=102,
        title=long_title,
        slug="super-long-breaking-headline-about-federal-reserve-monetary-policy",
        source=NewsSource(name="Financial Times", domain="ft.com"),
        category=NewsCategory(name="Business", slug="business"),
        original_url="https://ft.com/fed",
        canonical_url="https://ft.com/fed",
        canonical_url_hash="22" * 32,
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
        is_breaking=True,
    )
    post = format_x_post(article, base_url="https://metroscope.news", max_chars=280)
    assert validate_x_post_length(post, max_chars=280) is True
    assert calculate_x_post_weighted_length(post) <= 280
    assert "..." in post
    assert "https://metroscope.news/article/super-long-breaking-headline-about-federal-reserve-monetary-policy" in post
    assert "#Business" in post


# --- M-02 Twitter Text v3 Weighted Length Tests ---

def test_x_weighted_length_urls():
    # Long URL counts as 23
    long_url = "https://metroscope.news/article/super-long-headline-with-very-large-slug-exceeding-standard-length"
    assert calculate_x_post_weighted_length(long_url) == 23

    # Short URL counts as 23
    short_url = "https://t.co/xyz1"
    assert calculate_x_post_weighted_length(short_url) == 23

    # Multiple URLs: each contributes 23
    multi_url = "Link 1: https://example.com/one and Link 2: https://example.com/two"
    # "Link 1: " (8) + 23 + " and Link 2: " (13) + 23 = 67
    assert calculate_x_post_weighted_length(multi_url) == 67

    # URL with query parameters
    url_with_query = "https://metroscope.news/article/fed-rate?utm_source=social&ref=metro"
    assert calculate_x_post_weighted_length(url_with_query) == 23


def test_x_weighted_length_unicode_and_scripts():
    # Standard Latin (weight 1 each)
    assert calculate_x_post_weighted_length("Hello World") == 11

    # Accented Latin characters (Café, München -> weight 1 each in range 0..4351)
    assert calculate_x_post_weighted_length("Café") == 4
    assert calculate_x_post_weighted_length("München") == 7

    # Bangla / Bengali script (range U+0980..U+09FF falls in 0..4351 -> weight 1 each)
    bangla_text = "বাংলা"  # 5 unicode chars
    assert calculate_x_post_weighted_length(bangla_text) == 5

    # CJK characters (weight 2 each, code points > 4351)
    japanese_text = "日本語"  # 3 chars -> 6 weight
    assert calculate_x_post_weighted_length(japanese_text) == 6

    # Emojis (weight 2 each)
    assert calculate_x_post_weighted_length("🚨") == 2
    assert calculate_x_post_weighted_length("🔥") == 2
    assert calculate_x_post_weighted_length("🚨 BREAKING: ") == 2 + 11  # 13


def test_x_weighted_length_limits():
    # Text exactly at 280
    exact_text = "a" * 280
    assert calculate_x_post_weighted_length(exact_text) == 280
    assert validate_x_post_length(exact_text, max_chars=280) is True

    # Text exceeding 280
    overflow_text = "a" * 281
    assert calculate_x_post_weighted_length(overflow_text) == 281
    assert validate_x_post_length(overflow_text, max_chars=280) is False

    # 130 CJK characters = 260 weight <= 280
    cjk_fit = "日" * 130
    assert calculate_x_post_weighted_length(cjk_fit) == 260
    assert validate_x_post_length(cjk_fit, max_chars=280) is True

    # 141 CJK characters = 282 weight > 280
    cjk_over = "日" * 141
    assert calculate_x_post_weighted_length(cjk_over) == 282
    assert validate_x_post_length(cjk_over, max_chars=280) is False


def test_x_weighted_length_malformed_url():
    # Malformed URL without scheme: counted character-by-character
    raw = "not_a_valid_url_without_http.com"
    assert calculate_x_post_weighted_length(raw) == len(raw)
