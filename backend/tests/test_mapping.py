import pytest
from datetime import date
from decimal import Decimal
from app.services.mapping import (
    map_source_to_canonical,
    map_canonical_to_oem,
    MappingError,
    normalize_date,
    normalize_decimal,
    normalize_currency
)

def test_normalize_date():
    assert normalize_date("2026-10-01") == "2026-10-01"
    assert normalize_date(date(2026, 10, 1)) == "2026-10-01"
    assert normalize_date("01/10/2026") == "2026-01-10" # dateutil defaults to MM/DD/YYYY, we just test it parses
    with pytest.raises(ValueError):
        normalize_date("invalid")

def test_normalize_decimal():
    assert normalize_decimal("100.50") == Decimal("100.50")
    assert normalize_decimal("$1,000.50") == Decimal("1000.50")
    assert normalize_decimal(100.5) == Decimal("100.5")
    with pytest.raises(ValueError):
        normalize_decimal("invalid")

def test_normalize_currency():
    assert normalize_currency(" inr ") == "INR"
    assert normalize_currency("USD") == "USD"
    with pytest.raises(ValueError):
        normalize_currency(123)

def test_map_source_to_canonical():
    config = {
        "invoice_number": "invoiceNo",
        "invoice_date": "billDate",
        "supplier_dealer_code": "dealerCode",
        "subtotal": "subTotal",
        "currency": "currencyCode",
        "line_items": {
            "source_field": "items",
            "item_code": "sku",
            "quantity": "qty",
            "unit_price": "rate"
        }
    }
    
    source_data = {
        "invoiceNo": "INV-001",
        "billDate": "2026-10-01",
        "dealerCode": "DEALER-1",
        "subTotal": "$1,000.00",
        "currencyCode": "usd",
        "items": [
            {"sku": "PART-A", "qty": "2", "rate": "500.00"}
        ]
    }
    
    canonical = map_source_to_canonical(source_data, config)
    assert canonical["invoice_number"] == "INV-001"
    assert canonical["invoice_date"] == "2026-10-01"
    assert canonical["supplier_dealer_code"] == "DEALER-1"
    assert canonical["subtotal"] == "1000.00"
    assert canonical["currency"] == "USD"
    assert len(canonical["line_items"]) == 1
    assert canonical["line_items"][0]["item_code"] == "PART-A"
    assert canonical["line_items"][0]["quantity"] == "2"
    assert canonical["line_items"][0]["unit_price"] == "500.00"

def test_map_source_to_canonical_missing_path():
    config = {"invoice_number": "nonExistent"}
    source_data = {"other": "value"}
    with pytest.raises(MappingError) as exc:
        map_source_to_canonical(source_data, config)
    assert "Missing required path" in str(exc.value)

def test_map_canonical_to_oem():
    config = {
        "invoiceNumber": "invoice_number",
        "grossAmount": "total_amount",
        "items": {
            "source_field": "line_items",
            "materialCode": "item_code",
            "quantity": "quantity"
        }
    }
    
    canonical_data = {
        "invoice_number": "INV-001",
        "total_amount": "1000.00",
        "line_items": [
            {"item_code": "PART-A", "quantity": "2"}
        ]
    }
    
    oem_data = map_canonical_to_oem(canonical_data, config)
    assert oem_data["invoiceNumber"] == "INV-001"
    assert oem_data["grossAmount"] == "1000.00"
    assert len(oem_data["items"]) == 1
    assert oem_data["items"][0]["materialCode"] == "PART-A"
    assert oem_data["items"][0]["quantity"] == "2"
