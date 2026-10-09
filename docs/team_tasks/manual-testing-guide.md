# OneDMS Manual Testing Guide

A friendly checklist for the five people building OneDMS. Use it to check your own feature as you go, then run the shared demo together.

## Before You Start

- Use a development database and development storage bucket only. Do not test against production or real dealer invoices.
- Follow the setup steps in the repository `README.md`. The backend needs its local environment configured, the database schema set up, and demo data seeded. Never share or paste `.env` values, API keys, or connection strings into screenshots, chat, bug reports, or this document.
- Start the backend and frontend in separate terminals. The README lists the commands and local URLs.
- Open `http://localhost:8000/docs` for the interactive API page. The backend API uses `/api`, without `/v1`.
- Use synthetic invoices and files that contain no personal or confidential information.
- If the database or storage is unavailable, check `GET /api/health/dependencies` first. A health failure is an environment/setup issue; note it separately from a feature bug.

### Find Demo Dealer and DMS IDs

IDs are generated, so do not assume they are always `1` or `2`. If there is no dealer/DMS picker or list API yet, run this read-only query in your development database's SQL editor:

```sql
SELECT d.id AS dealer_id, d.dealer_code, d.name AS dealer_name,
       s.id AS dms_id, s.name AS dms_name, s.input_format
FROM dealers AS d
JOIN inbound_documents AS doc ON doc.dealer_id = d.id
JOIN dms_systems AS s ON s.id = doc.dms_id
WHERE d.dealer_code LIKE 'ONEDMS-DEMO-%'
GROUP BY d.id, d.dealer_code, d.name, s.id, s.name, s.input_format
ORDER BY d.dealer_code;
```

Use the API DMS for JSON submissions and the upload DMS for file submissions when those seeded profiles are present. If no rows appear, follow the README's schema setup and seed steps against the development database.

## Person 1: Intake and Object Storage

Test through Swagger at `http://localhost:8000/docs`.

1. Expand `POST /api/documents` and choose **Try it out**.
2. Enter a real demo `dealer_id` and `dms_id`. Select a small synthetic PDF, CSV, or JSON invoice file (10 MB or less), then execute.
3. Confirm the response is successful and includes a document `id`, `RECEIVED` status, original filename, MIME type, byte size, checksum, and receive time. Note the ID for the next step.
4. Expand `GET /api/documents/{document_id}/source`, enter that ID, and execute. Confirm the browser/API response serves the same source content. For an extra checksum check, compare the response checksum with the original file's SHA-256 using your operating system's file properties or hash tool.
5. Try an unsupported file type, an invalid dealer ID, an invalid DMS ID, and a file larger than 10 MB. Each should fail with a clear error; it should not appear to have been accepted.
6. Expand `POST /api/documents/json` and submit the synthetic request below with valid demo IDs. Confirm it creates a document and does not require an object-storage file.
7. Open `GET /api/documents/{document_id}/source` for the JSON document and confirm the submitted JSON can be retrieved.

Synthetic JSON request body (replace the two IDs):

```json
{
  "dealer_id": 1,
  "dms_id": 1,
  "payload": {
    "invoiceNo": "MANUAL-DEMO-001",
    "billDate": "2026-10-01",
    "dealerCode": "ONEDMS-DEMO-API",
    "buyerCode": "DAIMLER-DEMO",
    "currencyCode": "INR",
    "subTotal": "100.00",
    "taxTotal": "18.00",
    "grandTotal": "118.00",
    "items": [
      {
        "sku": "PART-DEMO-1",
        "description": "Synthetic filter",
        "qty": "2.000",
        "rate": "50.00",
        "discount": "0.00",
        "taxableValue": "100.00",
        "taxRate": "18.00",
        "taxAmount": "18.00",
        "lineTotal": "118.00",
        "chassisNo": null,
        "category": "PART"
      }
    ]
  }
}
```

## Person 2: Parsing and LLM Extraction

Use synthetic content only. Do not submit the same real document repeatedly to the LLM; calls may incur cost and send document text to an external provider.

1. Start with a structured JSON or CSV invoice. Confirm parsing returns the source fields correctly and does not call OpenRouter for data that can be parsed deterministically.
2. If PDF text extraction is implemented, use a small text-based synthetic PDF. Confirm it returns an invoice candidate in the agreed shape. A scanned/image-only PDF is not a fair failure test unless OCR was explicitly implemented.
3. Check missing or ambiguous values: the result should say what is missing or uncertain, not quietly invent a date, amount, dealer, or line item.
4. Check malformed PDF/text, invalid model JSON, provider timeout/error, and an unconfigured LLM key. The user-visible result should be a safe warning/failure that the workflow can handle; the app should remain running.
5. If the LLM has not yet been connected to the processing API, use the module's local development entry point or debugger with synthetic input. Do not add a temporary test script to the shared repository just for a manual check.
6. Review application logs after a failure. They must not contain the API key, full invoice text, full prompt, or raw sensitive model response.

