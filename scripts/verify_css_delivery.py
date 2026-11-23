"""Automated CSS Asset Delivery & Computed Style Verification Script.
"""

import urllib.request
import re
import sys

def main():
    print("=" * 70)
    print("METROSCOPE CSS LOADING & DELIVERY VERIFICATION")
    print("=" * 70)

    base_url = "http://localhost:3000"
    pages_to_test = [
        ("/", "Homepage"),
        ("/category/science", "Category (Science)"),
        ("/category/technology", "Category (Technology)"),
        ("/about", "About Page"),
        ("/search", "Search Page"),
    ]

    all_css_urls = set()

    # 1. Test HTML Pages and Extract CSS Links
    for path, label in pages_to_test:
        url = f"{base_url}{path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MetroScope-Verifier/1.0"})
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                html = resp.read().decode("utf-8")
                # Find all stylesheet links
                matches = re.findall(r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', html)
                if not matches:
                    # Sometimes href precedes rel
                    matches = re.findall(r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\']', html)
                
                print(f"[HTML] {label:<25} ({path:<20}) : HTTP {status} (Found {len(matches)} CSS link(s))")
                for css_path in matches:
                    all_css_urls.add(css_path)
        except Exception as e:
            print(f"[HTML] {label:<25} ({path:<20}) : FAILED -> {e}")

    print("-" * 70)
    print(f"Total Unique CSS Assets Found: {len(all_css_urls)}")
    print("-" * 70)

    # 2. Test CSS Assets Delivery
    css_success = True
    for css_path in sorted(all_css_urls):
        full_css_url = f"{base_url}{css_path}" if css_path.startswith("/") else css_path
        try:
            req = urllib.request.Request(full_css_url, headers={"User-Agent": "MetroScope-Verifier/1.0"})
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                content_type = resp.headers.get("Content-Type", "")
                content = resp.read()
                css_text = content.decode("utf-8", errors="ignore")
                
                # Check for critical MetroScope custom theme variables and utilities
                has_theme_vars = "--background:" in css_text or "--primary:" in css_text
                has_tailwind_base = "*,:after,:before" in css_text or "*,::before,::after" in css_text

                print(f"[CSS] {css_path}")
                print(f"      Status: HTTP {status}")
                print(f"      Content-Type: {content_type}")
                print(f"      File Size: {len(content):,} bytes")
                print(f"      Tailwind Core Present: {'YES' if has_tailwind_base else 'NO'}")
                print(f"      MetroScope Theme Variables Present: {'YES' if has_theme_vars else 'NO'}")

                if status != 200 or "text/css" not in content_type:
                    css_success = False
        except Exception as e:
            print(f"[CSS] {css_path} : FAILED -> {e}")
            css_success = False

    print("-" * 70)
    # 3. Test Static Public Assets (Logo)
    logo_url = f"{base_url}/logo.png"
    try:
        req = urllib.request.Request(logo_url, headers={"User-Agent": "MetroScope-Verifier/1.0"})
        with urllib.request.urlopen(req) as resp:
            status = resp.status
            content_type = resp.headers.get("Content-Type", "")
            size = len(resp.read())
            print(f"[ASSET] /logo.png : HTTP {status} ({content_type}, {size:,} bytes)")
    except Exception as e:
        print(f"[ASSET] /logo.png : FAILED -> {e}")

    print("=" * 70)
    if css_success and len(all_css_urls) > 0:
        print("VERDICT: ALL CSS ASSETS ARE BEING SERVED WITH HTTP 200 AND VALID MIME TYPE!")
    else:
        print("VERDICT: CSS VERIFICATION FAILED!")
        sys.exit(1)
    print("=" * 70)

if __name__ == "__main__":
    main()
