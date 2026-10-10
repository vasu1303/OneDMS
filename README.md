# OneDMS — Unified Dealer Management System

> **Hackathon POC** — A standardized integration layer between OEMs and dealers,  
> normalizing 80+ DMS formats into one canonical data model.

## The Problem

OEMs like Daimler Truck work with 1,500–2,000 dealers running 80+ different DMS platforms.
Each DMS uses its own schemas, terminology, and formats (APIs, PDFs, Excel, flat files)
for the same business processes — orders, quotes, negotiations, invoices.

**OneDMS** creates a standardized layer on the OEM side so dealers change nothing.

## Architecture

```
DMS Sources (API / SFTP / Upload)
        │
        ▼
  ┌─────────────────────┐
  │  Databricks/PySpark  │  Ingestion → Transformation → Enrichment
  │  Pipeline (ETL)      │  Bronze → Silver → Gold
  └─────────┬───────────┘
            │  Canonical JSON
            ▼
  ┌─────────────────────┐
  │  FastAPI Backend     │  Config API, validation, exception queue
  └─────────┬───────────┘
            │  REST API
            ▼
  ┌─────────────────────┐
  │  React Dashboard     │  Unified view, onboarding, review
  └─────────────────────┘
```

## Tech Stack

| Layer       | Technology                        |
|-------------|-----------------------------------|
| Frontend    | React + TypeScript + Vite + Tailwind |
| Backend     | FastAPI + Uvicorn + SQLAlchemy    |
| Database    | Neon PostgreSQL + psycopg 3       |
| Files       | Neon Object Storage + boto3       |

## Implementation Status

The runnable application includes a React frontend, FastAPI ingestion and registry
APIs, PostgreSQL connection/session infrastructure, Neon Object Storage integration,
and health APIs. Onboarding supports JSON/API, CSV, PDF, and Excel (`.xls` and
`.xlsx`) profiles. PostgreSQL stores structured invoice data and object references;
original uploaded files belong in the private `onedmsinvoices` bucket. Credentials
and storage access stay in the backend, never in the browser.

The seven invoice tables described in [the database design](docs/architecture/OneDMS_Database_Design.md)
are implemented with SQLAlchemy models and an explicit schema setup command. An idempotent seed
script supplies synthetic demo data. Startup does not create tables, buckets, or files.
Authentication and production DMS connectors remain planned.

Each DMS integration profile has one input format and its own mapping. Registering
multiple formats creates separate profiles with the same DMS name, so each profile
can be selected independently for intake. Excel workbooks use the first worksheet,
with headers in row one and invoice line items in subsequent rows; each workbook
represents one invoice. PDF extraction uses the existing local parser and does not
perform OCR.

## Prerequisites

- Python 3.12+ and pip.
- Node.js 22.12+ in the Node 22 line, or a newer supported LTS release, and npm.
- A Neon project with PostgreSQL and Object Storage available for your branch.

## Neon Setup

1. In the Neon Console, select your project and branch. Open **Connect > Database**
   and copy the pooled PostgreSQL connection string. Preserve `sslmode=require`
   and `channel_binding=require`. Rotate any password previously shared in chat.
2. In the storage bucket view, verify that `onedmsinvoices` exists with **private** access;
   create it if missing. The application does not create the bucket. Neon currently
   supports Object Storage in Singapore, Ohio, N. Virginia, and Frankfurt.
3. Open **Connect > Storage** and choose **Parameters only** or **Python**.
   Copy the branch-specific endpoint, region, access key ID, and secret key.
   A storage credential needs `storage:read` for the health check, and
   `storage:write` for future uploads. The database password is not a storage key.
4. Add these values to the ignored `backend/.env` file. Use the same branch for
   database and storage. Do not derive the storage endpoint from the database host.

