import asyncio
import datetime
import json
import asyncpg
import httpx

DB_URL = "postgresql://metroscope_user:metroscope_secure_password@127.0.0.1:5433/metroscope"
API_BASE = "http://127.0.0.1:8000/api/v1"
FE_BASE = "http://localhost:3000"

TEST_ARTICLES = [
    {
        "slug": "test-auth-english-fulltext",
        "title": "NASA Mars Rover Discovers Evidence of Ancient River System",
        "canonical_url": "https://www.nasa.gov/news/mars-river-system",
        "original_url": "https://www.nasa.gov/news/mars-river-system",
        "language": "en",
        "description": "Perseverance rover identifies geological sediment layers indicating past surface water in Jezero Crater.",
        "full_text": "PASADENA, Calif. — NASA's Perseverance rover has collected geological samples confirming ancient river flow across Jezero Crater.\n\nKey Findings on Crater Sedimentation\n\nThe findings were confirmed following mineralogical spectrometry that revealed crystalline clay minerals formed in the presence of liquid water.\n\n> The sedimentation layers closely resemble fluvial deltas seen on Earth, indicating a long-lived lake basin.\n\nNext Phase of Core Retrieval\n\nMission scientists reported that sealed titanium tubes are being pre-positioned for future international retrieval operations.",
        "content_display_authorized": True,
        "image_url": "https://images.nasa.gov/photo/artemis.jpg",
        "image_metadata": json.dumps({
            "external_only": True,
            "hero": {
                "url": "https://images.nasa.gov/photo/artemis.jpg",
                "caption": "Panoramic mosaic of ancient river delta sediment layers inside Jezero Crater.",
                "credit": "NASA/JPL-Caltech/MSSS",
                "authorized": True,
                "reason": "US Federal Government public domain visual media",
            },
            "inline_images": [
                {
                    "url": "https://images.nasa.gov/photo/rover-arm.jpg",
                    "caption": "Robotic arm coring drill positioned over fine-grained sedimentary rock.",
                    "credit": "NASA/JPL-Caltech",
                    "authorized": True,
                }
            ],
            "rights": {
                "full_text_authorized": True,
                "hero_image_authorized": True,
                "inline_images_authorized": True,
            }
        }),
        "source_name": "NASA Jet Propulsion Laboratory",
        "source_domain": "nasa.gov",
        "category_slug": "science",
    },
    {
        "slug": "test-auth-unicode-bangla",
        "title": "নাসার নতুন কৃত্রিম উপগ্রহ জলবায়ু গবেষণায় নতুন দিগন্ত উন্মোচন করেছে",
        "canonical_url": "https://www.nasa.gov/bn/climate-satellite",
        "original_url": "https://www.nasa.gov/bn/climate-satellite",
        "language": "bn",
        "description": "নাসার নতুন কৃত্রিম উপগ্রহ বায়ুমণ্ডলের তাপমাত্রা ও মেঘের গঠন নির্ভুলভাবে পরিমাপ করবে।",
        "full_text": "ওয়াশিংটন — মার্কিন মহাকাশ গবেষণা সংস্থা নাসা পৃথিবীর জলবায়ু পরিবর্তনের সুনির্দিষ্ট তথ্য সংগ্রহের লক্ষ্যে নতুন উপগ্রহ সফলভাবে উৎক্ষেপণ করেছে।\n\nজলবায়ু গবেষণায় নতুন দিগন্ত\n\nউপগ্রহটি মেরু অঞ্চলের বরফ গলার গতি এবং সমুদ্রপৃষ্ঠের উচ্চতা বৃদ্ধির তথ্য প্রতিদিন পৃথিবীতে পাঠাবে।\n\n> বিজ্ঞানীরা আশা করছেন এই তথ্য ভবিষ্যতের দুর্যোগ ব্যবস্থাপনায় বৈপ্লবিক পরিবর্তন আনবে।\n\nআন্তর্জাতিক মহাকাশ পর্যবেক্ষণ\n\nবিশ্বের বিভিন্ন দেশের গবেষণা সংস্থা এই উন্মুক্ত ডেটাসেট ব্যবহার করে আঞ্চলিক আবহাওয়া মডেল উন্নত করতে পারবে।",
        "content_display_authorized": True,
        "image_url": "https://images.nasa.gov/climate-satellite.jpg",
        "image_metadata": json.dumps({
            "external_only": True,
            "hero": {
                "url": "https://images.nasa.gov/climate-satellite.jpg",
                "caption": "মহাকাশ থেকে পৃথিবীর বায়ুমণ্ডলের তাপমাত্রা ও আর্দ্রতা পরিমাপক নতুন কৃত্রিম উপগ্রহ।",
                "credit": "নাসা/জেপিএল",
                "authorized": True,
                "reason": "US Federal Government public domain visual media",
            },
            "inline_images": [],
            "rights": {
                "full_text_authorized": True,
                "hero_image_authorized": True,
                "inline_images_authorized": True,
            }
        }),
        "source_name": "NASA Newsroom",
        "source_domain": "nasa.gov",
        "category_slug": "science",
    },
    {
        "slug": "test-unauth-commercial-masked",
        "title": "Tech Giants Announce Next-Generation Semiconductor Alliance",
        "canonical_url": "https://www.wsj.com/tech/semiconductor-alliance-2026",
        "original_url": "https://www.wsj.com/tech/semiconductor-alliance-2026",
        "language": "en",
        "description": "Major chip manufacturers form joint standards group to accelerate sub-2nm node packaging.",
        "full_text": "PROPRIETARY TEXT: This is full syndicated copy from WSJ that MUST NEVER be rendered publicly without express license. Paragraph 2 contains proprietary analysis and private interviews.",
        "content_display_authorized": False,
        "image_url": None,
        "image_metadata": json.dumps({
            "external_only": True,
            "hero": {
                "url": "https://images.wsj.net/im-semiconductor.jpg",
                "authorized": False,
                "reason": "Commercial publisher visual media: copyright reserved",
            },
            "inline_images": [],
            "rights": {
                "full_text_authorized": False,
                "hero_image_authorized": False,
                "inline_images_authorized": False,
            }
        }),
        "source_name": "The Wall Street Journal",
        "source_domain": "wsj.com",
        "category_slug": "technology",
    },
    {
        "slug": "test-summary-only-wire",
        "title": "Global Maritime Shipping Rates Stabilize Following Suez Transit Resumption",
        "canonical_url": "https://www.reuters.com/business/shipping-rates-stabilize-2026",
        "original_url": "https://www.reuters.com/business/shipping-rates-stabilize-2026",
        "language": "en",
        "description": "Container spot rates on Asia-to-Europe routes fell 8 percent this week as commercial transit resumed through the canal.",
        "full_text": None,
        "content_display_authorized": False,
        "image_url": None,
        "image_metadata": None,
        "source_name": "Reuters",
        "source_domain": "reuters.com",
        "category_slug": "business",
    },
    {
        "slug": "test-neither-field-flash",
        "title": "Stock Exchange Opening Bell Rings Flat on Heavy Morning Volume",
        "canonical_url": "https://www.bloomberg.com/news/opening-bell-flash",
        "original_url": "https://www.bloomberg.com/news/opening-bell-flash",
        "language": "en",
        "description": None,
        "full_text": None,
        "content_display_authorized": False,
        "image_url": None,
        "image_metadata": None,
        "source_name": "Bloomberg",
        "source_domain": "bloomberg.com",
        "category_slug": "business",
    },
]

