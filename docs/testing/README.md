# Synthetic PDF smoke test

Use [onedms_test_invoice.pdf](onedms_test_invoice.pdf) for a fresh upload.
It is a selectable-text PDF with a bordered line-item table, not a scan.

## Expected values

- Invoice: ONEDMS-PDF-TEST-20261010
- Date: 2026-10-10
- Currency: INR
- Brake pad kit: quantity 2, unit price 300.00, total 600.00
- Air filter: quantity 1, unit price 400.00, total 400.00
- Subtotal: 1000.00; tax: 0.00; grand total: 1000.00
- Spare parts: no chassis number required

Zero tax is intentional: the current local PDF parser assigns zero line tax.
This fixture tests the happy path; it does **not** fix extraction of taxed PDFs
or demonstrate real tax compliance. Do not change a real invoice's tax to pass validation.

## Browser test

1. Open **Invoice intake** and select **Multipart file** and **pdf**.
2. Enter existing demo dealer and DMS integer IDs. Use the lookup described in
   [the manual testing guide](../team_tasks/manual-testing-guide.md#find-demo-dealer-and-dms-ids);
   do not assume generated IDs are always 1.
3. Select the PDF linked above and submit it once.
4. Confirm a new document opens with **Received** status.
5. Process it, then open its invoice review page.
6. Compare the original and extracted values against the list above.
7. Expect **Valid** with zero validation findings, then choose **Approve invoice**.
8. Confirm **Approved** after the server responds.

If upload reports a connection failure, inspect the browser Network tab. An
OPTIONS 400 is a CORS issue, independent of invoice validation; restart the
backend serving that port after changing CORS. A review 422 means approval was
refused; inspect the findings rather than repeatedly clicking Approve.

## Completed offline check

The generator at [scripts/create_demo_pdf.py](../../scripts/create_demo_pdf.py)
creates this fixture and asserts its extracted number, date, currency, totals,
two line items, no parser warnings, and successful total reconciliation.
The check passed with zero findings. It makes no storage, database, or LLM calls.
Live upload, processing, and approval still need the browser test above.