import urllib.request
import json
import sys

BASE_URL = "http://localhost:3000"
API_URL = "http://127.0.0.1:8000/api/v1"

def check(url, expected_status=200):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MetroScope-Verifier/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            content = resp.read()
            assert status == expected_status, f"Expected {expected_status}, got {status}"
            return True, status, len(content)
    except Exception as e:
        return False, str(e), 0

print("=" * 70)
print("METROSCOPE COMPLETE WORKFLOW & ENDPOINT AUDIT")
print("=" * 70)

# 1. Health and Probes
for endpoint in ["/health", "/health/live", "/health/ready", "/health/metrics", "/api/v1/health"]:
    ok, status, size = check(f"http://127.0.0.1:8000{endpoint}")
    print(f"Health Probe: {endpoint:25} -> Status: {status} (Size: {size}b) [PASS: {ok}]")

# 2. Public Static & Feeds
for route in ["/", "/robots.txt", "/sitemap.xml", "/rss.xml", "/feed.xml", "/about", "/contact", "/privacy", "/terms"]:
    ok, status, size = check(f"{BASE_URL}{route}")
    print(f"Public Page:  {route:25} -> Status: {status} (Size: {size}b) [PASS: {ok}]")

# 3. All 10 Categories
categories = [
    "us", "world", "politics", "business", "technology",
    "science", "health", "environment", "sports", "entertainment"
]
for cat in categories:
    ok, status, size = check(f"{BASE_URL}/category/{cat}")
    print(f"Category:     /category/{cat:15} -> Status: {status} (Size: {size}b) [PASS: {ok}]")

# 4. Search & Pagination
for query in ["technology", "climate", "market"]:
    ok, status, size = check(f"{BASE_URL}/search?q={query}")
    print(f"Search Query: /search?q={query:14} -> Status: {status} (Size: {size}b) [PASS: {ok}]")

# 5. Article API list & detail
try:
    with urllib.request.urlopen(f"{API_URL}/articles?page=1&page_size=3") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"\nAPI Articles List: Total: {data['total']}, Page: {data['page']}, Items returned: {len(data['items'])}")
        if data['items']:
            slug = data['items'][0]['slug']
            ok, status, size = check(f"{BASE_URL}/article/{slug}")
            print(f"Article Detail: /article/{slug[:30]}... -> Status: {status} (Size: {size}b) [PASS: {ok}]")
            # Verify source attribution
            with urllib.request.urlopen(f"{API_URL}/articles/{slug}") as a_resp:
                a_data = json.loads(a_resp.read().decode("utf-8"))
                print(f"Article Attribution: Title='{a_data['title'][:40]}...', Publisher='{a_data.get('publisher_name') or a_data.get('source', {}).get('name')}', Canonical='{a_data.get('canonical_url')}'")
except Exception as e:
    print(f"Error checking article: {e}")

print("=" * 70)
print("AUDIT VERIFICATION COMPLETE")
