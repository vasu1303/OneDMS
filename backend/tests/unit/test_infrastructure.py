import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.stub import Stubber

from app.core.config import ENV_FILE, Settings
from app.core.database import check_database, create_database, database_url
from app.services.storage import create_storage


def configured_settings(**overrides):
    values = {
        "DATABASE_URL": "postgresql://test:password@example.neon.tech/neondb?sslmode=require&channel_binding=require",
        "AWS_ENDPOINT_URL_S3": "https://branch.storage.example.neon.tech",
        "AWS_REGION": "ap-southeast-1",
        "AWS_ACCESS_KEY_ID": "test-access-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret-key",
        "S3_BUCKET_NAME": "assets",
    }
    return Settings(_env_file=None, **(values | overrides))


def test_environment_path_and_secret_redaction():
    assert ENV_FILE == Path(__file__).resolve().parents[2] / ".env"
    settings = configured_settings()
    assert "test-secret-key" not in repr(settings)
    assert "test-access-key" not in repr(settings)
    assert "password" not in repr(settings)


def test_database_url_preserves_security_parameters():
    url = database_url(configured_settings().DATABASE_URL.get_secret_value())
    assert url.drivername == "postgresql+psycopg"
    assert url.query == {"sslmode": "require", "channel_binding": "require"}
    assert url.password == "password"


@pytest.mark.parametrize("value", [
    "sqlite:///test.db",
    "postgresql://test:password@example.neon.tech/neondb?sslmode=disable",
    "postgresql:///neondb?sslmode=require",
])
def test_database_rejects_unsupported_or_insecure_urls(value):
    with pytest.raises(ValueError):
        database_url(value)


def test_missing_config_does_not_create_clients():
    settings = configured_settings(DATABASE_URL="", AWS_SECRET_ACCESS_KEY="")
    assert create_database(settings) is None
    assert create_storage(settings) is None


def test_engine_configuration_and_disposal():
    engine = create_database(configured_settings())
    assert engine is not None
    assert engine.dialect.is_async
    assert engine.pool.size() == 5
    asyncio.run(engine.dispose())


def test_storage_configuration_and_read_only_probe():
    storage = create_storage(configured_settings())
    assert storage is not None
    assert storage.client.meta.endpoint_url == "https://branch.storage.example.neon.tech"
    assert storage.client.meta.region_name == "ap-southeast-1"
    assert storage.client.meta.config.signature_version == "s3v4"
    assert storage.client.meta.config.s3["addressing_style"] == "path"
    with Stubber(storage.client) as stubber:
        stubber.add_response("head_bucket", {}, {"Bucket": "assets"})
        asyncio.run(storage.check())
        stubber.assert_no_pending_responses()
    asyncio.run(storage.close())


def test_storage_rejects_unencrypted_endpoint():
    with pytest.raises(ValueError):
        create_storage(configured_settings(AWS_ENDPOINT_URL_S3="http://example.com"))


@pytest.mark.parametrize("scalar", [1, 0])
def test_database_probe_verifies_select_result(scalar):
    connection = AsyncMock()
    result = MagicMock()
    result.scalar_one.return_value = scalar
    connection.execute.return_value = result
    engine = MagicMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=connection)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=None)
    if scalar == 1:
        asyncio.run(check_database(engine))
    else:
        with pytest.raises(RuntimeError):
            asyncio.run(check_database(engine))
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"