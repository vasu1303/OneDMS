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
| Pipeline    | Databricks + PySpark              |
| AI/Agentic  | LLM extraction + mapping          |

## Implementation Status

The runnable application includes a React frontend scaffold, FastAPI, PostgreSQL
connection/session infrastructure, Neon Object Storage integration, and health APIs.
PostgreSQL is for structured invoice data and object references; original PDFs,
spreadsheets, and other source files belong in the private `onedmsinvoices` bucket.
Credentials and storage access stay in the backend, never in the browser.

The invoice tables described in [the database design](docs/architecture/OneDMS_Database_Design.md),
ingestion connectors, AI extraction, validation workflows, and Databricks/PySpark
jobs are planned, not implemented. Startup does not create tables, migrations,
buckets, or files. There is no upload API or authentication implementation yet.

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
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run.py
```

These commands use the virtual environment directly, so PowerShell activation is
not required. Runtime-only installations can use `requirements.txt` instead.

### Backend: macOS / Linux

```bash
cd backend
python3 -m venv .venv
test -f .env || cp .env.example .env
.venv/bin/python -m pip install -r requirements-dev.txt
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

## Tests And Build

Backend tests use mocks and botocore stubs; they do not need live credentials:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pip check
```

On macOS/Linux, use `.venv/bin/python` instead. To compile the frontend:

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
├── pipeline/       # Databricks / PySpark ETL
├── ai/             # AI extraction, mapping, validation
├── shared/         # Canonical schema, constants, enums
├── data/           # Synthetic test data (PDF, Excel, API, flat)
├── docs/           # Architecture, API docs, runbooks
├── infra/          # CI/CD scaffolding
├── scripts/        # Dev utilities
└── tests/          # Integration & E2E tests
```

## Team

Team of 5 — Hackathon 2026

## License

Internal — Nagarro
