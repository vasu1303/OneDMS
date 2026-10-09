# OneDMS invoice inspection frontend

React 19, TypeScript, Vite, React Router, TanStack Query, and Axios.
No UI framework or authentication implementation. This POC is not
production-secure. No backend or secret configuration is owned here.

## Interface direction

Subject: OEM invoice inspection. Audience: reviewers resolving extracted
invoice findings. Primary job: inspect the retained source, correct the
canonical record, then explicitly approve or reject saved values.

White #FFFFFF, mist #EDF2F6, graphite #233544, blue #2458A6,
green #216647, red #A92E3B. Segoe UI uses a 28/20/16/14px scale;
Consolas identifies records and aligns monetary fields.

```text
Desktop queue                 Desktop inspection
navigation | title / upload   navigation | invoice / saved total / status
           | filters                     | retained original | canonical editor
           | ruled ledger                |                   | lines / findings
                                         |                   | save / decision
Narrow: navigation above content; queue rows become labeled ledger records;
inspection stacks original above editor, with independently readable lines.
```

The invoice ledger is the primary viewport, not a promotional dashboard.
Only canonical editing receives the blue structural rule. No decorative
metrics, gradients, shadow cards, or status-badge collections. Plain control
labels, visible keyboard focus, source recovery, and error/empty recovery
take priority. One short save-feedback transition respects reduced motion.

## Running and checking

Use the existing `npm run dev`, `npm run build`, and `npm run lint` scripts.
The existing TypeScript 6 build/deprecation workaround is preserved.
Vite proxies `/api` to `http://localhost:8000`; live API is the default.
`VITE_API_URL`, if supplied, is only a public API base URL, never a secret.

The existing backend currently exposes health endpoints only. Upload,
source, processing, and invoice review are **not integrated yet**. A visible
API error in live mode is expected until the endpoint owners implement them.
There is no existing component test runner; no testing dependency was added.

## Provisional API coordination — not an agreed final contract

The DTOs in [src/types/index.ts](src/types/index.ts) and methods in
[src/services/api.ts](src/services/api.ts) retain the earlier frontend
proposal. Obtain actual example payloads from Persons 1 and 5 and finding
semantics from Person 3 before treating these as final or integrated.

All paths below are relative to `/api`:

| Operation | Proposed path / request | Proposed response |
| --- | --- | --- |
| Queue | `GET /documents`, optional status/dealer_code/q filters | Array, or items/data array envelope |
| Document | `GET /documents/{id}` | DocumentDetail |
| Original | `GET /documents/{id}/source` | Original bytes with accurate Content-Type |
| File intake | `POST /documents`, multipart dealer_id, dms_system_id, source_type, file | DocumentDetail |
| JSON intake | `POST /documents/json`, {dealer_id, dms_system_id, payload} | DocumentDetail |
| Process | `POST /documents/{id}/process` | DocumentDetail |
| Invoices | `GET /invoices`, `GET /invoices/{id}` | List / InvoiceDetail |
| Corrections | `PATCH /invoices/{id}`, {header, line_items} | Updated InvoiceDetail |
| Decision | `POST /invoices/{id}/review`, {decision: approve or reject, comment?} | Updated InvoiceDetail |

- Dealer/DMS input names currently say ID but transport values remain
  strings in the provisional submission DTO. No registry options or assumed
  numeric registry contract are invented. Coordinate registry lookup and IDs.
- Document/invoice/finding/line IDs must be positive safe JSON integers.
  Route IDs use positive decimal digits. String JSON IDs are rejected, not
  silently coerced; coordinate any transport change explicitly.
- Required amounts/quantities currently require finite JSON numbers. Missing
  values or decimal strings trigger visible contract errors instead of zero.
  Decimal precision, nullability, and string transport need backend agreement;
  this UI does not implement monetary reconciliation or validation rules.
- Missing received time, currency, and descriptive text are not replaced
  with the current date, USD, or fabricated identifiers. Unsupported required
  statuses and malformed list/line/finding containers produce contract errors.
- Editable header: invoice_number, invoice_date, dealer_invoice_ref,
  currency_code, subtotal_amount, discount_amount, tax_amount, total_amount.
- Editable lines: part_number, description, vin, quantity, unit_price,
  discount_amount, tax_amount, line_total; retain id and line_number.
  **These patch fields are provisional, not backend-confirmed**, including
  part_number, discount, and VIN. No auto-calculated comparison amounts.
- Finding proposal: severity, field, line_number, message, confidence,
  extracted_value, approved_value. Confidence is provisionally displayed as
  a 0–1 fraction; approved_value is labeled as API-supplied, not a user action.
  Zero values remain visible. Confirm the stable format with Person 3.
- Mutations expect updated objects, not 204 responses. Decisions show the
  status returned by the server; no invented delivery success or timestamps.
  Coordinate concurrency/versioning before multiple reviewers use this POC.
- Source uses the typed Axios blob client, cancellation and revoked object
  URLs. PDF/text/JSON/XML/CSV preview inline; other formats provide a download
  fallback. No direct storage URLs or browser access to infrastructure.

## Development fixtures

Fixture mode requires **both** Vite development mode and
`VITE_USE_MOCK_API=true`. It is off by default and ignored in production.
The navigation and source panel visibly label it. Existing synthetic
canonical records demonstrate layout only, not extraction or integration.
Seeded records have **no retained original** and report that clearly.
Only files or JSON actually submitted in the current fixture session are
retained in memory for source preview. Reloading discards fixture changes.

## Workflow behavior

Queue/detail poll every five seconds only while received/processing records
are active. Processing, correction, and decision mutations refresh relevant
document/invoice caches and the queue. Errors include backend messages when
available; retry never fabricates success.

The identity-keyed editor initializes once, retaining drafts on query
refreshes and failed mutations. Save/decision pending state disables edits
and conflicting decisions. Dirty drafts disable decisions and require a
confirmation before link/browser-back navigation; beforeunload protects
reload/close. Drafts are not persisted after confirmed abandonment.
JSON submission validates syntax and object shape locally, and submission
controls remain disabled until acceptance or failure. No arbitrary upload
size restriction is introduced.
