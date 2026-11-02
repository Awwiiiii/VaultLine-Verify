"""Health endpoint tests."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from vaultline_api.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("vaultline_api.services.readiness.check_database_connection", return_value=True)
def test_ready_reports_database_reachable(_check: object) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "reachable"}


@patch("vaultline_api.services.readiness.check_database_connection", return_value=False)
def test_ready_returns_503_when_database_is_unavailable(_check: object) -> None:
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "not_ready"


@patch("vaultline_api.services.readiness.check_database_connection", return_value=False)
def test_health_does_not_require_database(_check: object) -> None:
    response = client.get("/health")

    assert response.status_code == 200
