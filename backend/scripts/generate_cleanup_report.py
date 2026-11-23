import asyncio
import sys
import json
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.article import NewsArticle
from app.models.source import NewsSource
from app.models.category import NewsCategory
from app.services.article_validation_service import ArticleEditorialValidationService

async def generate_audit():
    async with async_session_factory() as db:
        res = await db.execute(select(NewsArticle).order_by(NewsArticle.id))
        articles = res.scalars().all()
        
        pass_list = []
        reject_list = []
        
        for a in articles:
            source = await db.get(NewsSource, a.source_id) if a.source_id else None
            cat = await db.get(NewsCategory, a.category_id) if a.category_id else None
            domain = source.domain if source else ""
            cat_slug = cat.slug if cat else "world"
            
            val_res = ArticleEditorialValidationService.evaluate_candidate(
                title=a.title,
                canonical_url=a.canonical_url,
                published_at=a.published_at,
                domain=domain,
                category_slug=cat_slug,
                summary=a.description,
                full_text=a.full_text,
                publisher_name=a.publisher_name or (source.name if source else None),
                author=a.author,
                image_url=a.image_url,
                language=a.language,
                content_display_authorized=a.content_display_authorized,
            )
            
            record_info = {
                "id": a.id,
                "title": a.title,
                "current_status": a.status,
                "domain": domain,
                "publisher": a.publisher_name or (source.name if source else None),
                "author": a.author,
                "category": cat_slug,
                "desc_len": len(a.description or ""),
                "full_text_len": len(a.full_text or ""),
                "authorized": a.content_display_authorized,
                "val_is_valid": val_res.is_valid,
                "val_status": val_res.status,
                "val_filter_reason": val_res.filter_reason,
            }
            
            if val_res.is_valid:
                pass_list.append(record_info)
            else:
                reject_list.append(record_info)
                
        print(f"TOTAL AUDITED: {len(articles)}")
        print(f"PASS (Eligible for Published status): {len(pass_list)}")
        print(f"REJECT (Proposed for Removal/Quarantine): {len(reject_list)}\n")
        
        print("=" * 80)
        print("PROPOSED REJECT / REMOVAL LIST:")
        print("=" * 80)
        for r in reject_list:
            print(f"ID {r['id']:2d} | Category: {r['category']:<10} | Current DB Status: {r['current_status']}")
            print(f"  Title:     {r['title'][:75]}")
            print(f"  Publisher: {r['publisher']}")
            print(f"  Domain:    {r['domain']}")
            print(f"  Reason:    {r['val_filter_reason']}")
            print(f"  Evidence:  desc_len={r['desc_len']}, full_text_len={r['full_text_len']}, authorized={r['authorized']}")
            print("-" * 80)
            
        print("\n" + "=" * 80)
        print("PASS LIST (Genuine, Design-Compatible News):")
        print("=" * 80)
        for p in pass_list:
            print(f"ID {p['id']:2d} | Category: {p['category']:<10} | Publisher: {p['publisher']}")
            print(f"  Title:     {p['title'][:75]}")
            print(f"  Author:    {p['author']}")
            print(f"  Content:   desc_len={p['desc_len']}, full_text_len={p['full_text_len']}, authorized={p['authorized']}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(generate_audit())
