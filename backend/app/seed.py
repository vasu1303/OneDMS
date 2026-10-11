from datetime import date, datetime, timezone
from decimal import Decimal
import sys

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import create_sync_database
from app.models import (
    Base, Dealer, DmsSystem, InboundDocument, InvoiceLineItem, MappingConfig,
    StandardizedInvoice, ValidationRule,
)
from app.setup_db import setup_database


def clean_database(engine):
    """Completely resets database tables and identity sequences cleanly."""
    setup_database(engine)
    with engine.begin() as connection:
        connection.execute(text("""
            TRUNCATE TABLE 
                invoice_line_items, 
                standardized_invoices, 
                inbound_documents, 
                mapping_configs, 
                validation_rules, 
                dms_systems, 
                dealers 
            RESTART IDENTITY CASCADE;
        """))
    print("Database cleaned: All tables truncated and identity sequences reset.")


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


def create_document_with_invoice(
    session,
    dealer,
    dms,
    source: str,
    invoice_number: str,
    line_specs: list,
    doc_status: str = "COMPLETED",
    val_status: str = "VALID",
    rev_status: str = "NOT_REQUIRED",
    error_message: str | None = None,
    findings: list | None = None,
    received_at: datetime | None = None,
    filename: str | None = None,
    inserted: dict | None = None,
):
    if received_at is None:
        received_at = datetime.now(timezone.utc)
    if inserted is None:
        inserted = {}

    lines = []
    for line_number, (item_code, description, quantity, unit_price, chassis_number) in enumerate(line_specs, start=1):
        taxable_amount = (quantity * unit_price).quantize(Decimal("0.01"))
        tax_amount = (taxable_amount * Decimal("0.18")).quantize(Decimal("0.01"))
        lines.append({
            "line_number": line_number,
            "item_code": item_code,
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "discount_amount": Decimal("0.00"),
            "taxable_amount": taxable_amount,
            "tax_rate": Decimal("18.00"),
            "tax_amount": tax_amount,
            "line_total": taxable_amount + tax_amount,
            "chassis_number": chassis_number,
        })

    subtotal = sum(line["taxable_amount"] for line in lines)
    tax_total = sum(line["tax_amount"] for line in lines)
    grand_total = subtotal + tax_total

    payload_lines = [{
        **{key: str(value) if isinstance(value, Decimal) else value for key, value in line.items()},
        "item_category": "VEHICLE" if line["chassis_number"] else "PART",
    } for line in lines]

    mime_types = {
        "api": "application/json",
        "json": "application/json",
        "csv": "text/csv",
        "xml": "application/xml",
        "xls": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }

    raw_payload = {
        "invoiceNo": invoice_number,
        "billDate": received_at.strftime("%Y-%m-%d"),
        "dealerCode": dealer.dealer_code,
        "buyerCode": "DAIMLER-DEMO",
        "currencyCode": "INR",
        "subTotal": str(subtotal),
        "taxTotal": str(tax_total),
        "grandTotal": str(grand_total),
        "items": [{
            "sku": line["item_code"],
            "description": line["description"],
            "qty": str(line["quantity"]),
            "rate": str(line["unit_price"]),
            "discount": "0.00",
            "taxableValue": str(line["taxable_amount"]),
            "taxRate": "18.00",
            "taxAmount": str(line["tax_amount"]),
            "lineTotal": str(line["line_total"]),
            "chassisNo": line["chassis_number"],
            "category": "VEHICLE" if line["chassis_number"] else "PART",
        } for line in lines],
    }

    doc = InboundDocument(
        dealer_id=dealer.id,
        dms_id=dms.id,
        document_type="INVOICE",
        received_at=received_at,
        status=doc_status,
        original_file_name=filename or f"{invoice_number}.{source}",
        mime_type=mime_types.get(source, "application/octet-stream"),
        file_size_bytes=42000 + (len(lines) * 1500),
        storage_key=None,
        raw_payload=raw_payload if source in ("api", "json") else None,
        error_message=error_message,
    )
    session.add(doc)
    session.flush()
    inserted["inbound_documents"] = inserted.get("inbound_documents", 0) + 1

    # For RECEIVED / PROCESSING / FAILED without standardized invoice:
    if doc_status in ("RECEIVED", "FAILED") and not line_specs:
        return doc

    canonical_payload = {
        "invoice_number": invoice_number,
        "invoice_date": received_at.date().isoformat(),
        "supplier_dealer_code": dealer.dealer_code,
        "buyer_oem_id": "DAIMLER-DEMO",
        "currency": "INR",
        "subtotal": str(subtotal),
        "tax_amount": str(tax_total),
        "total_amount": str(grand_total),
        "line_items": payload_lines,
    }

    if findings:
        canonical_payload["_onedms"] = {
            "validation": {
                "issues": findings
            }
        }

    invoice = StandardizedInvoice(
        document_id=doc.id,
        invoice_number=invoice_number,
        invoice_date=received_at.date(),
        buyer_oem_id="DAIMLER-DEMO",
        currency="INR",
        subtotal=subtotal,
        tax_amount=tax_total,
        total_amount=grand_total,
        canonical_payload=canonical_payload,
        validation_status=val_status,
        review_status=rev_status,
        oem_delivery_status="SENT" if rev_status == "APPROVED" else "NOT_SENT",
    )
    session.add(invoice)
    session.flush()
    inserted["standardized_invoices"] = inserted.get("standardized_invoices", 0) + 1

    for line in lines:
        get_or_create(session, InvoiceLineItem, {
            "invoice_id": invoice.id,
            "line_number": line["line_number"],
        }, line, inserted)

    return doc


