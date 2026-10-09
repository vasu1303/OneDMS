# Person 4: Invoice Review Frontend

## Assignment

You are the coding agent responsible for the usable React workflow that lets an OEM reviewer see submitted invoices, understand validation/extraction issues, correct data, and make a review decision.

## Current project context

- Frontend is React 19, TypeScript, Vite, React Router, Axios, and TanStack Query. Use existing dependencies and conventions; do not introduce a new UI framework.
- `frontend/src/App.tsx` is currently a static readiness page. `frontend/src/services/api.ts` already configures the `/api` base URL.
- `frontend/src/types/index.ts` describes generic order/quote transactions and string IDs; it does not match the invoice-only database, whose IDs are generated integers. Replace or extend types for this invoice workflow without inventing unsupported backend data.
- There is no authentication implementation. Do not imply that the POC is production-secure.

## Build

1. Create navigable screens for an invoice/document queue and invoice review detail. Keep the first viewport focused on the working queue, not marketing content.
2. Queue view: show invoice/document identifier, dealer, DMS, received time, processing/validation/review status, and actionable error/review summary. Provide useful status filtering and loading, empty, and error states.
3. Review view: show extracted/canonical header and line items beside or in close association with the retained original document. Load the original via the backend source endpoint; do not construct storage URLs in the browser.
4. Allow correction of supported invoice header/line fields and submit edits through the agreed API. Add explicit approve and reject actions with confirmation/feedback and refresh the queue after completion.
5. Display validation findings by severity, field/line, and message. Clearly distinguish extracted values from approved values and show uncertainty where the API supplies it.
6. Add the intake form for dealer, DMS, and supported upload types. Use the backend multipart endpoint; show upload progress or a clear pending state and errors.
7. Use typed API client methods and server state through the project's existing React Query dependency. Avoid fake success states: any mocked API mode must be development-only and clearly isolated.
8. Keep invoice IDs numeric in frontend types while tolerating JSON transport values only as specified by the backend. Do not preserve order/quote workflows that have no backend/database support.
9. Add focused component or integration coverage using mocked API responses if the existing test setup supports it. At minimum, run the frontend's existing lint/build commands and report any pre-existing failures distinctly.

## API contract to coordinate

Use unversioned `/api` paths. Coordinate final response types with Person 5. Expected operations include:

- `POST /documents` for multipart upload and `POST /documents/json` for JSON submission.
- `GET /documents` and `GET /documents/{id}` for queue/details.
- `GET /documents/{id}/source` for the original file streamed through the backend.
- `POST /documents/{id}/process` to start/await POC processing if that is the agreed workflow.
- `GET /invoices` and `GET /invoices/{id}` for canonical data and findings.
- `PATCH /invoices/{id}` for corrections and `POST /invoices/{id}/review` for approve/reject.
- A mock export operation only if Person 5 exposes it.

Do not invent final paths independently; record the agreed paths and payloads in frontend types/client methods.

## Ownership boundaries

- You own frontend routes, screens, invoice types, API client methods, and UI states.
- Person 1 owns upload/source backend endpoints; Person 5 owns document/invoice workflow and review APIs.
- Person 3 owns validation/mapping semantics. Render supplied findings; do not reproduce business rules in TypeScript.
- Do not access Neon, S3, or OpenRouter directly from the browser. Never put secrets in `VITE_*` variables.

## Acceptance criteria

- A reviewer can upload an invoice, see its processing state, open the result, inspect the original, correct fields, and approve/reject using backend APIs.
- Invalid, failed, review-required, approved, and empty queue states are understandable and recoverable.
- API or network failures do not appear as successful actions; retry/navigation behavior is sensible.
- UI works at desktop and narrow mobile widths without clipped controls or overlapping invoice content.
- `npm run build` and `npm run lint` are run; report errors rather than hiding them.

## Coordinate before coding

Get example request/response JSON from Person 1 and Person 5 before finalizing types. Get the stable validation finding format from Person 3. Build against fixtures while backend endpoints are in progress, then remove or disable fixtures for the integrated demo.Act as a design lead at a studio known for distinct visual identities. Before coding, identify the subject, audience, and primary job. Write a short design plan (4–6 named hex colors, type roles, layout with ASCII wireframes, principles), then check it against what you’d produce for any similar brief; revise anything generic. Avoid default AI traits: cream + serif + terracotta, black + neon accent, broadsheet pastiche, identical rounded cards with the same soft shadow, gradient washes, all-caps eyebrows, middle-dot meta strings, → on every link, single-word headline accents, and decorative 01/02/03 numbering. Use one or two clearly distinct typefaces with a real scale and lines under 80 characters. Make the hero the most characteristic thing in the subject’s world. Spend boldness in one place, use motion once and purposefully, and write plain, specific, active-voice copy. Ensure responsiveness, focus states, contrast and reduced motion, then critique your own screenshots and remove one thing