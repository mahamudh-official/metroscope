import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.article import NewsArticle
from app.models.source import NewsSource
from app.models.category import NewsCategory

async def audit():
    output_lines = []
    async with async_session_factory() as db:
        res = await db.execute(select(NewsArticle).order_by(NewsArticle.id))
        articles = res.scalars().all()
        output_lines.append(f"Total articles in DB: {len(articles)}\n")
        
        for a in articles:
            source = await db.get(NewsSource, a.source_id) if a.source_id else None
            cat = await db.get(NewsCategory, a.category_id) if a.category_id else None
            output_lines.append(f"=== Article ID {a.id} ===")
            output_lines.append(f"Title:         {a.title}")
            output_lines.append(f"Status:        {a.status} (Filter: {a.filter_reason})")
            output_lines.append(f"Category:      {cat.slug if cat else None}")
            output_lines.append(f"Domain:        {source.domain if source else None}")
            output_lines.append(f"Publisher:     {a.publisher_name}")
            output_lines.append(f"Author:        {a.author}")
            output_lines.append(f"Desc (len {len(a.description or '')}): {repr((a.description or '')[:100])}")
            output_lines.append(f"FullText (len {len(a.full_text or '')}): Authorized={a.content_display_authorized}")
            output_lines.append(f"URL:           {a.canonical_url}")
            output_lines.append("-" * 60)

    report_path = Path(backend_dir).parent / "docs" / "reports" / "initial_21_records_audit.txt"
    report_path.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"Audit written to {report_path}")

if __name__ == "__main__":
    asyncio.run(audit())
