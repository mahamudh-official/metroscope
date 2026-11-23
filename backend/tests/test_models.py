import pytest
import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.models.category import NewsCategory
from app.models.source import NewsSource
from app.models.article import NewsArticle
from app.models.ingestion import DiscoveryIngestionRun


@pytest.mark.asyncio
async def test_create_category_and_unique_constraint(db_session: AsyncSession):
    cat1 = NewsCategory(name="Technology", slug="technology", description="Tech news")
    db_session.add(cat1)
    await db_session.commit()

    assert cat1.id is not None
    assert cat1.created_at is not None

    # Duplicate slug should trigger integrity error
    cat2 = NewsCategory(name="Tech Duplicate", slug="technology")
    db_session.add(cat2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_create_source_and_article(db_session: AsyncSession):
    source = NewsSource(name="Associated Press", domain="apnews.com", is_active=True)
    category = NewsCategory(name="US News", slug="us", is_active=True)
    db_session.add_all([source, category])
    await db_session.commit()

    article = NewsArticle(
        title="Major Economic Accord Signed",
        slug="major-economic-accord-signed",
        description="Leaders from multiple nations signed the landmark accord.",
        source_id=source.id,
        category_id=category.id,
        original_url="https://apnews.com/article/123",
        canonical_url="https://apnews.com/article/123",
        canonical_url_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        language="en",
        country="US",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        discovered_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(article)
    await db_session.commit()

    assert article.id is not None

    # Test uniqueness of canonical_url_hash
    duplicate_article = NewsArticle(
        title="Duplicate Story",
        slug="duplicate-story",
        source_id=source.id,
        category_id=category.id,
        original_url="https://apnews.com/article/123?utm=copy",
        canonical_url="https://apnews.com/article/123",
        canonical_url_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    db_session.add(duplicate_article)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_delete_source_preserves_articles(db_session: AsyncSession):
    source = NewsSource(name="Reuters Wire", domain="reuterswire.com", is_active=True)
    category = NewsCategory(name="World Affairs", slug="world-affairs", is_active=True)
    db_session.add_all([source, category])
    await db_session.commit()

    article = NewsArticle(
        title="Diplomatic Accord Reached",
        slug="diplomatic-accord-reached",
        source_id=source.id,
        category_id=category.id,
        original_url="https://reuterswire.com/diplomacy",
        canonical_url="https://reuterswire.com/diplomacy",
        canonical_url_hash="2222222222222222222222222222222222222222222222222222222222222222",
        language="en",
        country="US",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(article)
    await db_session.commit()

    article_id = article.id

    # Delete the source
    await db_session.delete(source)
    await db_session.commit()

    # Article must still exist
    fetch_stmt = select(NewsArticle).where(NewsArticle.id == article_id)
    res = await db_session.execute(fetch_stmt)
    remaining_article = res.scalar_one_or_none()
    assert remaining_article is not None
    assert remaining_article.title == "Diplomatic Accord Reached"


@pytest.mark.asyncio
async def test_delete_category_preserves_articles(db_session: AsyncSession):
    source = NewsSource(name="Tech Dispatch Daily", domain="tddaily.com", is_active=True)
    category = NewsCategory(name="Artificial Intelligence", slug="ai-desk", is_active=True)
    db_session.add_all([source, category])
    await db_session.commit()

    article = NewsArticle(
        title="New Model Released",
        slug="new-model-released",
        source_id=source.id,
        category_id=category.id,
        original_url="https://tddaily.com/model",
        canonical_url="https://tddaily.com/model",
        canonical_url_hash="3333333333333333333333333333333333333333333333333333333333333333",
        language="en",
        country="US",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(article)
    await db_session.commit()

    article_id = article.id

    # Delete the category
    await db_session.delete(category)
    await db_session.commit()

    # Article must still exist
    fetch_stmt = select(NewsArticle).where(NewsArticle.id == article_id)
    res = await db_session.execute(fetch_stmt)
    remaining_article = res.scalar_one_or_none()
    assert remaining_article is not None
    assert remaining_article.title == "New Model Released"


@pytest.mark.asyncio
async def test_discovery_ingestion_run(db_session: AsyncSession):
    run = DiscoveryIngestionRun(
        provider="webz",
        status="running",
        fetched_count=25,
        inserted_count=18,
        duplicate_count=7,
        failed_count=0,
    )
    db_session.add(run)
    await db_session.commit()

    assert run.id is not None
    assert run.started_at is not None
    assert run.fetched_count == 25
