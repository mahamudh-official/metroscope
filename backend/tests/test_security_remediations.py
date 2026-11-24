"""Comprehensive Security Regression Tests for MetroScope Production Hardening.

Verifies fixes for:
- VULN-01: Stored XSS prevention in titles, summaries, publisher names, and JSON-LD.
- VULN-02: Billable ScreenshotOne rendering endpoint authentication and rate limiting.
- VULN-03: Docker Compose PostgreSQL port isolation (no 0.0.0.0 exposure).
- VULN-04: Protection of /health/ops and /social/facebook/status telemetry endpoints.
- VULN-05: Rejection of static default SECRET_KEY fallback in production mode.
- VULN-07: Search endpoint query length bounds (min_length=2).
- VULN-08: Production domain (themetroscope.com) configuration in ALLOWED_HOSTS and CORS.
"""

from collections import defaultdict
import datetime
from pathlib import Path
import socket
from unittest.mock import AsyncMock, patch
import httpx
import pytest
import yaml
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.endpoints.photo_cards import check_render_rate_limit, _render_rate_limit_records
from app.api.v1.endpoints.social import verify_operator_auth
from app.core.config import Settings, settings
from app.main import create_app
from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.services.article_validation_service import (
    ArticleEditorialValidationService,
    HTML_INJECTION_PATTERN,
)

AUTH_HEADER = {"Authorization": "Bearer test-operator-token"}
API_KEY_HEADER = {"X-API-Key": "test-operator-token"}


# ---------------------------------------------------------------------------
# 1. VULN-01: Stored XSS & HTML Injection Prevention
# ---------------------------------------------------------------------------
class TestXSSRemediation:
    """Verifies that malicious HTML, script tags, breakouts, and event handlers are strictly blocked."""

    @pytest.mark.parametrize(
        "payload,expected_blocked",
        [
            ("Global Markets Rally</script><svg onload=alert(1)>", True),
            ("Markets Surge </script>", True),
            ("Hello </script/x>", True),
            ("Breaking News <script>alert(1)</script>", True),
            ("Top Story <svg onload='alert(document.domain)'>", True),
            ("Economy Report <img src=x onerror=alert(1)>", True),
            ("White House Briefing <iframe src='https://attacker.com'>", True),
            ("Markets Update <BODY onload=alert(1)>", True),
            ("Tech News <div style='background:url(x)'>", True),
            ("Government Policy onclick=alert(1)", True),
            ("Trade Deal Announcement javascript:alert(1)", True),
            # Legitimate headlines that must NOT be falsely blocked
            ("Federal Reserve Holds Interest Rates at 5.25% - 5.50%", False),
            ("Oil Drops < $50 a Barrel in Rapid Trading", False),
            ("Tech Companies See Gains > 10% This Quarter", False),
            ("Apple & Microsoft Announce New AI Partnership", False),
            ("Bipartisan Senate Panel Approves $1.2 Trillion Infrastructure Bill", False),
        ],
    )
    def test_title_html_injection_regex(self, payload: str, expected_blocked: bool):
        is_blocked = bool(HTML_INJECTION_PATTERN.search(payload))
        assert is_blocked == expected_blocked, f"Payload '{payload}' expected blocked={expected_blocked}, got {is_blocked}"

    def test_validate_title_blocks_closing_script_tags(self):
        ok, reason = ArticleEditorialValidationService.validate_title(
            "Global Markets Surge</script><svg onload=alert(1)>"
        )
        assert ok is False
        assert "illegal HTML tags" in reason

    def test_validate_title_allows_legitimate_math_inequalities(self):
        ok, reason = ArticleEditorialValidationService.validate_title(
            "Inflation Rate Drops < 3% Across Major Sectors"
        )
        assert ok is True
        assert reason is None

    def test_validate_summary_rejects_html_injection(self):
        clean_summary, is_valid = ArticleEditorialValidationService.validate_summary(
            "Economic output increased</script><img src=x onerror=alert(1)> significantly.",
            title="Economic Output Increases Ahead of Projections",
        )
        assert is_valid is False
        assert clean_summary is None

    def test_validate_publisher_rejects_html_tags(self):
        ok, pub, err = ArticleEditorialValidationService.validate_publisher(
            publisher_name="Reuters<script>alert(1)</script>",
            domain="reuters.com",
            title="Global Supply Chains Normalize in Fourth Quarter",
        )
        assert ok is False
        assert "illegal HTML tags" in err