def seed_database(session: Session):
    session.execute(text("SELECT pg_advisory_xact_lock(741239018)"))
    inserted = {name: 0 for name in Base.metadata.tables}
    profiles = {}

    dealers_config = [
        ("api", "Velocity Vehicle Group (API Direct)", "27AAACV1234F1Z8", 1, "API", "JSON", "Velocity CDK Drive API"),
        ("xml", "Premier Truck Group (XML Inbound)", "06AABCP5678G2Z1", 2, "UPLOAD", "XML", "Premier Reynolds XML DMS"),
        ("xls", "Transwest Fleet Solutions (Excel Batch)", "29AABCT9012H1Z5", 2, "UPLOAD", "EXCEL", "Transwest Procede Excede (XLS)"),
        ("csv", "Rush Truck Centers (CSV EDI)", "33AABCR3456J2Z9", 2, "UPLOAD", "CSV", "Rush Karmak Fusion (CSV)"),
        ("json", "Performance Commercial Trucks (JSON Feed)", "07AABCP7890K1Z3", 2, "UPLOAD", "JSON", "Performance Auto/Mate (JSON)"),
        ("pdf", "MHC Kenworth Fleet (Digital PDF)", "24AABCM2345L2Z7", 2, "UPLOAD", "PDF", "MHC FleetMaster (PDF Engine)"),
    ]

    for source, dealer_name, gstin, tier, method, source_format, dms_name in dealers_config:
        dealer = get_or_create(session, Dealer, {"dealer_code": f"ONEDMS-DEMO-{source.upper()}"}, {
            "name": dealer_name, "gstin": gstin,
        }, inserted)
        dms = get_or_create(session, DmsSystem, {
            "name": dms_name, "integration_tier": tier,
            "integration_method": method, "input_format": source_format,
        }, {}, inserted)
        profiles[source] = (dealer, dms)

        if source in ("api", "json"):
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
        }, f"{dms_name} Canonical Mapping", config, inserted)

    # Daimler Outbound Mapping
    add_mapping(session, {
        "mapping_direction": "CANONICAL_TO_OEM", "dms_id": None, "target_system": "DAIMLER_ERP",
    }, "Daimler OEM Central Invoicing Gateway", {
        "invoiceNumber": "invoice_number", "invoiceDate": "invoice_date",
        "supplierCode": "supplier_dealer_code", "currencyCode": "currency", "grossAmount": "total_amount",
        "items": {"source_field": "line_items", "materialCode": "item_code", "quantity": "quantity",
                  "netPrice": "unit_price", "chassisNumber": "chassis_number"},
    }, inserted)

    # Validation Rules
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

    # 1. COMPLETED: Cascadia 126 Heavy Tractor (API - Velocity)
    d, dms = profiles["api"]
    create_document_with_invoice(
        session, d, dms, "api", "INV-2026-VEL-8941",
        [
            ("TRK-CAS-126", "Freightliner Cascadia 126 Sleeper Cab Tractor", Decimal("1.000"), Decimal("142500.00"), "1FUJGLDR5MLNV8941"),
            ("ENG-DD15-G5", "Detroit DD15 Gen 5 505HP Powertrain Package", Decimal("1.000"), Decimal("28000.00"), None),
        ],
        doc_status="COMPLETED", val_status="VALID", rev_status="NOT_REQUIRED",
        received_at=datetime(2026, 10, 9, 14, 25, tzinfo=timezone.utc),
        filename="telemetry_packet_8941.json", inserted=inserted,
    )

    # 2. REVIEW_REQUIRED: Air Disc Brake Kit with Tax Variance (XML - Premier Truck Group)
    d, dms = profiles["xml"]
    create_document_with_invoice(
        session, d, dms, "xml", "INV-2026-PFE-1022",
        [
            ("BRK-ADB22X", "Bendix ADB22X Heavy Duty Air Disc Brake Caliper Kit", Decimal("4.000"), Decimal("485.00"), None),
            ("CAM-KT-145", "Meritor S-Cam Heavy Duty Camshaft Bushing Kit", Decimal("2.000"), Decimal("145.00"), None),
        ],
        doc_status="REVIEW_REQUIRED", val_status="REVIEW_REQUIRED", rev_status="PENDING",
        error_message="Reconciliation finding: Tax variance detected against supplier schedule.",
        findings=[
            {
                "id": 1,
                "severity": "warning",
                "field": "tax_amount",
                "line_number": None,
                "message": "Tax total calculated as $401.40. Reconcile against supplier state exemptions.",
                "confidence": 0.96,
                "extracted_value": "401.40",
                "approved_value": None,
            }
        ],
        received_at=datetime(2026, 10, 8, 11, 40, tzinfo=timezone.utc),
        filename="premier_freight_inv_1022.xml", inserted=inserted,
    )

    # 3. COMPLETED: Heavy transmission & parts overhaul (XLS - Transwest)
    d, dms = profiles["xls"]
    create_document_with_invoice(
        session, d, dms, "xls", "INV-2026-TWG-4091",
        [
            ("CLT-EATON-10", "Eaton Fuller 10-Speed Advantage Heavy Clutch Kit", Decimal("1.000"), Decimal("1850.00"), None),
            ("STR-DELCO-39", "Delco Remy 39MT Heavy Duty Planetary Starter Motor", Decimal("1.000"), Decimal("520.00"), None),
            ("FLT-DON-BLU", "Donaldson Blue Fuel Water Separator Filter", Decimal("6.000"), Decimal("68.50"), None),
        ],
        doc_status="COMPLETED", val_status="VALID", rev_status="NOT_REQUIRED",
        received_at=datetime(2026, 10, 7, 16, 15, tzinfo=timezone.utc),
        filename="transwest_parts_batch_4091.xlsx", inserted=inserted,
    )

    # 4. REVIEW_REQUIRED: Western Star 49X Truck with Missing Chassis/VIN (CSV - Rush)
    d, dms = profiles["csv"]
    create_document_with_invoice(
        session, d, dms, "csv", "INV-2026-RSH-7712",
        [
            ("TRK-WS-49X", "Western Star 49X Heavy Vocational Truck Chassis", Decimal("1.000"), Decimal("178000.00"), None),
            ("TIR-MICH-STR", "Michelin X Line Energy Z 275/80R22.5 Steer Tire", Decimal("4.000"), Decimal("620.00"), None),
        ],
        doc_status="REVIEW_REQUIRED", val_status="REVIEW_REQUIRED", rev_status="PENDING",
        error_message="Vehicle line item requires chassis/VIN number for registration.",
        findings=[
            {
                "id": 1,
                "severity": "error",
                "field": "line_items.chassis_number",
                "line_number": 1,
                "message": "Item category VEHICLE requires a valid 17-character VIN/Chassis number.",
                "confidence": 0.99,
                "extracted_value": None,
                "approved_value": None,
            }
        ],
        received_at=datetime(2026, 10, 6, 9, 30, tzinfo=timezone.utc),
        filename="rush_fleet_shipment_7712.csv", inserted=inserted,
    )

    # 5. APPROVED: Warranty Service & Dyno Tuning (PDF - MHC Kenworth)
    d, dms = profiles["pdf"]
    create_document_with_invoice(
        session, d, dms, "pdf", "INV-2026-MHC-5540",
        [
            ("TURBO-X15", "Cummins X15 Holset VGT High Performance Turbocharger", Decimal("1.000"), Decimal("3450.00"), None),
            ("FLT-DEF-OEM", "Fleetguard DEF Dosing Unit Filter Cartridge", Decimal("1.000"), Decimal("85.00"), None),
            ("LAB-ECM-TUNE", "Labor: Factory Precision ECM Calibration & Dyno Load Test", Decimal("4.000"), Decimal("170.00"), None),
        ],
        doc_status="COMPLETED", val_status="VALID", rev_status="APPROVED",
        received_at=datetime(2026, 10, 5, 13, 10, tzinfo=timezone.utc),
        filename="mhc_warranty_service_5540.pdf", inserted=inserted,
    )

    # 6. REVIEW_REQUIRED: Kenworth T680 Sleeper Scheduled Service (PDF - MHC Kenworth)
    d, dms = profiles["pdf"]
    create_document_with_invoice(
        session, d, dms, "pdf", "INV-2026-MHC-5548",
        [
            ("SVC-T680-OH", "Kenworth T680 High-Mileage Scheduled Overhaul Package", Decimal("1.000"), Decimal("8200.00"), None),
            ("PMP-CP4-BOSCH", "Bosch High Pressure Common Rail Fuel Injection Pump", Decimal("1.000"), Decimal("2150.00"), None),
        ],
        doc_status="REVIEW_REQUIRED", val_status="REVIEW_REQUIRED", rev_status="PENDING",
        error_message="Audit flag: Subtotal requires verification against supplier list price schedule.",
        findings=[
            {
                "id": 1,
                "severity": "warning",
                "field": "subtotal",
                "line_number": None,
                "message": "Overhaul package rate requires OEM campaign authorization code.",
                "confidence": 0.91,
                "extracted_value": "8200.00",
                "approved_value": None,
            }
        ],
        received_at=datetime(2026, 10, 4, 15, 50, tzinfo=timezone.utc),
        filename="kenworth_t680_sleeper_5548.pdf", inserted=inserted,
    )

    # 7. COMPLETED: Fleet trailer suspension & 5th wheel kit (CSV - Rush)
    d, dms = profiles["csv"]
    create_document_with_invoice(
        session, d, dms, "csv", "INV-2026-RSH-7720",
        [
            ("SUS-HEND-KIT", "Hendrickson INTRAAX Air Suspension Rebuild Kit", Decimal("1.000"), Decimal("1420.00"), None),
            ("WHL-JOST-5TH", "Jost JSK37USB 5th Wheel Top Plate Rebuild Kit", Decimal("1.000"), Decimal("1150.00"), None),
        ],
        doc_status="COMPLETED", val_status="VALID", rev_status="NOT_REQUIRED",
        received_at=datetime(2026, 10, 2, 8, 45, tzinfo=timezone.utc),
        filename="rush_parts_edi_7720.csv", inserted=inserted,
    )

    # 8. PROCESSING: Inbound JSON feed currently being extracted
    d, dms = profiles["json"]
    create_document_with_invoice(
        session, d, dms, "json", "INV-2026-PTK-3309",
        [
            ("FLT-PREV-PKG", "Fleet Routine Preventive Maintenance Service Pack", Decimal("3.000"), Decimal("380.00"), None),
            ("OIL-SYN-15W40", "Mobil Delvac 1 ESP 15W-40 Full Synthetic 55-Gal Drum", Decimal("1.000"), Decimal("890.00"), None),
        ],
        doc_status="PROCESSING", val_status="PENDING", rev_status="NOT_REQUIRED",
        received_at=datetime(2026, 10, 10, 17, 0, tzinfo=timezone.utc),
        filename="perf_truck_batch_3309.json", inserted=inserted,
    )

    # 9. FAILED: Raw Inbound Document with Parser Syntax Error
    d, dms = profiles["api"]
    create_document_with_invoice(
        session, d, dms, "api", "INV-2026-VEL-8945",
        [],
        doc_status="FAILED", val_status="PENDING", rev_status="NOT_REQUIRED",
        error_message="Parser failure: Invalid numeric token 'N/A' encountered in unit_price field at item row 3.",
        received_at=datetime(2026, 10, 3, 10, 15, tzinfo=timezone.utc),
        filename="velocity_stream_packet_8945.json", inserted=inserted,
    )

    # 10. RECEIVED: Newly received Excel manifest waiting in intake queue
    d, dms = profiles["xls"]
    create_document_with_invoice(
        session, d, dms, "xls", "INV-2026-TWG-4098",
        [],
        doc_status="RECEIVED", val_status="PENDING", rev_status="NOT_REQUIRED",
        received_at=datetime(2026, 10, 11, 11, 20, tzinfo=timezone.utc),
        filename="twg_morning_manifest_4098.xlsx", inserted=inserted,
    )

    return inserted


def main():
    engine = None
    try:
        engine = create_sync_database(settings)
        # Always clean first as required
        clean_database(engine)
        with Session(engine) as session, session.begin():
            inserted = seed_database(session)
            totals = {
                table.name: session.scalar(select(func.count()).select_from(table))
                for table in Base.metadata.sorted_tables
            }
        print("Database seeded successfully with enterprise demo records:")
        for name, count in inserted.items():
            print(f"- {name}: inserted {count}; total {totals[name]}")
    except Exception as error:
        raise SystemExit(
            f"Seed failed ({type(error).__name__}): {error}. Transaction rolled back."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()