"""Consolidated runtime smoke check for MetroScope News Desk attribution & system health."""
import asyncio
import json
import sys
import urllib.error
import urllib.request

sys.path.insert(0, "backend")

from sqlalchemy import text
from app.db.session import async_engine


def fetch_http(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "MetroScope-SmokeCheck/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace"), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace"), dict(e.headers)


async def check_database():
    async with async_engine.connect() as conn:
        total = (await conn.execute(text("SELECT count(id) FROM news_articles"))).scalar()
        published = (await conn.execute(text("SELECT count(id) FROM news_articles WHERE status = 'published'"))).scalar()
        filtered = (await conn.execute(text("SELECT count(id) FROM news_articles WHERE status = 'filtered'"))).scalar()
        desk_author_count = (
            await conn.execute(
                text("SELECT count(id) FROM news_articles WHERE author = 'MetroScope News Desk'")
            )
        ).scalar()
        distinct_authors = (
            await conn.execute(text("SELECT DISTINCT author FROM news_articles"))
        ).scalars().all()
        dup_uuids = (
            await conn.execute(
                text("SELECT uuid, count(*) FROM news_articles GROUP BY uuid HAVING count(*) > 1")
            )
        ).all()
        dup_hashes = (
            await conn.execute(
                text("SELECT canonical_url_hash, count(*) FROM news_articles GROUP BY canonical_url_hash HAVING count(*) > 1")
            )
        ).all()
        sample_sources = (
            await conn.execute(
                text(
                    "SELECT a.id, a.author, a.publisher_name, s.name, s.domain "
                    "FROM news_articles a LEFT JOIN news_sources s ON a.source_id = s.id "
                    "ORDER BY a.id LIMIT 5"
                )
            )
        ).all()

    return {
        "total": total,
        "published": published,
        "filtered": filtered,
        "desk_author_count": desk_author_count,
        "distinct_authors": list(distinct_authors),
        "duplicate_uuids": len(dup_uuids),
        "duplicate_url_hashes": len(dup_hashes),
        "sample_sources": [
            {
                "id": r[0],
                "author": r[1],
                "publisher_name": r[2],
                "source_name": r[3],
                "source_domain": r[4],
            }
            for r in sample_sources
        ],
    }


async def main():
    report = {}

    # 1. Database integrity & author attribution
    report["database"] = await check_database()

    # 2. Backend Health & Ops endpoints
    backend_endpoints = [
        "/health",
        "/health/live",
        "/health/ready",
        "/api/v1/health",
        "/api/v1/health/metrics",
        "/api/v1/health/ops",
        "/api/v1/articles",
        "/api/v1/categories",
        "/api/v1/categories/technology/articles",
        "/api/v1/articles/nasa-mars-rover-discovers-evidence-of-ancient-river-system",
    ]
    report["backend_probes"] = {}
    for ep in backend_endpoints:
        status, body, _ = fetch_http(f"http://127.0.0.1:8000{ep}")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body[:300]
        report["backend_probes"][ep] = {"status": status, "body": parsed}

    # 3. Frontend live page probes
    frontend_routes = [
        "/",
        "/category/us",
        "/category/technology",
        "/search?q=news",
        "/article/nasa-mars-rover-discovers-evidence-of-ancient-river-system",
    ]
    report["frontend_probes"] = {}
    for route in frontend_routes:
        status, html, _ = fetch_http(f"http://127.0.0.1:3000{route}")
        has_og = 'property="og:title"' in html and 'property="og:site_name"' in html
        has_twitter = 'name="twitter:card"' in html and 'name="twitter:title"' in html
        has_jsonld = 'application/ld+json' in html
        report["frontend_probes"][route] = {
            "status": status,
            "length": len(html),
            "has_og_tags": has_og,
            "has_twitter_tags": has_twitter,
            "has_jsonld": has_jsonld,
        }

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
