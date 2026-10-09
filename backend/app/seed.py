from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import create_sync_database
from app.models import (
    Base, Dealer, DmsSystem, InboundDocument, InvoiceLineItem, MappingConfig,
    StandardizedInvoice, ValidationRule,
)


def get_or_create(session, model, filters, values, inserted):
    record = session.execute(select(model).filter_by(**filters)).scalar_one_or_none()
    if record is None:
        record = model(**(filters | values))
        session.add(record)
        session.flush()
        inserted[model.__tablename__] += 1
    return record


def add_mapping(session, filters, name, config, inserted):
    version = session.scalar(select(func.coalesce(func.max(MappingConfig.version), 0)).where(
        MappingConfig.mapping_direction == filters["mapping_direction"],
        MappingConfig.dms_id == filters["dms_id"],
        MappingConfig.target_system == filters["target_system"],
        MappingConfig.document_type == "INVOICE",
    )) + 1
    return get_or_create(session, MappingConfig, filters | {"document_type": "INVOICE", "is_active": True}, {
        "mapping_name": name, "mapping_config": config, "version": version,
    }, inserted)


def add_demo_invoice(session, dealer, dms, source, number, line_specs, needs_review, inserted):
    lines = []
    for line_number, (item_code, description, quantity, unit_price, chassis_number) in enumerate(line_specs, start=1):
        taxable_amount = (quantity * unit_price).quantize(Decimal("0.01"))
        tax_amount = (taxable_amount * Decimal("0.18")).quantize(Decimal("0.01"))
        lines.append({
            "line_number": line_number, "item_code": item_code, "description": description,
            "quantity": quantity, "unit_price": unit_price, "discount_amount": Decimal("0.00"),
            "taxable_amount": taxable_amount, "tax_rate": Decimal("18.00"),
            "tax_amount": tax_amount, "line_total": taxable_amount + tax_amount,
            "chassis_number": chassis_number,
        })
    subtotal = sum(line["taxable_amount"] for line in lines)
    tax_amount = sum(line["tax_amount"] for line in lines)
    payload_lines = [{
        **{key: str(value) if isinstance(value, Decimal) else value for key, value in line.items()},
        "item_category": "VEHICLE" if line["chassis_number"] else "PART",
    } for line in lines]
    raw_payload = {
        "invoiceNo": number, "billDate": "2026-10-01", "dealerCode": dealer.dealer_code,
        "buyerCode": "DAIMLER-DEMO", "currencyCode": "INR", "subTotal": str(subtotal),
        "taxTotal": str(tax_amount), "grandTotal": str(subtotal + tax_amount),
        "items": [{
            "sku": line["item_code"], "description": line["description"],
            "qty": str(line["quantity"]), "rate": str(line["unit_price"]),
            "discount": "0.00", "taxableValue": str(line["taxable_amount"]),
            "taxRate": "18.00", "taxAmount": str(line["tax_amount"]),
            "lineTotal": str(line["line_total"]), "chassisNo": line["chassis_number"],
            "category": "VEHICLE" if line["chassis_number"] else "PART",
        } for line in lines],
    }
    invoice = session.execute(
        select(StandardizedInvoice).join(InboundDocument)
        .where(StandardizedInvoice.invoice_number == number,
               InboundDocument.dealer_id == dealer.id, InboundDocument.dms_id == dms.id)
    ).scalar_one_or_none()
    if invoice is None:
        document = InboundDocument(
            dealer_id=dealer.id, dms_id=dms.id, document_type="INVOICE",
            received_at=datetime(2026, 10, 1, 10, tzinfo=timezone.utc),
            status="REVIEW_REQUIRED" if needs_review else "COMPLETED",
            original_file_name=f"{number}.csv" if source == "csv" else None,
            mime_type="text/csv" if source == "csv" else "application/json",
            storage_key=None, raw_payload=raw_payload if source == "api" else None,
            error_message="Demo invoice requires auditor review." if needs_review else None,
        )
        session.add(document)
        session.flush()
        inserted["inbound_documents"] += 1
        invoice = StandardizedInvoice(
            document_id=document.id, invoice_number=number, invoice_date=date(2026, 10, 1),
            buyer_oem_id="DAIMLER-DEMO", currency="INR", subtotal=subtotal,
            tax_amount=tax_amount, total_amount=subtotal + tax_amount,
            canonical_payload={
                "invoice_number": number, "invoice_date": "2026-10-01",
                "supplier_dealer_code": dealer.dealer_code, "buyer_oem_id": "DAIMLER-DEMO",
                "currency": "INR", "subtotal": str(subtotal), "tax_amount": str(tax_amount),
                "total_amount": str(subtotal + tax_amount), "line_items": payload_lines,
            },
            validation_status="REVIEW_REQUIRED" if needs_review else "VALID",
            review_status="PENDING" if needs_review else "NOT_REQUIRED", oem_delivery_status="NOT_SENT",
        )
        session.add(invoice)
        session.flush()
        inserted["standardized_invoices"] += 1
    for line in lines:
        get_or_create(session, InvoiceLineItem, {
            "invoice_id": invoice.id, "line_number": line["line_number"],
        }, line, inserted)


