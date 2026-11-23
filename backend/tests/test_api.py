import pytest
import datetime
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.category import NewsCategory
from app.models.source import NewsSource
from app.models.article import NewsArticle


@pytest.mark.asyncio
async def test_get_empty_articles(client: AsyncClient):
    response = await client.get("/api/v1/articles")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_categories(client: AsyncClient, db_session: AsyncSession):
    cat = NewsCategory(name="World News", slug="world", description="Global events")
    db_session.add(cat)
    await db_session.commit()

    response = await client.get("/api/v1/categories")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(c["slug"] == "world" for c in data)


@pytest.mark.asyncio
async def test_get_articles_and_slug(client: AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="Tech Dispatch", domain="techdispatch.com")
    cat = NewsCategory(name="Technology", slug="technology")
    db_session.add_all([source, cat])
    await db_session.commit()

    article = NewsArticle(
        title="Breakthrough Quantum Processor Demonstrated",
        slug="breakthrough-quantum-processor-demonstrated",
        description="Researchers unveil 10000-qubit coherent system.",
        source_id=source.id,
        category_id=cat.id,
        original_url="https://techdispatch.com/quantum",
        canonical_url="https://techdispatch.com/quantum",
        canonical_url_hash="1111111111111111111111111111111111111111111111111111111111111111",
        language="en",
        country="US",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        discovered_at=datetime.datetime.now(datetime.timezone.utc),
        status="published",
    )
    db_session.add(article)
    await db_session.commit()

    # List articles
    list_resp = await client.get("/api/v1/articles")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] == 1
    assert list_data["items"][0]["slug"] == "breakthrough-quantum-processor-demonstrated"

    # Detail by slug
    detail_resp = await client.get("/api/v1/articles/breakthrough-quantum-processor-demonstrated")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["title"] == "Breakthrough Quantum Processor Demonstrated"
    assert detail_data["source"]["domain"] == "techdispatch.com"

    # Non-existent slug returns 404
    missing_resp = await client.get("/api/v1/articles/non-existent-article")
    assert missing_resp.status_code == 404

    # Category articles endpoint
    cat_resp = await client.get("/api/v1/categories/technology/articles")
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert cat_data["total"] == 1


@pytest.mark.asyncio
async def test_deterministic_pagination_identical_timestamps(client: AsyncClient, db_session: AsyncSession):
    same_time = datetime.datetime(2026, 11, 7, 12, 0, 0, tzinfo=datetime.timezone.utc)
    source = NewsSource(name="AP News", domain="apnews-deterministic.com")
    db_session.add(source)
    await db_session.commit()

    # Create 4 articles with exact same published_at
    for idx in range(1, 5):
        art = NewsArticle(
            title=f"Article Index {idx}",
            slug=f"article-index-{idx}",
            original_url=f"https://apnews-deterministic.com/art-{idx}",
            canonical_url=f"https://apnews-deterministic.com/art-{idx}",
            canonical_url_hash=f"{idx}" * 64,
            source_id=source.id,
            published_at=same_time,
            status="published",
        )
        db_session.add(art)
    await db_session.commit()

    # Page 1 (size=2)
    p1 = await client.get("/api/v1/articles?page=1&page_size=2")
    assert p1.status_code == 200
    p1_items = p1.json()["items"]
    assert len(p1_items) == 2

    # Page 2 (size=2)
    p2 = await client.get("/api/v1/articles?page=2&page_size=2")
    assert p2.status_code == 200
    p2_items = p2.json()["items"]
    assert len(p2_items) == 2

    # IDs must be strictly descending: [4, 3] on page 1, [2, 1] on page 2
    p1_ids = [item["id"] for item in p1_items]
    p2_ids = [item["id"] for item in p2_items]

    assert p1_ids[0] > p1_ids[1]
    assert p2_ids[0] > p2_ids[1]
    assert p1_ids[1] > p2_ids[0]  # No overlap across pages
    assert set(p1_ids).isdisjoint(set(p2_ids))


