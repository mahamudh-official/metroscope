"""Data Repair Script for MetroScope Validation Pipeline Correction.

Reprocesses existing database records using the new centralized validation rules:
- Cleans and normalizes author names (removes emails, generic labels, unknown placeholders).
- Cleans and normalizes publisher display names (strips marketing taglines, rejects - homepage).
- Updates article publication status (quarantines/filters articles without genuine summary and authorized full text,
  and articles with invalid/spam publisher identities).
- Preserves all legitimate real articles, sources, categories, and newsletter data without resetting the database.
"""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.article import NewsArticle
from app.models.source import NewsSource
from app.services.article_validation_service import ArticleEditorialValidationService
from app.services.normalizer_service import normalize_author_name, normalize_publisher_name


async def repair_data():
    print("=" * 80)
    print("METROSCOPE — EXISTING DATA REPAIR")
    print("=" * 80)

    async with async_session_factory() as db:
        res = await db.execute(select(NewsArticle).order_by(NewsArticle.id))
        articles = res.scalars().all()

        print(f"Total articles to evaluate: {len(articles)}")
        print("-" * 80)

        for art in articles:
            source = await db.get(NewsSource, art.source_id) if art.source_id else None
            domain = source.domain if source else ""

            old_status = art.status
            old_author = art.author
            old_pub = art.publisher_name

            # 1. Normalize Publisher
            clean_pub = normalize_publisher_name(
                raw_name=art.publisher_name or (source.name if source else None),
                domain=domain,
                title=art.title,
            )

            # 2. Normalize Author
            clean_author = normalize_author_name(
                raw_author=art.author,
                title=art.title,
                publisher=clean_pub,
                domain=domain,
            )

            # 3. Evaluate Editorial Validation Candidate
            val_result = ArticleEditorialValidationService.evaluate_candidate(
                title=art.title,
                canonical_url=art.canonical_url,
                published_at=art.published_at,
                domain=domain,
                category_slug=art.category.slug if art.category else "world",
                summary=art.description,
                full_text=art.full_text,
                publisher_name=clean_pub,
                author=clean_author,
                image_url=art.image_url,
                language=art.language,
                content_display_authorized=art.content_display_authorized,
            )

            # Apply repaired values
            art.author = clean_author
            art.publisher_name = clean_pub
            art.status = val_result.status
            art.filter_reason = val_result.filter_reason
            if val_result.cleaned_summary is not None:
                art.description = val_result.cleaned_summary
            if val_result.cleaned_full_text is not None:
                art.full_text = val_result.cleaned_full_text

            if source and clean_pub:
                source.name = clean_pub

            print(f"Article ID {art.id:2d}: '{art.title[:45]}...'")
            print(f"  Author:    {old_author!r} -> {art.author!r}")
            print(f"  Publisher: {old_pub!r} -> {art.publisher_name!r}")
            print(f"  Status:    {old_status} -> {art.status} ({art.filter_reason or 'No filter reason'})")
            print()

        await db.commit()
        print("=" * 80)
        print("DATABASE COMMITTED SUCCESSFULLY")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(repair_data())
