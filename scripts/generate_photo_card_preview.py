"""Generates realistic HTML preview files for MetroScope photo cards."""

import datetime
from pathlib import Path
import sys

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.services.photo_card_service import PhotoCardService, PhotoCardData
from app.schemas.canonical_article import CanonicalMetroScopeArticle

def main():
    service = PhotoCardService()

    # 1. Standard technology article matching user-approved sample
    sample_tech = PhotoCardData(
        headline="AI and robotics are reshaping global industry",
        category="Technology",
        published_at=datetime.datetime(2026, 11, 17, 12, 0, 0, tzinfo=datetime.timezone.utc),
        image_url="https://images.unsplash.com/photo-1485827404703-89b55fcc595e?auto=format&fit=crop&w=1600&q=88",
        website_url="https://themetroscope.com",
    )
    html_tech = service.render_html(sample_tech, canvas_fixed=False)

    out_file = Path("docs/reports/photo_card_preview.html")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(html_tech, encoding="utf-8")
    print(f"Generated sample photo card preview at: {out_file.resolve()}")

    # 2. Also generate fixed 1080x1080 canvas version for ScreenshotOne testing
    html_fixed = service.render_html(sample_tech, canvas_fixed=True)
    fixed_file = Path("docs/reports/photo_card_canvas_1080x1080.html")
    fixed_file.write_text(html_fixed, encoding="utf-8")
    print(f"Generated 1080x1080 canvas preview at: {fixed_file.resolve()}")

    # 3. Environment sample without image (fallback gradient)
    sample_fallback = PhotoCardData(
        headline="Global Climate Accord Reaches Critical Implementation Milestone Across Developing Economies",
        category="Environment",
        published_at=datetime.datetime(2026, 11, 17, 14, 30, 0, tzinfo=datetime.timezone.utc),
        image_url=None,
        website_url="https://themetroscope.com",
    )
    html_fallback = service.render_html(sample_fallback, canvas_fixed=False)
    fallback_file = Path("docs/reports/photo_card_fallback_preview.html")
    fallback_file.write_text(html_fallback, encoding="utf-8")
    print(f"Generated fallback gradient preview at: {fallback_file.resolve()}")

    # 4. Canonical schema integration verification
    canonical_art = CanonicalMetroScopeArticle(
        uuid="test-uuid-canonical-101",
        title="NASA Mars Rover Discovers Ancient Riverbed Formations on Jezero Crater",
        canonical_url="https://nasa.gov/news/mars-rover-jezero-crater",
        canonical_url_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        domain="nasa.gov",
        publisher_name="NASA",
        published_at=datetime.datetime(2026, 11, 17, 10, 0, 0, tzinfo=datetime.timezone.utc),
        category_slug="science",
        language="en",
        author="MetroScope News Desk",
        full_text=(
            "Scientists operating NASA's Perseverance Mars rover have identified extensive sedimentary layering "
            "consistent with an ancient meandering riverbed on the rim of Jezero Crater. The discovery provides "
            "compelling geological evidence that liquid water once flowed continuously across the Martian surface "
            "for sustained periods billions of years ago."
        ),
        content_display_authorized=True,
        image_url="https://images.unsplash.com/photo-1614728894747-a83421e2b9c9?auto=format&fit=crop&w=1600&q=88",
        hero_image_authorized=True,
    )
    html_canonical = service.render_html(canonical_art, canvas_fixed=False)
    canonical_file = Path("docs/reports/photo_card_canonical_preview.html")
    canonical_file.write_text(html_canonical, encoding="utf-8")
    print(f"Generated canonical article preview at: {canonical_file.resolve()}")

    # Also copy main preview to artifact directory
    artifact_dir = Path(r"C:\Users\Hasan\.gemini\antigravity\brain\4f53b72f-8d4e-4c36-af68-f3030d11f33f")
    if artifact_dir.exists():
        artifact_preview = artifact_dir / "photo_card_preview.html"
        artifact_preview.write_text(html_tech, encoding="utf-8")
        print(f"Copied preview to artifact directory: {artifact_preview}")

if __name__ == "__main__":
    main()