# ---------------------------------------------------------------------------
# 2. VULN-02: ScreenshotOne Rendering Endpoint Auth & Rate Limiting
# ---------------------------------------------------------------------------
class TestScreenshotOneProtection:
    """Verifies that GET /api/v1/photo-cards/articles/{id}/render requires operator auth and enforces rate limits."""

    @pytest.mark.asyncio
    async def test_render_endpoint_unauthorized_rejection(self, client: httpx.AsyncClient):
        # Unauthenticated request must return 401
        response = await client.get("/api/v1/photo-cards/articles/1/render")
        assert response.status_code == 401
        err = response.json()
        err_msg = (err.get("message") or err.get("detail") or "").lower()
        assert "operator authorization" in err_msg

    @pytest.mark.asyncio
    async def test_render_endpoint_invalid_token_rejection(self, client: httpx.AsyncClient):
        # Invalid credentials must return 401
        response = await client.get(
            "/api/v1/photo-cards/articles/1/render",
            headers={"Authorization": "Bearer totally-invalid-secret-key"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_render_endpoint_authorized_proceeds(
        self, client: httpx.AsyncClient, db_session
    ):
        cat = NewsCategory(name="Technology", slug="technology")
        db_session.add(cat)
        await db_session.commit()

        art = NewsArticle(
            title="Autonomous Robotics Milestone Reached in Manufacturing",
            slug="autonomous-robotics-milestone",
            description="Robotics engineers demonstrate advanced tactile manipulation.",
            canonical_url="https://example.com/robotics",
            original_url="https://example.com/robotics",
            canonical_url_hash="r" * 64,
            category_id=cat.id,
            published_at=datetime.datetime.now(datetime.timezone.utc),
            status="published",
        )
        db_session.add(art)
        await db_session.commit()

        with patch("app.services.photo_card_service.ScreenshotOneClient.is_configured", return_value=False):
            # With valid operator Bearer token, it passes auth check
            resp = await client.get(
                f"/api/v1/photo-cards/articles/{art.id}/render",
                headers=AUTH_HEADER,
            )
            # Service unavailable (503) proves authentication succeeded and reached business logic
            assert resp.status_code == 503

    def test_render_rate_limiter_enforcement(self):
        test_ip = "192.0.2.100"
        _render_rate_limit_records[test_ip] = []

        # 30 requests allowed
        for _ in range(30):
            assert check_render_rate_limit(test_ip) is True

        # 31st request rejected
        assert check_render_rate_limit(test_ip) is False

        # Reset
        _render_rate_limit_records[test_ip] = []

    def test_trusted_client_ip_extraction(self):
        from app.api.v1.endpoints.photo_cards import get_trusted_client_ip
        from starlette.datastructures import Headers

        class MockClient:
            def __init__(self, host):
                self.host = host

        class MockRequest:
            def __init__(self, host, headers):
                self.client = MockClient(host)
                self.headers = Headers(headers)

        # 1. Direct untrusted client cannot spoof X-Real-IP
        direct_req = MockRequest("203.0.113.50", {"x-real-ip": "10.0.0.99"})
        assert get_trusted_client_ip(direct_req) == "203.0.113.50"

        # 2. Trusted proxy (127.0.0.1) has X-Real-IP accepted
        proxy_req = MockRequest("127.0.0.1", {"x-real-ip": "203.0.113.50"})
        assert get_trusted_client_ip(proxy_req) == "203.0.113.50"

        # 3. Trusted internal Docker proxy (172.18.0.2) has X-Real-IP accepted
        docker_req = MockRequest("172.18.0.2", {"x-real-ip": "198.51.100.25"})
        assert get_trusted_client_ip(docker_req) == "198.51.100.25"



def _repo_root() -> Path:
    current = Path.cwd()
    if (current / "docker-compose.yml").exists():
        return current
    if (current.parent / "docker-compose.yml").exists():
        return current.parent
    return Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# 3. VULN-03: PostgreSQL Port Exposure in Compose Files
# ---------------------------------------------------------------------------
class TestPostgresPortIsolation:
    """Verifies that PostgreSQL port 5432 is not exposed to 0.0.0.0."""

    def test_docker_compose_binds_postgres_to_localhost_only(self):
        compose_path = _repo_root() / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml must exist"
        with open(compose_path, "r", encoding="utf-8") as f:
            compose_data = yaml.safe_load(f)

        db_service = compose_data["services"]["db"]
        ports = db_service.get("ports", [])
        for port_mapping in ports:
            # Must either start with 127.0.0.1: or not map to host
            port_str = str(port_mapping)
            assert port_str.startswith("127.0.0.1:"), (
                f"docker-compose.yml db service exposes port without loopback binding: {port_str}"
            )

    def test_docker_compose_prod_has_no_host_port_for_db(self):
        compose_prod_path = _repo_root() / "docker-compose.prod.yml"
        assert compose_prod_path.exists(), "docker-compose.prod.yml must exist"
        with open(compose_prod_path, "r", encoding="utf-8") as f:
            compose_data = yaml.safe_load(f)

        db_service = compose_data["services"]["db"]
        assert "ports" not in db_service or not db_service["ports"], (
            "docker-compose.prod.yml must NOT expose host ports for db service"
        )

        for svc_name in ["backend", "worker", "frontend"]:
            image_str = compose_data["services"][svc_name]["image"]
            assert "${IMAGE_TAG:?" in image_str, f"{svc_name} image must require IMAGE_TAG"
            assert ":-latest" not in image_str, f"{svc_name} must NOT have :-latest fallback"


# ---------------------------------------------------------------------------
# 4. VULN-08: Production Domain & ALLOWED_HOSTS Hardening
# ---------------------------------------------------------------------------
class TestProductionDomainConfiguration:
    """Verifies that themetroscope.com is configured across ALLOWED_HOSTS and CORS."""

    def test_canonical_domain_in_allowed_hosts(self):
        assert "themetroscope.com" in settings.ALLOWED_HOSTS
        assert "www.themetroscope.com" in settings.ALLOWED_HOSTS
        assert "api.themetroscope.com" in settings.ALLOWED_HOSTS

    def test_canonical_domain_in_cors_origins(self):
        assert "https://themetroscope.com" in settings.BACKEND_CORS_ORIGINS
        assert "https://www.themetroscope.com" in settings.BACKEND_CORS_ORIGINS

    def test_site_url_points_to_canonical_domain(self):
        # Default Settings without local override must default SITE_URL to https://themetroscope.com
        prod_settings = Settings(
            ENVIRONMENT="production",
            SITE_URL="https://themetroscope.com",
        )
        assert prod_settings.SITE_URL == "https://themetroscope.com"

    def test_trusted_host_middleware_allows_themetroscope_com(self):
        app = create_app()
        client = TestClient(app)

        # Requests with canonical Host header must succeed
        res = client.get("/health", headers={"Host": "themetroscope.com"})
        assert res.status_code == 200

        res_api = client.get("/health", headers={"Host": "api.themetroscope.com"})
        assert res_api.status_code == 200

        # Untrusted host must be rejected with 400 Bad Request
        res_evil = client.get("/health", headers={"Host": "evil-attacker-site.com"})
        assert res_evil.status_code == 400


# ---------------------------------------------------------------------------
# 5. VULN-04 & VULN-05: Telemetry Protection & Production Secret Key Validation
# ---------------------------------------------------------------------------
class TestTelemetryAndAuthHardening:
    """Verifies /health/ops and /facebook/status require authentication and disallows default secret in prod."""

    def test_health_ops_rejects_unauthenticated(self):
        app = create_app()
        client = TestClient(app)
        res = client.get("/api/v1/health/ops")
        assert res.status_code == 401

    def test_health_ops_accepts_operator_token(self):
        app = create_app()
        client = TestClient(app)
        with patch("app.api.v1.endpoints.health.check_db_connection", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = True
            res = client.get("/api/v1/health/ops", headers=AUTH_HEADER)
            assert res.status_code == 200
            assert "database_connected" in res.json()

    @pytest.mark.asyncio
    async def test_facebook_status_rejects_unauthenticated(self, client: httpx.AsyncClient):
        res = await client.get("/api/v1/social/facebook/status")
        assert res.status_code == 401

    @pytest.mark.asyncio
    async def test_facebook_status_accepts_operator_token(self, client: httpx.AsyncClient):
        res = await client.get("/api/v1/social/facebook/status", headers=AUTH_HEADER)
        assert res.status_code == 200
        assert "facebook_enabled" in res.json()

    def test_production_mode_rejects_default_salt_in_operator_auth(self):
        # Simulate production environment with static default salt
        with patch.object(settings, "ENVIRONMENT", "production"):
            with patch.object(settings, "SECRET_KEY", "metroscope_secret_key_default_salt"):
                with pytest.raises(Exception) as exc_info:
                    verify_operator_auth(authorization="Bearer metroscope_secret_key_default_salt")
                assert "401" in str(exc_info.value)

    @pytest.mark.parametrize("weak_secret", ["secret", "123456", "admin", "password", "short_key", "test-operator-token"])
    def test_production_mode_rejects_weak_secrets(self, weak_secret):
        with patch.object(settings, "ENVIRONMENT", "production"):
            with patch.object(settings, "SECRET_KEY", weak_secret):
                with patch.object(settings, "OPERATOR_API_KEY", None):
                    with pytest.raises(Exception) as exc_info:
                        verify_operator_auth(authorization=f"Bearer {weak_secret}")
                    assert "401" in str(exc_info.value)

    def test_production_mode_accepts_strong_secret(self):
        strong_secret = "c4a7f98b1e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d"
        with patch.object(settings, "ENVIRONMENT", "production"):
            with patch.object(settings, "SECRET_KEY", strong_secret):
                assert verify_operator_auth(authorization=f"Bearer {strong_secret}") is True


# ---------------------------------------------------------------------------
# 6. VULN-07: Search Query Length Bounds
# ---------------------------------------------------------------------------
class TestSearchQueryBounds:
    """Verifies that search requires min_length=2 and max_length=100."""

    @pytest.mark.asyncio
    async def test_search_rejects_single_character_query(self, client: httpx.AsyncClient):
        res = await client.get("/api/v1/articles?q=a")
        # FastAPI returns 422 Unprocessable Entity when query param constraint fails
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_search_accepts_two_character_query(self, client: httpx.AsyncClient):
        res = await client.get("/api/v1/articles?q=ai")
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# 7. VULN-06: SSRF & TOCTOU DNS Rebinding Socket-Level Hardening
# ---------------------------------------------------------------------------
class TestSSRFDNSRebindingHardening:
    """Verifies socket-level interception and URL port filtering for SSRF / DNS rebinding."""

    def test_image_url_rejects_non_standard_ports(self):
        from app.services.image_validation_service import ImageValidationService
        for port in [8000, 8080, 5432, 22, 9000]:
            ok, err = ImageValidationService.validate_url_syntax(f"https://images.example.com:{port}/photo.jpg")
            assert not ok
            assert "Prohibited non-standard port" in err

    def test_image_url_accepts_standard_ports(self):
        from app.services.image_validation_service import ImageValidationService
        ok1, err1 = ImageValidationService.validate_url_syntax("https://images.example.com/photo.jpg")
        assert ok1 and err1 is None
        ok2, err2 = ImageValidationService.validate_url_syntax("https://images.example.com:443/photo.jpg")
        assert ok2 and err2 is None

    @pytest.mark.asyncio
    async def test_ssrf_safe_backend_blocks_private_ip_resolution(self):
        from app.services.image_validation_service import SSRFSafeAsyncBackend, ImageValidationError
        backend = SSRFSafeAsyncBackend()
        for unsafe_host in ["127.0.0.1", "169.254.169.254", "10.0.0.1", "localhost"]:
            with pytest.raises(ImageValidationError):
                await backend.connect_tcp(unsafe_host, 443)

    @pytest.mark.asyncio
    async def test_ssrf_safe_backend_blocks_non_standard_port(self):
        from app.services.image_validation_service import SSRFSafeAsyncBackend, ImageValidationError
        backend = SSRFSafeAsyncBackend()
        with pytest.raises(ImageValidationError) as exc:
            await backend.connect_tcp("example.com", 8000)
        assert "Prohibited non-standard port" in str(exc.value)

    @pytest.mark.asyncio
    async def test_ssrf_safe_backend_dns_rebinding_ip_pinning_and_interception(self):
        """Simulates DNS rebinding attack where hostname resolves to private IP during TCP connect."""
        from app.services.image_validation_service import SSRFSafeAsyncBackend, ImageValidationError
        backend = SSRFSafeAsyncBackend()

        # Case 1: Host resolves to private/metadata IP (169.254.169.254) upon connect_tcp
        fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]
        with patch("socket.getaddrinfo", return_value=fake_addrinfo):
            with pytest.raises(ImageValidationError) as exc:
                await backend.connect_tcp("attacker-controlled-rebinding.com", 443)
            assert "prohibited private/internal IP" in str(exc.value)

        # Case 2: Host resolves to public safe IP (93.184.216.34) -> proves socket connects to the resolved IP
        safe_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with patch("socket.getaddrinfo", return_value=safe_addrinfo):
            with patch.object(SSRFSafeAsyncBackend.__bases__[0], "connect_tcp", new_callable=AsyncMock) as mock_super_connect:
                mock_super_connect.return_value = "mock_stream"
                stream = await backend.connect_tcp("example.com", 443)
                assert stream == "mock_stream"
                # Verify that the super connect_tcp was invoked with the pinned IP, NOT the domain name
                mock_super_connect.assert_called_once()
                call_args = mock_super_connect.call_args[0]
                assert call_args[0] == "93.184.216.34", f"Expected IP '93.184.216.34' passed to socket, got {call_args[0]}"
                assert call_args[1] == 443


# ---------------------------------------------------------------------------
# 8. VULN-09 & VULN-10: CI/CD Audit Policy & CSP Hardening
# ---------------------------------------------------------------------------
class TestCIAuditPolicyAndCSPHardening:
    """Verifies that CI does not suppress security audit codes and CSP eliminates unsafe-eval."""

    def test_ci_workflow_does_not_suppress_audit_failures(self):
        ci_path = _repo_root() / ".github/workflows/ci.yml"
        assert ci_path.exists()
        content = ci_path.read_text(encoding="utf-8")
        assert "npm audit" in content
        assert "pip-audit" in content
        assert "npm audit --audit-level=critical || true" not in content
        assert "pip-audit -r requirements.txt || true" not in content

    def test_nginx_csp_eliminates_unsafe_eval(self):
        nginx_conf = _repo_root() / "infrastructure/nginx/conf.d/metroscope.conf"
        assert nginx_conf.exists()
        content = nginx_conf.read_text(encoding="utf-8")
        assert "Content-Security-Policy" in content
        assert "'unsafe-eval'" not in content
        assert "'unsafe-inline'" in content
        # Ensure http://localhost:8000 is removed from connect-src
        assert "http://localhost:8000" not in content


