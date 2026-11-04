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


def test_provider_diagnostics_never_exposes_key(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "SYNTHETIC-private-test-value")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    response = client.get("/system/provider")
    assert response.status_code == 200
    assert response.json()["configuration"] == "configured"
    assert response.json()["availability"] == "untested"
    assert response.json()["live_validation"] == "untested"
    assert "SYNTHETIC-private-test-value" not in response.text


def test_provider_diagnostics_missing_configuration(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    response = client.get("/system/provider")
    assert response.json()["configuration"] == "unavailable"
    assert response.json()["availability"] == "unavailable"


def test_provider_diagnostics_disabled_requests(monkeypatch) -> None:
    from vaultline_api.investigations.providers import MetaAIProvider, get_provider

    monkeypatch.setenv("MODEL_API_KEY", "SYNTHETIC-test")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    app.dependency_overrides[get_provider] = lambda: MetaAIProvider(allow_requests=False)
    try:
        assert client.get("/system/provider").json()["availability"] == "unavailable"
    finally:
        app.dependency_overrides.pop(get_provider)
