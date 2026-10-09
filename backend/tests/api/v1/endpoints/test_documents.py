import io
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps.db import get_db_session
from app.api.deps.storage import get_storage
from app.main import app
from app.models.invoice import Dealer, DmsSystem, InboundDocument

# Test data
mock_dealer = Dealer(id=1, dealer_code="D1", name="Test Dealer")
mock_dms = DmsSystem(id=1, name="Test DMS", integration_tier=1, input_format="CSV")

@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.add = MagicMock()
    # Mock db.get for Dealer, DmsSystem, InboundDocument
    async def mock_get(model, id):
        if model == Dealer and id == 1:
            return mock_dealer
        if model == DmsSystem and id == 1:
            return mock_dms
        if model == InboundDocument and id == 1:
            return InboundDocument(
                id=1, dealer_id=1, dms_id=1, original_file_name="test.pdf",
                mime_type="application/pdf", storage_key="inbound/1/1/test.pdf"
            )
        if model == InboundDocument and id == 2:
            return InboundDocument(
                id=2, dealer_id=1, dms_id=1, raw_payload={"foo": "bar"},
                mime_type="application/json", storage_key=None
            )
        return None
    db.get.side_effect = mock_get
    return db

@pytest.fixture
def mock_storage():
    storage = AsyncMock()
    
    # Mock get_file_stream
    async def mock_get_file_stream(key):
        async def stream_generator():
            yield b"mock content"
        return stream_generator(), "application/pdf"
    
    storage.get_file_stream.side_effect = mock_get_file_stream
    return storage

@pytest.fixture
def client(mock_db, mock_storage):
    async def override_get_db():
        yield mock_db
        
    def override_get_storage():
        return mock_storage
        
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_upload_document_success(client, mock_db, mock_storage):
    file_content = b"pdf content"
    files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
    data = {"dealer_id": "1", "dms_id": "1"}
    
    # db.refresh needs to update the ID of the inserted object
    async def mock_refresh(obj):
        obj.id = 1
        obj.received_at = "2026-10-09T00:00:00Z"
    mock_db.refresh.side_effect = mock_refresh
    
    response = client.post("/api/documents", data=data, files=files)
    assert response.status_code == 201
    assert response.json()["original_file_name"] == "test.pdf"
    assert response.json()["status"] == "RECEIVED"
    
    mock_storage.upload_file.assert_called_once()
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

def test_upload_document_invalid_type(client):
    file_content = b"text content"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
    data = {"dealer_id": "1", "dms_id": "1"}
    
    response = client.post("/api/documents", data=data, files=files)
    assert response.status_code == 415

def test_submit_json_document_success(client, mock_db):
    data = {
        "dealer_id": 1,
        "dms_id": 1,
        "payload": {"invoice_number": "12345"}
    }
    
    async def mock_refresh(obj):
        obj.id = 2
        obj.received_at = "2026-10-09T00:00:00Z"
    mock_db.refresh.side_effect = mock_refresh
    
    response = client.post("/api/documents/json", json=data)
    assert response.status_code == 201
    assert response.json()["status"] == "RECEIVED"
    assert response.json()["mime_type"] == "application/json"
    
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()

def test_get_document_source_storage(client, mock_storage):
    response = client.get("/api/documents/1/source")
    assert response.status_code == 200
    assert response.content == b"mock content"
    mock_storage.get_file_stream.assert_called_once_with("inbound/1/1/test.pdf")

def test_get_document_source_json_payload(client):
    response = client.get("/api/documents/2/source")
    assert response.status_code == 200
    assert response.json() == {"foo": "bar"}