@pytest.mark.asyncio
async def test_trending_and_breaking_api_filters(client: AsyncClient, db_session: AsyncSession):
    source = NewsSource(name="Wire Source", domain="wiresource.com")
    db_session.add(source)
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    art_standard = NewsArticle(
        title="Standard Daily Briefing",
        slug="standard-daily-briefing",
        original_url="https://wiresource.com/briefing",
        canonical_url="https://wiresource.com/briefing",
        canonical_url_hash="aa" * 32,
        source_id=source.id,
        published_at=now,
        status="published",
        is_trending=False,
        is_breaking=False,
    )
    art_trending = NewsArticle(
        title="Historic Trade Accord Ratified",
        slug="historic-trade-accord-ratified",
        original_url="https://wiresource.com/trade-accord",
        canonical_url="https://wiresource.com/trade-accord",
        canonical_url_hash="bb" * 32,
        source_id=source.id,
        published_at=now,
        status="published",
        is_trending=True,
        is_breaking=False,
        cluster_id="cluster-trade-1234",
    )
    art_breaking = NewsArticle(
        title="Major Flash Flooding Prompts Evacuations",
        slug="major-flash-flooding-prompts-evacuations",
        original_url="https://wiresource.com/flooding",
        canonical_url="https://wiresource.com/flooding",
        canonical_url_hash="cc" * 32,
        source_id=source.id,
        published_at=now,
        status="published",
        is_trending=True,
        is_breaking=True,
        cluster_id="cluster-flood-5678",
    )
    db_session.add_all([art_standard, art_trending, art_breaking])
    await db_session.commit()

    # Query with trending=true
    resp_trending = await client.get("/api/v1/articles?trending=true")
    assert resp_trending.status_code == 200
    trending_items = resp_trending.json()["items"]
    trending_slugs = [item["slug"] for item in trending_items]
    assert "historic-trade-accord-ratified" in trending_slugs
    assert "major-flash-flooding-prompts-evacuations" in trending_slugs
    assert "standard-daily-briefing" not in trending_slugs

    # Query with breaking=true
    resp_breaking = await client.get("/api/v1/articles?breaking=true")
    assert resp_breaking.status_code == 200
    breaking_items = resp_breaking.json()["items"]
    breaking_slugs = [item["slug"] for item in breaking_items]
    assert "major-flash-flooding-prompts-evacuations" in breaking_slugs
    assert "historic-trade-accord-ratified" not in breaking_slugs
    assert "standard-daily-briefing" not in breaking_slugs


@pytest.mark.asyncio
async def test_get_related_articles_cluster_and_category(client: AsyncClient, db_session: AsyncSession):
    source1 = NewsSource(name="Publisher One", domain="pubone.com")
    source2 = NewsSource(name="Publisher Two", domain="pubtwo.com")
    cat = NewsCategory(name="Environment", slug="environment")
    db_session.add_all([source1, source2, cat])
    await db_session.commit()

    now = datetime.datetime.now(datetime.timezone.utc)
    cluster_tag = "cluster-wildfire-2026"

    lead_article = NewsArticle(
        title="Wildfire Spreads Along Coastal Ridge",
        slug="wildfire-spreads-along-coastal-ridge",
        original_url="https://pubone.com/wildfire-lead",
        canonical_url="https://pubone.com/wildfire-lead",
        canonical_url_hash="dd" * 32,
        source_id=source1.id,
        category_id=cat.id,
        published_at=now,
        status="published",
        cluster_id=cluster_tag,
    )
    related_in_cluster = NewsArticle(
        title="Firefighters Contain 40 Percent of Coastal Ridge Fire",
        slug="firefighters-contain-40-percent-of-coastal-ridge-fire",
        original_url="https://pubtwo.com/wildfire-followup",
        canonical_url="https://pubtwo.com/wildfire-followup",
        canonical_url_hash="ee" * 32,
        source_id=source2.id,
        category_id=cat.id,
        published_at=now,
        status="published",
        cluster_id=cluster_tag,
    )
    db_session.add_all([lead_article, related_in_cluster])
    await db_session.commit()

    # Query related endpoint
    rel_resp = await client.get(f"/api/v1/articles/{lead_article.slug}/related?limit=5")
    assert rel_resp.status_code == 200
    rel_items = rel_resp.json()
    assert len(rel_items) >= 1
    assert rel_items[0]["slug"] == related_in_cluster.slug
    assert "cluster_id" not in rel_items[0]
    assert "quality_score" not in rel_items[0]
    assert "status" not in rel_items[0]

    # Missing article slug returns 404
    missing_rel = await client.get("/api/v1/articles/unknown-lead-article/related")
    assert missing_rel.status_code == 404