async def setup_test_records():
    conn = await asyncpg.connect(DB_URL)
    cat_id = await conn.fetchval("SELECT id FROM news_categories LIMIT 1")
    src_id = await conn.fetchval("SELECT id FROM news_sources LIMIT 1")
    now = datetime.datetime.now(datetime.timezone.utc)

    for item in TEST_ARTICLES:
        import hashlib
        url_hash = hashlib.sha256(item["canonical_url"].encode("utf-8")).hexdigest()
        exists = await conn.fetchval("SELECT id FROM news_articles WHERE slug = $1", item["slug"])
        if exists:
            await conn.execute("""
                UPDATE news_articles 
                SET title = $2, canonical_url = $3, canonical_url_hash = $4, original_url = $5, language = $6,
                    description = $7, full_text = $8, content_display_authorized = $9,
                    image_url = $10, image_metadata = $11,
                    status = 'published', published_at = $12
                WHERE slug = $1
            """, item["slug"], item["title"], item["canonical_url"], url_hash, item["original_url"],
               item["language"], item["description"], item["full_text"], item["content_display_authorized"],
               item.get("image_url"), item.get("image_metadata"), now)
        else:
            await conn.execute("""
                INSERT INTO news_articles (
                    slug, title, canonical_url, canonical_url_hash, original_url, language,
                    description, full_text, content_display_authorized,
                    image_url, image_metadata,
                    category_id, source_id, status, published_at, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, 'published', $14, $14, $14)
            """, item["slug"], item["title"], item["canonical_url"], url_hash, item["original_url"],
               item["language"], item["description"], item["full_text"], item["content_display_authorized"],
               item.get("image_url"), item.get("image_metadata"), cat_id, src_id, now)

    await conn.close()
    print("Database test records seeded/verified successfully.")

