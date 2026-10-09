# Person 1: Document Intake and Object Storage

## Assignment

You are the coding agent responsible for receiving dealer invoice submissions and safely retaining their original source. Implement this as a bounded backend feature that other agents can call without knowing storage details.

## Current project context

- Backend: `backend/app`, FastAPI with async SQLAlchemy.
- API prefix is `/api`; there is no version segment.
- Existing storage client is `backend/app/services/storage.py`. It currently creates an S3-compatible Neon Object Storage client and checks bucket connectivity, but has no upload/download methods.
- Existing invoice models are in `backend/app/models/invoice.py`. Preserve the seven-table design; do not introduce processing-run, user, or storage-provider tables.
- `inbound_documents` supports file metadata, `storage_key`, optional `raw_payload`, checksum, status, and latest error.
- Never read, print, or commit `backend/.env` or credentials. Use `.env.example` for documentation changes.

## Build

1. Implement file intake for the POC's agreed formats: PDF, CSV, and JSON. XLSX can be added only if time permits and its parser is actually implemented. Reject unsupported types and oversized uploads with actionable HTTP errors.
2. Add `POST /api/documents` as multipart upload. Require valid `dealer_id` and `dms_id`; accept one invoice document per submission. Return the created document ID, status, file metadata, and checksum.
3. Add `POST /api/documents/json` for JSON invoice submissions. Store the submitted JSON in `raw_payload`; do not require an object-storage object for this route.
4. Extend the existing storage abstraction with async-safe upload and source retrieval methods. Boto3 calls must not block the event loop; use the repository's established async conventions.
5. Generate object keys on the server. Do not use a client filename as a path or expose bucket credentials, object endpoints, or permanent public URLs.
6. Persist document metadata and the private object reference. Handle failure boundaries: if upload fails, report failure and retain no false storage reference; if the database commit fails after a successful upload, attempt best-effort orphan cleanup and log a sanitized error.
7. Add `GET /api/documents/{document_id}/source` to stream the retained source through the backend for the review UI. Set a safe content type and sanitized inline filename. Do not return credentials or bucket URLs.
8. Add focused API/service tests using mocked storage and database dependencies. Do not require live Neon, S3, or LLM credentials to run them.

## Ownership boundaries

- You own intake routes, upload validation, object upload/source retrieval, checksum generation, and creation of `InboundDocument` rows.
- Person 5 owns processing, document/invoice list and detail APIs, review APIs, and orchestration after intake.
- Person 2 owns parsing/extraction. Do not call the LLM from intake.
- Person 4 consumes your endpoints; coordinate their exact response shapes before implementation.
- Do not implement frontend pages, mapping/rules, invoice persistence, or OEM export.

## Shared contract

- Public paths begin with `/api`, not `/api/v1`.
- New documents start as `RECEIVED`.
- A file response includes `id`, `status`, `original_file_name`, `mime_type`, `file_size_bytes`, `checksum_sha256`, and `received_at`.
- JSON submissions use the same document model and return the same metadata shape; their `storage_key` may be null.
- Keep errors safe for users and logs: never include secrets or dump full invoice payloads in exception messages.

## Acceptance criteria

- A valid PDF, CSV, or JSON submission creates one document record and can be retrieved by ID.
- A file submission stores its original privately and the source endpoint serves it through the backend.
- A JSON submission retains its payload without inventing a storage key.
- Invalid dealer/DMS IDs, unsupported types, size violations, storage errors, and database errors have predictable responses and do not leave misleading document state.
- Duplicate content is detectable from the checksum; document the behavior and avoid silently overwriting an existing object.
- Tests run without external services, and the README's local setup remains valid.

## Coordinate before coding

Agree with Person 5 on dependency injection/session access and route ownership. Agree with Person 4 on the upload fields and response JSON. Agree with Person 2 on supported MIME types and how JSON versus uploaded files are handed to processing.
