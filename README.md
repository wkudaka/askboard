# Askboard

Upload CSVs, ask questions in plain language, get a dashboard built on the fly.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design and the roadmap.

**Status:** phase 2 (CSV ingestion). Workspaces, CSV upload with format/type inference
(Brazilian and US number/date formats, currency, booleans), schema review in the UI, load into
Postgres with per-column profiling. Next: phase 3 (ask questions; answers as tables).

## Layout

```
backend/    FastAPI + psycopg 3 (Python 3.11+)
frontend/   React + Vite + TypeScript
docker/     Postgres init scripts (creates the askboard_test database)
docs/       Architecture
```

## Run

```bash
# Postgres (host port 5433) + backend (port 8000)
docker compose up -d --build --wait

# Frontend (port 5173)
cd frontend
npm install
npm run dev
```

### Backend without Docker

```bash
docker compose up -d --wait db
cd backend
python -m venv .venv
.venv/Scripts/activate          # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m askboard.main         # http://localhost:8000
```

> **Windows:** psycopg's async mode does not work on the default `ProactorEventLoop`.
> Always start uvicorn with `--loop askboard.runtime:new_selector_event_loop`
> (`python -m askboard.main` already does this).

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Liveness: always 200 while the process runs |
| GET | `/readyz` | Readiness: 200 if Postgres answers, 503 otherwise |
| POST | `/workspaces` | Create a workspace (`{"name": ...}`) and its `ws_<id>` schema |
| GET | `/workspaces`, `/workspaces/{id}` | List / get workspaces |
| POST | `/workspaces/{id}/datasets` | Upload a CSV (multipart `file`): returns the inferred schema + first rows |
| POST | `/workspaces/{id}/datasets/{ds}/confirm` | Load it, optionally overriding `table_name` and column `name`/`pg_type` |
| GET | `/workspaces/{id}/datasets[/{ds}]` | List / get datasets with column profiles |

### How CSV ingestion works

1. **Detect** encoding (UTF-8, UTF-8 BOM, cp1252) and delimiter (`,` `;` tab `|`).
2. **Normalize** headers into snake_case ASCII identifiers (`Preço Unitário` → `preco_unitario`).
3. **Infer** a type per column from all values: `boolean`, `bigint`, `numeric`, `date`,
   `timestamp`, `timestamptz` or `text`. `;` files default to decimal comma; day-first dates
   unless values prove month-first. Leading-zero codes (CEP, ids) stay `text`.
4. **Review**: the raw file waits in `askboard.dataset_sources` until the user confirms.
5. **Load** with `COPY`; rows that do not fit (wrong column count, unparseable value for a
   forced type) are rejected and reported by line, never silently dropped.
6. **Profile** each column (nulls, distinct, min/max, most frequent values) for the LLM context.

## Tests

The project is developed test-first (red, then green, then refactor).

```bash
# Backend: unit tests always run; integration tests need Postgres and skip otherwise
cd backend
docker compose up -d --wait db
.venv/Scripts/python -m pytest              # all
.venv/Scripts/python -m pytest -m "not integration"

# Frontend
cd frontend
npm test
```

## Database

- `askboard` schema: metadata (workspaces, datasets, columns, relationships, questions)
  and `schema_migrations`.
- `ws_<id>` schemas: one per workspace, holding the uploaded tables (created in phase 2).
- `askboard_reader` role: used via `SET LOCAL ROLE` to run generated SQL. It has no access
  to `askboard` and cannot create objects.
- Migrations live in `backend/askboard/db/migrations/NNN_name.sql`. They run automatically
  on startup (`AUTO_MIGRATE=true`), under an advisory lock, each one in its own transaction.