def seed_database(session: Session):
    session.execute(text("SELECT pg_advisory_xact_lock(741239018)"))
    inserted = {name: 0 for name in Base.metadata.tables}
    profiles = {}
    for source, dealer_name, tier, method, source_format in (
        ("api", "Demo North Trucks", 1, "API", "JSON"),
        ("csv", "Demo South Trucks", 2, "UPLOAD", "CSV"),
    ):
        dealer = get_or_create(session, Dealer, {"dealer_code": f"ONEDMS-DEMO-{source.upper()}"}, {
            "name": dealer_name, "gstin": None,
        }, inserted)
        dms = get_or_create(session, DmsSystem, {
            "name": f"Demo {source.upper()} DMS", "integration_tier": tier,
            "integration_method": method, "input_format": source_format,
        }, {}, inserted)
        profiles[source] = (dealer, dms)
        if source == "api":
            config = {
                "invoice_number": "invoiceNo", "invoice_date": "billDate",
                "supplier_dealer_code": "dealerCode", "buyer_oem_id": "buyerCode",
                "currency": "currencyCode", "subtotal": "subTotal", "tax_amount": "taxTotal",
                "total_amount": "grandTotal", "line_items": {
                    "source_field": "items", "item_code": "sku", "description": "description",
                    "quantity": "qty", "unit_price": "rate", "discount_amount": "discount",
                    "taxable_amount": "taxableValue", "tax_rate": "taxRate", "tax_amount": "taxAmount",
                    "line_total": "lineTotal", "chassis_number": "chassisNo", "item_category": "category",
                },
            }
        else:
            config = {
                "invoice_number": "InvoiceNumber", "invoice_date": "InvoiceDate",
                "supplier_dealer_code": "DealerCode", "buyer_oem_id": "BuyerCode",
                "currency": "Currency", "subtotal": "Subtotal", "tax_amount": "TaxTotal",
                "total_amount": "GrandTotal", "line_items": {
                    "source_field": "rows", "item_code": "SKU", "description": "Description",
                    "quantity": "Qty", "unit_price": "UnitPrice", "discount_amount": "Discount",
                    "taxable_amount": "TaxableValue", "tax_rate": "TaxRate", "tax_amount": "TaxAmount",
                    "line_total": "LineTotal", "chassis_number": "ChassisNumber", "item_category": "Category",
                },
            }
        add_mapping(session, {
            "mapping_direction": "SOURCE_TO_CANONICAL", "dms_id": dms.id, "target_system": None,
        }, f"Demo {source.upper()} invoice mapping", config, inserted)
        add_demo_invoice(session, dealer, dms, source, "DEMO-INV-001", [
            ("PART-BRAKE", "Brake pad kit", Decimal("2.000"), Decimal("300.00"), None),
            ("PART-FILTER", "Air filter", Decimal("1.000"), Decimal("400.00"), None),
        ], source == "csv", inserted)
    dealer, dms = profiles["api"]
    add_demo_invoice(session, dealer, dms, "api", "DEMO-TRUCK-001", [
        ("TRUCK-DEMO", "Synthetic demonstration truck", Decimal("1.000"), Decimal("2500000.00"),
         "DEMO-TRUCK-CHASSIS-001"),
    ], False, inserted)
    add_mapping(session, {
        "mapping_direction": "CANONICAL_TO_OEM", "dms_id": None, "target_system": "DAIMLER_ERP",
    }, "Demo Daimler ERP invoice output", {
        "invoiceNumber": "invoice_number", "invoiceDate": "invoice_date",
        "supplierCode": "supplier_dealer_code", "currencyCode": "currency", "grossAmount": "total_amount",
        "items": {"source_field": "line_items", "materialCode": "item_code", "quantity": "quantity",
                  "netPrice": "unit_price", "chassisNumber": "chassis_number"},
    }, inserted)
    rules = (
        ("REQUIRED_INVOICE_FIELDS", "Required invoice header fields", "ERROR", {
            "type": "REQUIRED_FIELDS", "fields": ["invoice_number", "invoice_date", "supplier_dealer_code", "buyer_oem_id"],
        }),
        ("REGISTERED_DEALER", "Sending dealer is registered", "ERROR", {"type": "REGISTERED_DEALER"}),
        ("VALID_LINE_VALUES", "Valid quantities and prices", "ERROR", {
            "type": "NUMERIC_BOUNDS", "collection": "line_items", "fields": {
                "quantity": {"exclusive_minimum": 0}, "unit_price": {"minimum": 0},
            },
        }),
        ("SUPPORTED_CURRENCY", "Supported invoice currency", "ERROR", {
            "type": "ALLOWED_VALUES", "field": "currency", "values": ["INR", "EUR", "USD"],
        }),
        ("INVOICE_TOTAL_RECONCILIATION", "Header and line totals reconcile", "ERROR", {
            "type": "TOTAL_RECONCILIATION", "subtotal_field": "subtotal", "tax_field": "tax_amount",
            "total_field": "total_amount", "line_collection": "line_items", "tolerance": 0.01,
            "line_subtotal_field": "taxable_amount", "line_tax_field": "tax_amount", "line_total_field": "line_total",
        }),
        ("DUPLICATE_INVOICE", "Flag duplicate invoices from the same dealer", "WARNING", {
            "type": "DUPLICATE_INVOICE", "fields": ["supplier_dealer_code", "invoice_number", "invoice_date"],
        }),
        ("VEHICLE_CHASSIS_NUMBER_REQUIRED", "Vehicle lines identify the exact truck", "ERROR", {
            "type": "CONDITIONAL_REQUIRED_FIELD", "collection": "line_items", "field": "chassis_number",
            "when": {"item_category": "VEHICLE"},
        }),
    )
    for code, name, severity, config in rules:
        get_or_create(session, ValidationRule, {"rule_code": code}, {
            "rule_name": name, "document_type": "INVOICE", "rule_config": config,
            "severity": severity, "is_active": True,
        }, inserted)
    return inserted


def main():
    engine = None
    try:
        engine = create_sync_database(settings)
        with Session(engine) as session, session.begin():
            inserted = seed_database(session)
            totals = {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }
        for name, count in inserted.items():
            print(f"{name}: inserted {count}; total {totals[name]}")
    except Exception as error:
        raise SystemExit(
            f"Seed failed ({type(error).__name__}). Transaction rolled back; "
            "check DATABASE_URL and run python -m app.setup_db first."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()