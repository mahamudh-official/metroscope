import asyncio
import os
import subprocess
import sys
import time
import urllib.request
import json

def main():
    print("=" * 70)
    print("VERIFYING HOMEPAGE & BACKEND SERVICES")
    print("=" * 70)

    # 1. Start backend on port 8001 (since 8000 is used by docker edu container)
    backend_env = os.environ.copy()
    backend_env["PORT"] = "8001"
    backend_env["BACKEND_PORT"] = "8001"
    
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
        cwd="backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=backend_env,
    )
    print(f"Backend started (PID: {backend_proc.pid}) on http://127.0.0.1:8001")

    try:
        # Wait for backend readiness
        time.sleep(3)
        with urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=5) as r:
            health_body = r.read().decode()
            print(f"Backend Health check: HTTP {r.status} -> {health_body}")

        # Check published articles from backend API
        with urllib.request.urlopen("http://127.0.0.1:8001/api/v1/articles", timeout=5) as r:
            articles_data = json.loads(r.read().decode())
            print(f"Backend API Published Articles Count: {articles_data.get('total')}")
            for item in articles_data.get("items", []):
                print(f"  - [{item.get('id')}] {item.get('title')[:60]} (Author: {item.get('author')})")

        # 2. Start frontend on port 3000
        frontend_env = os.environ.copy()
        frontend_env["PORT"] = "3000"
        frontend_env["INTERNAL_API_URL"] = "http://127.0.0.1:8001/api/v1"
        frontend_env["NEXT_PUBLIC_API_URL"] = "http://localhost:8001/api/v1"
        frontend_env["NEXT_PUBLIC_SITE_URL"] = "http://localhost:3000"

        frontend_proc = subprocess.Popen(
            ["node", "server.js"],
            cwd=r"frontend\.next\standalone",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=frontend_env,
        )
        print(f"Frontend started (PID: {frontend_proc.pid}) on http://localhost:3000")

        try:
            time.sleep(4)
            # Query Homepage
            req = urllib.request.Request("http://localhost:3000", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as r:
                html = r.read().decode("utf-8", errors="ignore")
                print(f"Frontend Homepage HTTP Status: {r.status}")
                print(f"Frontend Homepage HTML length: {len(html)} bytes")
                # Check for MetroScope News Desk author in homepage
                desk_count = html.count("MetroScope News Desk")
                print(f"Found 'MetroScope News Desk' occurrences in homepage HTML: {desk_count}")
        finally:
            frontend_proc.terminate()
            frontend_proc.wait(timeout=3)
    finally:
        backend_proc.terminate()
        backend_proc.wait(timeout=3)

    print("=" * 70)
    print("HOMEPAGE & BACKEND VERIFICATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
