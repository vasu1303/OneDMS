import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.api.v1.endpoints import health
from app.core.config import Settings


@pytest.fixture
def infrastructure(monkeypatch):
    settings = Settings(
        _env_file=None,
        DATABASE_URL="",
        AWS_ENDPOINT_URL_S3="",
        AWS_ACCESS_KEY_ID="",
        AWS_SECRET_ACCESS_KEY="",
    )
    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(health, "settings", settings)
    database = MagicMock()
    database.dispose = AsyncMock()
    storage = MagicMock()
    storage.check = AsyncMock()
    storage.close = AsyncMock()
    monkeypatch.setattr(main, "create_database", MagicMock(return_value=database))
    monkeypatch.setattr(main, "create_storage", MagicMock(return_value=storage))
    monkeypatch.setattr(main, "create_session_factory", MagicMock())
    monkeypatch.setattr(health, "check_database", AsyncMock())
    return database, storage


def test_healthy_dependencies_and_cleanup(infrastructure):
    database, storage = infrastructure
    with TestClient(main.app) as client:
        response = client.get("/api/health/dependencies")
        assert response.status_code == 200
        assert client.get("/api/v1/health/dependencies").status_code == 404
        paths = client.get("/openapi.json").json()["paths"]
        assert "/api/health/dependencies" in paths
        assert not any("/v1/" in path for path in paths)
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        assert payload["status"] == "healthy"
        for name in ("database", "object_storage"):
            assert payload[name]["status"] == "healthy"
            assert payload[name]["latency_ms"] >= 0
    database.dispose.assert_awaited_once()
    storage.close.assert_awaited_once()


@pytest.mark.parametrize("dependency", ["database", "object_storage"])
def test_independent_failure_is_redacted(infrastructure, dependency):
    _, storage = infrastructure
    operation = health.check_database if dependency == "database" else storage.check
    operation.side_effect = RuntimeError("postgresql://secret:password@host/db storage-secret")
    with TestClient(main.app) as client:
        response = client.get("/api/health/dependencies")
        assert response.status_code == 503
        assert response.json()[dependency]["status"] == "failed"
        other = "object_storage" if dependency == "database" else "database"
        assert response.json()[other]["status"] == "healthy"
        assert "secret" not in response.text
        assert "password" not in response.text
        assert client.get("/api/health/").json() == {
            "status": "healthy", "version": "0.1.0",
        }


@pytest.mark.parametrize("dependency", ["database", "object_storage"])
def test_missing_configuration(infrastructure, monkeypatch, dependency):
    factory = "create_database" if dependency == "database" else "create_storage"
    monkeypatch.setattr(main, factory, lambda settings: None)
    with TestClient(main.app) as client:
        response = client.get("/api/health/dependencies")
        assert response.status_code == 503
        assert response.json()[dependency] == {"status": "not_configured", "latency_ms": None}
        assert client.get("/api/health/").status_code == 200


@pytest.mark.parametrize("dependency", ["database", "object_storage"])
def test_invalid_configuration_does_not_block_startup(infrastructure, monkeypatch, dependency):
    factory = "create_database" if dependency == "database" else "create_storage"
    monkeypatch.setattr(main, factory, MagicMock(side_effect=ValueError("secret-value")))
    with TestClient(main.app) as client:
        response = client.get("/api/health/dependencies")
        assert response.status_code == 503
        assert response.json()[dependency]["status"] == "configuration_error"
        assert "secret-value" not in response.text
        assert client.get("/api/health/").status_code == 200


@pytest.mark.parametrize("dependency", ["database", "object_storage"])
def test_timeout_is_bounded(infrastructure, monkeypatch, dependency):
    _, storage = infrastructure
    monkeypatch.setattr(health, "settings", health.settings.model_copy(
        update={"DEPENDENCY_TIMEOUT_SECONDS": 0.02},
    ))

    async def pending(*args):
        await asyncio.Event().wait()

    operation = health.check_database if dependency == "database" else storage.check
    operation.side_effect = pending
    with TestClient(main.app) as client:
        response = client.get("/api/health/dependencies")
        assert response.status_code == 503
        assert response.json()[dependency]["status"] == "timeout"
        other = "object_storage" if dependency == "database" else "database"
        assert response.json()[other]["status"] == "healthy"


def test_unconfigured_application_still_serves_docs(monkeypatch):
    settings = Settings(
        _env_file=None, DATABASE_URL="", AWS_ENDPOINT_URL_S3="",
        AWS_ACCESS_KEY_ID="", AWS_SECRET_ACCESS_KEY="",
    )
    monkeypatch.setattr(main, "settings", settings)
    with TestClient(main.app) as client:
        assert client.get("/docs").status_code == 200
        response = client.get("/api/health/dependencies")
        assert response.status_code == 503
        assert response.json()["database"]["status"] == "not_configured"
        assert response.json()["object_storage"]["status"] == "not_configured"