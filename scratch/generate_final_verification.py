import asyncio, sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path("backend").resolve()))

from app.db.session import async_session_factory
from app.models.article import NewsArticle
from app.services.photo_card_service import PhotoCardService

async def main():
    async with async_session_factory() as session:
        # Fetch article #83 (same as the Facebook post)
        article = await session.get(NewsArticle, 83)
        if not article:
            print("Article #83 not found")
            return

        print(f"Rendering Photo Card for Article #{article.id}: '{article.title}'...")
        service = PhotoCardService()
        
        # 1. Render HTML preview
        html_content = service.render_html(article, canvas_fixed=True)
        html_preview_path = Path("scratch/photo_card_verified_preview.html")
        html_preview_path.write_text(html_content, encoding="utf-8")
        print(f"Saved HTML preview to {html_preview_path}")

        # 2. Render actual JPEG image via ScreenshotOne
        img_bytes = await service.render_image(article, format="jpeg", image_quality=92)
        
        # Save to scratch
        img_scratch_path = Path("scratch/photo_card_verified_preview.jpg")
        img_scratch_path.write_bytes(img_bytes)
        print(f"Saved JPEG image to {img_scratch_path}")

        # Verify image dimensions with PIL
        im = Image.open(img_scratch_path)
        print("=== VERIFIED IMAGE METRICS ===")
        print(f"Format: {im.format}")
        print(f"Dimensions: {im.size} (Width: {im.width}px, Height: {im.height}px)")
        print(f"Aspect Ratio: {im.width / im.height:.2f}:1")
        print(f"File size: {len(img_bytes)} bytes ({len(img_bytes) / 1024:.1f} KB)")

        # Save to artifact directory
        artifact_dir = Path(r"C:\Users\Hasan\.gemini\antigravity\brain\0d98fc30-2c6f-43d8-b071-8b36c528cd7d")
        artifact_img = artifact_dir / "photo_card_verified_preview.jpg"
        artifact_img.write_bytes(img_bytes)
        artifact_html = artifact_dir / "photo_card_verified_preview.html"
        artifact_html.write_text(html_content, encoding="utf-8")
        print(f"Copied artifacts to {artifact_img} and {artifact_html}")

asyncio.run(main())
