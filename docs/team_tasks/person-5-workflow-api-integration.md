# Person 5: Workflow API, Persistence, and Integration

## Assignment

You are the coding agent responsible for the backend workflow that connects intake, extraction, mapping/validation, invoice persistence, review decisions, and mock OEM export. Publish the API contract early so the other four agents can work in parallel against it.

## Current project context

- FastAPI entry point: `backend/app/main.py`; API router: `backend/app/api/v1/router.py`.
- Existing API paths use `/api` with no version segment. Health endpoints are the only business-adjacent routes today.
- SQLAlchemy models for the final seven-table invoice design are in `backend/app/models/invoice.py`; database session setup is in `backend/app/core/database.py`.
- Do not add tables, UUID IDs, per-row storage-provider fields, Alembic/version tables, or a processing-runs table. `inbound_documents.error_message` is the latest actionable error only.
- Other agents own the intake/storage route, extraction module, mapping/rules functions, and frontend. Keep interfaces small and integrate their modules rather than duplicating them.

## First deliverable: publish contracts

Before substantial implementation, agree with all four agents on:

- Request/response models and unversioned paths.
- Extraction result type from Person 2 and mapping/validation result type from Person 3.
- Document/invoice status transitions and the policy for repeated processing.
- Which safe review metadata is stored under a reserved `_onedms` key in `canonical_payload`.

Recommended status flow: document `RECEIVED -> PROCESSING -> COMPLETED | REVIEW_REQUIRED | FAILED`; invoice validation `PENDING -> VALID | INVALID | REVIEW_REQUIRED`; review `NOT_REQUIRED | PENDING -> APPROVED | REJECTED`. Do not mark a failed extraction as a completed/valid invoice.

## Build

1. Add Pydantic request/response schemas and route modules following the existing API structure. Keep document intake route ownership with Person 1.
2. Implement document list/detail and invoice list/detail endpoints with pagination or a documented bounded result size and filters for the statuses needed by the UI.
3. Implement `POST /api/documents/{document_id}/process`. Load the document and source, invoke Person 2 extraction, load active mapping/rules, invoke Person 3 mapping/validation, and persist the invoice header and lines in one database transaction.
4. Update document and invoice statuses consistently. On a processing exception, store a sanitized, actionable `error_message`, set `FAILED` or `REVIEW_REQUIRED` according to the failure type, and do not expose stack traces, provider responses, or secrets.
5. Make repeated processing behavior explicit and idempotent for the POC: do not create a second invoice for a document with an existing invoice. Define whether a deliberate retry updates the existing invoice or requires an operator action; coordinate with the team.
6. Implement `PATCH /api/invoices/{invoice_id}` for reviewer corrections to supported canonical header/line fields. Re-run Person 3 validations after corrections and persist updated statuses/payload consistently.
7. Implement `POST /api/invoices/{invoice_id}/review` for approve/reject. Enforce that invalid invoices cannot be approved without an explicit agreed override; for the simplest POC, reject approval while `INVALID` and require correction first.
8. Expose the mock OEM payload operation using Person 3's mapping function. It must not call an actual Daimler endpoint. Clearly label the response as preview/mock.
9. Include the LLM dependency in a health/readiness response only if it can be checked without spending tokens on every health request. Keep liveness independent of external services. Do not return an API key, raw prompt, or raw provider response.
10. Add focused API/workflow tests with database, storage, LLM, and mapping dependencies mocked or isolated. Tests must not require live credentials.

## Persistence rules

- Respect the existing seven ORM models and foreign keys.
- Persist invoice header values in regular columns and the complete canonical invoice in `canonical_payload`.
- Keep review/extraction findings under the reserved `_onedms` metadata key if agreed; strip that key from OEM output.
- Use `Decimal` for money and quantity; serialize JSON values safely.
- Do not store temporary signed URLs, credentials, complete prompts, or unnecessary duplicate raw document content.
- Use transaction boundaries so a partially persisted header/line set is not presented as a complete invoice.

## Ownership boundaries

- You own processing orchestration, repositories/session wiring, workflow/list/detail/review/export APIs, and integration.
- Person 1 owns `POST /documents`, JSON intake, object upload, and `GET /documents/{id}/source`.
- Person 2 owns parsing and LLM calls.
- Person 3 owns pure mapping, validation, and OEM payload functions.
- Person 4 owns all frontend routes/components and consumes your published contract.
- Avoid broad model/schema redesign. If a requirement cannot fit the existing schema, explain the gap and ask before adding a table or changing the approved design.

## Acceptance criteria

- The API can process an intake record through extraction, mapping, validation, and atomic invoice/line persistence.
- Valid, invalid, uncertain, and failed cases produce consistent document/invoice statuses and explainable API responses.
- Review edits are revalidated; approve/reject decisions update state and are visible to the frontend.
- Repeated processing cannot create duplicate invoices for the same inbound document.
- Mock OEM output is deterministic for a fixed invoice/config and makes no external network call.
- API schema/docs describe the workflow and local setup remains consistent. Tests run without Neon, S3, or OpenRouter credentials.

## Integration checklist

- Keep `backend/app/api/v1/router.py` route registration conflict-free; coordinate additions with Person 1.
- Provide Person 4 example JSON responses early, including one valid and one review-required invoice.
- Confirm Person 2 and Person 3 module interfaces before wiring calls; do not wait for their finished UI or full implementations to create route/schema scaffolding.
- At integration, run backend-focused checks and the frontend build with the team. Record any unavailable live-service verification as a limitation.
