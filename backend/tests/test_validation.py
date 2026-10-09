import pytest
from app.services.validation import (
    ValidationContext,
    validate_canonical_payload,
    get_overall_status
)

@pytest.fixture
def context():
    return ValidationContext(
        is_registered_dealer=lambda x: x == 'DEALER-1',
        is_duplicate_invoice=lambda dealer, inv, dt: inv == 'DUP-001'
    )

def test_required_fields(context):
    rules = [{
        "rule_code": "REQ-1", "severity": "ERROR",
        "rule_config": {"type": "REQUIRED_FIELDS", "fields": ["invoice_number", "invoice_date"]}
    }]
    
    data = {"invoice_number": "INV-001"}
    results = validate_canonical_payload(data, rules, context)
    assert len(results) == 1
    assert not results[0].is_valid
    assert results[0].field == "invoice_date"

def test_registered_dealer(context):
    rules = [{
        "rule_code": "REG-1", "severity": "ERROR",
        "rule_config": {"type": "REGISTERED_DEALER"}
    }]
    
    data = {"supplier_dealer_code": "DEALER-2"}
    results = validate_canonical_payload(data, rules, context)
    assert len(results) == 1
    assert not results[0].is_valid
    
    data2 = {"supplier_dealer_code": "DEALER-1"}
    results2 = validate_canonical_payload(data2, rules, context)
    assert len(results2) == 0

def test_numeric_bounds(context):
    rules = [{
        "rule_code": "NUM-1", "severity": "ERROR",
        "rule_config": {
            "type": "NUMERIC_BOUNDS", 
            "collection": "line_items", 
            "fields": {"quantity": {"exclusive_minimum": 0}}
        }
    }]
    
    data = {"line_items": [{"quantity": "0"}]}
    results = validate_canonical_payload(data, rules, context)
    assert len(results) == 1
    assert not results[0].is_valid

def test_allowed_values(context):
    rules = [{
        "rule_code": "ALL-1", "severity": "ERROR",
        "rule_config": {"type": "ALLOWED_VALUES", "field": "currency", "values": ["INR", "USD"]}
    }]
    
    data = {"currency": "EUR"}
    results = validate_canonical_payload(data, rules, context)
    assert len(results) == 1
    assert not results[0].is_valid

def test_total_reconciliation(context):
    rules = [{
        "rule_code": "TOT-1", "severity": "ERROR",
        "rule_config": {
            "type": "TOTAL_RECONCILIATION",
            "subtotal_field": "subtotal", "tax_field": "tax_amount", "total_field": "total_amount",
            "line_collection": "line_items", "tolerance": 0.01,
            "line_subtotal_field": "taxable_amount", "line_tax_field": "tax_amount", "line_total_field": "line_total"
        }
    }]
    
    data = {
        "subtotal": "100.00", "tax_amount": "18.00", "total_amount": "118.00",
        "line_items": [
            {"taxable_amount": "100.00", "tax_amount": "18.00", "line_total": "118.00"}
        ]
    }
    results = validate_canonical_payload(data, rules, context)
    assert len(results) == 0
    
    data_bad_line = {
        "subtotal": "100.00", "tax_amount": "18.00", "total_amount": "118.00",
        "line_items": [
            {"taxable_amount": "100.00", "tax_amount": "18.00", "line_total": "110.00"}
        ]
    }
    results_bad = validate_canonical_payload(data_bad_line, rules, context)
    assert len(results_bad) == 1
    assert results_bad[0].field == "line_total"

def test_duplicate_invoice(context):
    rules = [{
        "rule_code": "DUP-1", "severity": "WARNING",
        "rule_config": {"type": "DUPLICATE_INVOICE"}
    }]
    
    data = {"supplier_dealer_code": "D", "invoice_number": "DUP-001", "invoice_date": "2026-10-01"}
    results = validate_canonical_payload(data, rules, context)
    assert len(results) == 1
    assert results[0].severity == "WARNING"
    assert get_overall_status(results) == "REVIEW_REQUIRED"

def test_conditional_required(context):
    rules = [{
        "rule_code": "COND-1", "severity": "ERROR",
        "rule_config": {
            "type": "CONDITIONAL_REQUIRED_FIELD",
            "collection": "line_items",
            "field": "chassis_number",
            "when": {"item_category": "VEHICLE"}
        }
    }]
    
    data = {"line_items": [{"item_category": "VEHICLE"}]}
    results = validate_canonical_payload(data, rules, context)
    assert len(results) == 1
    
    data2 = {"line_items": [{"item_category": "VEHICLE", "chassis_number": "CHAS-123"}]}
    results2 = validate_canonical_payload(data2, rules, context)
    assert len(results2) == 0
    
    data3 = {"line_items": [{"item_category": "PART"}]}
    results3 = validate_canonical_payload(data3, rules, context)
    assert len(results3) == 0