def verify_api_and_frontend():
    with httpx.Client(timeout=10.0) as client:
        print("\n--- Verifying Backend API Endpoint ---")
        for item in TEST_ARTICLES:
            slug = item["slug"]
            api_url = f"{API_BASE}/articles/{slug}"
            resp = client.get(api_url)
            assert resp.status_code == 200, f"API failed for {slug}: {resp.status_code}"
            data = resp.json()

            print(f"\n[API TEST] Slug: {slug}")
            print(f"  Title: {data['title'][:60]}")
            print(f"  Authorized: {data['content_display_authorized']}")
            print(f"  Full text exposed: {bool(data.get('full_text'))}")
            print(f"  Description: {bool(data.get('description'))}")
            print(f"  Image URL exposed: {bool(data.get('image_url'))}")

            if item["content_display_authorized"]:
                assert data["content_display_authorized"] is True
                assert data["full_text"] is not None
                assert len(data["full_text"]) > 20
                if item["language"] == "bn":
                    assert "মহাকাশ গবেষণা সংস্থা" in data["full_text"]
                else:
                    assert "Perseverance" in data["full_text"]
                print("  -> PASS (Authorized full text exposed)")
            else:
                assert data["content_display_authorized"] is False
                assert data["full_text"] is None, "CRITICAL: Unauthorized full_text leaked!"
                if item["description"]:
                    assert data["description"] == item["description"]
                    print("  -> PASS (Unauthorized full text masked, summary preserved)")
                else:
                    assert data["description"] is None
                    print("  -> PASS (Unauthorized, summary is None)")

        print("\n--- Verifying Next.js Frontend Rendering ---")
        for item in TEST_ARTICLES:
            slug = item["slug"]
            fe_url = f"{FE_BASE}/article/{slug}"
            fe_resp = client.get(fe_url)
            assert fe_resp.status_code == 200, f"Frontend failed for {slug}: {fe_resp.status_code}"
            html = fe_resp.text

            print(f"\n[FRONTEND TEST] URL: {fe_url}")
            assert "Original Reporting by" not in html, "ERROR: Redundant 'Original Reporting by' box still in HTML!"
            assert "Source: " not in html, "ERROR: Redundant 'Source: ' url display still in HTML!"

            if item["content_display_authorized"]:
                assert "article" in html.lower()
                if item["language"] == "bn":
                    assert "মহাকাশ গবেষণা সংস্থা" in html
                    assert "জলবায়ু গবেষণায়" in html
                    print("  -> PASS (Frontend rendered non-English Unicode full article body)")
                else:
                    assert "Perseverance rover" in html
                    assert "Key Findings" in html
                    print("  -> PASS (Frontend rendered English full article body with subheadings & paragraphs)")
            elif item["description"]:
                assert "Story Summary" in html
                assert "Read Full Article at" in html
                print("  -> PASS (Frontend rendered permitted summary fallback)")
            else:
                assert "Full reporting for this story was published by" in html
                assert "Read Full Article at" in html
                print("  -> PASS (Frontend rendered minimal headline fallback)")

    print("\nALL 5 TEST MATRIX CASES PASSED VERIFICATION!")

if __name__ == "__main__":
    asyncio.run(setup_test_records())
    verify_api_and_frontend()
