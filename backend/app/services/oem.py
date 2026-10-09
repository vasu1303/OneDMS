from datetime import datetime, timezone
from typing import Any

from app.api.v1.schemas.invoice import MockOEMResponse
from app.models.invoice import MappingConfig, StandardizedInvoice
from app.services.mapping import map_canonical_to_oem


class OEMExportService:
    """Person 3 integration for formatting canonical invoices for mock OEM export."""

    @staticmethod
    def generate_oem_payload(
        invoice: StandardizedInvoice,
        mapping_config: MappingConfig | None = None,
    ) -> MockOEMResponse:
        """Generates deterministic OEM (Daimler ERP) payload from canonical invoice.

        Reuses Person 3's map_canonical_to_oem function, strips any private _onedms
        metadata, and makes zero external network calls.
        """
        raw_canonical = invoice.canonical_payload or {}

        # 1. Cleanse internal metadata
        cleaned_canonical = {k: v for k, v in raw_canonical.items() if not k.startswith("_")}
        if "line_items" in cleaned_canonical and isinstance(cleaned_canonical["line_items"], list):
            cleaned_canonical["line_items"] = [
                {k: v for k, v in line.items() if not k.startswith("_")}
                for line in cleaned_canonical["line_items"]
            ]

        # 2. Extract mapping rules if provided
        config = mapping_config.mapping_config if mapping_config else {
            "invoiceNumber": "invoice_number",
            "invoiceDate": "invoice_date",
            "supplierCode": "supplier_dealer_code",
            "currencyCode": "currency",
            "grossAmount": "total_amount",
            "items": {
                "source_field": "line_items",
                "materialCode": "item_code",
                "description": "description",
                "quantity": "quantity",
                "netPrice": "unit_price",
                "chassisNumber": "chassis_number",
            },
        }

        # 3. Call Person 3's mapping function
        oem_payload = map_canonical_to_oem(cleaned_canonical, config)

        # Fallback if mapping returned empty keys
        if not oem_payload.get("invoiceNumber"):
            oem_payload["invoiceNumber"] = invoice.invoice_number
        if not oem_payload.get("invoiceDate"):
            oem_payload["invoiceDate"] = str(invoice.invoice_date)
        if not oem_payload.get("currencyCode"):
            oem_payload["currencyCode"] = invoice.currency
        if not oem_payload.get("grossAmount"):
            oem_payload["grossAmount"] = str(invoice.total_amount)

        return MockOEMResponse(
            is_mock=True,
            target_system=mapping_config.target_system if mapping_config and mapping_config.target_system else "DAIMLER_ERP",
            delivery_status="SENT" if invoice.oem_delivery_status == "SENT" else "NOT_SENT",
            payload=oem_payload,
            disclaimer="Preview / Mock: No external Daimler endpoint was called.",
            timestamp=datetime.now(timezone.utc),
        )