See Neon's [storage quickstart](https://neon.com/docs/storage/get-started) and
[credential instructions](https://neon.com/docs/storage/authentication).
If Object Storage is unavailable to your account, provision it before checking
connectivity; the database connection alone cannot enable it.

Required backend environment values (placeholders only):

```dotenv
DATABASE_URL=postgresql://YOUR_ROLE:YOUR_PASSWORD@YOUR_ENDPOINT-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
AWS_ENDPOINT_URL_S3=https://YOUR_BRANCH.storage.YOUR_REGION.aws.neon.tech
AWS_REGION=ap-southeast-1
AWS_ACCESS_KEY_ID=YOUR_STORAGE_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=YOUR_STORAGE_SECRET_ACCESS_KEY
S3_BUCKET_NAME=assets
DEPENDENCY_TIMEOUT_SECONDS=10
CORS_ORIGINS=["http://localhost:5173"]
```

Use the actual storage endpoint and region from Neon, not the placeholders.
Secrets must never be `VITE_*` variables. No Neon management API key or AWS
account is required by the backend. Environment variables override `backend/.env`;
that file is loaded independently of the working directory. The check timeout
accepts 1-60 seconds. Restart the backend after changing environment values.

## Local Setup

Use separate terminals for backend and frontend, starting from the repository root.
Copy the environment template only if you do not already have `.env`, then fill
in real values before starting the backend.

### Backend: Windows PowerShell

```powershell
cd backend
python -m venv .venv
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.setup_db
.\.venv\Scripts\python.exe run.py
```

These commands use the virtual environment directly, so PowerShell activation is
not required.

### Backend: macOS / Linux

```bash
cd backend
python3 -m venv .venv
test -f .env || cp .env.example .env
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m app.setup_db
.venv/bin/python run.py
```

### Frontend

In the second terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

The API base URL defaults to `http://localhost:8000/api`. To change it, set
`VITE_API_URL` in `frontend/.env.local` and restart Vite. This URL is public;
never put database or storage credentials in the frontend environment.

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend | http://localhost:8000 |
| API docs / interactive testing | http://localhost:8000/docs |
| API schema | http://localhost:8000/openapi.json |

## Database Setup And Demo Data

From the repository root, run these PowerShell commands against the database in
`backend/.env`. Choose a development branch and back up existing data before
changing the schema:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.setup_db
.\.venv\Scripts\python.exe -m app.seed
```

On macOS/Linux, substitute `.venv/bin/python` for `.\.venv\Scripts\python.exe`.
The setup command creates exactly `dealers`, `dms_systems`, `inbound_documents`,
`mapping_configs`, `validation_rules`, `standardized_invoices`, and
`invoice_line_items`, with the documented foreign keys, unique constraints, and
indexes. IDs are generated `BIGINT` integers, not UUIDs. Status/tier checks reject
unsupported values. Partial unique indexes allow one active mapping per source
DMS/document type or OEM target/document type. A
PostgreSQL trigger refreshes invoice `updated_at` even for direct SQL updates.
There is no schema-version table or Alembic dependency.

The command upgrades the previous six-table schema without deleting dealers,
documents, invoices, or line items. It remaps foreign keys to integer IDs, carries
the latest failed processing error onto the document, retires processing-attempt
history, and removes the old version table. A conflicting supplier/dealer
relationship or unexpected schema stops the update and rolls back. Run setup
without concurrent invoice writes; lock waits are bounded. Future schema changes
must be handled explicitly; `create_all` does not reconcile arbitrary alterations.

The seed adds two synthetic dealers, two DMS systems (JSON API and CSV upload),
three inbound documents, three invoices, five line items, three mapping configs,
and seven validation rules. Examples include spare parts with a null
`chassis_number`, a truck with a synthetic chassis number, and an invoice awaiting
review. Amounts use exact decimals and reconcile with the line items.
The two dealers deliberately share an invoice number to demonstrate that invoice
numbers are not globally unique.

Seeding uses generated integer IDs, natural-key lookups, and one transaction.
Reruns retain existing demo records and active mappings without overwriting edits;
failures roll back the transaction. Mapping and validation JSON are configuration
examples, not an implemented mapping/rules engine. Vehicle-specific chassis
requirements are described by a conditional rule; the database column remains
nullable for spare parts.
The script is **metadata-only**: it does not upload original files, and storage
keys remain null rather than pointing to nonexistent objects. The storage provider
is configured once in the backend, not stored on every document. The CSV
filename represents a synthetic source, not an actual retained file.

## Verify Connections

Liveness remains `GET /api/health/`. Test both dependencies with
`GET /api/health/dependencies` through Swagger UI or these commands:

```powershell
Invoke-RestMethod http://localhost:8000/api/health/
Invoke-RestMethod http://localhost:8000/api/health/dependencies
# Also displays the JSON body when the response is HTTP 503:
curl.exe -i http://localhost:8000/api/health/dependencies
```

```bash
curl -i http://localhost:8000/api/health/dependencies
```

Example successful response (timings vary):

```json
{
  "status": "healthy",
  "database": { "status": "healthy", "latency_ms": 120.5 },
  "object_storage": { "status": "healthy", "latency_ms": 85.2 }
}
```

The database executes `SELECT 1`; storage uses `HeadBucket` on `assets`. Checks
run independently and concurrently. Nothing is written or deleted, and bucket
contents and credentials are never returned. Passing confirms connectivity/read
access, not permission to insert rows or upload files.

HTTP `200` means both passed. HTTP `503` includes each service's status: `failed`,
`timeout`, `not_configured`, or `configuration_error`. Liveness and API docs remain
available when services fail or are unconfigured. Missing storage fields report
`not_configured`. Set `DEBUG=False` and restrict access to the operational endpoint
with deployment ingress controls before exposing the POC publicly.

## Build

To compile the frontend:

```bash
cd frontend
npm run build
```

## Troubleshooting

- **Database failed:** verify the rotated password and connection string, preserve
  TLS parameters, and allow outbound PostgreSQL traffic on port 5432. There is no
  SQLite fallback.
- **Storage failed:** verify the private `assets` bucket, exact branch endpoint,
  region, credential scopes, and branch lineage. Database credentials cannot be
  reused for S3 authentication. The client uses SigV4 and path-style addressing.
- **Not configured:** fill all settings and restart the backend. Placeholder
  values from the template are not a working configuration.
- **Timeout:** Neon compute can cold-start after inactivity. Retry or raise
  `DEPENDENCY_TIMEOUT_SECONDS` after checking networking.
- **Port occupied:** inside the backend virtual environment use
  `python -m uvicorn app.main:app --port 8001 --reload`; for the frontend use
  `npm run dev -- --port 5174`. Adjust `VITE_API_URL` and `CORS_ORIGINS` accordingly.
- **Vite won't start:** install a supported Node version and run `npm ci`.
- **PowerShell reports HTTP 503 as an error:** use `curl.exe -i` to inspect the
  JSON. This status indicates an unavailable dependency, not an API crash.

## Project Structure

```
OneDMS/
├── frontend/       # React + Vite + TypeScript
├── backend/        # FastAPI + Uvicorn
├── shared/         # Canonical schema, constants, enums
└── docs/           # Architecture, API docs, runbooks
```

## Team

Team of 5 — Hackathon 2026

## License

Internal — Nagarro
