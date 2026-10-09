"""CLI tool to parse any PDF, CSV, or JSON invoice file using the local extraction engine."""

import sys
import json
from pathlib import Path

from app.extraction.service import extraction_service


def parse_and_print(file_path_str: str):
    file_path = Path(file_path_str)
    if not file_path.exists():
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)

    print(f"\nParsing invoice document: {file_path.name}")
    print("-" * 65)

    with open(file_path, "rb") as f:
        content = f.read()

    result = extraction_service.extract_document(content, filename=file_path.name)

    print(f"Status:            {'SUCCESS' if result.success else 'FAILED'}")
    print(f"Detected Format:   {result.format.value.upper()}")
    print(f"Extraction Method: {result.extraction_method}")
    print(f"Duration:          {result.metadata.duration_ms} ms")

    if not result.success:
        print(f"Error Message:     {result.error_message}")
        if result.warnings:
            print(f"Warnings:          {result.warnings}")
        return

    if result.canonical_candidate:
        cand = result.canonical_candidate
        print("\n--- CANONICAL CANDIDATE (PROPOSED BY LOCAL EXTRACTOR) ---")
        print(f"Invoice Number:    {cand.invoice_number}")
        print(f"Invoice Date:      {cand.invoice_date}")
        print(f"Buyer OEM:         {cand.buyer_oem_id or 'N/A'}")
        print(f"Currency:          {cand.currency}")
        print(f"Subtotal:          {cand.subtotal_amount}")
        print(f"Tax Amount:        {cand.tax_amount}")
        print(f"Total Amount:      {cand.total_amount}")
        print(f"\nLine Items ({len(cand.line_items)} extracted):")
        for line in cand.line_items:
            chassis_info = f" | VIN: {line.chassis_number}" if line.chassis_number else ""
            print(
                f"  [{line.line_number}] Item: {line.item_code or 'N/A':<14} | "
                f"Qty: {line.quantity:>3} @ {line.unit_price:>8.2f} = {line.line_total:>8.2f} "
                f"| {line.description[:35]}{chassis_info}"
            )

    if result.source_data is not None:
        print("\n--- STRUCTURED SOURCE DATA (FOR MAPPING LAYER) ---")
        print(json.dumps(result.source_data, indent=2))

    if result.warnings:
        print(f"\nWarnings: {result.warnings}")

    print("-" * 65)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    else:
        target = "data/sample_dms_pdf/daimler_dealer_invoice.pdf"
    parse_and_print(target)
