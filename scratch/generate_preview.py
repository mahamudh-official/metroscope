import asyncio
from pathlib import Path
import sys

# Ensure backend path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db.session import async_engine
from app.models.article import NewsArticle
from app.services.photo_card_service import PhotoCardService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

async def main():
    async with AsyncSession(async_engine) as session:
        stmt = select(NewsArticle).options(selectinload(NewsArticle.category)).where(NewsArticle.id == 72)
        res = await session.execute(stmt)
        article = res.scalar_one_or_none()
        if not article:
            print("Article #72 not found!")
            return

        service = PhotoCardService()
        html_out = service.render_html(article, canvas_fixed=False)

        # 1. Save to scratch
        scratch_preview = Path(__file__).resolve().parent / "metroscope_photo_card_corrected_preview.html"
        scratch_preview.write_text(html_out, encoding="utf-8")

        # 2. Save to artifact directory
        artifact_path = Path(r"C:\Users\Hasan\.gemini\antigravity\brain\4f53b72f-8d4e-4c36-af68-f3030d11f33f\metroscope_photo_card_corrected_preview.html")
        artifact_path.write_text(html_out, encoding="utf-8")

        print("=== PREVIEW GENERATION SUMMARY ===")
        print(f"Article ID: {article.id}")
        print(f"Article Title: {article.title}")
        print(f"Published At (DB): {article.published_at}")
        print(f"Category: {article.category.name if article.category else 'N/A'}")
        print(f"Scratch Preview: {scratch_preview}")
        print(f"Artifact Preview: {artifact_path}")
        print(f"Brand logo <img> tag present: {'class=\"brand-logo\"' in html_out}")
        print(f"Base64 PNG URI present: {'data:image/png;base64,' in html_out}")
        print(f"Text wordmark absent: {'metro<span>scope</span>' not in html_out}")
        
        for line in html_out.splitlines():
            if 'class="date"' in line:
                print(f"Date Line in HTML: {line.strip()}")
            if 'class="brand"' in line:
                print(f"Brand Line in HTML: {line[:100]}...")

        # Also verify Article #56 to confirm different date
        stmt56 = select(NewsArticle).where(NewsArticle.id == 56)
        res56 = await session.execute(stmt56)
        art56 = res56.scalar_one_or_none()
        if art56:
            html56 = service.render_html(art56)
            for line in html56.splitlines():
                if 'class="date"' in line:
                    print(f"Article #56 Date Line in HTML: {line.strip()}")

asyncio.run(main())
