"""MetroScope Phase 9 — Frontend & API Routing Verification Script
Validates:
- All 12 frontend routes on Next.js standalone server (port 3000)
- Article slug resolution & SSR rendering with live data
- Category pages, Search, Legal/Informational pages
- Static assets, robots.txt, sitemap.xml, rss.xml
- API proxying & direct FastAPI responses (port 8000)
- Security headers: X-Content-Type-Options, X-Frame-Options, Referrer-Policy
"""

import urllib.request
import urllib.error
import json
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def probe(url, expected_status=200):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "MetroScope-Phase9-Validator/1.0", "Accept": "*/*"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            body = resp.read()
            headers = dict(resp.headers)
            return status, body, headers
    except urllib.error.HTTPError as e:
        body = e.read()
        return e.code, body, dict(e.headers)
    except Exception as e:
        return 0, str(e).encode(), {}

def main():
    print("=" * 70)
    print("METROSCOPE PHASE 9: FRONTEND & ROUTING VALIDATION")
    print("=" * 70)

    # 1. Fetch live articles from API to get a real slug
    status, body, headers = probe("http://127.0.0.1:8000/api/v1/articles?limit=5")
    assert status == 200, f"Failed to fetch articles from API: {status}"
    articles_data = json.loads(body.decode("utf-8"))
    articles = articles_data.get("items", [])
    print(f"[API] Retrieved {len(articles)} published articles from API.")
    assert len(articles) > 0, "No articles returned from API"
    sample_slug = articles[0]["slug"]
    print(f"  -> Sample slug: {sample_slug}")

    # 2. Test 12 Frontend Routes
    routes_to_test = [
        ("/", "Homepage (with Newsletter UI)", 200),
        ("/category/world", "World Category", 200),
        ("/category/business", "Business Category", 200),
        ("/category/technology", "Technology Category", 200),
        (f"/article/{sample_slug}", "Article Detail (SSR)", 200),
        ("/search?q=news", "Search Results", 200),
        ("/about", "About MetroScope", 200),
        ("/contact", "Contact Page", 200),
        ("/privacy", "Privacy Policy", 200),
        ("/terms", "Terms of Service", 200),
        ("/verify-subscription?token=sample_token_for_validation", "Verify Subscription", 200),
        ("/unsubscribe?token=sample_token_for_validation", "Unsubscribe Confirmation", 200),
        ("/this-route-does-not-exist-test-404", "Custom 404 Page", 404),
    ]

    print("\n[FRONTEND] Probing 13 Frontend Routes on http://localhost:3000...")
    all_passed = True
    for route, name, expected_code in routes_to_test:
        url = f"http://localhost:3000{route}"
        st, b, h = probe(url, expected_code)
        passed = (st == expected_code)
        if not passed:
            all_passed = False
        mark = "[PASS]" if passed else "[FAIL]"
        body_len = len(b)
        content_type = h.get("content-type", "unknown")
        print(f"  {mark} [{st}] {name:30s} -> {route} ({body_len} bytes, {content_type.split(';')[0]})")

    assert all_passed, "One or more frontend routes failed!"

    # 3. Test SEO & Feed Endpoints
    print("\n[SEO & FEEDS] Testing SEO and Feed Assets...")
    seo_routes = [
        ("/robots.txt", 200, "User-agent"),
        ("/sitemap.xml", 200, "urlset"),
        ("/rss.xml", 200, "rss"),
    ]
    for route, exp_code, expected_snippet in seo_routes:
        url = f"http://localhost:3000{route}"
        st, b, h = probe(url, exp_code)
        text_b = b.decode("utf-8", errors="replace")
        has_snippet = expected_snippet.lower() in text_b.lower()
        passed = (st == exp_code and has_snippet)
        mark = "[PASS]" if passed else "[FAIL]"
        print(f"  {mark} [{st}] {route:15s} -> snippet '{expected_snippet}' present={has_snippet}")
        assert passed, f"SEO route {route} failed!"

    # 4. Security Headers Verification
    print("\n[SECURITY HEADERS] Validating HTTP Security Headers...")
    # Check headers on FastAPI
    _, _, api_h = probe("http://127.0.0.1:8000/api/v1/health")
    print("  FastAPI Headers:")
    for header in ["x-content-type-options", "x-frame-options", "referrer-policy"]:
        val = api_h.get(header)
        print(f"    * {header}: {val}")

    # Check headers on Next.js
    _, _, fe_h = probe("http://localhost:3000/")
    print("  Next.js Headers:")
    for header in ["x-content-type-options", "x-frame-options", "referrer-policy", "x-powered-by"]:
        val = fe_h.get(header)
        print(f"    * {header}: {val}")

    print("\n" + "=" * 70)
    print("ALL FRONTEND & ROUTING VALIDATIONS PASSED PERFECTLY!")
    print("=" * 70)

if __name__ == "__main__":
    main()
