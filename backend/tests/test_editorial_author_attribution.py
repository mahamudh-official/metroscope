"""Verifies every article is consistently attributed to MetroScope News Desk."""

import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.source import NewsSource
from app.schemas.canonical_article import CanonicalMetroScopeArticle
from app.services.article_validation_service import ArticleEditorialValidationService
from app.services.normalizer_service import EDITORIAL_AUTHOR
from app.social.content_formatter import (
    format_facebook_post,
    format_x_post,
    validate_x_post_length,
)

DESK = "MetroScope News Desk"


def test_constant_value():
    assert EDITORIAL_AUTHOR == DESK


def _canonical_kwargs(**overrides):
    base = dict(
        uuid="author-test-uuid-001",
        title="Researchers Publish Comprehensive Study On Regional Water Policy",
        canonical_url="https://example-news.com/water-policy-study",
        canonical_url_hash="a" * 64,
        domain="example-news.com",
        publisher_name="Example News",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        category_slug="science",
        language="en",
        full_text=(
            "Researchers released a comprehensive study on regional water policy this week, "
            "analyzing reservoir levels, agricultural demand, and municipal usage across several "
            "counties, and recommending coordinated management to reduce shortages in dry seasons."
        ),
        content_display_authorized=True,
        image_url="https://images.example-news.com/water.jpg",
        hero_image_authorized=True,
    )
    base.update(overrides)
    return base


@pytest.mark.parametrize("provider_author", ["Jane Reporter", "admin", None, "Example News"])
def test_canonical_author_always_desk(provider_author):
    art = CanonicalMetroScopeArticle(**_canonical_kwargs(author=provider_author))
    assert art.author == DESK
    assert art.publisher_name == "Example News"  # source untouched


def test_validation_service_author_is_desk():
    res = ArticleEditorialValidationService.evaluate_candidate(
        title="Researchers Publish Comprehensive Study On Regional Water Policy",
        canonical_url="https://example-news.com/water-policy-study",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="example-news.com",
        category_slug="science",
        summary=None,
        full_text=_canonical_kwargs()["full_text"],
        publisher_name="Example News",
        author="Jane Reporter",
        image_url="https://images.example-news.com/water.jpg",
        language="en",
        content_display_authorized=True,
    )
    assert res.cleaned_author == DESK


def test_parser_author_is_desk():
    from app.integrations.webz import parser
    import inspect

    src = inspect.getsource(parser.normalize_webz_post)
    assert "author = EDITORIAL_AUTHOR" in src


def _article(author):
    return NewsArticle(
        id=1,
        title="Researchers Unveil Next-Generation Quantum Computing Processor",
        slug="quantum-processor",
        description="A breakthrough in quantum coherence.",
        author=author,
        source=NewsSource(id=1, name="Reuters", domain="reuters.com"),
        category=NewsCategory(id=1, name="Technology", slug="technology"),
        original_url="https://reuters.com/q",
        canonical_url="https://reuters.com/q",
        canonical_url_hash="11" * 32,
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )


def test_social_posts_use_desk_and_keep_source():
    art = _article("Jane Reporter")
    fb = format_facebook_post(art, base_url="https://metroscope.news")
    # Facebook post caption contains only title and fixed call to action in comments
    assert fb == f"{art.title}\n\nRead more in the comments."
    assert "Jane Reporter" not in fb

    x = format_x_post(art, base_url="https://metroscope.news")
    assert f"By {DESK}" in x
    assert "Jane Reporter" not in x
    assert validate_x_post_length(x, max_chars=280) is True


def test_x_post_long_headline_still_within_limit_with_desk():
    art = _article(None)
    art.title = "Very Long Headline " * 20
    x = format_x_post(art, base_url="https://metroscope.news")
    assert f"By {DESK}" in x
    assert validate_x_post_length(x, max_chars=280) is True


@pytest.mark.asyncio
async def test_public_api_returns_desk_for_legacy_rows(client: AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="Tech Dispatch", domain="techdispatch.com")
    cat = NewsCategory(name="Technology", slug="technology")
    db_session.add_all([source, cat])
    await db_session.commit()

    for i, legacy_author in enumerate(["Jane Reporter", None, "Tech Dispatch"], start=1):
        db_session.add(
            NewsArticle(
                title=f"Legacy Article Number {i} About Technology",
                slug=f"legacy-article-{i}",
                author=legacy_author,
                source_id=source.id,
                category_id=cat.id,
                original_url=f"https://techdispatch.com/{i}",
                canonical_url=f"https://techdispatch.com/{i}",
                canonical_url_hash=str(i) * 64,
                language="en",
                published_at=datetime.datetime.now(datetime.timezone.utc),
                status="published",
            )
        )
    await db_session.commit()

    listing = (await client.get("/api/v1/articles")).json()
    assert listing["total"] == 3
    assert all(item["author"] == DESK for item in listing["items"])
    assert all(item["source"]["name"] == "Tech Dispatch" for item in listing["items"])

    cat_listing = (await client.get("/api/v1/categories/technology/articles")).json()
    assert all(item["author"] == DESK for item in cat_listing["items"])

    detail = (await client.get("/api/v1/articles/legacy-article-1")).json()
    assert detail["author"] == DESK
    assert detail["title"] == "Legacy Article Number 1 About Technology"

    related = (await client.get("/api/v1/articles/legacy-article-1/related")).json()
    assert all(item["author"] == DESK for item in related)
