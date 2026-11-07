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