## Person 3: Mapping, Validation, and OEM Preview

Use the synthetic JSON above and the seeded API mapping as your happy-path case. If mapping/validation is not yet connected to an API, invoke the module's local development entry point or debugger with in-memory synthetic data.

1. Map the source fields into canonical names. Confirm the invoice number, date, dealer code, currency, header totals, and line fields all land in the intended places.
2. Check monetary values and quantities retain decimal precision (for example `2.000`, `50.00`, and `118.00`).
3. Change the currency to an unsupported value, make the quantity zero or negative, remove a required field, and make the header total disagree with the line totals. Confirm each produces a finding with a useful code/message and the relevant field or line.
4. Try a spare-parts line with no chassis number; it should not fail just because that optional field is empty. Try a line explicitly categorized as a vehicle without a chassis number; it should trigger the configured vehicle rule.
5. If duplicate detection is implemented, submit or map the same dealer/invoice/date combination twice and confirm it is flagged according to its configured severity.
6. Generate the mock OEM payload. Confirm field names follow the active output mapping, review metadata is absent, and nothing is sent to an actual OEM system.

## Person 4: Review Frontend

Use `http://localhost:5173` after starting the frontend and backend.

1. Check the initial screen and navigation. The app should present the invoice workflow, not claim that unfinished services are online.
2. Try the upload form with a supported synthetic invoice and valid demo dealer/DMS selections. Confirm progress, success, and failure feedback are understandable.
3. Open the document/invoice queue. Check status filters, loading state, empty state, and a backend error state where practical.
4. Open a seeded or newly processed invoice. Confirm header totals, line items, dealer/DMS information, and validation findings are readable.
5. Open the original document from the review page. Confirm it loads through the backend source endpoint and the browser does not need a direct storage URL or secret.
6. Edit a field, save, and confirm the displayed value refreshes from the API. Try approve/reject and confirm an invalid invoice cannot appear approved unless the backend explicitly supports an override.
7. Resize to a narrow phone-sized viewport. Check that the queue, findings, invoice fields, and action buttons do not overlap or get clipped.
8. If the matching backend API is not implemented yet, use only an explicitly development-only mock. Label this as a frontend-only check, not as an end-to-end success.

## Person 5: Workflow, Persistence, and API Integration

Use Swagger at `http://localhost:8000/docs` and the frontend when those routes are available.

1. Submit the synthetic JSON invoice using Person 1's intake route, then retrieve it by its returned document ID.
2. Start processing using the agreed processing endpoint. Confirm the document moves through the expected states and that the canonical invoice and its line items are saved.
3. Retrieve the invoice. Check the regular header/line fields, canonical payload, validation findings, and review status agree with one another.
4. Process the same document again. Confirm a second invoice is not created and the agreed retry behavior is clear to the user.
5. Submit an invoice with a mismatched total or missing required field. Confirm it is not silently marked valid or complete and that the response explains what needs attention.
6. Correct an invoice, save it, and confirm validation runs again. Approve a valid invoice and reject another; confirm the status returned by the API matches the decision.
7. Request a mock OEM preview. Confirm it is labeled as a preview and makes no external call.
8. Cause a safe failure (for example, use a missing document ID). Confirm the API returns a useful status/message without a traceback, provider response, credential, or database URL.
9. Check related records in the development database if needed. A document should have at most one standardized invoice; each invoice's lines should be complete, not partially written.

**Note:** Processing, invoice list/detail, correction, review, and OEM-preview routes are planned in the Person 5 brief but are not part of the current document endpoint router. Mark a step **Not implemented yet** until the route exists; do not treat its absence as an individual agent's test failure.

## Shared End-to-End Demo

Once all parts are integrated, run this short story with the synthetic invoice:

1. Person 1 submits the JSON invoice and records the returned document ID.
2. Person 5 starts processing and opens the resulting invoice.
3. Person 2 confirms the structured input was parsed without an unnecessary LLM call; use a text PDF as the separate LLM demo only if supported.
4. Person 3 shows the canonical result, validation findings, and mock OEM preview. Also show one intentionally incorrect invoice and its useful validation finding.
5. Person 4 opens the same invoice in the browser, views the original, fixes an issue if applicable, and approves it after it passes validation.
6. Person 5 confirms the final status and that only one invoice exists for the document.

A complete demo proves the path for these sample inputs. It does not prove support for every DMS, OCR for scans, authentication, production security, or a live OEM integration.

## Recording a Problem

When something fails, please share:

- **Which person/feature:**
- **What I tried:**
- **What I expected:**
- **What actually happened:**
- **Document or invoice ID:** Use synthetic data only.
- **Screenshot or response:** Remove names, invoice data, keys, URLs containing credentials, and all `.env` values.
- **Environment issue or feature issue:** Note health-check results if relevant.

Do not paste secrets, raw real invoices, or full sensitive model prompts/responses into an issue or team chat.
