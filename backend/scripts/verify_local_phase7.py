import requests
import json
import sys

BASE_API = "http://127.0.0.1:8000/api/v1"
BASE_FE = "http://localhost:3000"

print("--- 1. Testing Backend /articles Endpoint ---")
r = requests.get(f"{BASE_API}/articles")
assert r.status_code == 200, f"Expected 200, got {r.status_code}"
data = r.json()
items = data.get("items", [])
print(f"Total published articles returned by API: {len(items)}")
for art in items:
    print(f" - {art['title']} (Publisher: {art['source']['name']}, Author: {art.get('author')})")
    # Ensure no leaked internal validation or image_metadata fields
    assert "image_metadata" not in art
    assert "filter_reason" not in art

print("\n--- 2. Testing Specific Article Endpoints ---")
# Pottsville: Summary-only
r = requests.get(f"{BASE_API}/articles/pottsville-schuylkill-technology-center-partnership-to-restore-blighted-property-df1902df")
assert r.status_code == 200, f"Pottsville expected 200, got {r.status_code}"
pottsville = r.json()
print("Pottsville verification:")
print(f"  Title: {pottsville['title']}")
print(f"  Publisher: {pottsville['source']['name']}")
print(f"  Author: {pottsville.get('author')}")
print(f"  Description present: {bool(pottsville.get('description'))}")
print(f"  Full text (commercial/unauthorized): {pottsville.get('full_text')}")
assert pottsville['source']['name'] == "Skook News"
assert pottsville.get('author') is None  # Author correctly stripped from "Unknown (noreply@blogger.com)"
assert pottsville.get('full_text') is None  # Unauthorized full text hidden from public API

# NASA: Authorized full-text
r = requests.get(f"{BASE_API}/articles/nasa-mars-rover-discovers-evidence-of-ancient-river-system")
assert r.status_code == 200, f"NASA expected 200, got {r.status_code}"
nasa = r.json()
print("NASA Mars Rover verification:")
print(f"  Title: {nasa['title']}")
print(f"  Publisher: {nasa['source']['name']}")
print(f"  Author: {nasa.get('author')}")
print(f"  Full text length: {len(nasa.get('full_text') or '')}")
assert nasa['source']['name'] == "NASA"
assert nasa.get('author') == "Dr. Sarah Johnson"
assert nasa.get('full_text') is not None
assert "Jezero Crater" in nasa['full_text']

print("\n--- 3. Testing Quarantined/Filtered Regression Articles (Must 404 from public API) ---")
filtered_slugs = [
    "the-cost-difference-between-one-story-and-multi-story-commercial-builds-6ef07df4",
    "forging-trust-building-secure-international-gold-trading-partnerships-379eb0ad",
    "walmart-management-to-meet-virtually-with-oppenheimer-bf58d35e",
]
for slug in filtered_slugs:
    r = requests.get(f"{BASE_API}/articles/{slug}")
    print(f"  Slug '{slug[:35]}...': Status {r.status_code}")
    assert r.status_code == 404, f"Expected 404 for filtered article {slug}, got {r.status_code}"

print("\n--- 4. Testing Frontend Public Pages ---")
# Pottsville on Frontend
r = requests.get(f"{BASE_FE}/article/pottsville-schuylkill-technology-center-partnership-to-restore-blighted-property-df1902df")
assert r.status_code == 200
html = r.text
assert "Skook News" in html
assert "Unknown" not in html
assert "noreply@blogger.com" not in html
assert "Detailed reporting on this story is available directly from the primary publisher." not in html
assert "Full reporting published on original newsroom platform." not in html
assert "Covering news and specialized analysis for MetroScope" not in html
print("Pottsville frontend HTML verified: no fake placeholders, no fake author bio, genuine publisher attribution.")

# NASA on Frontend
r = requests.get(f"{BASE_FE}/article/nasa-mars-rover-discovers-evidence-of-ancient-river-system")
assert r.status_code == 200
nasa_html = r.text
assert "Dr. Sarah Johnson" in nasa_html
assert "NASA" in nasa_html
assert "Jezero Crater" in nasa_html
print("NASA frontend HTML verified: author displayed, publisher displayed, authorized full text rendered.")

# Filtered articles on Frontend (Must return 404)
for slug in filtered_slugs:
    r = requests.get(f"{BASE_FE}/article/{slug}")
    print(f"  Frontend slug '{slug[:35]}...': Status {r.status_code}")
    assert r.status_code == 404

# RSS Feeds
r_rss = requests.get(f"{BASE_FE}/rss.xml")
assert r_rss.status_code == 200
for slug in filtered_slugs:
    assert slug not in r_rss.text
print("RSS Feed verified: filtered articles excluded.")

print("\nALL PHASE 7 VERIFICATION CHECKS PASSED PERFECTLY!")
