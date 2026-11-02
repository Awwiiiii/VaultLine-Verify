"""Shared PostgreSQL integration fixtures; synthetic data and transaction rollback."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from vaultline_api.core.config import get_settings
from vaultline_api.db.session import get_db_session, get_engine
from vaultline_api.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "evidence_storage_dir", tmp_path)
    monkeypatch.setattr(settings, "max_upload_bytes", 4096)
    with get_engine().connect() as connection:
        transaction = connection.begin()

        def sessions():
            with Session(
                connection, join_transaction_mode="create_savepoint", expire_on_commit=False
            ) as session:
                yield session

        app.dependency_overrides[get_db_session] = sessions
        try:
            with TestClient(app) as client:
                yield client
        finally:
            app.dependency_overrides.clear()
            transaction.rollback()


@pytest.fixture
def case(client):
    response = client.post(
        "/api/v1/cases", json={"counterparty_name": "SYNTHETIC demonstration company"}
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture(autouse=True)
def no_live_http(monkeypatch):
    """All routine tests are offline; explicit MockTransport adapters remain usable."""
    import httpx

    def denied(*args, **kwargs):
        raise AssertionError("Live HTTP is disabled in automated tests")

    async def async_denied(*args, **kwargs):
        raise AssertionError("Live HTTP is disabled in automated tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", denied)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", async_denied)
