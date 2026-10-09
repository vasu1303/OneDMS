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
| Pipeline    | Databricks + PySpark              |
| AI/Agentic  | LLM extraction + mapping          |
| Infra       | Docker                            |

## Quick Start

### Frontend
```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

### Backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python run.py                # → http://localhost:8000
```

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
├── infra/          # Docker, CI/CD
├── scripts/        # Dev utilities
└── tests/          # Integration & E2E tests
```

## Team

Team of 5 — Hackathon 2026

## License

Internal — Nagarro
