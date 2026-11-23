from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import create_app


def test_root_health_endpoint():
    app = create_app()
    client = TestClient(app)
    with patch("app.api.v1.endpoints.health.check_db_connection", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = True
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database_connected"] is True
        assert "environment" in data
        assert "version" in data

        # Ensure no database credentials are leaked
        response_text = response.text.lower()
        assert "password" not in response_text
        assert "postgresql://" not in response_text


def test_api_v1_health_endpoint_degraded():
    app = create_app()
    client = TestClient(app)
    with patch("app.api.v1.endpoints.health.check_db_connection", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = False
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database_connected"] is False


def test_health_liveness_endpoint():
    app = create_app()
    client = TestClient(app)
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert "timestamp" in data


def test_health_readiness_endpoint():
    app = create_app()
    client = TestClient(app)

    # 1. Ready state (database online)
    with patch("app.api.v1.endpoints.health.check_db_connection", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = True
        res_ready = client.get("/health/ready")
        assert res_ready.status_code == 200
        data_ready = res_ready.json()
        assert data_ready["status"] == "ready"
        assert data_ready["database_ready"] is True

    # 2. Unready state (database offline -> 503)
    with patch("app.api.v1.endpoints.health.check_db_connection", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = False
        res_unready = client.get("/health/ready")
        assert res_unready.status_code == 503
        data_unready = res_unready.json()
        assert data_unready["status"] == "unready"
        assert data_unready["database_ready"] is False


def test_production_config_validation():
    from app.core.config import Settings
    prod_settings = Settings(
        ENVIRONMENT="production",
        DEBUG=True,
        POSTGRES_PASSWORD="metroscope_secure_password",
    )
    issues = prod_settings.validate_production_configuration()
    assert any("DEBUG" in i for i in issues)
    assert any("POSTGRES_PASSWORD" in i for i in issues)


def test_health_ops_endpoint():
    app = create_app()
    client = TestClient(app)
    with patch("app.api.v1.endpoints.health.check_db_connection", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = True
        # Unauthenticated access must be rejected
        unauth_resp = client.get("/api/v1/health/ops")
        assert unauth_resp.status_code == 401

        # Authorized operator access returns operational telemetry
        response = client.get(
            "/api/v1/health/ops",
            headers={"Authorization": "Bearer test-operator-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["database_connected"] is True
        assert "scheduler" in data
        assert "webz_morning_collection" in data["scheduler"]["collection_jobs"]
        assert "webz_evening_business" in data["scheduler"]["collection_jobs"]
        assert "ingestion" in data
        assert "articles_summary" in data
        assert "api_usage" in data
        assert "social_publishing" in data
        assert "facebook" in data["social_publishing"]
        assert "x" in data["social_publishing"]

